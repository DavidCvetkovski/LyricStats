"""SQLite cache for fetched lyrics and computed stats.

Tables:
  - Artist: one per artist name (case-insensitive key)
  - Song:   one per (artist_id, title), holds lyrics + cached stats JSON
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import DATABASE_URL, DB_PATH


class Artist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    genius_id: Optional[int] = Field(default=None, index=True)
    genius_url: Optional[str] = None  # canonical Genius web URL, for disambiguation
    fetched_at: Optional[datetime] = None
    catalogue_fetched_at: Optional[datetime] = None
    total_songs: Optional[int] = Field(default=None)


class Song(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artist.id", index=True)
    title: str = Field(index=True)
    album: Optional[str] = None
    year: Optional[int] = None
    genius_id: Optional[int] = Field(default=None, index=True)
    lyrics: str = ""
    stats_json: Optional[str] = None  # cached computed stats
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


def _make_engine():
    """Postgres (Neon, etc.) when DATABASE_URL is set, else a local SQLite file.

    On serverless the engine is created once per warm container and reused
    across invocations; pool_pre_ping recycles connections dropped by the
    pooler between cold periods.
    """
    if DATABASE_URL:
        url = DATABASE_URL
        # Normalise common Postgres URL forms to the psycopg (v3) driver.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return create_engine(url, echo=False, pool_pre_ping=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


_engine = _make_engine()
SQLModel.metadata.create_all(_engine)


def _migrate() -> None:
    """Idempotent column additions for tables created by older versions.

    Inspects existing columns in both SQLite and Postgres to dynamically add
    missing columns like `genius_url` and `total_songs`.
    """
    from sqlalchemy import inspect, text  # noqa: PLC0415

    inspector = inspect(_engine)
    if "artist" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("artist")}
        with _engine.begin() as conn:
            if "genius_url" not in columns:
                conn.execute(text("ALTER TABLE artist ADD COLUMN genius_url VARCHAR"))
            if "total_songs" not in columns:
                conn.execute(text("ALTER TABLE artist ADD COLUMN total_songs INTEGER"))


# Only run migrations locally on SQLite. The production Postgres database is
# already migrated; skipping inspection eliminates unnecessary network queries
# and latency during serverless cold starts.
if not DATABASE_URL:
    _migrate()


def session() -> Session:
    return Session(_engine)


# ---- artist helpers --------------------------------------------------------


def _norm(name: str) -> str:
    return name.strip().lower()


def get_or_create_artist(
    name: str,
    genius_id: int | None = None,
    genius_url: str | None = None,
) -> Artist:
    with session() as s:
        row = s.exec(select(Artist).where(Artist.name == _norm(name))).first()
        if row:
            dirty = False
            if genius_id and not row.genius_id:
                row.genius_id = genius_id
                dirty = True
            if genius_url and not row.genius_url:
                row.genius_url = genius_url
                dirty = True
            if dirty:
                s.add(row)
                s.commit()
                s.refresh(row)
            return row
        row = Artist(name=_norm(name), genius_id=genius_id, genius_url=genius_url)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def get_artist(name: str) -> Artist | None:
    with session() as s:
        return s.exec(select(Artist).where(Artist.name == _norm(name))).first()


# ---- song helpers ----------------------------------------------------------


def upsert_song(
    artist: Artist,
    title: str,
    lyrics: str,
    *,
    album: str | None = None,
    year: int | None = None,
    genius_id: int | None = None,
) -> Song:
    with session() as s:
        existing = s.exec(
            select(Song).where(Song.artist_id == artist.id, Song.title == title)
        ).first()
        if existing:
            existing.lyrics = lyrics
            existing.album = album or existing.album
            existing.year = year or existing.year
            existing.genius_id = genius_id or existing.genius_id
            existing.fetched_at = datetime.utcnow()
            existing.stats_json = None  # invalidate cache
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing
        row = Song(
            artist_id=artist.id,
            title=title,
            album=album,
            year=year,
            genius_id=genius_id,
            lyrics=lyrics,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def find_song(artist_name: str, title: str) -> Song | None:
    a = get_artist(artist_name)
    if not a:
        return None
    with session() as s:
        return s.exec(
            select(Song).where(Song.artist_id == a.id, Song.title.ilike(title))  # type: ignore[attr-defined]
        ).first()


def list_songs(artist: Artist) -> list[Song]:
    with session() as s:
        return list(s.exec(select(Song).where(Song.artist_id == artist.id)).all())


def save_stats(song: Song, stats: dict) -> None:
    with session() as s:
        row = s.get(Song, song.id)
        if not row:
            return
        row.stats_json = json.dumps(stats, ensure_ascii=False)
        s.add(row)
        s.commit()


def load_stats(song: Song) -> dict | None:
    if not song.stats_json:
        return None
    try:
        return json.loads(song.stats_json)
    except json.JSONDecodeError:
        return None


def mark_catalogue_fetched(artist: Artist) -> None:
    with session() as s:
        row = s.get(Artist, artist.id)
        if not row:
            return
        row.catalogue_fetched_at = datetime.utcnow()
        s.add(row)
        s.commit()
