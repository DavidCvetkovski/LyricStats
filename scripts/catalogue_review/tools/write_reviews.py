"""stdin: JSON {gkey: {"drop": {title: why} | [titles], "keep": [...], "rename": {title: new}, "why": default}} → review files.

An existing review is added to, never replaced: new drops and keeps join the
old ones, and its note and only-list stay. Take an entry out by editing the file."""
import json, sys, os  # noqa: E401
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
names = {ln.split("\t")[1]: ln.split("\t")[2] for ln in open(f"{ROOT}/output/review/top.tsv")}
data = json.load(sys.stdin)
os.makedirs(f"{ROOT}/scripts/catalogue_review", exist_ok=True)
for g, r in data.items():
    drop = r.get("drop", {})
    if isinstance(drop, list):
        drop = {t: r.get("why", "not theirs") for t in drop}
    path = f"{ROOT}/scripts/catalogue_review/{g}.json"
    out = {"artist": names.get(g, g), "reviewed": "2026-09-22", "drop": {}, "keep": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out = json.load(fh)
    out["drop"] = {**out.get("drop", {}), **drop}
    out["keep"] = list(dict.fromkeys(out.get("keep", []) + r.get("keep", [])))
    if r.get("rename"):
        out["rename"] = {**out.get("rename", {}), **r["rename"]}
    if r.get("only"):
        out["only"] = r["only"]
    if r.get("note"):
        out["note"] = r["note"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(g, len(out["drop"]), "drop,", len(out["keep"]), "keep")
