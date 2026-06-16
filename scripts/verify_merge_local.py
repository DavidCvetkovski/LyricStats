import sqlite3
import json
import os
import sys


def verify_merge():
    db_path = os.path.join("data", "lyricstats.db")
    if not os.path.exists(db_path):
        print("Database not found!")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Test 1: Total artists in aggregate table
    count = conn.execute("SELECT COUNT(*) FROM artistaggregate").fetchone()[0]
    print(f"Total artists in ArtistAggregate: {count:,}")
    if count < 100000:
        print("FAIL: Expected > 100k artists!")
        sys.exit(1)

    # Test 2: Taylor Swift verification
    row = conn.execute("SELECT * FROM artistaggregate WHERE name_key = 'taylorswift'").fetchone()
    if not row:
        print("FAIL: Taylor Swift not found!")
        sys.exit(1)

    print(f"\nTaylor Swift stats:")
    print(f"Song Count: {row['song_count']}")
    songs = json.loads(row["songs_json"])
    print(f"Songs in JSON array: {len(songs)}")

    if row["song_count"] < 400:
        print("FAIL: Taylor Swift song count is too low (expected > 400, she had 477 on Genius).")
        sys.exit(1)

    if len(songs) != row["song_count"]:
        print(
            f"FAIL: songs_json length ({len(songs)}) does not match song_count ({row['song_count']})!"
        )
        sys.exit(1)

    stats = json.loads(row["stats_json"])
    print(f"Total words: {stats.get('total_words')}")
    print(f"Avg wpm: {stats.get('avg_wpm')}")

    # Test 3: Voyage verification
    row2 = conn.execute("SELECT * FROM artistaggregate WHERE name_key = 'voyage'").fetchone()
    if row2:
        print(f"\nVoyage stats:")
        print(f"Song Count: {row2['song_count']}")
        if row2["song_count"] < 10:
            print("FAIL: Voyage song count too low.")
            sys.exit(1)

    print("\nALL VERIFICATION TESTS PASSED!")


if __name__ == "__main__":
    verify_merge()
