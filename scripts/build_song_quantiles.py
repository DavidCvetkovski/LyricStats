"""Build lyricstats/data/song_quantiles.json from the LRCLIB per-song table.

The per-song table (data/lrclib/_song_stat.db, phase 1 of import_lrclib.py)
holds one row per track in the dump, ~28 million of them. Reading every
row's numbers takes about a minute; a rowid sample every N rows is as good
for percentiles and takes a third of that. For each metric the output keeps
the value at every whole percentile, which is all the API needs to place a
song among the archive.

Usage:
    uv run python scripts/build_song_quantiles.py                 # 1-in-20 sample
    uv run python scripts/build_song_quantiles.py --every 200     # quick check
    uv run python scripts/build_song_quantiles.py --db path/to/_song_stat.db
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats.percentiles import QUANTILES_PATH  # noqa: E402

DEFAULT_DB = os.path.join("data", "lrclib", "_song_stat.db")
APP_DB = os.path.join("data", "lyricstats.db")

# Column → metric name used by lyricstats.reading. Timing metrics only count
# rows with synced lyrics; words per minute only rows with a real duration.
METRICS = {
    "wc": "wc",
    "uniq": "uniq",
    "ttr": "ttr",
    "rep": "rep",
    "hook": "hook",
    "rhyme": "rhyme",
    "drops": "drops",
    "awl": "awl",
    "q": "q",
    "one_word": "one_word",
    "wpm": "wpm",
    "first_s": "first",
    "gap_s": "gap",
    "fast15": "fast15",
}
TIMED = {"first_s", "gap_s", "fast15"}
MIN_WORDS, MAX_WORDS = 30, 2000


def quantiles(values: list[float]) -> list[float]:
    values.sort()
    n = len(values)
    return [values[min(n - 1, round(p / 100 * (n - 1)))] for p in range(101)]


def archive_size(app_db: str) -> int:
    """Distinct songs across the deduplicated artist catalogues."""
    if not os.path.exists(app_db):
        return 0
    conn = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    try:
        return int(conn.execute("SELECT SUM(song_count) FROM artistaggregate").fetchone()[0] or 0)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--every", type=int, default=20, help="sample 1 row in N")
    ap.add_argument("--out", default=str(QUANTILES_PATH))
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"per-song table not found: {args.db}")

    cols = ", ".join(METRICS)
    sql = (
        f"SELECT has_synced, duration, {cols} FROM song_stat "
        f"WHERE rowid % ? = 0 AND wc BETWEEN ? AND ?"
    )
    samples: dict[str, list[float]] = {m: [] for m in METRICS}
    t0 = time.time()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = 0
    for row in conn.execute(sql, (args.every, MIN_WORDS, MAX_WORDS)):
        rows += 1
        has_synced, duration, *vals = row
        for (col, _metric), v in zip(METRICS.items(), vals):
            if v is None:
                continue
            if col in TIMED and not has_synced:
                continue
            if col == "wpm" and (not duration or duration < 30 or v > 400):
                continue
            samples[col].append(float(v))
    conn.close()

    out = {
        "built_at": time.strftime("%Y-%m-%d"),
        "sampled_rows": rows,
        "sample_every": args.every,
        "archive_songs": archive_size(APP_DB),
        "metrics": {METRICS[col]: quantiles(v) for col, v in samples.items() if len(v) >= 1000},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(
        f"{rows:,} rows sampled in {time.time() - t0:.0f}s → {args.out} "
        f"({os.path.getsize(args.out) / 1024:.0f} KB, {len(out['metrics'])} metrics, "
        f"archive {out['archive_songs']:,} songs)"
    )
    for m, cuts in out["metrics"].items():
        print(f"  {m:9s} p10 {cuts[10]:>8}  p50 {cuts[50]:>8}  p90 {cuts[90]:>8}")


if __name__ == "__main__":
    main()
