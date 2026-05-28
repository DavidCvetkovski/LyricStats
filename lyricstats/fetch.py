"""Lyrics fetcher — Genius primary, lyrics.ovh fallback.

All results land in SQLite so we never re-scrape.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from . import db
from .config import GENIUS_TOKEN

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


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
        remove_section_headers=False,  # we want [Chorus] etc. for section stats
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)"],
        verbose=False,
    )
    g.sleep_time = 0.4
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
        a = db.get_or_create_artist(artist, genius_id=getattr(song, "artist_id", None))
        year = None
        if getattr(song, "year", None):
            try:
                year = int(str(song.year)[:4])
            except (ValueError, TypeError):
                year = None
        row = db.upsert_song(
            a,
            title=song.title,
            lyrics=song.lyrics,
            album=getattr(song, "album", None),
            year=year,
            genius_id=getattr(song, "id", None),
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

    a = db.get_or_create_artist(artist_obj.name, genius_id=artist_obj.id)
    songs = artist_obj.songs or []
    total = len(songs)
    for i, song in enumerate(songs, 1):
        if progress:
            progress(i, total, song.title)
        if not getattr(song, "lyrics", None):
            continue
        year = None
        if getattr(song, "year", None):
            try:
                year = int(str(song.year)[:4])
            except (ValueError, TypeError):
                year = None
        db.upsert_song(
            a,
            title=song.title,
            lyrics=song.lyrics,
            album=getattr(song, "album", None),
            year=year,
            genius_id=getattr(song, "id", None),
        )
        time.sleep(0.2)
    db.mark_catalogue_fetched(a)
    return len(songs)
