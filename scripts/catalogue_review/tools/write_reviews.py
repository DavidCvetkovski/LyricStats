"""stdin: JSON {gkey: {"drop": {title: why} | [titles], "keep": [...], "why": default}} → review files."""
import json, sys, os  # noqa: E401
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
names = {l.split("\t")[1]: l.split("\t")[2] for l in open(f"{ROOT}/output/review/top.tsv")}
data = json.load(sys.stdin)
os.makedirs(f"{ROOT}/scripts/catalogue_review", exist_ok=True)
for g, r in data.items():
    drop = r.get("drop", {})
    if isinstance(drop, list):
        drop = {t: r.get("why", "not theirs") for t in drop}
    out = {"artist": names.get(g, g), "reviewed": "2026-09-22", "drop": drop, "keep": r.get("keep", [])}
    if r.get("only"):
        out["only"] = r["only"]
    if r.get("note"):
        out["note"] = r["note"]
    with open(f"{ROOT}/scripts/catalogue_review/{g}.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(g, len(drop), "drop,", len(out["keep"]), "keep")
