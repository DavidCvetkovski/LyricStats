# Review tools

Run from the repository root with the project venv.

- `compact.py START END [BYTES]` prints the staged report for top artists START..END
  (from `output/review/top.tsv`) as compact sheets, ending with `NEXT=<i>`.
  `REPORT_DB` points it at another report database.
- `write_reviews.py` reads `{gkey: {"drop": {title: why}, "keep": [...], "note": ...}}`
  on stdin and writes `scripts/catalogue_review/<gkey>.json`.
- `check_reviews.py [gkey ...]` lists review titles that match no song, or several,
  by title key (`V=1` prints every match).
- `trace.py GKEY TEXT` folds one artist and shows which catalogue song holds the
  uploads whose title contains TEXT.
- `nonsong_audit.py`, `clf_audit.py`, `junk_audit.py` measure what the old
  Genius-era filters removed from the top artists.
