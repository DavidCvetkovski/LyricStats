"""Titles the fastText classifier flags (after the other layers pass) for top artists LO..HI."""
import sys, sqlite3
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from collections import Counter, defaultdict
import clean_catalogues as cc
from title_filter import load_classifier, _SONG_GUARD_RE
clf = load_classifier()
top = [l.rstrip("\n").split("\t") for l in open("output/review/top.tsv")]
lo, hi = int(sys.argv[1]), int(sys.argv[2])
o = sqlite3.connect(f"file:{cc.OWNER_DB}?mode=ro", uri=True)
c = cc.song_conn()
flag = defaultdict(Counter); n = 0; nf = 0
for i, g, disp, up in top[lo-1:hi]:
    akeys = [a for gg in sorted(cc.alias_group(g)) for (a,) in o.execute("SELECT akey FROM akey_map WHERE gkey=?", (gg,))]
    for j in range(0, len(akeys), 500):
        p = akeys[j:j+500]
        for (t,) in c.execute(f"SELECT title FROM song_stat WHERE akey IN ({','.join('?'*len(p))})", p):
            n += 1
            if not _SONG_GUARD_RE.search((t or "").lower()) and clf.is_junk(t):
                nf += 1; flag[disp][t] += 1
print("rows", n, "flagged", nf)
for a, cn in flag.items():
    print(a, "|", " · ".join(f"{t}×{k}" for t, k in cn.most_common(10)))
