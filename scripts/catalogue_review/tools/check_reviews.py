"""Check review files against the staged report: python check_reviews.py [gkey ...]
Prints drop/keep titles matching no song, or matching several songs by key."""
import sqlite3, sys, json, glob, os
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from catalogue import title_key, _alnum_squash
VERBOSE = bool(os.environ.get("V"))
import os; st = sqlite3.connect(os.environ.get("REPORT_DB", "data/lrclib/_clean_agg.db"))
files = sys.argv[1:] or [os.path.basename(f)[:-5] for f in sorted(glob.glob("scripts/catalogue_review/*.json"))]
for g in files:
    rv = json.load(open(f"scripts/catalogue_review/{g}.json"))
    d = st.execute("SELECT display FROM agg WHERE gkey=?", (g,)).fetchone()
    aw = _alnum_squash(d[0] if d else rv["artist"])
    rows = st.execute("SELECT title, uploads, reason FROM report WHERE gkey=?", (g,)).fetchall()
    by = {}
    for t, u, r in rows:
        by.setdefault(title_key(t, aw), []).append((t, u, r))
    for kind in ("drop", "keep", "only", "rename"):
        entries = rv.get(kind) or []
        if kind == "rename":  # after the fold the song carries its new title
            entries = list((rv.get(kind) or {}).values())
        for t in entries:
            m = by.get(title_key(t, aw), [])
            if len(m) != 1 or VERBOSE:
                print(f"{g} {kind} {t!r}: {len(m)} match {[(x[0], x[1]) for x in m][:4]}")
