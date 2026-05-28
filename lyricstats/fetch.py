"""Lyrics fetcher — Genius primary, lyrics.ovh fallback.

All results land in SQLite so we never re-scrape.
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
from .config import GENIUS_TOKEN

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


_API_PATH_ID_RE = re.compile(r"/(?:artists|songs)/(\d+)")


def _id_from_api_path(obj: Any) -> int | None:
    """Extract numeric id from lyricsgenius object's api_path (e.g. '/artists/53624')."""
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


# ── live progress via lyricsgenius's own logger ────────────────────────────
#
# lyricsgenius.search_artist is a single blocking call that fetches songs
# one at a time. Our own loop only runs after it finishes, so the progress
# callback never moves during the slow part. lyricsgenius does log each
# fetch at INFO level ("Song 5: 'Title'"), so we attach a temporary logging
# handler that turns those messages into real progress events.

_LG_SONG_RE = re.compile(r'^\s*Song\s+(\d+):\s*"(.+)"\s*$')


class _LyricsGeniusProgressHandler(logging.Handler):
    def __init__(
        self,
        on_progress: Callable[[int, int, str], None],
        total: int,
    ) -> None:
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
            # Cap the displayed count at the user's requested minimum so the
            # buffer fetches at the tail don't push the bar past 100%.
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
    log = logging.getLogger("lyricsgenius.genius")
    prev_level = log.level
    # Ensure the logger actually emits records to our handler.
    if prev_level == logging.NOTSET or prev_level > logging.INFO:
        log.setLevel(logging.INFO)
    handler = _LyricsGeniusProgressHandler(on_progress, total)
    log.addHandler(handler)
    try:
        yield
    finally:
        log.removeHandler(handler)
        if prev_level != log.level:
            log.setLevel(prev_level)


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


# ---- Genius ----------------------------------------------------------------


def _genius_client():
    if not GENIUS_TOKEN:
        raise FetchError(
            "GENIUS_TOKEN is not set. Add it to .env or .streamlit/secrets.toml "
            "(get one free at https://genius.com/api-clients)."
        )
    # Imported lazily so the app loads without lyricsgenius if user just wants the cache.
    import lyricsgenius  # noqa: PLC0415

    g = lyricsgenius.Genius(
        GENIUS_TOKEN,
        timeout=15,
        retries=2,
        sleep_time=0.4,
        remove_section_headers=False,  # we want [Chorus] etc. for section stats
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)"],
    )
    return g


