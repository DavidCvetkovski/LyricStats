"""Song keys whose uploads the title-junk layers remove entirely (top artists LO..HI)."""
import sys, sqlite3, re
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from collections import Counter, defaultdict
import clean_catalogues as cc
import import_dataset as d
from catalogue import title_key, _alnum_squash
top = [l.rstrip("\n").split("\t") for l in open("output/review/top.tsv")]
lo, hi = int(sys.argv[1]), int(sys.argv[2])
o = sqlite3.connect(f"file:{cc.OWNER_DB}?mode=ro", uri=True)
c = cc.song_conn()
def layer(t, wc):
    t = (t or "").lower()
    if d._SONG_GUARD_RE.search(t): return None
    if any(p in t for p in d._NON_SONG_SUBSTR): return "substr"
    if d.EXCEPTION_REGEX.search(t) and not re.search(r'(Live/2011|Live 2011|New Years Day)', t, re.I): return None
    if d.AGGRESSIVE_JUNK_REGEX.search(t): return "junkre"
    return None
out = Counter()
for i, g, disp, up in top[lo-1:hi]:
    aw = _alnum_squash(disp)
    akeys = [a for gg in sorted(cc.alias_group(g)) for (a,) in o.execute("SELECT akey FROM akey_map WHERE gkey=?", (gg,))]
    groups = defaultdict(list)
    for j in range(0, len(akeys), 500):
        p = akeys[j:j+500]
        for t, wc in c.execute(f"SELECT title, wc FROM song_stat WHERE akey IN ({','.join('?'*len(p))})", p):
            groups[title_key(t, aw)].append((t, layer(t, wc)))
    for k, rs in groups.items():
        if len(rs) >= 3 and all(L for _, L in rs):
            ts = Counter(t for t, _ in rs).most_common(2)
            print(f"{disp} | {k!r} ×{len(rs)} {Counter(L for _, L in rs).most_common(1)[0][0]} e.g. {ts}")
