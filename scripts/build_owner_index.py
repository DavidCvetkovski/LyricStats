#!/usr/bin/env python3
"""Which artist each song's words are filed under, and how often.

LRCLIB lists every upload of a recording under whatever artist name the
uploader typed, so a song turns up under its own artist hundreds of times and,
now and then, under somebody else: a compilation's headliner, a member's solo
name, a remixer, a typo. Counting uploads per (lyrics, artist) tells a song's
home from a stray copy, which is what the catalogue cleaning needs.

One parallel pass over data/lrclib/_song_stat.db. Each row's identity is the
importer's content fingerprint (its twelve most-used content words, sorted),
hashed to 64 bits; its artist is the importer's group key (lyricstats.db
normalize_key of the uploaded name). The table's own gkey column is not used:
an old rebuild keyed some artists with a stray "&" (Eminem) and every
non-Latin name to "". The result, data/lrclib/_fp_owner.db:

  owner(fp INTEGER, gkey TEXT, n INTEGER, title TEXT)   one row per (lyrics, artist)
  artist(gkey TEXT PRIMARY KEY, rows INTEGER, songs INTEGER)   uploads and distinct lyrics
  akey_map(akey TEXT, gkey TEXT)   the uploaded names behind each group key

  uv run python scripts/build_owner_index.py            # ~20 min on 8 workers
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import time
from collections import Counter
from functools import lru_cache
from multiprocessing import Pool

# numpy (pulled in by the title classifier's module) would start a BLAS
# thread pool in every worker; one thread each is plenty.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

SONG_DB = os.path.join(ROOT, "data", "lrclib", "_song_stat.db")
OUT_DB = os.path.join(ROOT, "data", "lrclib", "_fp_owner.db")
PART_DIR = os.path.join(ROOT, "data", "lrclib", "_fp_parts")


def fp_hash(fp: tuple | None) -> int | None:
    if not fp:
        return None
    h = hashlib.blake2b("|".join(fp).encode(), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=True)


@lru_cache(maxsize=None)
def group_key(akey: str) -> str:
    """The importer's grouping: normalize_key of the uploaded name, or the raw
    name when nothing alphanumeric is left."""
    from lyricstats.db import normalize_key

    return normalize_key(akey or "") or f"raw:{akey}"


def _chunk(args: tuple[int, int, int]) -> tuple[int, int]:
    from import_dataset import decode_tokens
    from import_lrclib import content_fingerprint

    k, lo, hi = args
    part = os.path.join(PART_DIR, f"part{k:03d}.db")
    done_mark = part + ".done"
    if os.path.exists(done_mark):  # resumed: this chunk finished last time
        return 0, 0
    src = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    src.execute("PRAGMA mmap_size=68000000000")
    agg: dict[tuple[int, str], list] = {}
    seen = 0
    for akey, title, toks in src.execute(
        "SELECT akey, title, toks FROM song_stat WHERE rowid >= ? AND rowid < ?", (lo, hi)
    ):
        seen += 1
        if not akey or not toks:
            continue
        gkey = group_key(akey)
        h = fp_hash(content_fingerprint(Counter(decode_tokens(toks))))
        if h is None:
            continue
        cur = agg.get((h, gkey))
        if cur is None:
            agg[(h, gkey)] = [1, title]
        else:
            cur[0] += 1
    src.close()
    if os.path.exists(part):
        os.remove(part)
    out = sqlite3.connect(part)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("CREATE TABLE owner (fp INTEGER, gkey TEXT, n INTEGER, title TEXT)")
    out.executemany("INSERT INTO owner VALUES (?,?,?,?)",
                    ((h, g, v[0], v[1]) for (h, g), v in agg.items()))
    out.commit()
    out.close()
    open(done_mark, "w").close()
    return seen, len(agg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunks", type=int, default=64)
    args = ap.parse_args()

    src = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    top = src.execute("SELECT max(rowid) FROM song_stat").fetchone()[0]
    src.close()
    os.makedirs(PART_DIR, exist_ok=True)
    step = top // args.chunks + 1
    jobs = [(k, 1 + k * step, 1 + (k + 1) * step) for k in range(args.chunks)]
    t0 = time.time()
    done = rows = pairs = 0
    with Pool(args.workers) as pool:
        for seen, n in pool.imap_unordered(_chunk, jobs):
            done += 1
            rows += seen
            pairs += n
            print(f"  {done}/{len(jobs)} chunks, {rows:,} rows, {pairs:,} pairs, "
                  f"{(time.time() - t0) / 60:.1f} min", flush=True)

    print("merging…", flush=True)
    if os.path.exists(OUT_DB):
        os.remove(OUT_DB)
    out = sqlite3.connect(OUT_DB)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("PRAGMA synchronous=OFF")
    out.execute("CREATE TABLE raw (fp INTEGER, gkey TEXT, n INTEGER, title TEXT)")
    for k in range(len(jobs)):
        part = os.path.join(PART_DIR, f"part{k:03d}.db")
        out.execute("ATTACH ? AS p", (part,))
        out.execute("INSERT INTO raw SELECT * FROM p.owner")
        out.commit()
        out.execute("DETACH p")
        os.remove(part)
        os.remove(part + ".done")
    out.execute("CREATE TABLE owner AS SELECT fp, gkey, sum(n) AS n, min(title) AS title "
                "FROM raw GROUP BY fp, gkey")
    out.execute("DROP TABLE raw")
    out.execute("CREATE INDEX idx_owner_fp ON owner(fp)")
    out.execute("CREATE INDEX idx_owner_gkey ON owner(gkey)")
    out.execute("CREATE TABLE artist AS SELECT gkey, sum(n) AS rows, count(*) AS songs "
                "FROM owner GROUP BY gkey")
    out.execute("CREATE UNIQUE INDEX idx_artist_gkey ON artist(gkey)")
    out.execute("CREATE TABLE akey_map (akey TEXT, gkey TEXT)")
    src = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    out.executemany("INSERT INTO akey_map VALUES (?, ?)",
                    ((a, group_key(a)) for (a,) in src.execute("SELECT DISTINCT akey FROM song_stat") if a))
    src.close()
    out.execute("CREATE INDEX idx_akey_map_gkey ON akey_map(gkey)")
    out.commit()
    out.execute("VACUUM")
    out.close()
    os.rmdir(PART_DIR)
    print(f"done in {(time.time() - t0) / 60:.1f} min → {OUT_DB}", flush=True)


if __name__ == "__main__":
    main()
