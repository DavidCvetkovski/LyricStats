import sqlite3
import re
import time
import os

start = time.time()
db_path = "data/lrclib/_song_stat.db"
conn = sqlite3.connect(db_path)

print("Fetching akeys...", flush=True)
artists = [r[0] for r in conn.execute("SELECT DISTINCT akey FROM song_stat").fetchall()]

canonical_map = {}
squashed_to_rep = {}
for c_key in artists:
    if not c_key:
        continue
    squashed = re.sub(r"[^a-z0-9]", "", c_key)
    if not squashed:
        canonical_map[c_key] = c_key
        continue
    if squashed in squashed_to_rep:
        canonical_map[c_key] = squashed_to_rep[squashed]
    else:
        squashed_to_rep[squashed] = c_key
        canonical_map[c_key] = c_key

print(f"Generated {len(canonical_map)} mappings.", flush=True)

import unicodedata


def normalize_key(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9&]", "", name)
    return name.strip()


conn.create_function(
    "canonical_key", 1, lambda x: normalize_key(canonical_map.get(x, x) if x else "")
)

print("Rebuilding table sequentially...", flush=True)
conn.execute("PRAGMA journal_mode=OFF")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("PRAGMA cache_size=1000000")

# check if we already have song_stat_new
try:
    conn.execute("DROP TABLE song_stat_new")
except:
    pass

conn.execute("""
CREATE TABLE song_stat_new AS 
SELECT *, canonical_key(akey) as gkey FROM song_stat
""")

print("Dropping old table...", flush=True)
conn.execute("DROP TABLE song_stat")

print("Renaming table...", flush=True)
conn.execute("ALTER TABLE song_stat_new RENAME TO song_stat")

print("Indexing...", flush=True)
conn.execute("CREATE INDEX idx_gkey ON song_stat(gkey)")
conn.execute("CREATE INDEX idx_artist ON song_stat(akey)")

print(f"Done in {time.time() - start:.1f}s!", flush=True)
conn.close()
