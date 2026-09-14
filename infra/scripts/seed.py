#!/usr/bin/env python3
"""Export a slice of the local LyricStats SQLite database as CSV for Postgres.

The cluster's Postgres starts empty and the API creates the tables when it
starts. This writes the precomputed artist aggregates for the N largest
catalogues, plus any artists named with --artist, to stdout; `make seed`
pipes that into psql's \\copy inside the Postgres pod.

The source database is opened read-only. Standard library only.

  python3 infra/scripts/seed.py --limit 2000 --artist "Jala Brat" > aggregates.csv
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = (
    "name",
    "name_key",
    "display_name",
    "song_count",
    "has_sections",
    "stats_json",
    "songs_json",
    "source",
    "built_at",
)
DEFAULT_ARTISTS = ("Taylor Swift", "The Weeknd", "Lana Del Rey", "Jala Brat")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database", default="data/lyricstats.db", help="SQLite source file")
    parser.add_argument("--limit", type=int, default=2000, help="How many of the largest catalogues")
    parser.add_argument(
        "--artist",
        action="append",
        default=list(DEFAULT_ARTISTS),
        help="Also include this artist by display name (repeatable)",
    )
    args = parser.parse_args()

    path = Path(args.database).resolve()
    if not path.is_file():
        parser.error(f"{path} does not exist")

    source = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    columns = ", ".join(COLUMNS)
    rows: dict[str, tuple] = {}

    for row in source.execute(
        f"SELECT {columns} FROM artistaggregate ORDER BY song_count DESC LIMIT ?", (args.limit,)
    ):
        rows[row[0]] = row
    for artist in args.artist:
        for row in source.execute(
            f"SELECT {columns} FROM artistaggregate WHERE lower(display_name) = lower(?)", (artist,)
        ):
            rows.setdefault(row[0], row)
    source.close()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    writer = csv.writer(sys.stdout, lineterminator="\n")
    size = 0
    for name, name_key, display, count, has_sections, stats, songs, src, built_at in rows.values():
        record = (
            name,
            name_key or "",
            display,
            count,
            "true" if has_sections else "false",
            stats or "",
            songs or "",
            src or "dataset",
            built_at or now,
        )
        size += sum(len(str(value)) for value in record)
        writer.writerow(record)

    print(f"seed: exported {len(rows)} artists ({size / 1_048_576:.1f} MB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
