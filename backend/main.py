"""FastAPI backend — thin wrapper around the lyricstats package.

Serves JSON for the Next.js frontend. Every endpoint is short and stateless so
it fits a serverless function: the browser orchestrates a catalogue fetch by
calling `/api/artist/pool` once, then `/api/song/by-id` per song, then
`/api/artist` to aggregate from the shared (Postgres) cache.
"""

from __future__ import annotations

from collections import Counter
import builtins
import json
import logging
import random
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lyricstats import db, fetch, stats
from lyricstats.percentiles import archive_songs, percentiles
from lyricstats.reading import reading
from lyricstats.config import SEED_KEY, LIVE_FETCH_ENABLED
from lyricstats.text import tokenize, all_lines


log = logging.getLogger("lyricstats.api")
logging.basicConfig(level=logging.INFO)

# Target floor for live (non-dataset) artists: try to fetch up to this many
# songs. Below it, the view is flagged `limited` so the UI can say so.
MIN_VIEW = 20

app = FastAPI(title="LyricStats API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    # Localhost for dev; any *.vercel.app origin (prod + preview deploys) in
    # production. The API carries no cookies, so credentials stay off.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://lyricstats.dev",
        "https://www.lyricstats.dev",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_public_reads(request: Request, call_next):
    """Cache small public reads; explicit refreshes and errors stay uncached.

    Vercel consumes its separate CDN header, allowing repeated lookups to skip
    the Python function while browsers keep a shorter freshness window.
    """
    response = await call_next(request)
    if request.url.path not in {"/api/song", "/api/artist/suggest", "/api/artist/titles"}:
        return response
    explicit_read = request.query_params.get("force", "").lower() in {"1", "true", "yes", "on", "t", "y"}
    if request.method == "GET" and response.status_code == 200 and not explicit_read:
        response.headers["Cache-Control"] = "public, max-age=60"
        response.headers["Vercel-CDN-Cache-Control"] = (
            "public, max-age=300, stale-while-revalidate=600"
        )
        # CORS reflects allowed origins. Include Origin even on requests with
        # no Origin header so that response cannot hide a later CORS variant.
        vary = {value.strip().lower() for value in response.headers.get("Vary", "").split(",")}
        if "origin" not in vary:
            response.headers.add_vary_header("Origin")
    else:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vercel-CDN-Cache-Control"] = "no-store"
    return response


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": "0.3.0"}


# ── seed ingest — push full-quality lyrics from a residential IP ─────────────


class IngestSong(BaseModel):
    artist: str
    title: str
    lyrics: str
    album: str | None = None
    year: int | None = None
    genius_id: int | None = None
    artist_id: int | None = None
    artist_url: str | None = None


@app.post("/api/ingest")
def ingest(song: IngestSong, x_seed_key: str = Header(default="")) -> dict[str, Any]:
    """Upsert one song's lyrics into the shared database.

    Guarded by the SEED_KEY shared secret. The seed scripts (run on your
    laptop/phone, where Genius scraping works) fetch full lyrics and POST them
    here, so the deployed app can serve them without ever scraping itself.
    """
    if not SEED_KEY:
        raise HTTPException(status_code=503, detail="Ingest disabled: SEED_KEY not set.")
    if x_seed_key != SEED_KEY:
        raise HTTPException(status_code=403, detail="Bad or missing X-Seed-Key.")
    if not song.lyrics.strip():
        raise HTTPException(status_code=400, detail="Empty lyrics.")

    a = db.get_or_create_artist(song.artist, genius_id=song.artist_id, genius_url=song.artist_url)
    db.upsert_song(
        a,
        title=song.title,
        lyrics=song.lyrics,
        album=song.album,
        year=song.year,
        genius_id=song.genius_id,
    )
    return {"ok": True, "artist": a.name, "title": song.title}


# ── single song ────────────────────────────────────────────────────────────


# ── song ─────────────────────────────────────────────────────────────────────
#
# A song page is set from three things: the text and its reading (computed
# once, cached next to the lyrics), the artist's catalogue for context, and
# the archive-wide quantiles for where the song stands among everything.

CATALOGUE_POINTS = 240  # dots per strip on the song page; bigger catalogues are thinned


def _title_rows(agg: db.ArtistAggregate) -> list[list[Any]]:
    """A dataset artist's catalogue: [title, year, wc, uniq, ttr, chorus, rep, has_sec]."""
    try:
        rows = json.loads(agg.songs_json or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, list) and len(r) == 8 and isinstance(r[0], str)]


