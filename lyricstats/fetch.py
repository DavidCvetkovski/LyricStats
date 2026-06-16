"""Lyrics fetcher.

Two layers, chosen by where the code runs:

* **Listing / metadata** always uses the official Genius API
  (``api.genius.com``, token-based). It works from anywhere — including
  Vercel's datacenter IPs.
* **Lyric text** comes from the best available source:
  - ``GENIUS_SCRAPE=1`` (default; laptop/phone, residential IP) →
    scrape genius.com for full lyrics *with* ``[Chorus]``/``[Verse]`` tags.
  - otherwise (Vercel) → ``lrclib.net`` then ``lyrics.ovh`` (plain text,
    no section tags).

Everything saved lands in the database so we never re-fetch.
"""

from __future__ import annotations

import logging
import random
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from . import db
from .config import GENIUS_SCRAPE, GENIUS_TOKEN, ONLY_LRCLIB

log = logging.getLogger(__name__)

_GENIUS_API = "https://api.genius.com"
_UA = "LyricStats/0.3 (+https://lyricstats.vercel.app)"


class FetchError(RuntimeError):
    pass


# ── small adapters around Genius objects (covered by tests) ─────────────────

_API_PATH_ID_RE = re.compile(r"/(?:artists|songs)/(\d+)")


def _id_from_api_path(obj: Any) -> int | None:
    """Extract numeric id from a lyricsgenius object's api_path (e.g. '/artists/53624')."""
    path = getattr(obj, "api_path", None)
    if not path:
        return None
    m = _API_PATH_ID_RE.search(str(path))
    return int(m.group(1)) if m else None


def _album_name(obj: Any) -> str | None:
    """Song.album is a dict in lyricsgenius v3 ({'name': ..., 'full_title': ...})."""
    album = getattr(obj, "album", None)
    if not album:
        return None
    if isinstance(album, dict):
        return album.get("name") or album.get("full_title")
    if isinstance(album, str):
        return album
    return getattr(album, "name", None)


def _song_year(obj: Any) -> int | None:
    """Year isn't a direct field on lyricsgenius v3 Song. Try release_date string."""
    for attr in ("year", "release_date", "release_date_for_display"):
        val = getattr(obj, attr, None)
        if val:
            m = re.match(r"(\d{4})", str(val))
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return None


def _year_from_str(val: Any) -> int | None:
    if not val:
        return None
    m = re.search(r"(\d{4})", str(val))
    return int(m.group(1)) if m else None


# ── live progress via lyricsgenius's own logger (covered by tests) ──────────
#
# lyricsgenius logs each fetch at INFO level ("Song 5: 'Title'"). When we scrape
# a whole catalogue through it we turn those messages into progress events.

_LG_SONG_RE = re.compile(r'^\s*Song\s+(\d+):\s*"(.+)"\s*$')


class _LyricsGeniusProgressHandler(logging.Handler):
    def __init__(self, on_progress: Callable[[int, int, str], None], total: int) -> None:
        super().__init__(level=logging.INFO)
        self.on_progress = on_progress
        self.total = total

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            m = _LG_SONG_RE.match(msg)
            if not m:
                return
            n = int(m.group(1))
            title = m.group(2).strip()
            # Cap at the requested total so tail/buffer fetches don't exceed 100%.
            self.on_progress(min(n, self.total), self.total, title)
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def _lyricsgenius_progress(
    on_progress: Callable[[int, int, str], None] | None,
    total: int,
) -> Iterator[None]:
    if on_progress is None:
        yield
        return
    lg_log = logging.getLogger("lyricsgenius.genius")
    prev_level = lg_log.level
    if prev_level == logging.NOTSET or prev_level > logging.INFO:
        lg_log.setLevel(logging.INFO)
    handler = _LyricsGeniusProgressHandler(on_progress, total)
    lg_log.addHandler(handler)
    try:
        yield
    finally:
        lg_log.removeHandler(handler)
        if prev_level != lg_log.level:
            lg_log.setLevel(prev_level)


# ── Genius official metadata API (works from any IP) ────────────────────────


def _api_headers() -> dict[str, str]:
    if not GENIUS_TOKEN:
        raise FetchError(
            "GENIUS_TOKEN is not set. Add it to .env "
            "(get one free at https://genius.com/api-clients)."
        )
    return {"Authorization": f"Bearer {GENIUS_TOKEN}", "User-Agent": _UA}


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _genius_api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = requests.get(
        f"{_GENIUS_API}{path}", headers=_api_headers(), params=params or {}, timeout=15
    )
    r.raise_for_status()
    return r.json()


