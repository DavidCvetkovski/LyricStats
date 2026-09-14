#!/usr/bin/env python3
"""Extract the small, reproducible Issue 02 snapshot without changing a database.

Standard library only. One indexed artist lookup, at most 64 KiB of cached
song metadata, a five-second query deadline, no lyrics or network requests.
The destination must be new: successful snapshots are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

ARTIST_KEY = "jala brat"
SELECTED_TITLES = ("Godzilla", "Bass & Rave", "Mufasa", "Ajkula", "Comfort")
MAX_SOURCE_BYTES = 65_536
MAX_SONGS = 500
QUERY_SECONDS = 5


def extract(database: Path) -> dict:
    """Read only the named aggregate; fail if the expected source has changed."""
    database = database.resolve(strict=True)
    started = time.monotonic()
    connection = sqlite3.connect(
        database.as_uri() + "?mode=ro", uri=True, timeout=1
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(
            lambda: int(time.monotonic() - started > QUERY_SECONDS), 1_000
        )
        # Require the known index so schema drift cannot turn this into a scan.
        row = connection.execute(
            "SELECT display_name, song_count, source, built_at, songs_json "
            "FROM artistaggregate INDEXED BY ix_artistaggregate_name "
            "WHERE name = ? AND length(CAST(songs_json AS BLOB)) <= ? LIMIT 1",
            (ARTIST_KEY, MAX_SOURCE_BYTES),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise ValueError("Expected small Jala Brat aggregate is missing or too large")
    artist, expected_count, source, built_at, encoded_songs = row
    if source != "lrclib":
        raise ValueError("This article's methodology requires the LRCLIB snapshot")
    songs = json.loads(encoded_songs)
    if not isinstance(songs, list) or not 1 <= len(songs) <= MAX_SONGS:
        raise ValueError("Unexpected catalogue shape or row count")
    if len(songs) != expected_count:
        raise ValueError("Catalogue is capped or incomplete relative to its aggregate")

    for song in songs:
        if (
            not isinstance(song, list)
            or len(song) != 8
            or not isinstance(song[0], str)
            or not isinstance(song[2], int)
            or song[2] <= 0
            or not isinstance(song[3], int)
            or not 0 < song[3] <= song[2]
            or not isinstance(song[4], (float, int))
            or not 0 <= song[4] <= 1
            or not isinstance(song[6], (float, int))
            or not 0 <= song[6] <= 1
        ):
            raise ValueError("Unexpected song metadata; inspect before publication")

    selected = []
    for title in SELECTED_TITLES:
        matches = [song for song in songs if song[0] == title]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one cached entry for {title!r}")
        song = matches[0]
        selected.append(
            {
                "title": title,
                "word_count": song[2],
                "unique_words": song[3],
                "type_token_ratio": song[4],
                "repetition_ratio": song[6],
            }
        )

    return {
        "schema_version": 1,
        "issue": "02",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "database": database.name,
            "table": "artistaggregate",
            "artist_key": ARTIST_KEY,
            "artist": artist,
            "dataset": source,
            "built_at": built_at,
            "songs_json_sha256": hashlib.sha256(encoded_songs.encode()).hexdigest(),
            "source_bytes": len(encoded_songs.encode()),
            "row_schema": [
                "title", "year", "word_count", "unique_words", "type_token_ratio",
                "chorus_ratio", "repetition_ratio", "has_sections",
            ],
        },
        "catalogue_entries": len(songs),
        "median_repetition_ratio": statistics.median(song[6] for song in songs),
        "selected_songs": selected,
        # Preserve the tiny source checkpoint so figures remain auditable even
        # after the local database receives a later update. Never stores lyrics.
        "source_rows": songs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/lyricstats.db"))
    parser.add_argument("--output", type=Path, required=True, help="A NEW JSON path")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new path to preserve the snapshot")
    started = time.monotonic()
    snapshot = extract(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(snapshot, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    print(
        f"Saved {snapshot['catalogue_entries']} cached entries to {args.output} "
        f"in {time.monotonic() - started:.3f}s; no database writes or network calls."
    )


if __name__ == "__main__":
    main()
