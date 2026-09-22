#!/usr/bin/env python3
"""Clean every artist's catalogue: one version per song, only their songs.

The rules live in scripts/catalogue.py; this script runs them over the big
per-song table and carries the result to the app database and production.

  uv run python scripts/clean_catalogues.py --sample "Michael Jackson" --sample Avicii
      Re-fold a few artists and print what changed and why, writing nothing.

  uv run python scripts/clean_catalogues.py --top 500 --sheets output/review
      The 500 most-uploaded artists (the famous ones), one review sheet each:
      every song kept with its uploads, and every song set aside with why.

  uv run python scripts/clean_catalogues.py --fold
      Every artist with a page (≥ 25 songs), in parallel, into
      data/lrclib/_clean_agg.db (staging), then the corpus pass (percentiles
      among those artists, signature and exclusive words).

  uv run python scripts/clean_catalogues.py --commit
      Replace the staged artists' aggregates in the app database (a copy of
      the old table is kept as data/lyricstats.pre-clean.db).

Hand reviews are scripts/catalogue_review/<name key>.json:
  {"artist": "Michael Jackson",
   "drop": {"ABC": "The Jackson 5", ...},     # title → why
   "keep": ["Come Together"],                 # restore what a rule set aside
   "only": [...]}                             # a list curated in full
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from functools import lru_cache

# numpy (pulled in by the title classifier) would start a BLAS thread pool in
# every worker; one thread each is plenty.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("DATABASE_URL", None)

SONG_DB = os.path.join(ROOT, "data", "lrclib", "_song_stat.db")
OWNER_DB = os.path.join(ROOT, "data", "lrclib", "_fp_owner.db")
STAGE_DB = os.path.join(ROOT, "data", "lrclib", "_clean_agg.db")
PART_DIR = os.path.join(ROOT, "data", "lrclib", "_clean_parts")
APP_DB = os.path.join(ROOT, "data", "lyricstats.db")
REVIEW_DIR = os.path.join(ROOT, "scripts", "catalogue_review")
MIN_SONGS = 5

_owner_conn: sqlite3.Connection | None = None
def song_conn() -> sqlite3.Connection:
    """The per-song table, memory-mapped: the kernel's read-ahead makes the
    scattered reads of one artist's uploads several times faster."""
    c = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    c.execute("PRAGMA mmap_size=68000000000")
    return c


def load_reviews() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if os.path.isdir(REVIEW_DIR):
        for f in sorted(os.listdir(REVIEW_DIR)):
            if f.endswith(".json"):
                with open(os.path.join(REVIEW_DIR, f), encoding="utf-8") as fh:
                    out[f[:-5]] = json.load(fh)
    return out


def owners(fp: tuple) -> list[tuple[str, int, str]]:
    return _owners_cached(fp)


@lru_cache(maxsize=200_000)
def _owners_cached(fp: tuple) -> list[tuple[str, int, str]]:
    from build_owner_index import fp_hash

    global _owner_conn
    if _owner_conn is None:
        _owner_conn = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    return _owner_conn.execute(
        "SELECT gkey, n, title FROM owner WHERE fp = ? ORDER BY n DESC LIMIT 12", (fp_hash(fp),)
    ).fetchall()


@lru_cache(maxsize=500_000)
def artist_uploads(gkey: str) -> int:
    global _owner_conn
    if _owner_conn is None:
        _owner_conn = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    r = _owner_conn.execute("SELECT rows FROM artist WHERE gkey = ?", (gkey,)).fetchone()
    return r[0] if r else 0


