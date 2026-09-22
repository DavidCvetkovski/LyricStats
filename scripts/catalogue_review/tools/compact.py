"""Compact review text for top artists: python compact.py START END"""
import sqlite3, sys, json
import os; st = sqlite3.connect(os.environ.get("REPORT_DB", "data/lrclib/_clean_agg.db"))
top = [l.rstrip("\n").split("\t") for l in open("output/review/top.tsv")]
lo, hi = int(sys.argv[1]), int(sys.argv[2])
budget = int(sys.argv[3]) if len(sys.argv) > 3 else 27000
used = 0
out_lines = []
nxt = None
for i, g, d, up in top[lo - 1:hi]:
    rep = st.execute("SELECT title, uploads, wc, reason, owner, owner_n, flags FROM report WHERE gkey = ? "
                     "ORDER BY uploads DESC, title", (g,)).fetchall()
    kept = [r for r in rep if r[3] is None]
    gone = [r for r in rep if r[3] is not None]
    out = []
    for t, u, wc, _r, o, on, fl in kept:
        s = t
        if u <= 5: s += f" ×{u}"
        if wc < 100 or wc > 900: s += f" {wc}w"
        if fl: s += f" ⚑{o}×{on}"
        out.append(s)
    block = f"#{i} {d} [{g}] kept {len(kept)}: " + " · ".join(out)
    if gone:
        block += "\n   ASIDE " + str(len(gone)) + ": " + " · ".join(f"{t} ×{u} ({r.replace('belongs to another artist','→')}{' ' + o + '×' + str(on) if o and 'belongs' in r else ''})" for t, u, wc, r, o, on, fl in gone)
    size = len(block.encode())
    if out_lines and used + size > budget:
        nxt = i
        break
    out_lines.append(block)
    used += size
print("\n".join(out_lines))
print(f"NEXT={nxt}" if nxt else "NEXT=done")
