"""Namesake review queue: python namesakes.py OUT_DIR [BUDGET]

A page that holds another act with the same name often shows it as a cluster
of songs in a language the page otherwise does not sing in, from albums the
rest of the page never appears on (the Romanian rapper on Guess Who's page,
the Brazilian Anastácia on Anastacia's). This lists those clusters, one hint
sheet per BUDGET bytes, for a reviewer to confirm and drop; nothing is dropped
here, because most multilingual pages are the artist's own work (a Spanish
album, a Japanese version). Pages in output/review/*.tsv (hand-reviewed or
queued for it) are left out.

Reads the fold report's song languages (data/lrclib/_clean_agg.db).
"""
import glob
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "scripts")
from catalogue import _is_pseudo  # noqa: E402

# Languages the word lists confuse with each other: a cluster of one on a
# page of another is not evidence of anything.
CONFUSED = [{"es", "pt", "it", "fr", "ro", "sc"}, {"bs", "pl", "ru", "uk", "cy"}, {"de", "nl"}, {"sv", "nl"}]
MIN_CLUSTER = 2        # songs in the other language
MAX_SHARE = 0.6        # of the page's classified songs
MAX_UNCLASSIFIED = 0.4


def confused(a: str, b: str) -> bool:
    if {a, b} <= {"hi", "bs", "en"}:  # Hindi written in Latin letters reads as Bosnian or English
        return True
    return any(a in g and b in g for g in CONFUSED)


def album_key(a: str | None) -> str:
    return " ".join((a or "").lower().split())


def main() -> None:
    out_dir = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
    os.makedirs(out_dir, exist_ok=True)
    st = sqlite3.connect(os.environ.get("REPORT_DB", "data/lrclib/_clean_agg.db"))
    reviewed = {ln.split("\t")[1] for path in glob.glob("output/review/*.tsv")
                for ln in open(path, encoding="utf-8") if ln[:1].isdigit()}
    display = dict(st.execute("SELECT gkey, display FROM agg"))
    songs: dict[str, list[tuple]] = defaultdict(list)
    for g, title, uploads, lang, album in st.execute(
            "SELECT gkey, title, uploads, lang, album FROM report WHERE reason IS NULL"):
        songs[g].append((title, uploads, lang, album))
    blocks, skipped = [], Counter()
    for g, rows in songs.items():
        if g in reviewed or _is_pseudo(g) or _is_pseudo(display.get(g, "")):
            skipped["reviewed or not an artist"] += 1
            continue
        langs = Counter(lang for _t, _u, lang, _a in rows if lang)
        labeled = sum(langs.values())
        if not labeled or (len(rows) - labeled) / len(rows) > MAX_UNCLASSIFIED:
            skipped["too few songs classified"] += 1
            continue
        main_lang = langs.most_common(1)[0][0]
        clusters = []
        for lang, n in langs.items():
            if lang == main_lang or n < MIN_CLUSTER or n / labeled > MAX_SHARE or confused(lang, main_lang):
                continue
            mine = [r for r in rows if r[2] == lang]
            theirs = {album_key(r[3]) for r in rows if r[2] != lang} - {""}
            if {album_key(r[3]) for r in mine} & theirs:
                continue  # an album shared with the rest of the page: the artist's own
            clusters.append((lang, mine))
        if not clusters:
            continue
        head = f"#{g} {display.get(g, g)} [{g}] kept {len(rows)}; languages " + ", ".join(
            f"{lang} {n}" for lang, n in langs.most_common()) + f", unclassified {len(rows) - labeled}"
        lines = [head]
        for lang, mine in clusters:
            albums = Counter(album_key(r[3]) or "-" for r in mine).most_common(4)
            lines.append(f"   CLUSTER {lang} ({len(mine)} songs; albums " + "; ".join(
                f"{a} ×{n}" for a, n in albums) + "): " + " · ".join(
                f"{t} ×{u}" + (f" [{a}]" if a else "") for t, u, _l, a in sorted(mine, key=lambda r: -r[1])))
        rest = sorted((r for r in rows if r[2] == main_lang), key=lambda r: -r[1])[:12]
        lines.append(f"   REST ({main_lang}, top by uploads): " + " · ".join(
            f"{t}" + (f" [{a}]" if a else "") for t, _u, _l, a in rest))
        blocks.append((g, "\n".join(lines)))
    blocks.sort()
    n, used, part = 0, 0, []
    index = []
    for g, block in blocks:
        size = len(block.encode())
        if part and used + size > budget:
            n += 1
            open(os.path.join(out_dir, f"n{n:03d}.txt"), "w", encoding="utf-8").write("\n".join(b for _g, b in part))
            index.append((n, len(part)))
            part, used = [], 0
        part.append((g, block))
        used += size
    if part:
        n += 1
        open(os.path.join(out_dir, f"n{n:03d}.txt"), "w", encoding="utf-8").write("\n".join(b for _g, b in part))
        index.append((n, len(part)))
    print(f"{len(blocks):,} pages flagged in {n} sheets → {out_dir}; skipped {dict(skipped)}")


if __name__ == "__main__":
    main()