def fold_one(song: sqlite3.Connection, gkey: str, review: dict | None, *, report: list | None = None):
    from import_lrclib import fold_artist

    if review and review.get("remove"):
        return None  # not an artist's page: a fragment of a duo's name, an audio drama

    global _owner_conn
    if _owner_conn is None:
        _owner_conn = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    group = alias_group(gkey)
    akeys = [a for g in sorted(group) for (a,) in
             _owner_conn.execute("SELECT akey FROM akey_map WHERE gkey = ?", (g,))]
    song.row_factory = sqlite3.Row
    rows: list[dict] = []
    for i in range(0, len(akeys), 500):
        part = akeys[i:i + 500]
        rows += [dict(r) for r in song.execute(
            f"SELECT * FROM song_stat WHERE akey IN ({','.join('?' * len(part))})", part)]
    if len(rows) < MIN_SONGS:
        return None
    skip = group | removed_keys()

    def owners_here(fp):  # the artist's other names, and removed pages, are not other artists
        return [o for o in owners(fp) if o[0] not in skip]

    return fold_artist(rows, min_songs=MIN_SONGS, owners=owners_here,
                       artist_uploads=artist_uploads, review=review,
                       gkey=gkey, report=report)


def _fold_chunk(args: tuple[int, list[str]]) -> tuple[int, int]:
    from import_dataset import encode_tokens

    k, gkeys = args
    reviews = load_reviews()
    song = song_conn()
    part = os.path.join(PART_DIR, f"part{k:03d}.db")
    if os.path.exists(part):
        os.remove(part)
    out = sqlite3.connect(part)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("CREATE TABLE agg (gkey TEXT, display TEXT, stats_json TEXT, songs_json TEXT)")
    out.execute("CREATE TABLE tok (gkey TEXT, toks TEXT)")
    out.execute("CREATE TABLE report (gkey TEXT, title TEXT, uploads INTEGER, wc INTEGER, "
                "reason TEXT, owner TEXT, owner_n INTEGER, flags TEXT, album TEXT)")
    done = 0
    for gkey in gkeys:
        report: list = []
        r = fold_one(song, gkey, reviews.get(gkey), report=report)
        if r:
            display, stats, songs_list, g = r
            out.execute("INSERT INTO agg VALUES (?,?,?,?)",
                        (gkey, display, json.dumps(stats, ensure_ascii=False),
                         json.dumps(songs_list, ensure_ascii=False)))
            out.execute("INSERT INTO tok VALUES (?,?)", (gkey, encode_tokens(g)))
            out.executemany("INSERT INTO report VALUES (?,?,?,?,?,?,?,?,?)", [
                (gkey, s.title, s.uploads, rows[s.rep]["wc"], s.reason,
                 s.owner[0] if s.owner else None, s.owner[1] if s.owner else None,
                 ",".join(s.flags) or None, rows[s.rep]["album"])
                for s, rows in report])
            done += 1
    out.commit()
    out.close()
    song.close()
    return len(gkeys), done


# ── aliases ──────────────────────────────────────────────────────────────────

ALIAS_PATH = os.path.join(ROOT, "data", "lrclib", "_aliases.json")
_aliases: dict | None = None


def _name_words(name: str) -> list[str]:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return [w for w in re.split(r"[^\w]+", s) if w]