@retry(
    retry=retry_if_exception_type((requests.RequestException, FetchError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _genius_search_song(artist: str, title: str):
    g = _genius_client()
    return g.search_song(title=title, artist=artist, get_full_info=False)


@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _genius_search_artist(name: str, max_songs: int):
    g = _genius_client()
    return g.search_artist(name, max_songs=max_songs, sort="popularity", include_features=False)


# ---- lyrics.ovh fallback ---------------------------------------------------


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


# ---- public API ------------------------------------------------------------


@dataclass
class FetchedSong:
    artist: str
    title: str
    lyrics: str
    source: str  # "genius" | "ovh" | "cache"
    album: str | None = None
    year: int | None = None


def fetch_song(artist: str, title: str, *, force: bool = False) -> FetchedSong:
    """Get one song. Cache → Genius → lyrics.ovh."""
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

    # Try Genius
    try:
        song = _genius_search_song(artist, title)
    except FetchError:
        song = None
    except Exception as e:
        log.warning("Genius search failed: %s", e)
        song = None

    if song and song.lyrics:
        primary = getattr(song, "primary_artist", None)
        artist_genius_id = _id_from_api_path(primary) if primary else None
        artist_url = getattr(primary, "url", None) if primary else None
        a = db.get_or_create_artist(
            artist, genius_id=artist_genius_id, genius_url=artist_url
        )
        row = db.upsert_song(
            a,
            title=song.title,
            lyrics=song.lyrics,
            album=_album_name(song),
            year=_song_year(song),
            genius_id=_id_from_api_path(song),
        )
        return FetchedSong(
            artist=a.name, title=row.title, lyrics=row.lyrics,
            source="genius", album=row.album, year=row.year,
        )

    # Fallback
    ovh = _ovh_lyrics(artist, title)
    if ovh:
        a = db.get_or_create_artist(artist)
        row = db.upsert_song(a, title=title, lyrics=ovh)
        return FetchedSong(artist=a.name, title=row.title, lyrics=row.lyrics, source="ovh")

    raise FetchError(f"Could not find lyrics for '{artist} — {title}' on Genius or lyrics.ovh.")


def fetch_artist_catalogue(
    name: str,
    *,
    min_songs: int = 20,
    hard_cap: int = 100,
    pool_size: int = 200,
    shuffle_seed: str | None = None,
    progress=None,  # callable(done, total, current_title) for UI
) -> int:
    """Save a uniformly random sample of `min_songs` from the artist's
    Genius catalogue.

    Two-phase fetch so the progress bar tracks only what the user actually
    waits for:

    1. Pool phase: pull up to `pool_size` song metadata entries via
       Genius's paginated artist_songs endpoint. No lyrics here, just
       titles + ids. Cheap.
    2. Random sample: pick `min_songs` ids from the pool. With
       `shuffle_seed` set, the sample is deterministic; without it,
       fully random.
    3. Lyric phase: fetch lyrics for exactly those N ids, reporting
       progress per song.

    Saved count is at most `min_songs`. Songs without lyrics
    (instrumentals etc.) are silently skipped.
    """
    n = min(min_songs, hard_cap)
    g = _genius_client()

    # ── 1. Resolve artist ────────────────────────────────────────────
    # search_artist with max_songs=0 just gets artist metadata, no lyrics.
    artist_obj = _genius_search_artist(name, max_songs=0)
    if artist_obj is None:
        raise FetchError(f"Artist '{name}' not found on Genius.")
    artist_id = _id_from_api_path(artist_obj)
    if artist_id is None:
        raise FetchError(f"Could not resolve Genius id for '{name}'.")

    a = db.get_or_create_artist(
        artist_obj.name,
        genius_id=artist_id,
        genius_url=getattr(artist_obj, "url", None),
    )

    # ── 2. Pool song metadata ────────────────────────────────────────
    pool: list[dict[str, Any]] = []
    per_page = 50
    page = 1
    while len(pool) < pool_size:
        try:
            res = g.artist_songs(artist_id, per_page=per_page, page=page, sort="popularity")
        except Exception as e:  # noqa: BLE001
            log.warning("artist_songs page %d failed: %s", page, e)
            break
        songs_meta = (res or {}).get("songs", []) if isinstance(res, dict) else []
        if not songs_meta:
            break
        # Keep collaborations too — artists with frequent features
        # (e.g. Buba Corelli with Jala Brat) would otherwise show as
        # almost-empty catalogues.
        pool.extend(songs_meta)
        if len(songs_meta) < per_page:
            break
        page += 1
        time.sleep(0.15)

    if not pool:
        raise FetchError(f"No songs found on Genius for '{artist_obj.name}'.")

    # ── 3. Random sample ─────────────────────────────────────────────
    rng = random.Random(shuffle_seed) if shuffle_seed else random.Random()
    sample = rng.sample(pool, min(n, len(pool)))

    # ── 4. Fetch lyrics for the sampled songs ────────────────────────
    saved = 0
    for i, meta in enumerate(sample, 1):
        title = meta.get("title", "?")
        sid = meta.get("id")
        if progress:
            progress(i, n, title)
        if not sid:
            continue
        try:
            song = g.search_song(song_id=int(sid), get_full_info=False)
        except Exception as e:  # noqa: BLE001
            log.warning("lyric fetch failed for %s: %s", title, e)
            continue
        if not song or not song.lyrics:
            continue
        db.upsert_song(
            a,
            title=song.title,
            lyrics=song.lyrics,
            album=_album_name(song),
            year=_song_year(song),
            genius_id=_id_from_api_path(song),
        )
        saved += 1
        time.sleep(0.15)

    if progress:
        progress(n, n, "done")
    db.mark_catalogue_fetched(a)
    return saved
