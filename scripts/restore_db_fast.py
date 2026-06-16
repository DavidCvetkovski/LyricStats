#!/usr/bin/env python3
import os
import sys
import sqlite3
import psycopg


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
    return url


def main():
    prod_url = _prod_url()
    print("Connecting raw to Postgres...")
    pg_conn = psycopg.connect(prod_url)

    sqlite_path = "data/lyricstats.db"
    print(f"Connecting to local SQLite: {sqlite_path}...")
    sqlite_conn = sqlite3.connect(sqlite_path)

    print("Recreating local artistaggregate table...")
    sqlite_conn.execute("DROP TABLE IF EXISTS artistaggregate")
    sqlite_conn.execute("""
    CREATE TABLE artistaggregate (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(255) NOT NULL UNIQUE,
        name_key VARCHAR(255) NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        song_count INTEGER NOT NULL,
        has_sections BOOLEAN NOT NULL,
        stats_json TEXT NOT NULL,
        songs_json TEXT NOT NULL,
        source VARCHAR(50) NOT NULL,
        built_at TEXT NOT NULL
    )
    """)
    sqlite_conn.commit()

    print("Streaming aggregates from production...")
    total = 0
    with pg_conn.cursor() as pg_cursor:
        # Declare server-side cursor
        pg_cursor.execute(
            "DECLARE restore_cursor CURSOR FOR "
            "SELECT name, name_key, display_name, song_count, has_sections, stats_json, songs_json, source, CAST(built_at AS TEXT) FROM artistaggregate"
        )

        batch_size = 2000
        while True:
            pg_cursor.execute(f"FETCH {batch_size} FROM restore_cursor")
            rows = pg_cursor.fetchall()
            if not rows:
                break

            sqlite_conn.executemany(
                "INSERT INTO artistaggregate (name, name_key, display_name, song_count, has_sections, stats_json, songs_json, source, built_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            sqlite_conn.commit()
            total += len(rows)
            print(f"  Synced {total:,} rows...", flush=True)

    sqlite_conn.close()
    pg_conn.close()
    print(f"✅ Successfully restored {total:,} aggregates locally in seconds!")


if __name__ == "__main__":
    main()