def build_aliases(min_overlap: float = 0.25) -> dict:
    """One artist filed under several names: "Tyler, The Creator" and "The
    Creator, Tyler"; "The Beatles", "Beatles" and "Beatles, The". Names whose
    words match once order and "the" are set aside are one artist when the
    smaller one's songs are largely the bigger one's too (so the catch-all
    "Band" does not fold into The Band). Returns {alias: canonical}; the
    canonical is the name with a page and the most uploads, not an inverted
    "Surname, First" or "Name, The" spelling."""
    from collections import defaultdict

    own = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    rows = dict(own.execute("SELECT gkey, rows FROM artist"))
    app = sqlite3.connect(APP_DB)
    pages = {k: d for k, d in app.execute(
        "SELECT name_key, display_name FROM artistaggregate WHERE song_count >= 25")}
    groups: dict[tuple, set[str]] = defaultdict(set)
    for akey, g in own.execute("SELECT akey, gkey FROM akey_map"):
        ws = [w for w in _name_words(akey) if w != "the"]
        if ws and rows.get(g, 0) >= MIN_SONGS:
            groups[tuple(sorted(ws))].add(g)

    prefer: set[str] = set()
    pref_path = os.path.join(REVIEW_DIR, "_prefer.txt")
    if os.path.exists(pref_path):
        with open(pref_path, encoding="utf-8") as fh:
            prefer = {x.strip() for x in fh if x.strip() and not x.startswith("#")}

    def inverted(g: str) -> bool:
        d = pages.get(g) or ""
        return ", " in d or d.lower().endswith(" the")

    def fps(g: str) -> set[int]:
        return {f for (f,) in own.execute("SELECT fp FROM owner WHERE gkey = ?", (g,))}

    out: dict[str, str] = {}
    for gs in groups.values():
        if len(gs) < 2 or not any(g in pages for g in gs):
            continue
        order = sorted(gs, key=lambda g: (g not in prefer, g not in pages, inverted(g), -rows.get(g, 0)))
        canon = order[0]
        canon_fps = fps(canon)
        for g in order[1:]:
            mine = fps(g)
            if mine and len(mine & canon_fps) / len(mine) >= min_overlap:
                out[g] = canon
    with open(ALIAS_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    print(f"{len(out):,} aliases → {ALIAS_PATH}", flush=True)
    return out


# Hand-made aliases: credits the first importer split in two ("Simon &
# Garfunkel" filed under "Simon" and under "Garfunkel"), folded into the duo.
MANUAL_ALIAS_PATH = os.path.join(REVIEW_DIR, "_aliases_manual.tsv")


def aliases() -> dict[str, str]:
    global _aliases
    if _aliases is None:
        _aliases = {}
        if os.path.exists(ALIAS_PATH):
            with open(ALIAS_PATH, encoding="utf-8") as fh:
                _aliases = json.load(fh)
        if os.path.exists(MANUAL_ALIAS_PATH):
            with open(MANUAL_ALIAS_PATH, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip() and not line.startswith("#"):
                        alias, canonical = line.rstrip("\n").split("\t")[:2]
                        _aliases[alias.strip()] = canonical.strip()
        # follow chains to their end: "garfunkelsimon" → "simongarfunkel" → "simonandgarfunkel"
        for a in list(_aliases):
            c, seen = _aliases[a], {a}
            while c in _aliases and c not in seen:
                seen.add(c)
                c = _aliases[c]
            _aliases[a] = c
    return _aliases


_removed: set[str] | None = None


def removed_keys() -> set[str]:
    """Pages a review removes: halves of a split credit, audio dramas. They
    hold no songs of their own, so they claim none from anyone else."""
    global _removed
    if _removed is None:
        _removed = {g for g, r in load_reviews().items() if r.get("remove")}
    return _removed


def alias_group(gkey: str) -> set[str]:
    """The key and every alias folded into it."""
    return {gkey} | {a for a, c in aliases().items() if c == gkey}


# ── sample ───────────────────────────────────────────────────────────────────


def sample(names: list[str]) -> None:
    from lyricstats.db import normalize_key

    reviews = load_reviews()
    app = sqlite3.connect(APP_DB)
    song = song_conn()
    for name in names:
        gkey = normalize_key(name)
        old = app.execute("SELECT song_count, songs_json, stats_json FROM artistaggregate WHERE name_key = ?",
                          (gkey,)).fetchone()
        report: list = []
        t0 = time.time()
        r = fold_one(song, gkey, reviews.get(gkey), report=report)
        if not r:
            print(f"## {name}: nothing folded")
            continue
        display, stats, songs_list, _g = r
        old_titles = {t[0]: t[2] for t in json.loads(old[1])} if old else {}
        print(f"\n## {display}: {old[0] if old else '-'} → {stats['song_count']} songs, "
              f"{json.loads(old[2])['total_words'] if old else '-'} → {stats['total_words']} words "
              f"({time.time() - t0:.1f}s)")
        why = Counter(s.reason for s, _ in report if s.reason)
        print("   set aside:", dict(why))
        for s, rows in sorted(report, key=lambda x: -x[0].uploads):
            if s.reason:
                own = f"  [{s.owner[0]} ×{s.owner[1]}]" if s.owner else ""
                print(f"   – {s.title[:60]:60s} ×{s.uploads:<4d} {rows[s.rep]['wc']:5d}w  {s.reason}{own}")
        changed = [(t[0], old_titles.get(t[0]), t[2]) for t in songs_list
                   if t[0] in old_titles and old_titles[t[0]] != t[2]]
        print(f"   words changed on {len(changed)} songs:",
              "; ".join(f"{t} {a}→{b}" for t, a, b in sorted(changed, key=lambda x: -abs((x[1] or 0) - x[2]))[:12]))
        flagged = [(s, rows) for s, rows in report if s.reason is None and s.flags]
        for s, rows in sorted(flagged, key=lambda x: -x[0].owner[1])[:20]:
            print(f"   ? {s.title[:60]:60s} ×{s.uploads:<4d} [{s.owner[0]} ×{s.owner[1]}]")


# ── fold everything ──────────────────────────────────────────────────────────


def fold_all(workers: int, chunks: int, only: list[str] | None = None) -> None:
    """Fold every artist (or `only` these keys, replacing their staged rows)."""
    own = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    if only:
        gkeys = only
        chunks = min(chunks, len(gkeys))
    else:
        # The artists with a page (≥ 25 songs): the ones the site shows. The
        # small ones stay as they are in the app database, which only this
        # machine reads; folding them too would take hours of random reads.
        app = sqlite3.connect(APP_DB)
        keys = {k for (k,) in app.execute("SELECT name_key FROM artistaggregate WHERE song_count >= 25")}
        app.close()
        rows_of = dict(own.execute("SELECT gkey, rows FROM artist"))
        build_aliases()
        global _aliases
        _aliases = None  # reload: the new automatic aliases and the hand-made ones
        al = aliases()
        keys = {al.get(k, k) for k in keys} - removed_keys()
        gkeys = sorted((k for k in keys if rows_of.get(k, 0) >= MIN_SONGS), key=lambda k: -rows_of[k])
    own.close()
    print(f"{len(gkeys):,} artists to fold", flush=True)
    os.makedirs(PART_DIR, exist_ok=True)
    jobs = [(k, gkeys[k::chunks]) for k in range(chunks)]  # the big ones spread over all chunks
    t0 = time.time()
    total = folded = 0
    import multiprocessing

    with multiprocessing.get_context("fork").Pool(workers) as pool:
        for n, done in pool.imap_unordered(_fold_chunk, jobs):
            total += n
            folded += done
            print(f"  {total:,}/{len(gkeys):,} artists read, {folded:,} folded, "
                  f"{(time.time() - t0) / 60:.1f} min", flush=True)

    if os.path.exists(STAGE_DB) and not only:
        os.remove(STAGE_DB)
    st = sqlite3.connect(STAGE_DB)
    st.execute("PRAGMA journal_mode=OFF")
    if only:
        for i in range(0, len(gkeys), 500):
            part = gkeys[i:i + 500]
            st.execute(f"DELETE FROM agg WHERE gkey IN ({','.join('?' * len(part))})", part)
            st.execute(f"DELETE FROM report WHERE gkey IN ({','.join('?' * len(part))})", part)
        st.commit()
    st.execute("CREATE TABLE IF NOT EXISTS agg (gkey TEXT PRIMARY KEY, display TEXT, stats_json TEXT, "
               "songs_json TEXT)")
    tok_path = os.path.join(ROOT, "data", "lrclib", "_artist_tok_clean.db")
    if not only and os.path.exists(tok_path):
        os.remove(tok_path)
    tk = sqlite3.connect(tok_path)
    tk.execute("PRAGMA journal_mode=OFF")
    tk.execute("CREATE TABLE IF NOT EXISTS artist_tok (name TEXT PRIMARY KEY, toks TEXT)")
    st.execute("CREATE TABLE IF NOT EXISTS report (gkey TEXT, title TEXT, uploads INTEGER, wc INTEGER, "
               "reason TEXT, owner TEXT, owner_n INTEGER, flags TEXT, album TEXT)")
    for k in range(chunks):
        part = os.path.join(PART_DIR, f"part{k:03d}.db")
        st.execute("ATTACH ? AS p", (part,))
        st.execute("INSERT OR REPLACE INTO agg SELECT * FROM p.agg")
        st.execute("INSERT INTO report SELECT * FROM p.report")
        st.commit()
        st.execute("DETACH p")
        tk.execute("ATTACH ? AS p", (part,))
        tk.execute("INSERT OR REPLACE INTO artist_tok SELECT gkey, toks FROM p.tok")
        tk.commit()
        tk.execute("DETACH p")
        os.remove(part)
    os.rmdir(PART_DIR)
    st.execute("CREATE INDEX IF NOT EXISTS idx_report_gkey ON report(gkey)")
    st.commit()
    st.close()
    tk.close()
    print(f"folded in {(time.time() - t0) / 60:.1f} min → {STAGE_DB}", flush=True)
    if not only:
        corpus()


def corpus() -> None:
    """The importer's corpus pass over the staged aggregates."""
    import import_lrclib as imp

    st = sqlite3.connect(STAGE_DB)
    aggs = [(g, d, json.loads(s), json.loads(sl)) for g, d, s, sl in
            st.execute("SELECT gkey, display, stats_json, songs_json FROM agg")]
    every = [g for g, *_ in aggs]
    aggs, n_stubs = imp.drop_truncation_stubs(aggs)
    keep = {g for g, *_ in aggs}
    print(f"{len(aggs):,} aggregates ({n_stubs} truncation stubs set aside); corpus pass…", flush=True)
    # corpus_pass reads each artist's vocabulary from TOK_PATH by gkey
    imp.TOK_PATH = os.path.join(ROOT, "data", "lrclib", "_artist_tok_clean.db")
    imp.corpus_pass(aggs)
    st.executemany("UPDATE agg SET stats_json = ? WHERE gkey = ?",
                   ((json.dumps(s, ensure_ascii=False), g) for g, _d, s, _sl in aggs))
    st.execute("CREATE TABLE IF NOT EXISTS stub (gkey TEXT)")
    st.execute("DELETE FROM stub")
    st.executemany("INSERT INTO stub VALUES (?)", ((g,) for g in every if g not in keep))
    st.commit()
    st.close()
    print("corpus pass written", flush=True)


# ── review sheets ────────────────────────────────────────────────────────────


def top_artists(n: int, must: list[str] | None = None) -> list[tuple[str, str, int]]:
    """The artists whose pages matter most: `must` (named by hand, the ones
    people look up today) first, then the most-uploaded real artists with a
    page (≥ 25 songs), n in all."""
    from catalogue import _is_pseudo
    from lyricstats.db import normalize_key

    st = sqlite3.connect(STAGE_DB)
    pages = {g: (d, json.loads(s)["song_count"]) for g, d, s in st.execute(
        "SELECT gkey, display, stats_json FROM agg")}
    own = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    uploads = dict(own.execute("SELECT gkey, rows FROM artist"))
    out, seen = [], set()
    for name in must or []:
        g = normalize_key(name)
        if g in pages and g not in seen:
            out.append((g, pages[g][0], uploads.get(g, 0)))
            seen.add(g)
    for g, rows in sorted(uploads.items(), key=lambda x: -x[1]):
        if len(out) >= n:
            break
        if g in pages and g not in seen and pages[g][1] >= 25 and not _is_pseudo(pages[g][0]) \
                and not _is_pseudo(g):
            out.append((g, pages[g][0], rows))
            seen.add(g)
    return out


def sheets(n: int, out_dir: str, start: int = 0, must: list[str] | None = None) -> None:
    """One text sheet per top artist from the staged report: every song kept
    (most-uploaded first) and every song set aside, with the evidence."""
    os.makedirs(out_dir, exist_ok=True)
    st = sqlite3.connect(STAGE_DB)
    top = top_artists(n, must)
    with open(os.path.join(out_dir, "top.tsv"), "w") as fh:
        for i, (g, d, rows) in enumerate(top, 1):
            fh.write(f"{i}\t{g}\t{d}\t{rows}\n")
    for i, (g, d, rows) in enumerate(top[start:], start + 1):
        rep = st.execute("SELECT title, uploads, wc, reason, owner, owner_n, flags, album FROM report "
                         "WHERE gkey = ? ORDER BY uploads DESC, title", (g,)).fetchall()
        kept = [r for r in rep if r[3] is None]
        gone = [r for r in rep if r[3] is not None]
        lines = [f"# {i}. {d} [{g}] {rows} uploads · kept {len(kept)} · set aside {len(gone)}"]
        items = []
        for title, up, wc, _r, owner, on, flags, album in kept:
            extra = f" ⚑{owner}×{on}" if flags else ""
            items.append(f"{title} ×{up} {wc}w{extra}")
        lines.append("KEPT: " + " · ".join(items))
        lines.append("ASIDE: " + " · ".join(
            f"{title} ×{up} ({reason}{'; ' + owner + '×' + str(on) if owner else ''})"
            for title, up, _wc, reason, owner, on, _f, _a in gone))
        with open(os.path.join(out_dir, f"{i:03d}-{g}.txt"), "w") as fh:
            fh.write("\n".join(lines) + "\n")


# ── commit ───────────────────────────────────────────────────────────────────


def commit() -> None:
    """Replace the local aggregates with the staged ones, keeping names stable."""
    from lyricstats.db import normalize_key

    backup = os.path.join(ROOT, "data", "lyricstats.pre-clean.db")
    app = sqlite3.connect(APP_DB)
    if not os.path.exists(backup):
        print(f"keeping the old aggregates in {backup}…", flush=True)
        app.execute("ATTACH ? AS b", (backup,))
        app.execute("CREATE TABLE b.artistaggregate AS SELECT * FROM main.artistaggregate")
        app.commit()
        app.execute("DETACH b")
    # One key can hold two stored spellings ("Rosalía", "rosalia"); both get
    # the cleaned catalogue, each keeping its own name.
    names: dict[str, list[tuple[str, str]]] = {}
    for k, n, d in app.execute("SELECT name_key, name, display_name FROM artistaggregate"):
        names.setdefault(k, []).append((n, d))
    st = sqlite3.connect(STAGE_DB)
    stubs = {g for (g,) in st.execute("SELECT gkey FROM stub")} if st.execute(
        "SELECT name FROM sqlite_master WHERE name='stub'").fetchone() else set()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    used: set[str] = set()
    for g, display, stats_json, songs_json in st.execute("SELECT gkey, display, stats_json, songs_json FROM agg"):
        if g in stubs or g in aliases() or g in removed_keys():
            continue  # folded into another page, or not a page at all
        count = json.loads(stats_json)["song_count"]
        for name, disp in names.get(g, [(display.strip().lower(), display)]):
            if name in used:
                continue
            used.add(name)
            rows.append((name, normalize_key(disp) or g, disp, count, stats_json, songs_json, now))
    # pages that are not pages any more: other spellings folded into an
    # artist, and pages a review removed
    reviews = load_reviews()
    gone = {a: f"folded into {c}" for a, c in aliases().items()}
    gone.update({g: "removed: " + r["remove"] for g, r in reviews.items() if r.get("remove")})
    removed = [(name, g, why) for g, why in gone.items() for name, _d in names.get(g, [])]
    with open(os.path.join(ROOT, "output", "catalogue-removed-pages.json"), "w", encoding="utf-8") as fh:
        json.dump([{"name": n, "key": g, "why": w} for n, g, w in removed], fh, ensure_ascii=False, indent=0)
    app.executemany("DELETE FROM artistaggregate WHERE name = ?", ((n,) for n, _g, _w in removed))
    print(f"{len(removed):,} pages removed (aliases and reviewed removals)", flush=True)
    print(f"writing {len(rows):,} aggregates…", flush=True)
    app.executemany("DELETE FROM artistaggregate WHERE name = ?", ((r[0],) for r in rows))
    app.executemany(
        "INSERT INTO artistaggregate (name, name_key, display_name, song_count, has_sections, stats_json, "
        "songs_json, source, built_at) VALUES (?,?,?,?,0,?,?,'lrclib',?)", rows)
    app.commit()
    print("committed", flush=True)


# ── production ───────────────────────────────────────────────────────────────

# Heavy keys production has never carried (scripts/push_aggregates.py strips them).
PROD_DROP_KEYS = ("albums", "density_curve", "lang_mix")
PROD_SONGS_CAP = 500


def prod_backup(path: str) -> None:
    """Every production aggregate row, as it is, to a gzipped JSON-lines file."""
    import gzip

    import psycopg
    from build_signatures import prod_url

    n = 0
    with psycopg.connect(prod_url(), connect_timeout=15) as conn, gzip.open(path, "wt", encoding="utf-8") as fh:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor(name="backup") as cur:
            cur.itersize = 2000
            cur.execute("SELECT id, name, name_key, display_name, song_count, has_sections, stats_json, "
                        "songs_json, source, built_at FROM artistaggregate ORDER BY id")
            cols = [d.name for d in cur.description]
            for row in cur:
                rec = dict(zip(cols, row))
                rec["built_at"] = rec["built_at"].isoformat() if rec["built_at"] else None
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    print(f"backed up {n:,} production rows → {path}", flush=True)


def prod_plan(path: str) -> None:
    """For every production row, the cleaned catalogue from the app database."""
    import psycopg
    from build_signatures import prod_url

    app = sqlite3.connect(APP_DB)
    local = {name: (count, stats, songs) for name, count, stats, songs in app.execute(
        "SELECT name, song_count, stats_json, songs_json FROM artistaggregate")}
    with psycopg.connect(prod_url(), connect_timeout=15) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        names = [n for (n,) in conn.execute("SELECT name FROM artistaggregate")]
    patches, missing = {}, []
    for name in names:
        row = local.get(name)
        if not row:
            missing.append(name)
            continue
        count, stats_json, songs_json = row
        stats = json.loads(stats_json)
        for k in PROD_DROP_KEYS:
            stats.pop(k, None)
        songs = json.loads(songs_json)[:PROD_SONGS_CAP]
        patches[name] = {"song_count": count,
                         "stats_json": json.dumps(stats, ensure_ascii=False, separators=(",", ":")),
                         "songs_json": json.dumps(songs, ensure_ascii=False, separators=(",", ":"))}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "patches": patches, "missing": missing},
                  fh, ensure_ascii=False)
    print(f"production plan: {len(patches):,} rows, {len(missing):,} without a cleaned catalogue "
          f"(left as they are) → {path}", flush=True)


