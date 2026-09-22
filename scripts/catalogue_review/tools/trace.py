"""python trace.py GKEY SUBSTRING — which catalogue song holds uploads whose title contains SUBSTRING."""
import sys, os
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
os.environ.pop("DATABASE_URL", None)
from collections import Counter
import clean_catalogues as cc
g, sub = sys.argv[1], sys.argv[2].lower()
rep = []
cc.fold_one(cc.song_conn(), g, cc.load_reviews().get(g), report=rep)
for s, rows in rep:
    titles = [rows[i]["title"] for i in s.rows]
    if any(sub in t.lower() for t in titles):
        print(repr(s.title), "uploads", s.uploads, "reason", s.reason, "owner", s.owner, "flags", s.flags,
              Counter(titles).most_common(6), "rep wc", rows[s.rep]["wc"])
