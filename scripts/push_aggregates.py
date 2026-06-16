#!/usr/bin/env python3
"""Push the precomputed ArtistAggregate table from the local SQLite DB up to
the production Postgres (Neon) database, and set up trigram fuzzy search.

Only touches the ``artistaggregate`` table — the existing Artist/Song (Balkan
lyrics-backed) data on prod is left untouched. Idempotent: drops and recreates
just the aggregate table, bulk-inserts, then (re)creates the pg_trgm index.

Usage:
    uv run python scripts/push_aggregates.py            # push
    uv run python scripts/push_aggregates.py --dry-run  # counts only
"""

from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.pop("DATABASE_URL", None)
os.environ.pop("POSTGRES_URL", None)

from sqlalchemy import create_engine, insert, text
from sqlmodel import Session, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats import db  # noqa: E402


def _prod_url() -> str:
    url = None
    if os.path.exists(".env.prod"):
        with open(".env.prod") as f:
            for line in f:
                if line.strip().startswith("DATABASE_URL="):
                    raw = line.strip().split("=", 1)[1].split("#", 1)[0].strip()
                    url = raw.strip("'\"")
    if not url:
        print("Error: DATABASE_URL not found in .env.prod")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=1000)
    args = ap.parse_args()

    # Read every local aggregate as plain dicts (detached from the session).
    with Session(db._engine) as ls:
        rows = ls.exec(select(db.ArtistAggregate).where(db.ArtistAggregate.song_count >= 25)).all()
        payload = []
        import json

        for r in rows:
            stats = json.loads(r.stats_json) if r.stats_json else {}
            # Strip heavy metadata that blows up the database size
            stats.pop("percentiles", None)
            stats.pop("albums", None)
            stats.pop("density_curve", None)
            stats.pop("lang_mix", None)

            songs = json.loads(r.songs_json) if r.songs_json else []
            songs = songs[:500]  # Only store top 500 songs

            payload.append(
                {
                    "name": r.name,
                    "name_key": r.name_key,
                    "display_name": r.display_name,
                    "song_count": r.song_count,
                    "has_sections": r.has_sections,
                    "stats_json": json.dumps(stats, separators=(",", ":")),
                    "songs_json": json.dumps(songs, separators=(",", ":")),
                    "source": r.source,
                    "built_at": r.built_at,
                }
            )
    print(f"Local aggregates to push: {len(payload):,}")
    if args.dry_run:
        return
    if not payload:
        print("Nothing to push.")
        return

    prod_engine = create_engine(_prod_url(), echo=False)
    try:
        with prod_engine.connect():
            pass
    except Exception as e:  # noqa: BLE001
        print(f"Error connecting to production database: {e}")
        sys.exit(1)

    tbl = db.ArtistAggregate.__table__

    print("Recreating artistaggregate table on prod…")
    tbl.drop(prod_engine, checkfirst=True)
    tbl.create(prod_engine)

    print(f"Bulk-inserting {len(payload):,} rows…")
    t0 = time.time()
    with prod_engine.begin() as conn:
        for i in range(0, len(payload), args.batch):
            conn.execute(insert(tbl), payload[i : i + args.batch])
            if (i // args.batch) % 10 == 0:
                print(f"  …{i:,}/{len(payload):,}", flush=True)
    print(f"  inserted in {time.time() - t0:.0f}s")

    print("Enabling pg_trgm + GIN index on name_key (fuzzy 'did you mean')…")
    with prod_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_aggregate_name_key_trgm "
                "ON artistaggregate USING gin (name_key gin_trgm_ops)"
            )
        )

    with prod_engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM artistaggregate")).scalar()
        size = conn.execute(
            text("SELECT pg_size_pretty(pg_total_relation_size('artistaggregate'))")
        ).scalar()
        db_size = conn.execute(
            text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        ).scalar()
    print(f"\n✅ Prod artistaggregate: {n:,} rows, table {size}, whole DB {db_size}")


if __name__ == "__main__":
    main()