def prod_apply(path: str, batch: int = 4000) -> None:
    """Replace each row's catalogue, count and stats, in batches with a vacuum
    between them so the table reuses its space under the storage cap."""
    import psycopg
    from build_signatures import prod_url

    with open(path, encoding="utf-8") as fh:
        patches = list(json.load(fh)["patches"].items())
    total = 0
    with psycopg.connect(prod_url(), connect_timeout=15, autocommit=True) as conn:
        conn.execute("CREATE TEMP TABLE cat_patch (name text PRIMARY KEY, song_count int, "
                     "stats_json text, songs_json text)")
        for start in range(0, len(patches), batch):
            part = patches[start:start + batch]
            with conn.transaction():
                conn.execute("TRUNCATE cat_patch")
                with conn.cursor().copy("COPY cat_patch FROM STDIN") as cp:
                    for name, p in part:
                        cp.write_row((name, p["song_count"],
                                      p["stats_json"].replace("\\u0000", "").replace("\x00", ""),
                                      p["songs_json"].replace("\\u0000", "").replace("\x00", "")))
                cur = conn.execute(
                    "UPDATE artistaggregate a SET song_count = p.song_count, stats_json = p.stats_json, "
                    "songs_json = p.songs_json, built_at = now() FROM cat_patch p WHERE a.name = p.name")
                total += cur.rowcount
            conn.execute("VACUUM artistaggregate")
            size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
            print(f"  {min(start + batch, len(patches)):,}/{len(patches):,} rows, {total:,} updated, "
                  f"database {size}", flush=True)
    print("done", flush=True)


