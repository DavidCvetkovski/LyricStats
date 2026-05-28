"""Lyrics fetcher — Genius primary, lyrics.ovh fallback.

All results land in SQLite so we never re-scrape.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

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
    max_songs: int = 30,
    progress=None,  # callable(done, total, current_title) for UI
) -> int:
    """Fetch up to `max_songs` for an artist. Returns count fetched."""
    artist_obj = _genius_search_artist(name, max_songs=max_songs)
    if artist_obj is None:
        raise FetchError(f"Artist '{name}' not found on Genius.")

    a = db.get_or_create_artist(
        artist_obj.name,
        genius_id=_id_from_api_path(artist_obj),
        genius_url=getattr(artist_obj, "url", None),
    )
    songs = artist_obj.songs or []
    total = len(songs)
    saved = 0
    for i, song in enumerate(songs, 1):
        if progress:
            progress(i, total, song.title)
        if not getattr(song, "lyrics", None):
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
        time.sleep(0.2)
    db.mark_catalogue_fetched(a)
    return saved
