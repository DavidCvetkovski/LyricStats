"""FastAPI backend — thin wrapper around the lyricstats package.

Serves JSON for the Next.js frontend. Every endpoint is short and stateless so
it fits a serverless function: the browser orchestrates a catalogue fetch by
calling `/api/artist/pool` once, then `/api/song/by-id` per song, then
`/api/artist` to aggregate from the shared (Postgres) cache.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lyricstats import db, fetch, stats
from lyricstats.config import SEED_KEY

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

    a = db.get_or_create_artist(
        song.artist, genius_id=song.artist_id, genius_url=song.artist_url
    )
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


@app.get("/api/song")
def song(
    artist: str = Query(..., min_length=1),
    title: str = Query(..., min_length=1),
    force: bool = Query(False),
) -> dict[str, Any]:
    try:
        s = fetch.fetch_song(artist, title, force=force)
    except fetch.FetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("song fetch failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    db_song = db.find_song(s.artist, s.title)
    cached = db.load_stats(db_song) if db_song else None
    # Migrate old caches that pre-date new fields (e.g. section_sequence)
    if cached and "section_sequence" in cached:
        st = stats.SongStats(**cached)
    else:
        st = stats.compute(s.lyrics)
        if db_song:
            db.save_stats(db_song, st.to_dict())

    return {
        "artist": s.artist,
        "title": s.title,
        "album": s.album,
        "year": s.year,
        "source": s.source,
        "lyrics": s.lyrics,
        "stats": st.to_dict(),
    }


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
            st = stats.SongStats(**cached)
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
        "cached_total": len(valid_songs),
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
    stats = db.load_aggregate_stats(agg) or {}
    songs: list[dict[str, Any]] = []
    if agg.songs_json:
        try:
            for row in json.loads(agg.songs_json):
                title, year, wc, uniq, ttr, chorus, rep, has_sec = row
                songs.append({
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
                })
        except (ValueError, TypeError):
            songs = []
    return {
        "name": agg.display_name,
        "genius_url": None,
        "songs": songs,
        "stats": stats,
        "cached_total": agg.song_count,
        "sampled": len(songs) or agg.song_count,
        "has_sections": agg.has_sections,
        "source": "dataset",
        "limited": False,
    }


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

    # 1. Prefer the precomputed dataset aggregate when it's richer than whatever
    #    we have cached — a stray cached song or two must not shadow it. Answers
    #    instantly with zero fetches.
    if not fresh and agg and agg.song_count > len(cached_valid):
        return {
            "name": agg.display_name,
            "genius_url": None,
            "to_fetch": [],
            "cached_total": agg.song_count,
        }

    # 2. Lyrics-backed cache already holds a full view (>= MIN_VIEW valid songs),
    #    OR we've already cached everything Genius has for this artist (a niche
    #    artist with < MIN_VIEW total): serve it, no fetch. The latter avoids
    #    re-querying Genius on every view for limited catalogues.
    exhausted = (
        existing is not None
        and existing.total_songs is not None
        and existing.total_songs >= 1
        and len(cached_songs) >= existing.total_songs
    )
    if not fresh and (len(cached_valid) >= MIN_VIEW or exhausted):
        return {
            "name": existing.name if existing else name,
            "genius_url": existing.genius_url if existing else None,
            "to_fetch": [],
            "cached_total": len(cached_valid),
        }

    # 3. Nothing cached and not in the dataset: a typo may have a close dataset
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

    # 4. Live fetch toward the MIN_VIEW floor. resolve_and_sample re-queries
    #    Genius (refreshing total_songs), so a stale low count can't strand us;
    #    it naturally returns only as many as the artist actually has.
    try:
        a, sample = fetch.resolve_and_sample(name, MIN_VIEW, shuffle_seed=shuffle or None)
    except fetch.FetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("artist pool failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    all_cached = db.list_songs(a)
    cached_genius_ids = {s.genius_id for s in all_cached if s.genius_id is not None}
    cached_titles = {s.title.strip().lower() for s in all_cached}

    to_fetch = []
    for m in sample:
        song_id = m.get("id")
        if not song_id:
            continue
        title = m.get("title", "?")
        if int(song_id) in cached_genius_ids or title.strip().lower() in cached_titles:
            continue
        to_fetch.append({"id": int(song_id), "title": title})

    return {
        "name": a.name,
        "genius_url": a.genius_url,
        "to_fetch": to_fetch,
        "cached_total": len(all_cached),
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
    """Aggregate stats over a random sample of the artist's cached songs.

    Pure read + compute over the shared cache (no Genius fetch), so it returns
    quickly. The browser calls this after it has populated the cache via
    `/api/artist/pool` + `/api/song/by-id`.
    """
    # Prefer whichever source is richer. A few English artists have a stray
    # lyrics-backed song or two cached from past live searches; that thin cache
    # must not shadow a full dataset aggregate (e.g. Drake: 1 cached vs 482).
    agg = db.get_artist_aggregate(name)
    if agg:
        lb = db.get_artist(name)
        lb_valid = 0
        if lb:
            lb_valid = sum(
                1 for s in db.list_songs(lb) if s.lyrics and s.lyrics.strip()
            )
        if agg.song_count > lb_valid:
            return _dataset_payload(agg)

    try:
        return _aggregate_payload(name, n=min, shuffle=shuffle)
    except HTTPException as e:
        # No lyrics-backed catalogue cached — fall back to the precomputed
        # dataset aggregate (instant, no fetches) if we have one.
        if e.status_code == 404 and agg:
            return _dataset_payload(agg)
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("aggregate failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
