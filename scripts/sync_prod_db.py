#!/usr/bin/env python3
import os
import sys
from sqlmodel import Session, create_engine, select
from lyricstats import db

def main():
    # Read production DATABASE_URL from .env.local
    prod_url = None
    if os.path.exists(".env.local"):
        with open(".env.local") as f:
            for line in f:
                if line.strip().startswith("DATABASE_URL="):
                    # Strip any comments if present
                    raw_val = line.strip().split("=", 1)[1].split("#", 1)[0].strip()
                    prod_url = raw_val.strip("'\"")

    if not prod_url:
        print("Error: DATABASE_URL not found in .env.local")
        sys.exit(1)

    # Normalise Postgres URL to use psycopg driver
    if prod_url.startswith("postgres://"):
        prod_url = "postgresql+psycopg://" + prod_url[len("postgres://"):]
    elif prod_url.startswith("postgresql://"):
        prod_url = "postgresql+psycopg://" + prod_url[len("postgresql://"):]

    print("Connecting to production database...")
    try:
        prod_engine = create_engine(prod_url, echo=False)
        # Test connection
        with prod_engine.connect() as conn:
            pass
    except Exception as e:
        print(f"Error connecting to production database: {e}")
        sys.exit(1)

    # Local SQLite engine
    local_engine = db._engine

    print("Syncing Artists...")
    with Session(prod_engine) as prod_session, Session(local_engine) as local_session:
        # Get all artists from prod
        prod_artists = prod_session.exec(select(db.Artist)).all()
        artist_map = {} # maps prod artist ID to local artist object
        for pa in prod_artists:
            # Check if artist exists locally
            la = local_session.exec(select(db.Artist).where(db.Artist.name == pa.name)).first()
            if not la:
                la = db.Artist(
                    name=pa.name,
                    genius_id=pa.genius_id,
                    genius_url=pa.genius_url,
                    fetched_at=pa.fetched_at,
                    catalogue_fetched_at=pa.catalogue_fetched_at,
                    total_songs=pa.total_songs
                )
                local_session.add(la)
                local_session.commit()
                local_session.refresh(la)
                print(f"Added local artist: {pa.name}")
            else:
                # Sync fields
                la.total_songs = pa.total_songs or la.total_songs
                la.genius_id = pa.genius_id or la.genius_id
                la.genius_url = pa.genius_url or la.genius_url
                local_session.add(la)
                local_session.commit()
                local_session.refresh(la)
            artist_map[pa.id] = la

        # Get all songs from prod
        print("Syncing Songs...")
        prod_songs = prod_session.exec(select(db.Song)).all()
        synced_songs = 0
        for ps in prod_songs:
            # Get local artist mapping
            la = artist_map.get(ps.artist_id)
            if not la:
                continue
            
            # Check if song exists locally under this artist
            ls = local_session.exec(
                select(db.Song).where(db.Song.artist_id == la.id, db.Song.title == ps.title)
            ).first()
            if not ls:
                ls = db.Song(
                    artist_id=la.id,
                    title=ps.title,
                    album=ps.album,
                    year=ps.year,
                    genius_id=ps.genius_id,
                    lyrics=ps.lyrics,
                    stats_json=ps.stats_json,
                    fetched_at=ps.fetched_at
                )
                local_session.add(ls)
                synced_songs += 1
            else:
                # Update missing fields or empty lyrics
                dirty = False
                if not ls.lyrics and ps.lyrics:
                    ls.lyrics = ps.lyrics
                    dirty = True
                if not ls.stats_json and ps.stats_json:
                    ls.stats_json = ps.stats_json
                    dirty = True
                if not ls.genius_id and ps.genius_id:
                    ls.genius_id = ps.genius_id
                    dirty = True
                if dirty:
                    local_session.add(ls)
                    synced_songs += 1

        local_session.commit()
        print(f"Sync complete! Synced {synced_songs} songs.")

if __name__ == "__main__":
    main()