def _unslug(s: str) -> str:
    """A URL slug back into words; anything that was never a slug passes through."""
    s = s.strip()
    if " " in s or "-" not in s:
        return s
    return " ".join(part for part in s.split("-") if part)


def _resolve(
    artist: str, title: str
) -> tuple[str, str, db.ArtistAggregate | None, list[Any] | None]:
    """Turn what the URL carries (a name, or its slug) into the names we file
    under. Slugs lose accents and punctuation, so both sides meet on the same
    aggressive key: 'michael-jackson' and 'Michael Jackson' at 'michaeljackson'.

    Returns (artist name, title, dataset aggregate, catalogue row); the last
    two are None when the song is not in the dataset.
    """
    agg = db.get_artist_aggregate(artist)
    if agg:
        want = db.normalize_key(title)
        for row in _title_rows(agg):
            if db.normalize_key(row[0]) == want:
                return agg.display_name, row[0], agg, row
        return agg.display_name, _unslug(title), agg, None
    lb = db.find_artist_by_key(artist)
    if lb:
        # Keep the caller's casing when it named the artist; a slug takes the
        # filed (lower-case) name, which is what the provider was asked with.
        name = artist if artist.lower() == lb.name else lb.name
        cached = db.find_song_by_key(lb, title)
        if cached:
            return name, cached.title, None, None
        return name, _unslug(title), None, None
    return _unslug(artist), _unslug(title), None, None