def prod_remove(path: str) -> None:
    """Delete the production rows of pages that are no longer pages (other
    spellings folded into an artist, reviewed removals). Back up first."""
    import psycopg
    from build_signatures import prod_url

    with open(path, encoding="utf-8") as fh:
        names = sorted({r["name"] for r in json.load(fh)})
    with psycopg.connect(prod_url(), connect_timeout=15) as conn:
        cur = conn.execute("DELETE FROM artistaggregate WHERE name = ANY(%s)", (names,))
        conn.commit()
    print(f"removed {cur.rowcount:,} production rows of {len(names):,} listed", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", action="append")
    ap.add_argument("--top", type=int)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--sheets")
    ap.add_argument("--fold", action="store_true")
    ap.add_argument("--refold-reviewed", action="store_true",
                    help="fold again the artists that have a review, replacing their staged rows")
    ap.add_argument("--must", help="a file of artist names that belong in the top list")
    ap.add_argument("--prod-backup", help="save every production row to this .jsonl.gz first")
    ap.add_argument("--prod-plan", help="compute the production patch into this file")
    ap.add_argument("--prod-apply", help="apply a saved production patch")
    ap.add_argument("--prod-remove", help="delete the production rows listed in this file")
    ap.add_argument("--corpus", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunks", type=int, default=64)
    args = ap.parse_args()
    if args.sample:
        sample(args.sample)
    must = None
    if args.must:
        with open(args.must, encoding="utf-8") as fh:
            must = [x.strip() for x in fh if x.strip() and not x.startswith("#")]
    if args.fold:
        fold_all(args.workers, args.chunks)
    if args.refold_reviewed:
        # reviewed artists, and the pages the hand-made aliases fold names into
        manual = set()
        if os.path.exists(MANUAL_ALIAS_PATH):
            with open(MANUAL_ALIAS_PATH, encoding="utf-8") as fh:
                manual = {line.split("\t")[0].strip() for line in fh if line.strip() and not line.startswith("#")}
        targets = {aliases()[a] for a in manual if a in aliases()}
        fold_all(args.workers, args.chunks, only=sorted((set(load_reviews()) | targets) - set(aliases())))
    if args.top and args.sheets:
        sheets(args.top, args.sheets, args.start, must)
    if args.corpus:
        corpus()
    if args.commit:
        commit()
    if args.prod_backup:
        prod_backup(args.prod_backup)
    if args.prod_plan:
        prod_plan(args.prod_plan)
    if args.prod_apply:
        prod_apply(args.prod_apply)
    if args.prod_remove:
        prod_remove(args.prod_remove)


if __name__ == "__main__":
    main()
