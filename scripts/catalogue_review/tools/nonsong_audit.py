"""Which uploads does is_non_song drop, per layer, for the top artists."""
import sys, sqlite3, re
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from collections import Counter, defaultdict
import clean_catalogues as cc
import import_dataset as d
from import_dataset import decode_tokens
top = [l.rstrip("\n").split("\t") for l in open("output/review/top.tsv")]
lo, hi = int(sys.argv[1]), int(sys.argv[2])
o = sqlite3.connect(f"file:{cc.OWNER_DB}?mode=ro", uri=True)
c = cc.song_conn(); c.row_factory = sqlite3.Row
def layer(r, cnt):
    t = (r["title"] or "").lower()
    if d._SONG_GUARD_RE.search(t): return None
    if 0 < r["wc"] < 60: return "short"
    if r["wc"] > d.MAX_SONG_WORDS: return "long"
    if any(p in t for p in d._NON_SONG_SUBSTR): return "substr"
    if d.EXCEPTION_REGEX.search(t) and not re.search(r'(Live/2011|Live 2011|New Years Day)', t, re.I): pass
    elif d.AGGRESSIVE_JUNK_REGEX.search(t): return "junkre"
    if r["ttr"] > 0.65 and d.is_english_toks(cnt): return "ttr"
    return None
tot = Counter(); ex = defaultdict(Counter); allrows = 0
for i, g, disp, up in top[lo-1:hi]:
    akeys = [a for gg in sorted(cc.alias_group(g)) for (a,) in o.execute("SELECT akey FROM akey_map WHERE gkey=?", (gg,))]
    rows = []
    for j in range(0, len(akeys), 500):
        p = akeys[j:j+500]
        rows += c.execute(f"SELECT title, wc, ttr, toks FROM song_stat WHERE akey IN ({','.join('?'*len(p))})", p).fetchall()
    allrows += len(rows)
    for r in rows:
        L = layer(r, Counter(decode_tokens(r["toks"])))
        if L:
            tot[L] += 1
            if L == "ttr": ex[disp][(r["title"], r["wc"], round(r["ttr"], 2))] += 1
print("rows", allrows, dict(tot))
for a, cn in ex.items():
    print(a, "|", " · ".join(f"{t}({w}w {tt})×{n}" for (t, w, tt), n in cn.most_common(8)))
