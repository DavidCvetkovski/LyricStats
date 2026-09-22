"""Split-credit pieces: for each part of a multi-name credit that has a page,
the key sharing most of its songs. Twins ("Simon"/"Garfunkel") share most
songs at a similar size; a band suffix ("The Heartbreakers") sits inside its
leader's catalogue. Reads output/fragments.tsv (find_fragments.py)."""
import csv
import sqlite3
from collections import Counter

own = sqlite3.connect("file:data/lrclib/_fp_owner.db?mode=ro", uri=True)
rows = dict(own.execute("SELECT gkey, rows FROM artist"))
parts = {}
for r in csv.DictReader(open("output/fragments.tsv"), delimiter="\t"):
    parts.setdefault(r["part_key"], (r["part"], int(r["part_songs"]), set()))[2].add(r["full"])
out = []
for k, (name, songs, fulls) in parts.items():
    fps = [f for (f,) in own.execute("SELECT fp FROM owner WHERE gkey = ?", (k,))]
    if not fps:
        continue
    co = Counter()
    for f in fps:
        for (g,) in own.execute("SELECT gkey FROM owner WHERE fp = ? AND gkey != ? ORDER BY n DESC LIMIT 8", (f, k)):
            co[g] += 1
    if not co:
        continue
    g, c = co.most_common(1)[0]
    share = c / len(fps)
    if share >= 0.5:
        out.append((rows.get(k, 0), k, name, songs, round(share, 2), g, rows.get(g, 0), round(rows.get(k, 0) / max(1, rows.get(g, 0)), 2), " | ".join(sorted(fulls))[:90]))
out.sort(key=lambda r: -r[0])
print("part_rows\tpart_key\tpart\tpart_songs\tshare\tco_key\tco_rows\tratio\tfull_credits")
for r in out:
    print("\t".join(map(str, r)))
