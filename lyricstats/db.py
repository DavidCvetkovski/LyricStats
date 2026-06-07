"""SQLite cache for fetched lyrics and computed stats.

Tables:
  - Artist: one per artist name (case-insensitive key)
  - Song:   one per (artist_id, title), holds lyrics + cached stats JSON
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import DATABASE_URL, DB_PATH


def normalize_key(name: str) -> str:
    """Aggressive normalisation for 'is this obviously the same artist?' matching.

    Strips accents, lowercases, and drops every non-alphanumeric character so
    casing/punctuation/spacing differences collapse to one key:
      'JAY-Z' / 'jay z' → 'jayz';  'Beyoncé' → 'beyonce';
      'Tyler, the Creator' / 'tyler the creator' → 'tylerthecreator'.
    An exact match on this key is treated as 'very close' (auto-load).
    """
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return "".join(c for c in s if c.isalnum())


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


class ArtistAggregate(SQLModel, table=True):
    """Precomputed career-wide stats for an artist, imported in bulk from a
    lyrics dataset (no per-song lyrics stored).

    This powers instant artist lookup: the browser sends just a name and gets
    the whole-catalogue aggregate back with zero Genius/lyric fetches. Kept
    separate from Artist/Song so the lyrics-backed flow (Balkan seeds, on-demand
    song pages) is untouched. ``stats_json`` holds the full ArtistStats payload;
    the scalar columns exist for indexing/filtering and size accounting.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)       # _norm (strip+lower) key
    name_key: str = Field(default="", index=True)    # aggressive key for fuzzy/auto match
    display_name: str                                 # original casing for display
    song_count: int = Field(default=0, index=True)
    has_sections: bool = Field(default=False)
    stats_json: str = ""                              # full ArtistStats.to_dict()
    source: str = Field(default="dataset")
    built_at: datetime = Field(default_factory=datetime.utcnow)


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


# ---- precomputed artist aggregates (dataset import) ------------------------


def get_artist_aggregate(name: str) -> "ArtistAggregate | None":
    """Exact-or-very-close lookup: matches on the aggressive name_key so
    casing/accents/punctuation differences auto-resolve. On the rare key
    collision, prefer the artist with the larger catalogue."""
    key = normalize_key(name)
    if not key:
        return None
    with session() as s:
        return s.exec(
            select(ArtistAggregate)
            .where(ArtistAggregate.name_key == key)
            .order_by(ArtistAggregate.song_count.desc())  # type: ignore[attr-defined]
        ).first()


def suggest_artist_aggregates(name: str, limit: int = 1) -> list["ArtistAggregate"]:
    """Looser 'did you mean?' candidates for a typo with no exact key match.

    Postgres uses pg_trgm similarity (set up at sync time); SQLite falls back to
    a difflib ratio over candidate names sharing a prefix/substring. Returns the
    best matches above a similarity floor, most-songs first as a tiebreak.
    """
    key = normalize_key(name)
    if len(key) < 3:
        return []

    if DATABASE_URL:
        from sqlalchemy import text  # noqa: PLC0415

        with session() as s:
            rows = s.exec(  # type: ignore[call-overload]
                text(
                    "SELECT * FROM artistaggregate "
                    "WHERE similarity(name_key, :q) > 0.4 "
                    "ORDER BY similarity(name_key, :q) DESC, song_count DESC "
                    "LIMIT :lim"
                ).bindparams(q=key, lim=limit)
            ).all()
            return list(rows)

    # SQLite fallback: difflib over a coarse candidate set (cheap prefiltering
    # by shared 3-char prefix keeps this from scanning the whole table).
    import difflib  # noqa: PLC0415

    prefix = key[:3]
    with session() as s:
        candidates = s.exec(
            select(ArtistAggregate).where(ArtistAggregate.name_key.like(f"{prefix}%"))  # type: ignore[attr-defined]
        ).all()
    scored = [
        (difflib.SequenceMatcher(None, key, c.name_key).ratio(), c) for c in candidates
    ]
    scored = [sc for sc in scored if sc[0] > 0.6]
    scored.sort(key=lambda sc: (sc[0], sc[1].song_count), reverse=True)
    return [c for _, c in scored[:limit]]


def upsert_artist_aggregate(
    *,
    name: str,
    display_name: str,
    song_count: int,
    has_sections: bool,
    stats: dict,
    source: str = "dataset",
) -> None:
    key = _norm(name)
    nkey = normalize_key(name)
    payload = json.dumps(stats, ensure_ascii=False)
    with session() as s:
        existing = s.exec(
            select(ArtistAggregate).where(ArtistAggregate.name == key)
        ).first()
        if existing:
            existing.name_key = nkey
            existing.display_name = display_name
            existing.song_count = song_count
            existing.has_sections = has_sections
            existing.stats_json = payload
            existing.source = source
            existing.built_at = datetime.utcnow()
            s.add(existing)
        else:
            s.add(
                ArtistAggregate(
                    name=key,
                    name_key=nkey,
                    display_name=display_name,
                    song_count=song_count,
                    has_sections=has_sections,
                    stats_json=payload,
                    source=source,
                )
            )
        s.commit()


def reset_aggregates() -> None:
    """Drop and recreate the ArtistAggregate table for a clean full re-import
    (also picks up schema changes like the name_key column locally)."""
    ArtistAggregate.__table__.drop(_engine, checkfirst=True)  # type: ignore[attr-defined]
    ArtistAggregate.__table__.create(_engine)  # type: ignore[attr-defined]


def load_aggregate_stats(agg: "ArtistAggregate") -> dict | None:
    if not agg.stats_json:
        return None
    try:
        return json.loads(agg.stats_json)
    except json.JSONDecodeError:
        return None
