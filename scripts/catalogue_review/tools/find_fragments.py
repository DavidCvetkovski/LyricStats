"""Pages that are a piece of a split credit ("Garfunkel" out of "Simon &
Garfunkel"). For every page whose name joins several names ("X & Y", "X, Y
& Z", "X + Y", "X / Y", "X and the Y"), each part that has a page of its own
is measured: the share of its songs (fingerprints) that the full credit or
the other parts also hold. Prints part, full credit, shares and sizes.

    .venv/bin/python scripts/catalogue_review/tools/find_fragments.py > output/fragments.tsv
"""
import re
import sqlite3
import sys

sys.path.insert(0, ".")
from lyricstats.db import normalize_key  # noqa: E402

app = sqlite3.connect("file:data/lyricstats.db?mode=ro", uri=True)
own = sqlite3.connect("file:data/lrclib/_fp_owner.db?mode=ro", uri=True)
pages = {}
for k, d, n in app.execute("SELECT name_key, display_name, song_count FROM artistaggregate"):
    if k not in pages or n > pages[k][1]:
        pages[k] = (d, n)
rows = dict(own.execute("SELECT gkey, rows FROM artist"))
SEP = re.compile(r"\s*(?:&|\+|/|,|;|\band the\b|\band\b|\bwith\b|\bx\b)\s*", re.I)


def fps(g):
    return {f for (f,) in own.execute("SELECT fp FROM owner WHERE gkey = ?", (g,))}


cache = {}


def fp(g):
    if g not in cache:
        cache[g] = fps(g)
    return cache[g]


seen = set()
out = []
for full_key, (full, n_full) in pages.items():
    parts = [p for p in SEP.split(full) if p and p.strip()]
    if len(parts) < 2:
        continue
    pkeys = [normalize_key(p) for p in parts]
    pkeys = [k for k in pkeys if k and k != full_key]
    for i, k in enumerate(pkeys):
        if k not in pages or pages[k][1] < 25 or (k, full_key) in seen:
            continue
        seen.add((k, full_key))
        mine = fp(k)
        if not mine:
            continue
        others = set(fp(full_key))
        for j, k2 in enumerate(pkeys):
            if j != i:
                others |= fp(k2)
        share = len(mine & others) / len(mine)
        if share >= 0.3:
            out.append((round(share, 2), k, pages[k][0], pages[k][1], rows.get(k, 0), full_key, full, n_full, rows.get(full_key, 0), i))
out.sort(key=lambda r: -r[4])
print("share\tpart_key\tpart\tpart_songs\tpart_rows\tfull_key\tfull\tfull_songs\tfull_rows\tposition")
for r in out:
    print("\t".join(map(str, r)))