def _meta_from_api_song(d: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Genius API song object into the slim meta dict we pass around.

    Genius credits a song to a single ``primary_artist`` but co-leads (duos like
    Jala Brat & Buba Corelli, or Voyage & Nucci) are listed in the *plural*
    ``primary_artists``. We capture the full main-artist list so callers can tell
    a true lead from a mere feature — e.g. "Bass" and "Balkan" are co-led, and
    must count for *both* names, not just whichever Genius listed first.
    """
    album = d.get("album")
    album_name = album.get("name") if isinstance(album, dict) else None
    year = (d.get("release_date_components") or {}).get("year")
    if not year:
        year = _year_from_str(d.get("release_date_for_display"))
    pa = d.get("primary_artist") or {}
    primaries = d.get("primary_artists") or []
    primary_ids = [p.get("id") for p in primaries if p.get("id")]
    primary_names = [p.get("name") for p in primaries if p.get("name")]
    # Fall back to the singular field if the plural one is absent/empty.
    if not primary_ids and pa.get("id"):
        primary_ids = [pa["id"]]
    if not primary_names and pa.get("name"):
        primary_names = [pa["name"]]
    return {
        "id": d.get("id"),
        "title": d.get("title") or "?",
        "url": d.get("url"),
        "album": album_name,
        "year": year,
        "artist_name": pa.get("name"),
        "artist_id": pa.get("id"),
        "artist_url": pa.get("url"),
        "primary_artist_ids": primary_ids,
        "primary_artist_names": primary_names,
    }


def search_artist_api(name: str) -> tuple[int, str, str | None]:
    """Resolve an artist via the Genius API. Returns (id, name, url)."""
    data = _genius_api_get("/search", {"q": name})
    hits = data.get("response", {}).get("hits", [])
    target = name.strip().lower()
    best: dict[str, Any] | None = None
    for h in hits:
        pa = (h.get("result") or {}).get("primary_artist") or {}
        if not pa.get("id"):
            continue
        if best is None:
            best = pa
        if (pa.get("name") or "").strip().lower() == target:
            best = pa
            break
    if not best:
        raise FetchError(f"Artist '{name}' not found on Genius.")
    return int(best["id"]), best.get("name") or name, best.get("url")


def artist_songs_api(
    artist_id: int, pool_size: int = 1000, *, main_only: bool = True
) -> tuple[list[dict[str, Any]], bool]:
    """Page the artist's songs via the Genius API. Metadata only, no lyrics.

    Returns a tuple of (pool, reached_end) where reached_end is True if we
    finished paging all available songs from Genius.

    The ``/artists/{id}/songs`` endpoint returns every song the artist touches —
    lead, featured, producer or writer. With ``main_only`` (the default) we keep
    only songs where the artist is a *main* artist (present in the song's
    ``primary_artists`` list), so a guest-heavy artist's body of work isn't
    diluted by tracks that are mostly someone else's. Co-led duo tracks still
    count because both names live in ``primary_artists``.
    """
    pool: list[dict[str, Any]] = []
    page: int | None = 1
    per_page = 50
    reached_end = False
    while page and len(pool) < pool_size:
        data = _genius_api_get(
            f"/artists/{artist_id}/songs",
            {"per_page": per_page, "page": page, "sort": "popularity"},
        )
        resp = data.get("response", {})
        songs = resp.get("songs", []) or []
        if not songs:
            reached_end = True
            break
        for s in songs:
            if not s.get("id"):
                continue
            meta = _meta_from_api_song(s)
            if main_only and artist_id not in meta["primary_artist_ids"]:
                continue
            pool.append(meta)
        page = resp.get("next_page")
        if not page:
            reached_end = True
            break
        time.sleep(0.1)
    return pool, reached_end


def _artist_is_main(target: str, primary_names: list[str]) -> bool:
    """True if `target` matches one of the song's main (primary) artists.

    Tolerant of partial names ("jala" ↔ "Jala Brat") so links carrying a
    canonical db name and free-text searches both resolve.
    """
    t = target.strip().lower()
    if not t:
        return False
    for n in primary_names:
        n = (n or "").strip().lower()
        if not n:
            continue
        if t == n or t in n or n in t:
            return True
    return False


def search_song_api(artist: str, title: str) -> dict[str, Any] | None:
    """Resolve a single song via the Genius API. Metadata only, no lyrics.

    Only returns a hit where `artist` is one of the song's *main* artists — a
    feature/credit alone doesn't qualify. Genius parks duo tracks under a single
    ``primary_artist`` but lists co-leads in ``primary_artists`` (plural), so we
    match against that full list and skip hits where the artist is merely
    featured.
    """
    data = _genius_api_get("/search", {"q": f"{artist} {title}"})
    hits = data.get("response", {}).get("hits", [])
    for h in hits:
        res = h.get("result") or {}
        if not res.get("id"):
            continue
        meta = _meta_from_api_song(res)
        if _artist_is_main(artist, meta["primary_artist_names"]):
            return meta
    return None


# ── lyric sources ───────────────────────────────────────────────────────────


def _genius_client():
    # Imported lazily so the app loads without lyricsgenius if scraping is off.
    import lyricsgenius  # noqa: PLC0415

    client = lyricsgenius.Genius(
        GENIUS_TOKEN,
        timeout=15,
        retries=2,
        sleep_time=0.4,
        remove_section_headers=False,  # keep [Chorus] etc. for section stats
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)"],
    )
    client.verbose = False
    return client


def _scrape_genius_lyrics(
    *, song_url: str | None = None, song_id: int | None = None, title: str = "?"
) -> str | None:
    """Full lyrics with section tags, scraped from genius.com. Residential IP only."""
    if not GENIUS_TOKEN:
        return None
    try:
        g = _genius_client()
        if song_url:
            lyrics = g.lyrics(song_url=song_url)
        elif song_id:
            song = g.search_song(song_id=int(song_id), get_full_info=False)
            lyrics = song.lyrics if song else None
        else:
            return None
        lyrics = (lyrics or "").strip()
        return lyrics or None
    except Exception as e:  # noqa: BLE001
        log.warning("Genius scrape failed for %s: %s", title, e)
        return None


def _lrclib_lyrics(artist: str, title: str) -> tuple[str | None, str | None]:
    """Plain lyrics from lrclib.net (no key). Returns (lyrics, album)."""
    headers = {"User-Agent": _UA}
    try:
        r = requests.get(
            "https://lrclib.net/api/get",
            params={"artist_name": artist, "track_name": title},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            j = r.json()
            ly = (j.get("plainLyrics") or "").strip()
            if ly:
                return ly, j.get("albumName")
        # Broader search fallback.
        r = requests.get(
            "https://lrclib.net/api/search",
            params={"track_name": title, "artist_name": artist},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            for it in r.json() or []:
                ly = (it.get("plainLyrics") or "").strip()
                if ly:
                    return ly, it.get("albumName")
    except requests.RequestException:
        pass
    return None, None


def _ovh_lyrics(artist: str, title: str) -> str | None:
    try:
        r = requests.get(
            f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}/{requests.utils.quote(title)}",
            timeout=10,
        )
        if r.status_code != 200:
            return None
        return (r.json().get("lyrics") or "").strip() or None
    except requests.RequestException:
        return None


def get_lyrics(
    artist: str,
    title: str,
    *,
    song_url: str | None = None,
    song_id: int | None = None,
    allow_scrape: bool | None = None,
) -> tuple[str | None, str, str | None]:
    """Best-effort lyric text. Returns (lyrics, source, album).

    Order: Genius scrape (if allowed) → lrclib → lyrics.ovh.
    `source` is one of "genius" | "lrclib" | "ovh" | "none".
    """
    if ONLY_LRCLIB:
        ly, album = _lrclib_lyrics(artist, title)
        if ly:
            return ly, "lrclib", album
        return None, "none", None

    if allow_scrape is None:
        allow_scrape = GENIUS_SCRAPE

    if allow_scrape and (song_url or song_id):
        ly = _scrape_genius_lyrics(song_url=song_url, song_id=song_id, title=title)
        if ly:
            return ly, "genius", None

    ly, album = _lrclib_lyrics(artist, title)
    if ly:
        return ly, "lrclib", album

    ly2 = _ovh_lyrics(artist, title)
    if ly2:
        return ly2, "ovh", None

    return None, "none", None


# ── public API ──────────────────────────────────────────────────────────────


@dataclass
class FetchedSong:
    artist: str
    title: str
    lyrics: str
    source: str  # "genius" | "lrclib" | "ovh" | "cache"
    album: str | None = None
    year: int | None = None


def fetch_song(artist: str, title: str, *, force: bool = False) -> FetchedSong:
    """Get one song. Cache → Genius API metadata + best lyric source."""
    if not force:
        cached = db.find_song(artist, title)
        if cached and cached.lyrics:
            a = db.get_artist(artist)
            return FetchedSong(
                artist=a.name if a else artist,
                title=cached.title,
                lyrics=cached.lyrics,
                source="cache",
                album=cached.album,
                year=cached.year,
            )

    # Resolve canonical metadata via the API (works on any IP).
    meta: dict[str, Any] | None = None
    try:
        meta = search_song_api(artist, title)
    except Exception as e:  # noqa: BLE001
        log.warning("Genius API search failed: %s", e)

    canon_artist = (meta and meta.get("artist_name")) or artist
    canon_title = (meta and meta.get("title")) or title
    song_url = meta.get("url") if meta else None
    song_id = meta.get("id") if meta else None

    lyrics, source, album = get_lyrics(
        canon_artist, canon_title, song_url=song_url, song_id=song_id
    )
    if not lyrics:
        raise FetchError(
            f"Could not find lyrics for '{artist} — {title}' on Genius, lrclib or lyrics.ovh."
        )

    a = db.get_or_create_artist(
        canon_artist,
        genius_id=meta.get("artist_id") if meta else None,
        genius_url=meta.get("artist_url") if meta else None,
    )
    row = db.upsert_song(
        a,
        title=canon_title,
        lyrics=lyrics,
        album=album or (meta.get("album") if meta else None),
        year=meta.get("year") if meta else None,
        genius_id=song_id,
    )
    return FetchedSong(
        artist=a.name,
        title=row.title,
        lyrics=row.lyrics,
        source=source,
        album=row.album,
        year=row.year,
    )


def resolve_and_sample(
    name: str,
    n: int,
    *,
    hard_cap: int = 500,
    pool_size: int = 1000,
    shuffle_seed: str | None = None,
) -> tuple[db.Artist, list[dict[str, Any]]]:
    """Resolve an artist and pick a random sample of up to `n` songs to fetch —
    *without* fetching any lyrics. Uses the Genius API, so it works on Vercel.

    Returns the persisted Artist row and the sampled meta dicts (id, title,
    url, album, year). The caller fetches lyrics per song via `fetch_one_by_id`.
    """
    n = min(n, hard_cap)
    artist_id, artist_name, artist_url = search_artist_api(name)
    a = db.get_or_create_artist(artist_name, genius_id=artist_id, genius_url=artist_url)

    pool, reached_end = artist_songs_api(artist_id, pool_size=pool_size)
    if not pool:
        raise FetchError(f"No songs found on Genius for '{artist_name}'.")

    if reached_end:
        with db.session() as s:
            db_artist = s.get(db.Artist, a.id)
            if db_artist:
                db_artist.total_songs = len(pool)
                s.add(db_artist)
                s.commit()
                a.total_songs = len(pool)

    rng = random.Random(shuffle_seed) if shuffle_seed else random.Random()
    sample = rng.sample(pool, min(n, len(pool)))
    return a, sample


def fetch_one_by_id(
    artist: db.Artist,
    song_id: int,
    title: str = "?",
    *,
    song_url: str | None = None,
    album: str | None = None,
    year: int | None = None,
) -> bool:
    """Fetch and store lyrics for one song. Short enough for a serverless call.

    On a residential IP (GENIUS_SCRAPE on) this scrapes full lyrics; on Vercel
    it falls back to lrclib/lyrics.ovh by artist + title. Returns True if saved.
    """
    # Check if already cached in DB (even if empty lyrics, indicating a previous attempt)
    if song_id:
        with db.session() as s:
            existing = s.exec(
                db.select(db.Song).where(
                    db.Song.artist_id == artist.id, db.Song.genius_id == song_id
                )
            ).first()
            if existing:
                return True
    existing = db.find_song(artist.name, title)
    if existing:
        # Keep genius_id updated if it was missing
        if song_id and not existing.genius_id:
            with db.session() as s:
                db_song = s.get(db.Song, existing.id)
                if db_song:
                    db_song.genius_id = song_id
                    s.add(db_song)
                    s.commit()
        return True

    lyrics, _source, src_album = get_lyrics(artist.name, title, song_url=song_url, song_id=song_id)
    # Save empty lyrics to mark as attempted so we don't repeat the fetch
    if not lyrics:
        lyrics = ""
    db.upsert_song(
        artist,
        title=title,
        lyrics=lyrics,
        album=src_album or album,
        year=year,
        genius_id=int(song_id) if song_id else None,
    )
    return True


def fetch_artist_catalogue(
    name: str,
    *,
    min_songs: int = 20,
    hard_cap: int = 500,
    pool_size: int = 1000,
    shuffle_seed: str | None = None,
    progress=None,  # callable(done, total, current_title) for UI
) -> int:
    """Save a uniformly random sample of `min_songs` from the artist's catalogue
    in one blocking call.

    Thin wrapper composing `resolve_and_sample` + `fetch_one_by_id`. Used by
    the seed scripts and tests; the Vercel frontend drives the two halves
    itself so each HTTP request stays short. Saved count is at most
    `min_songs`; songs without findable lyrics are silently skipped.
    """
    n = min(min_songs, hard_cap)
    a, sample = resolve_and_sample(
        name, n, hard_cap=hard_cap, pool_size=pool_size, shuffle_seed=shuffle_seed
    )

    saved = 0
    for i, meta in enumerate(sample, 1):
        title = meta.get("title", "?")
        if progress:
            progress(i, n, title)
        if fetch_one_by_id(
            a,
            int(meta["id"]) if meta.get("id") else 0,
            title,
            song_url=meta.get("url"),
            album=meta.get("album"),
            year=meta.get("year"),
        ):
            saved += 1
        time.sleep(0.15)

    if progress:
        progress(n, n, "done")
    db.mark_catalogue_fetched(a)
    return saved
