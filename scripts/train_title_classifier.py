"""Train a fastText classifier that flags Genius *non-song* pages by title.

Why this exists
---------------
The dataset mixes real songs with Genius pages that aren't songs — interviews,
tour-costume lists, playlists, chart-history, award-show performances, book
forewords, instagram posts, etc. They have normal song-like stats (a transcript
repeats words just like a chorus does), so the *title* is the only reliable
signal. A hand-maintained substring blocklist is whack-a-mole; this distills a
curated weak-labeler into a tiny fastText model whose subword n-grams generalise
past exact keywords (Costume↔Costumes↔Wardrobe, Foreword↔Forward↔Prologue) and
classify a title in microseconds.

This is **build-time only**: trained on your laptop, loaded by the fold in
import_dataset.py. It never ships to Vercel (the app only reads aggregates).

Pipeline
--------
  1. dump   → cache DISTINCT titles from the temp song_stat DB to a text file
  2. audit  → print random samples of each weak-labelled class to eyeball FPs
  3. train  → weak-label, train fastText, evaluate on a hand-labelled gold set

Usage:
    uv run python scripts/train_title_classifier.py dump
    uv run python scripts/train_title_classifier.py audit
    uv run python scripts/train_title_classifier.py train
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # for title_filter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from title_filter import _SONG_GUARD_RE, normalize  # noqa: E402

TMP_DB = "./data/_import_tmp.db"
TITLES_CACHE = "./data/_titles.txt"
MODEL_PATH = "./data/title_clf.bin"

# ── weak labeler ─────────────────────────────────────────────────────────────
#
# JUNK patterns are precise multi-word phrases wherever a word could also be a
# real song title. We deliberately do NOT list real song types here — freestyle,
# interlude, intro, outro, skit, remix, demo, live, acoustic, version, edit,
# reprise, instrumental, bonus are all legitimate and must stay SONG.

#
# Conservative by design: every pattern below was audited against real samples
# from the dataset, and anything that grazed real songs was tightened or cut —
# e.g. bare "phone call" (real: "Another Phone Call"), "instagram" (DJ Snake's
# "Instagram"), "open letter" (Jay-Z), "amas" (Spanish "you love"), "grammy"
# ("Grammy Family"). We bias to PRECISION and let fastText's subword n-grams +
# the existing import blocklist recover recall.
_JUNK_PATTERNS = [
    # interviews / behind-the-scenes / meta
    r"\binterview\b", r"\bthe making of\b", r"\bmaking of\b", r"\bbehind the scenes\b",
    r"\bin conversation\b", r"\bannotat", r"\bdirectors? commentary\b",
    r"\breacts? to\b", r"\bresponds? to\b", r"\bconference call\b",
    # award shows (conservative — avoid Spanish "amas", "Grammy Family", "Oscar")
    r"\bvmas?\b", r"\bbet awards?\b", r"\bamerican music awards\b", r"\boscars\b",
    r"\bsuper ?bowl\b", r"\bhalftime\b", r"\bbillboard music awards?\b",
    r"\bmtv (video|movie) awards?\b", r"\bacademy of country\b", r"\biheartradio\b",
    r"\bartist of the (decade|year|month)\b", r"\bgrammy awards?\b",
    r"\blatin grammys?\b", r"\bacceptance speech\b", r"\bvictory speech\b",
    r"\baward acceptance\b",
    # tour merch / setlists (require 'tour' context so real 'guests'/'costumes'
    # songs survive)
    r"\btour (costumes?|book|guide|dates?|rehearsals?|diary|programme?|setlist|special guests?|intro)\b",
    r"\bsetlist\b",
    # book / liner prose
    r"\bforeword\b", r"\bprologue\b", r"\bepilogue\b", r"\bpreface\b",
    r"\bliner notes\b", r"\bbooklet\b",
    # lists / catalogue meta
    r"\bplaylist\b", r"\bchart history\b", r"\bdiscography\b", r"\btracklist",
    r"\bgreatest hits\b",
    # social posts (require an action noun; bare 'instagram' is a real song)
    r"\binstagram (post|story|stories|live|caption|rant|feed)\b",
    r"\bfacebook post\b", r"\btwitter (rant|thread)\b", r"\btweetstorm\b",
    r"\ba message from\b", r"\bmessage from\b",
    # speeches / scripts / transcripts
    r"\bcommencement\b", r"\bted talk\b", r"\bkeynote\b", r"\bscreenplay\b",
    r"\bfilm script\b", r"\bmovie script\b", r"\btranscript\b",
    # art / film / press
    r"\bdocumentary\b", r"\balbum art\b", r"\bcover art\b",
    r"\bpress (release|conference)\b", r"\bofficial statement\b",
    # translations / romanizations (not the artist's own writing)
    r"\btraducci[óo]n\b", r"\btradu[çc][ãa]o\b", r"\bt[üu]rk[çc]e\b",
    r"\b[çc]eviri\b", r"\bs[öo]zleri\b", r"\bromaniz", r"\b[üu]bersetzung\b",
    r"\bperevod\b",
]
_JUNK_RE = re.compile("|".join(_JUNK_PATTERNS), re.IGNORECASE)

def weak_label(title: str) -> int | None:
    """1=song, 0=non-song, None=skip (don't train on it). Title-only signal.

    ``_SONG_GUARD_RE`` and ``normalize`` are shared with inference via
    title_filter so training data and the fold can't drift apart.
    """
    t = (title or "").strip()
    if len(t) < 2:
        return None
    if _JUNK_RE.search(t) and not _SONG_GUARD_RE.search(t):
        return 0
    if _JUNK_RE.search(t):
        return None  # both junk + guard present → ambiguous, don't train on it
    return 1


# ── hand-labelled gold set (the honest eval — independent of the weak labeler) ─

GOLD: list[tuple[str, int]] = [
    # real songs (incl. tricky high-TTR / short / meta-sounding ones)
    ("Shake It Off", 1), ("98 Freestyle", 1), ("Black Hoodies Interlude", 1),
    ("A Milli", 1), ("Cruel Summer", 1), ("Bombaclat", 1), ("Mr. Carter", 1),
    ("champagne problems", 1), ("Just Pretend", 1), ("Encore / Curtains Down", 1),
    ("C.R.E.A.M.", 1), ("Intro", 1), ("Outro", 1), ("The Skit", 1),
    ("Love Letter", 1), ("Performance", 1), ("Statement", 1), ("Speech", 1),
    ("Freestyle", 1), ("Reprise", 1), ("Last Christmas", 1), ("Style", 1),
    ("Tim McGraw", 1), ("All Too Well", 1), ("Lover", 1), ("seven", 1),
    ("no body no crime", 1), ("exile", 1), ("Welcome to New York", 1),
    # non-songs
    ("Reputation Tour Costumes", 0), ("Speak Now Tour Costumes", 0),
    ("Playlist by ME", 0), ("Songs Taylor Loves Playlist", 0),
    ("Taylor Swifts Chart History", 0), ("A Message From Taylor", 0),
    ("The Making Of A Song - King of My Heart", 0),
    ("Taylor Swifts First Phone Call With Tim McGraw", 0),
    ("AMAs Artist of the Decade Performance", 0),
    ("Political Instagram Post", 0), ("Folklore Foreword", 0),
    ("Lover Foreword", 0), ("Reputation Tour Book Intro", 0),
    ("Reputation Tour Special Guests", 0), ("1989 World Tour Costumes", 0),
    ("ESPYs Conference Call", 0), ("Drake Discography", 0),
    ("Lemonade Film Script", 0), ("Beyoncé VMAs 2014", 0),
    ("Grammy Acceptance Speech", 0), ("Red Taylors Version Traducción asturiana", 0),
    ("The Archer Türkçe Sözleri", 0), ("Taylor Swift Responds To Kanyes Famous Lyric", 0),
    ("DJ Semtex Interview", 0), ("Reputation Prologue", 0),
]


def load_titles() -> list[str]:
    if not os.path.exists(TITLES_CACHE):
        sys.exit(f"No {TITLES_CACHE} — run `dump` first.")
    with open(TITLES_CACHE, encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f]


def cmd_dump() -> None:
    print(f"Pulling DISTINCT titles from {TMP_DB} …", flush=True)
    c = sqlite3.connect(TMP_DB)
    n = 0
    with open(TITLES_CACHE, "w", encoding="utf-8") as f:
        for (title,) in c.execute("SELECT DISTINCT title FROM song_stat"):
            if title:
                f.write(title.replace("\n", " ") + "\n")
                n += 1
    c.close()
    print(f"  wrote {n:,} distinct titles → {TITLES_CACHE}")


def cmd_audit() -> None:
    titles = load_titles()
    junk, song = [], []
    for t in titles:
        lbl = weak_label(t)
        if lbl == 0:
            junk.append(t)
        elif lbl == 1:
            song.append(t)
    print(f"weak labels: {len(junk):,} non-song, {len(song):,} song "
          f"({len(junk)/max(1,len(titles))*100:.2f}% junk)\n")
    rnd = random.Random(42)
    print("=== 30 random NON-SONG (check for false positives) ===")
    for t in rnd.sample(junk, min(30, len(junk))):
        print("  ✗", t[:70])
    print("\n=== 30 random SONG (check for missed junk) ===")
    for t in rnd.sample(song, min(30, len(song))):
        print("  ✓", t[:70])


def cmd_train() -> None:
    import fasttext  # noqa: PLC0415

    titles = load_titles()
    rows: list[tuple[str, int]] = []
    for t in titles:
        lbl = weak_label(t)
        if lbl is None:
            continue
        norm = normalize(t)
        if norm:
            rows.append((norm, lbl))

    junk = [r for r in rows if r[1] == 0]
    song = [r for r in rows if r[1] == 1]
    print(f"labelled: {len(junk):,} junk / {len(song):,} song")

    # Keep all junk; sample a much larger song set (~10x) for broad coverage of
    # the "song" space. The deliberate imbalance makes the model conservative —
    # it predicts "song" unless a title clearly reads as junk, so the costly
    # error (dropping a real song) stays rare.
    rnd = random.Random(7)
    rnd.shuffle(song)
    song = song[: max(len(junk) * 10, 60000)]
    data = junk + song
    rnd.shuffle(data)

    train_path = "./data/_title_train.txt"
    with open(train_path, "w", encoding="utf-8") as f:
        for norm, lbl in data:
            label = "song" if lbl == 1 else "junk"
            f.write(f"__label__{label} {norm}\n")

    print(f"training fastText on {len(data):,} rows …", flush=True)
    model = fasttext.train_supervised(
        input=train_path, lr=0.5, epoch=25, wordNgrams=2,
        dim=50, minn=2, maxn=5, loss="softmax", verbose=0,
    )
    model.save_model(MODEL_PATH)
    print(f"  saved → {MODEL_PATH}")

    # Honest eval on the hand-labelled gold set.
    print("\n=== GOLD eval ===")
    tp = tn = fp = fn = 0
    wrong: list[str] = []
    for title, truth in GOLD:
        lbl, prob = model.predict(normalize(title))
        pred_junk = lbl[0] == "__label__junk"
        conf = prob[0]
        is_junk_truth = truth == 0
        if pred_junk and is_junk_truth:
            tn += 1
        elif not pred_junk and not is_junk_truth:
            tp += 1
        elif pred_junk and not is_junk_truth:
            fp += 1
            wrong.append(f"  FALSE-DROP (song→junk): {title!r}  p={conf:.2f}")
        else:
            fn += 1
            wrong.append(f"  MISSED (junk→song): {title!r}  p={conf:.2f}")
    total = len(GOLD)
    print(f"  songs kept (tp): {tp}   junk caught (tn): {tn}")
    print(f"  false-drops (fp): {fp}  missed junk (fn): {fn}")
    print(f"  accuracy: {(tp+tn)/total*100:.1f}%")
    for w in wrong:
        print(w)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dump", "audit", "train"])
    args = ap.parse_args()
    {"dump": cmd_dump, "audit": cmd_audit, "train": cmd_train}[args.cmd]()


if __name__ == "__main__":
    main()
