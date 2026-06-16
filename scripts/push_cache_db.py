#!/usr/bin/env python3
"""Push clean artist and song tables from local SQLite database to Neon Postgres."""

from __future__ import annotations

import os
import sys
from sqlalchemy import create_engine, insert, text
from sqlmodel import Session, select
from lyricstats import db


def _prod_url() -> str:
    url = None
    if os.path.exists(".env.local"):
        with open(".env.local") as f:
            for line in f:
                if line.strip().startswith("DATABASE_URL="):
                    raw = line.strip().split("=", 1)[1].split("#", 1)[0].strip()
                    url = raw.strip("'\"")
    if not url:
        print("Error: DATABASE_URL not found in .env.local")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def main() -> None:
    prod_engine = create_engine(_prod_url(), echo=False)
    local_engine = db._engine

    # Load local artists and songs
    with Session(local_engine) as ls:
        artists = ls.exec(select(db.Artist)).all()
        songs = ls.exec(select(db.Song)).all()

    print(f"Local artists to push: {len(artists)}")
    print(f"Local songs to push: {len(songs)}")

    print("Recreating artist and song tables on production...")
    with prod_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS song CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS artist CASCADE"))

    db.SQLModel.metadata.create_all(prod_engine)

    print("Inserting artists...")
    artist_payload = [
        {
            "id": a.id,
            "name": a.name,
            "genius_id": a.genius_id,
            "genius_url": a.genius_url,
            "fetched_at": a.fetched_at,
            "catalogue_fetched_at": a.catalogue_fetched_at,
            "total_songs": a.total_songs,
        }
        for a in artists
    ]
    with prod_engine.begin() as conn:
        if artist_payload:
            conn.execute(insert(db.Artist.__table__), artist_payload)

    print("Inserting songs...")
    song_payload = [
        {
            "id": s.id,
            "artist_id": s.artist_id,
            "title": s.title,
            "album": s.album,
            "year": s.year,
            "genius_id": s.genius_id,
            "lyrics": s.lyrics,
            "stats_json": s.stats_json,
            "fetched_at": s.fetched_at,
        }
        for s in songs
    ]
    with prod_engine.begin() as conn:
        if song_payload:
            conn.execute(insert(db.Song.__table__), song_payload)

    print("✅ Successfully pushed clean cache tables to production!")


if __name__ == "__main__":
    main()