@app.get("/api/song")
def song(
    artist: Annotated[str, Query(min_length=1, max_length=120)],
    title: Annotated[str, Query(min_length=1, max_length=300)],
    force: bool = False,
) -> dict[str, Any]:
    """One song, read: its text, its numbers, and where it stands.

    `artist` and `title` may be names or the slugs from a song page's URL.
    Stored analysis is served first; a provider is only asked on a miss, or
    on an explicit `force`. When no provider has the text but the catalogue
    knows the song, its stored figures are served without the text.
    """
    artist, title = artist.strip(), title.strip()
    if not artist or not title:
        raise HTTPException(status_code=422, detail="Enter an artist and song title.")

    name, canon, agg, row = _resolve(artist, title)

    if not force:
        cached = db.find_song(name, canon)
        if not (cached and cached.lyrics.strip()):
            # The text may be filed under the provider's spelling of the name.
            lb = db.find_artist_by_key(name)
            cached = db.find_song_by_key(lb, canon) if lb else None
        if cached and cached.lyrics.strip():
            return _song_payload(name, cached, source="cache", agg=agg, row=row)

    try:
        s = fetch.fetch_song(name, canon, force=force)
    except fetch.FetchError as e:
        if row is not None:
            return _summary_payload(agg, row)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("song fetch failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    shown = name if agg else s.artist
    saved = db.find_song(s.artist, s.title)
    if saved and saved.lyrics == s.lyrics:
        return _song_payload(shown, saved, source=s.source, agg=agg, row=row)
    # A provider adapter may return lyrics without persisting them.
    return _assemble(
        shown, s.title, s.album, s.year, s.source, s.lyrics,
        stats.compute(s.lyrics).to_dict(), reading(s.title, s.lyrics), agg, row,
    )


def _song_payload(
    artist: str,
    song: db.Song,
    *,
    source: str,
    agg: db.ArtistAggregate | None = None,
    row: list[Any] | None = None,
) -> dict[str, Any]:
    cached = db.load_stats(song)
    # Migrate old caches that pre-date new fields (e.g. section_sequence)
    if cached and "section_sequence" in cached:
        st = cached
    else:
        st = stats.compute(song.lyrics).to_dict()
        db.save_stats(song, st)
    stored = st.get("reading")
    if stored is None or "drop_at" not in stored:
        # A cache entry from before the reading, or before its marks, existed:
        # read the text again now. The clock keys are kept from the stored
        # reading, because the synced lines they came from were never kept.
        fresh = reading(song.title, song.lyrics)
        if fresh and stored:
            for key in ("wpm", "first", "gap", "gap_at", "fast15", "curve", "last", "duration"):
                if stored.get(key) is not None:
                    fresh[key] = stored[key]
        st = {**st, "reading": fresh}
        db.save_stats(song, st)
    return _assemble(
        artist, song.title, song.album, song.year, source, song.lyrics, st, st["reading"], agg, row
    )


def _summary_payload(agg: db.ArtistAggregate, row: list[Any]) -> dict[str, Any]:
    """The catalogue's figures for a song whose text no provider has."""
    title, year, wc, uniq, ttr, chorus, rep, has_sec = row
    st = stats.SongStats(
        word_count=wc,
        unique_words=uniq,
        type_token_ratio=ttr,
        chorus_ratio=chorus,
        repetition_ratio=rep,
    ).to_dict()
    r = {"wc": wc, "uniq": uniq, "ttr": ttr, "rep": rep}
    out = _assemble(agg.display_name, title, None, year, "dataset", "", st, r, agg, row, complete=False)
    out["has_sections"] = bool(has_sec)
    return out


def _assemble(
    artist: str,
    title: str,
    album: str | None,
    year: int | None,
    source: str,
    lyrics: str,
    st: dict[str, Any],
    r: dict[str, Any] | None,
    agg: db.ArtistAggregate | None,
    row: list[Any] | None,
    *,
    complete: bool = True,
) -> dict[str, Any]:
    st = {k: v for k, v in st.items() if k != "reading"}
    return {
        "artist": artist,
        "title": title,
        "album": album,
        "year": year,
        "source": source,
        "lyrics": lyrics,
        "stats": st,
        "reading": r,
        "analysis_complete": complete,
        "has_sections": any(k != "other" for k in (st.get("section_kinds") or {})),
        "catalogue": _catalogue(agg, row, r) if agg else None,
        "percentiles": percentiles(r) if r else {},
        "archive_songs": archive_songs(),
        "slug": {"artist": db.slugify(artist), "title": db.slugify(title)},
    }


def _catalogue(
    agg: db.ArtistAggregate, row: list[Any] | None, r: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Where the song sits among the artist's other songs, from the same
    catalogue the artist page is built on: a rank (1 = highest) and a thinned
    strip of every song's value, for words, variety and repetition."""
    rows = _title_rows(agg)
    if not rows:
        return None
    r = r or {}
    out: dict[str, Any] = {
        "artist": agg.display_name,
        "songs": len(rows),
        "in_catalogue": row is not None,
    }
    for name, idx, value in (("words", 2, r.get("wc")), ("variety", 4, r.get("ttr")), ("repetition", 6, r.get("rep"))):
        vals = sorted(x[idx] for x in rows if isinstance(x[idx], (int, float)))
        if not vals or value is None:
            out[name] = None
            continue
        if len(vals) > CATALOGUE_POINTS:
            step = len(vals) / CATALOGUE_POINTS
            points = [vals[int(i * step)] for i in range(CATALOGUE_POINTS)]
        else:
            points = vals
        out[name] = {
            "value": value,
            "rank": sum(1 for v in vals if v > value) + 1,
            "median": vals[len(vals) // 2],
            "low": vals[0],
            "high": vals[-1],
            "points": points,
        }
    return out


@app.get("/api/artist/titles")
def artist_titles(name: str = Query(..., min_length=1, max_length=120)) -> dict[str, Any]:
    """Every title we can open for an artist, for the song search box."""
    agg = db.get_artist_aggregate(name)
    if agg:
        return {"name": agg.display_name, "titles": [r[0] for r in _title_rows(agg)]}
    lb = db.find_artist_by_key(name)
    if not lb:
        return {"name": name, "titles": []}
    return {"name": lb.name, "titles": db.list_titles(lb)}


# ── artist ──────────────────────────────────────────────────────────────────


def _pick_n(songs: list[db.Song], n: int, seed_key: str) -> list[db.Song]:
    """Random sample of N songs from the cached list.

    With a shuffle token in the seed key, every Examine click returns a
    different sample. Without one (initial URL load / restored from
    localStorage), the seed is stable for the same (artist, N) so a
    refresh shows the same songs.

    The population is sorted by song id first only to make `rng.sample`
    indices map to a stable order across runs — they're then shuffled
    into the returned list by sample(), so output order is random.
    """
    if n >= len(songs):
        # Even when N matches, return in a randomised order so the
        # catalogue display doesn't appear sorted by anything.
        ordered = sorted(songs, key=lambda s: s.id or 0)
        rng = random.Random(seed_key)
        rng.shuffle(ordered)
        return ordered
    ordered = sorted(songs, key=lambda s: s.id or 0)
    rng = random.Random(seed_key)
    return rng.sample(ordered, n)


def _aggregate_payload(name: str, n: int, shuffle: str) -> dict[str, Any]:
    a = db.get_artist(name)
    if not a:
        raise HTTPException(status_code=404, detail=f"No cached data for '{name}'.")
    all_songs = db.list_songs(a)
    if not all_songs:
        raise HTTPException(status_code=404, detail=f"No songs for '{name}'.")

    # Filter out zero-word songs (instrumental, empty, translation metadata, etc.)
    valid_songs = []
    for s in all_songs:
        if not s.lyrics or not s.lyrics.strip():
            continue
        cached = db.load_stats(s)
        if cached and "word_count" in cached:
            if cached["word_count"] == 0:
                continue
            st = stats.SongStats.from_dict(cached)
        else:
            st = stats.compute(s.lyrics)
            db.save_stats(s, st.to_dict())
            if st.word_count == 0:
                continue
        valid_songs.append((s, st))

    if not valid_songs:
        raise HTTPException(status_code=404, detail=f"No songs with lyrics for '{name}'.")

    # Sample from the valid songs
    sampled_pairs = _pick_n([x[0] for x in valid_songs], n, seed_key=f"{a.name}|{n}|{shuffle}")
    valid_map = {s.id: st for s, st in valid_songs}

    pairs: list[tuple[str, str]] = []
    metas: list[dict[str, Any]] = []
    for s in sampled_pairs:
        st = valid_map[s.id]
        pairs.append((s.title, s.lyrics))
        metas.append(
            {
                "title": s.title,
                "album": s.album,
                "year": s.year,
                "word_count": st.word_count,
                "unique_words": st.unique_words,
                "type_token_ratio": st.type_token_ratio,
                "chorus_ratio": st.chorus_ratio,
                "repetition_ratio": st.repetition_ratio,
                "line_count": st.line_count,
                # Real structure only — untagged lyrics parse as a single
                # "other" section, which doesn't count.
                "has_sections": any(k != "other" for k in st.section_kinds),
            }
        )

    agg = stats.aggregate(pairs)
    return {
        "name": a.name,
        "genius_url": a.genius_url,
        "songs": metas,
        "stats": agg.to_dict(),
        "cached_total": len(valid_songs)
        if len(valid_songs) <= n
        else (a.total_songs if a.total_songs else len(valid_songs)),
        "sampled": len(sampled_pairs),
        # A live/lyrics-backed artist with fewer than MIN_VIEW songs is a
        # partial picture (e.g. niche artists with little on lrclib/ovh).
        "limited": len(valid_songs) < MIN_VIEW,
        "source": "cache",
    }


def _dataset_payload(agg: db.ArtistAggregate) -> dict[str, Any]:
    """Build the ArtistPayload shape from a precomputed dataset aggregate.

    Carries the whole-career figures plus a compact per-song catalogue (no
    lyrics — song pages fetch those live), served instantly with zero lyric
    fetches. `has_sections` is at the payload level so chorus-share still gates.
    """
    agg_stats = db.load_aggregate_stats(agg) or {}
    songs: list[dict[str, Any]] = []
    if agg.songs_json:
        try:
            for row in json.loads(agg.songs_json):
                title, year, wc, uniq, ttr, chorus, rep, has_sec = row
                songs.append(
                    {
                        "title": title,
                        "album": None,
                        "year": year,
                        "word_count": wc,
                        "unique_words": uniq,
                        "type_token_ratio": ttr,
                        "chorus_ratio": chorus,
                        "repetition_ratio": rep,
                        "line_count": 0,
                        "has_sections": bool(has_sec),
                    }
                )
        except (ValueError, TypeError):
            songs = []
    return {
        "name": agg.display_name,
        "genius_url": None,
        "songs": songs,
        "stats": agg_stats,
        "cached_total": agg.song_count,
        "sampled": len(songs) or agg.song_count,
        "has_sections": agg.has_sections,
        "source": "dataset",
        "limited": False,
    }


def _get_merged_song_count(agg: db.ArtistAggregate | None, lb: db.Artist | None) -> int:
    dataset_titles = set()
    if agg and agg.songs_json:
        try:
            for row in json.loads(agg.songs_json):
                dataset_titles.add(row[0].strip().lower())
        except Exception:
            pass

    live_titles = set()
    if lb:
        all_songs = db.list_songs(lb)
        for s in all_songs:
            if not s.lyrics or not s.lyrics.strip():
                continue
            cached = db.load_stats(s)
            if cached and "word_count" in cached:
                if cached["word_count"] == 0:
                    continue
            live_titles.add(s.title.strip().lower())

    if not agg:
        return len(live_titles)

    return len(dataset_titles.union(live_titles))


@app.get("/api/artist/suggest")
def artist_suggest(
    q: str = Query("", max_length=120),
    limit: int = Query(8, ge=1, le=20),
) -> dict[str, Any]:
    """Typeahead suggestions from the precomputed dataset (instant, no fetch).

    Powers the search-box autocomplete: a short DB query over the dataset
    artists, returning display names plus catalogue size to disambiguate.
    """
    rows = db.search_artist_aggregates(q, limit=limit)
    # The precomputed count is enough to disambiguate search results. Loading
    # every catalogue and its cached lyrics here multiplied DB transfer on
    # every keystroke; the artist page still reports the merged live count.
    return {"suggestions": [{"name": r.display_name, "song_count": r.song_count} for r in rows]}


@app.get("/api/artist/pool")
def artist_pool(
    name: str = Query(..., min_length=1),
    min: int = Query(20, ge=1, le=500, alias="min"),
    fresh: bool = Query(False),
    shuffle: str = Query("", max_length=32),
) -> dict[str, Any]:
    """Plan a catalogue fetch. Fast: resolves the artist and samples song
    metadata on Genius, but fetches no lyrics.

    Returns the list of songs the browser should fetch one-by-one via
    `/api/song/by-id`. When `fresh` is false and the cache already holds at
    least `min` songs, `to_fetch` is empty so the client skips straight to
    `/api/artist` (today's prefer-cache default).
    """
    existing = db.get_artist(name)
    cached_songs = db.list_songs(existing) if existing else []
    cached_valid = [s for s in cached_songs if s.lyrics and s.lyrics.strip()]
    agg = db.get_artist_aggregate(name)

    merged_count = _get_merged_song_count(agg, existing)

    # 1. We fast-return if we ALREADY have enough songs (dataset + cache) to satisfy
    #    the user's request `min`, OR if we have exhausted everything Genius has.
    exhausted = (
        existing is not None
        and existing.total_songs is not None
        and existing.total_songs >= 1
        and len(cached_songs) >= existing.total_songs
    )
    if not fresh and (merged_count >= min or exhausted or agg is not None):
        return {
            "name": agg.display_name if agg else (existing.name if existing else name),
            "genius_url": existing.genius_url if existing else None,
            "to_fetch": [],
            "cached_total": merged_count,
        }

    # 2. Nothing cached and not in the dataset: a typo may have a close dataset
    #    match — suggest it instead of a slow live fetch.
    if not cached_valid and not agg:
        suggestions = db.suggest_artist_aggregates(name, limit=1)
        if suggestions:
            return {
                "name": name,
                "genius_url": None,
                "to_fetch": [],
                "cached_total": 0,
                "suggestion": suggestions[0].display_name,
            }

    # 3. Live fetch toward the `min` floor. resolve_and_sample re-queries
    #    Genius (refreshing total_songs), so a stale low count can't strand us.
    if not LIVE_FETCH_ENABLED:
        return {
            "name": agg.display_name if agg else (existing.name if existing else name),
            "genius_url": existing.genius_url if existing else None,
            "to_fetch": [],
            "cached_total": merged_count,
        }

    try:
        a, sample = fetch.resolve_and_sample(name, min, pool_size=min, shuffle_seed=shuffle or None)
    except fetch.FetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("artist pool failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    all_cached = db.list_songs(a)
    cached_genius_ids = {s.genius_id for s in all_cached if s.genius_id is not None}
    cached_titles = {s.title.strip().lower() for s in all_cached}

    dataset_titles = set()
    if agg and agg.songs_json:
        try:
            for row in json.loads(agg.songs_json):
                dataset_titles.add(row[0].strip().lower())
        except Exception:
            pass

    to_fetch = []
    for m in sample:
        song_id = m.get("id")
        if not song_id:
            continue
        title = m.get("title", "?")
        norm_title = title.strip().lower()
        if (
            int(song_id) in cached_genius_ids
            or norm_title in cached_titles
            or norm_title in dataset_titles
        ):
            continue
        to_fetch.append({"id": int(song_id), "title": title})

    return {
        "name": a.name,
        "genius_url": a.genius_url,
        "to_fetch": to_fetch,
        "cached_total": _get_merged_song_count(agg, a),
    }


@app.get("/api/song/by-id")
def song_by_id(
    name: str = Query(..., min_length=1),
    id: int = Query(..., ge=1),
    title: str = Query("?"),
) -> dict[str, Any]:
    """Fetch one song's lyrics by Genius id and cache them under the artist.

    Called once per song by the browser while it drives a catalogue fetch.
    """
    a = db.get_artist(name) or db.get_or_create_artist(name)
    try:
        saved = fetch.fetch_one_by_id(a, id, title)
    except fetch.FetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("song-by-id fetch failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": saved}


@app.get("/api/artist")
def artist(
    name: str = Query(..., min_length=1),
    min: int = Query(20, ge=1, le=500, alias="min"),
    shuffle: str = Query("", max_length=32),
) -> dict[str, Any]:
    """Aggregate stats over a dynamically merged catalogue of precomputed dataset
    songs and live-cached songs.
    """
    agg = db.get_artist_aggregate(name)
    lb = db.get_artist(name)

    if not agg and not lb:
        raise HTTPException(status_code=404, detail=f"No cached data for '{name}'.")

    display_name = agg.display_name if agg else (lb.name if lb else name)
    genius_url = lb.genius_url if lb else None

    # 1. Parse dataset songs
    dataset_songs_map = {}
    if agg and agg.songs_json:
        try:
            for row in json.loads(agg.songs_json):
                title, year, wc, uniq, ttr, chorus, rep, has_sec = row
                norm_title = title.strip().lower()
                dataset_songs_map[norm_title] = {
                    "title": title,
                    "album": None,
                    "year": year,
                    "word_count": wc,
                    "unique_words": uniq,
                    "type_token_ratio": ttr,
                    "chorus_ratio": chorus,
                    "repetition_ratio": rep,
                    "line_count": 0,
                    "has_sections": bool(has_sec),
                }
        except Exception:
            pass

    # 2. Parse live cached songs
    live_songs_map = {}
    valid_songs = []
    if lb:
        all_songs = db.list_songs(lb)
        for s in all_songs:
            if not s.lyrics or not s.lyrics.strip():
                continue
            cached = db.load_stats(s)
            if cached and "word_count" in cached:
                if cached["word_count"] == 0:
                    continue
                st = stats.SongStats.from_dict(cached)
            else:
                st = stats.compute(s.lyrics)
                db.save_stats(s, st.to_dict())
                if st.word_count == 0:
                    continue

            norm_title = s.title.strip().lower()
            song_data = {
                "title": s.title,
                "album": s.album,
                "year": s.year,
                "word_count": st.word_count,
                "unique_words": st.unique_words,
                "type_token_ratio": st.type_token_ratio,
                "chorus_ratio": st.chorus_ratio,
                "repetition_ratio": st.repetition_ratio,
                "line_count": st.line_count,
                "has_sections": any(k != "other" for k in st.section_kinds),
            }
            live_songs_map[norm_title] = song_data
            valid_songs.append((s, st))

    # 3. Merge: prefer live cache over dataset
    merged_songs_map = {}
    merged_songs_map.update(dataset_songs_map)
    merged_songs_map.update(live_songs_map)

    # Sort merged songs by word_count descending
    merged_songs = sorted(merged_songs_map.values(), key=lambda x: x["word_count"], reverse=True)

    if not merged_songs:
        raise HTTPException(status_code=404, detail=f"No songs with lyrics for '{name}'.")

    # 4. Compile / Update statistics
    if agg:
        # We have a dataset base. Let's load the aggregate stats
        agg_stats = db.load_aggregate_stats(agg) or {}

        # Recalculate aggregates over all merged songs
        merged_len = len(merged_songs)
        song_count = merged_len
        agg_stats["song_count"] = song_count

        new_words = sum(
            s["word_count"] for title, s in live_songs_map.items() if title not in dataset_songs_map
        )
        total_words = agg_stats.get("total_words", 0) + new_words
        agg_stats["total_words"] = total_words
        agg_stats["avg_words_per_song"] = round(total_words / song_count, 2) if song_count else 0.0

        agg_stats["avg_ttr"] = (
            round(sum(s["type_token_ratio"] for s in merged_songs) / merged_len, 4)
            if merged_len
            else 0.0
        )

        sec_songs = [s for s in merged_songs if s["has_sections"]]
        agg_stats["avg_chorus_ratio"] = (
            round(sum(s["chorus_ratio"] for s in sec_songs) / len(sec_songs), 4)
            if sec_songs
            else 0.0
        )
        agg_stats["avg_repetition_ratio"] = (
            round(sum(s["repetition_ratio"] for s in merged_songs) / merged_len, 4)
            if merged_len
            else 0.0
        )

        # Highlights
        _DEMO_KW = (
            "(demo)",
            "[demo]",
            "(snippet)",
            "[snippet]",
            "(teaser)",
            "[teaser]",
            "(promo)",
            "[promo]",
            "(skit)",
            "[skit]",
        )
        eligible = [
            s
            for s in merged_songs
            if s["word_count"] >= 80 and not any(kw in s["title"].lower() for kw in _DEMO_KW)
        ]
        if not eligible:
            eligible = merged_songs

        if eligible:
            longest = max(eligible, key=lambda s: s["word_count"])
            shortest = builtins.min(eligible, key=lambda s: s["word_count"])
            richest = max(eligible, key=lambda s: s["type_token_ratio"])
            agg_stats["longest_song"] = {"title": longest["title"], "words": longest["word_count"]}
            agg_stats["shortest_song"] = {
                "title": shortest["title"],
                "words": shortest["word_count"],
            }
            agg_stats["richest_song"] = {
                "title": richest["title"],
                "ttr": richest["type_token_ratio"],
            }

        # Merge top words counts for any new songs in the live cache
        new_songs_objs = [
            s for s, st in valid_songs if s.title.strip().lower() not in dataset_songs_map
        ]
        if new_songs_objs:
            top_words_dict = {w: c for w, c in agg_stats.get("top_words", [])}
            top_words_no_stop_dict = {w: c for w, c in agg_stats.get("top_words_no_stop", [])}

            global_counts = Counter()
            for ns in new_songs_objs:
                tokens = tokenize(" ".join(all_lines(ns.lyrics)))
                global_counts.update(tokens)

            for w, c in global_counts.items():
                if w in top_words_dict:
                    top_words_dict[w] += c
                if w not in stats.STOPWORDS and w in top_words_no_stop_dict:
                    top_words_no_stop_dict[w] += c

            agg_stats["top_words"] = sorted(
                top_words_dict.items(), key=lambda x: x[1], reverse=True
            )[:30]
            agg_stats["top_words_no_stop"] = sorted(
                top_words_no_stop_dict.items(), key=lambda x: x[1], reverse=True
            )[:30]

        has_sections = agg.has_sections or any(s["has_sections"] for s in merged_songs)
        source = "dataset"
        limited = False
        cached_total = song_count
    else:
        # Only live cache exists. Run full aggregation over all cached songs.
        songs_with_lyrics = [(s.title, s.lyrics) for s, st in valid_songs]
        agg_stats_obj = stats.aggregate(songs_with_lyrics)
        agg_stats = agg_stats_obj.to_dict()
        has_sections = any(s["has_sections"] for s in merged_songs)
        source = "cache"
        limited = len(valid_songs) < MIN_VIEW
        cached_total = len(valid_songs)

    return {
        "name": display_name,
        "genius_url": genius_url,
        "songs": merged_songs,
        "stats": agg_stats,
        "cached_total": cached_total,
        "sampled": len(merged_songs),
        "has_sections": has_sections,
        "source": source,
        "limited": limited,
    }
