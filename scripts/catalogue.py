"""One artist's LRCLIB uploads → the songs that are theirs, one version each.

LRCLIB lists every upload of every release under whatever artist name the
uploader typed. The importer used to group those uploads by title or lyrics
and keep the longest, which let extended mixes and megamixes stand in for the
songs ("Bad" at 1,147 words), let medleys and typo'd copies count as songs of
their own, and left in songs that were only filed under the artist: a group's
hits under a member's name, a remixer's remix of somebody else's song, a
stray upload that belongs to another artist.

clean() works on the rows of one artist:

  1. group the uploads of one song: the same title once track numbers, years,
     artist credits and version words are stripped; the same lyric
     fingerprint; or nearly the same words (one text contained in the other);
  2. stand each song for its most-uploaded transcription (the studio
     recording is on every compilation; an extended mix is on one), named by
     its most common plain title;
  3. set aside what is not the artist's song: medleys, megamixes and
     mash-ups; remixes the artist is credited for (somebody else's words);
     non-songs; and a song uploaded here once or twice that lives elsewhere
     (ownership, from scripts/build_owner_index.py);
  4. apply the hand review (scripts/catalogue_review/*.json) for the artists
     that have one: songs to drop, songs to keep, or the whole list.

Every decision is reported with its reason, for the review sheets.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from import_lrclib import _alnum_squash, canonical_title, content_fingerprint
from lyricstats.stats import STOPWORDS

# ── titles ───────────────────────────────────────────────────────────────────

# "01 ", "01. ", "1 - ", "1-01 ", "B2 ", "175.", "06-": a track or side number
# in front of the title. "7 Rings", "99 Problems" and "22" are titles.
TRACK_NO_RE = re.compile(
    r"^\s*(?:"
    r"0\d{1,2}\s*[-._)]?\s*"            # 01 / 01. / 01 -
    r"|\d{1,3}\s*[-._)]\s*(?:\d{1,2}\s*[-._)]?\s*)?"  # 1 - / 1-01 / 175.
    r"|[A-Da-d]\d{1,2}\s*[-._)]?\s+"      # B2 (vinyl side)
    r")(?=\S)"
)
# Download-site and upload junk glued to titles.
TITLE_JUNK_RE = re.compile(
    r"\s*[-–|]?\s*(?:spotubedl\.com|spotifydown\.com|y2mate\.com|www\.\S+|\S+\.(?:com|net|org))\s*$",
    re.I,
)
TRAILING_YEAR_RE = re.compile(r"\s+(?:19|20)\d{2}$")
MASH_RE = re.compile(r"\b(?:megamix|mega[- \u2010]mix|medley|mash-?up|megamashup)\b", re.I)
# A skit is talk; an interlude, intro or outro of a few lines is a fragment
# between songs, or talk ("Nicki Minaj Speaks", "Intro to Both Sides Now").
SKIT_RE = re.compile(r"\bskit\b", re.I)
INTERLUDE_RE = re.compile(r"\b(?:interlude|intro|introductions?|outro|prologue|speaks|dialog(?:ue)?)\b", re.I)
INTERLUDE_MAX_WORDS = 100
# Title unions skip rows whose words are mostly uploaded under another title.
KEY_UNION_GUARD = True
# A text holding two unlike songs is a medley and merges with neither.
MEDLEY_GUARD = True
# Words that make a bracket or dash clause a version of a song.
VERSION_WORD_RE = re.compile(
    r"\b(?:remix(?:ed)?|mix|edit|rework|bootleg|dub|version|flip|refix|vip|remode|"
    r"re-?edit|cover|live|acoustic|instrumental|a ?capp?ella|sped up|slowed|"
    r"demo|snippet|teaser|preview|remaster(?:ed|i[sz]ad[ao]|is[ée]e?)?|mono|stereo|ao vivo|en vivo|en directo)\b",
    re.I,
)
# a bracket clause, or one cut off by a truncated title: "A Kind Of Magic (Demo"
CLAUSE_RE = re.compile(r"[(\[{][^)\]}]*(?:[)\]}]|$)")
# Talk, not a song. Phrases that are also song titles ("Message From a Black
# Man", "Trapped in the Closet Chapter 1", "Commercial for Levi", "Radio
# Show", "No Spoken Word") are left out, or count only as a bracket clause.
NON_SONG_RE = re.compile(
    r"\b(?:voice[- ]?over|voice memo|interview|commentary|track by track|"
    r"radio promo|spoken intro|audio book|audiobook|"
    r"behind the scenes|album preview|phone call with|phone conversation|"
    r"press conference|acceptance speech|liner notes|tracklist|full album|spoken interlude|"
    r"band introductions?|band intros?|introducing the band|pr[ée]sentation des musiciens|radio spot|"
    r"announcements?|halftime show|promotional spot|radio commercial|tour promo|album ad|"
    r"session highlights|studio banter)\b"
    r"|[(\[-]\s*spoken word\b",
    re.I,
)
# A clause that credits a remixer ("(Avicii Remix)", "- Alec Empire Mix"); a
# "(Taylor's Version)" or "(Live)" is the artist's own recording, not a remix.
REMIX_WORD_RE = re.compile(r"\b(?:remix(?:ed)?|mix|edit|rework|bootleg|dub|flip|refix|vip|re-?edit)\b", re.I)
# Artists that are not one artist: compilations, placeholders, cover mills.
PSEUDO_ARTIST_RE = re.compile(
    r"^(?:various.*|va|v\.a\.|v a|aa\.? ?vv\.?|diverse.*|verschiedene.*|varios.*|"
    r"v[aá]rios.*|vari|autori vari|artistes? divers|compilation.*|unknown.*|"
    r"artist|artists|song|songs|the|a|y|e|x|n/a|none|null|undefined|"
    r"kidz bop.*|glee cast|karaoke.*|sing king.*|the hit crew.*|party hits.*|"
    r"mr\.? entertainer.*|ameritz.*|hit masters.*|starlite.*|.*tribute.*|"
    r".*cover band.*|.*covers?\b.*|.*orchestra$)$",
    re.I,
)


def plain(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def strip_track_no(title: str) -> str:
    t = TRACK_NO_RE.sub("", title, count=1)
    return t if len(t) >= 2 else title


def strip_artist(title: str, artist_words: str) -> str:
    """Drop the artist's own name glued in front: "Michael Jackson - Bad",
    "michael jackson billie jean", "Quincy Jones_…" is left for ownership."""
    if not artist_words:
        return title
    n = len(artist_words.split())
    words = re.split(r"(\s*[-–:|]\s*|\s+)", title.strip())
    # words alternates [word, sep, word, sep, ...]; the credit is the first n words
    if len(words) > 2 * n and _alnum_squash("".join(words[:2 * n - 1])) == artist_words \
            and re.fullmatch(r"\s*[-–:|]\s*", words[2 * n - 1]):
        rest = "".join(words[2 * n:]).strip()
        if rest:
            return rest
    return title


@lru_cache(maxsize=400_000)
def title_key(title: str, artist_words: str) -> str:
    """The key a song's uploads share: no track number, credit, year or version."""
    t = plain(title)
    t = TITLE_JUNK_RE.sub("", t)
    t = strip_track_no(t)
    t = strip_artist(t, artist_words)
    k = canonical_title(t, None)
    k2 = TRAILING_YEAR_RE.sub("", k)
    return k2 if len(k2) >= 3 else k


@lru_cache(maxsize=400_000)
def version_clauses(title: str) -> tuple[str, ...]:
    out = [m.group(0) for m in CLAUSE_RE.finditer(title) if VERSION_WORD_RE.search(m.group(0))]
    parts = re.split(r"\s[-–—]\s", title)
    if len(parts) > 1 and VERSION_WORD_RE.search(parts[-1]):
        out.append(parts[-1])
    return tuple(out)


@lru_cache(maxsize=400_000)
def is_plain_title(title: str) -> bool:
    """A title with no version clause and no junk: how the song is usually named."""
    t = plain(title)
    return not version_clauses(t) and not TITLE_JUNK_RE.search(t) and not MASH_RE.search(t)


@lru_cache(maxsize=400_000)
def display_title(title: str, artist_words: str) -> str:
    t = plain(title)
    t = TITLE_JUNK_RE.sub("", t)
    t = strip_track_no(t)
    t = strip_artist(t, artist_words)
    for _ in range(3):  # "Proposta - Versão Remasterizada (Ao Vivo)": a clause inside a clause
        cs = version_clauses(t)
        if not cs:
            break
        for c in cs:
            t = t.replace(c, "")
        t = re.sub(r"\s*[-–—]\s*$", "", t.strip())
    t = re.sub(r"\s{2,}", " ", t).strip(" -–")
    return t or plain(title)


# ── lyrics ───────────────────────────────────────────────────────────────────


# Scripts whose vowel signs the word tokenizer drops ("गले" is stored as "गल"),
# leaving words of one or two letters: count the two-letter ones as content, or
# a Hindi song has too few words to be compared with its other uploads.
SPLIT_SCRIPT_RE = re.compile(r"[\u0900-\u0DFF\u0E00-\u0EFF\u0F00-\u0FFF\u1000-\u109F\u1780-\u17FF]")


def content(cnt: Counter) -> Counter:
    return Counter({w: c for w, c in cnt.items()
                    if (len(w) > 2 or (len(w) == 2 and SPLIT_SCRIPT_RE.match(w))) and w not in STOPWORDS})


def containment(a: Counter, b: Counter) -> float:
    """How much of the smaller text is in the other (weighted by counts)."""
    sa, sb = sum(a.values()), sum(b.values())
    if not sa or not sb:
        return 0.0
    small, big = (a, b) if sa <= sb else (b, a)
    return sum(min(c, big.get(w, 0)) for w, c in small.items()) / min(sa, sb)


# ── the pass ─────────────────────────────────────────────────────────────────


@dataclass
class Song:
    rows: list[int]                  # indices into the artist's rows
    rep: int                         # the row that stands for the song
    title: str                       # display title
    key: str
    uploads: int
    fp: tuple | None = None
    reason: str | None = None        # why it was set aside (None = kept)
    owner: tuple[str, int, str] | None = None   # (gkey, uploads, title) elsewhere
    flags: list[str] = field(default_factory=list)


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _representative(rows: list[dict], idx: list[int]) -> int:
    """The most-uploaded transcription among the plainly titled uploads."""
    pool = [i for i in idx if is_plain_title(rows[i]["title"])] or idx
    by_wc: dict[int, list[int]] = defaultdict(list)
    for i in pool:
        by_wc[rows[i]["wc"]].append(i)
    wcs = sorted(rows[i]["wc"] for i in pool)
    median = wcs[len(wcs) // 2]
    best_wc = max(by_wc, key=lambda w: (len(by_wc[w]), any(rows[i]["has_synced"] for i in by_wc[w]),
                                        -abs(w - median)))
    return max(by_wc[best_wc], key=lambda i: rows[i]["has_synced"])


def _best_title(rows: list[dict], idx: list[int], artist_words: str) -> str:
    cands = [display_title(rows[i]["title"], artist_words) for i in idx if is_plain_title(rows[i]["title"])]
    if not cands:
        cands = [display_title(rows[i]["title"], artist_words) for i in idx]
    freq = Counter(c for c in cands if len(_alnum_squash(c)) >= 1)
    if not freq:
        return plain(rows[idx[0]]["title"])

    def score(t: str) -> tuple:
        shouting = t.isupper() and len(t) > 4
        camel = bool(re.search(r"[a-z][A-Z]", t))
        return (freq[t], not shouting, not camel, -len(t))

    return max(freq, key=score)


MEDLEY_SPLIT_RE = re.compile(r"\s+/\s+|\s*/\s*(?=[A-Z])|\s+[xX]\s+|\s+vs\.?\s+")


def _names_listed_songs(title: str, own_key: str, keys_here: set[str], artist_words: str,
                        dash: bool = False) -> bool:
    """A title of two or more parts, one of them another song of this catalogue
    (`dash`: " - " separates parts too, for a text already known to hold two songs)."""
    t = re.sub(r"^\s*medley\s*:\s*", "", title, flags=re.I)
    parts = [p for p in (re.split(r"\s+[-–]\s+", t) if dash else [t]) for p in MEDLEY_SPLIT_RE.split(p)]
    parts = [p for p in parts if p.strip()]
    return len(parts) > 1 and all(len(_alnum_squash(p)) >= 3 for p in parts) \
        and any(title_key(p, artist_words) in keys_here - {own_key} for p in parts)


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return "".join(c for c in s if c.isalnum())


NOT_A_CREDIT_RE = re.compile(
    r"\b(?:feat|ft|featuring|with|prod|produced|remix|mix|version|live|edit|demo|from|of|by|"
    r"theme|part|pt|vol|take|session|reprise|intro|outro|interlude)\b", re.I)


def other_artist_named(title: str, gkey: str, artist_uploads, song_owners: set[str]) -> str | None:
    """Another artist credited in the title: "Culture Club / Time", "Seu Jorge -
    Queen Bitch", "Sad But True (Metallica)". The name must belong to an
    artist who holds this song's lyrics too."""
    t = plain(title)
    cands: list[str] = []
    m = re.match(r"^(.+?)\s*(?:\s/\s|/(?=\S)|\s[-–—]\s|_|:\s)\s*(.+)$", t)
    if m:
        cands.append(m.group(1))
    m = re.search(r"\s[-–—]\s([^-–—]+)$", t)
    if m:
        cands.append(m.group(1))
    for c in CLAUSE_RE.findall(t):
        inner = c[1:-1]
        if not NOT_A_CREDIT_RE.search(inner):
            cands.append(inner)
    for c in cands:
        for part in re.split(r"\s*(?:,|&|\+|\band\b|\bx\b|\bvs\.?)\s*", c, flags=re.I):
            k = _key(part)
            if len(k) < 4 or k == gkey or gkey in k or k in gkey:
                continue
            # the named artist must hold this song's lyrics too: "(Nightmare)"
            # in "Alive (Nightmare)" is a subtitle, not the band Nightmare
            if k in song_owners and artist_uploads(k) >= 20:
                return part.strip()
    return None


def _is_pseudo(gkey_or_name: str) -> bool:
    return bool(PSEUDO_ARTIST_RE.match((gkey_or_name or "").strip()))


def clean(rows: list[dict], toks: list[Counter], *, display: str, gkey: str,
          owners=None, artist_uploads=None, review: dict | None = None) -> list[Song]:
    """Group, choose and filter one artist's rows. `owners(fp)` returns
    [(gkey, uploads, title)] for the lyrics fingerprint across the archive;
    `artist_uploads(gkey)` how many uploads an artist key has."""
    artist_words = _alnum_squash(display)
    own_words = {w for w in artist_words.split() if len(w) >= 3 and w not in STOPWORDS
                 and not VERSION_WORD_RE.fullmatch(w)}
    n = len(rows)
    fp_of: dict[int, tuple | None] = {}
    fps = []
    for c in toks:  # uploads of one transcription share one Counter
        if id(c) not in fp_of:
            fp_of[id(c)] = content_fingerprint(c)
        fps.append(fp_of[id(c)])
    keys = [title_key(r["title"], artist_words) for r in rows]

    # A transcription uploaded mostly under another title is that song's, and
    # joins it by its words, not by its own title: one "Underneath the Sky"
    # carrying the words of "Step Out" must not make the two songs one.
    fp_keys: dict[tuple, Counter] = defaultdict(Counter)
    for i in range(n):
        if fps[i]:
            fp_keys[fps[i]][keys[i]] += 1
    uf = UnionFind(n)
    first_key: dict[str, int] = {}
    first_fp: dict[tuple, int] = {}
    for i in range(n):
        k = keys[i]
        stray = KEY_UNION_GUARD and fps[i] and fp_keys[fps[i]].most_common(1)[0][0] != k \
            and fp_keys[fps[i]][k] * 2 < sum(fp_keys[fps[i]].values())
        if k and len(k) >= 3 and k != artist_words and not stray:
            if k in first_key:
                uf.union(i, first_key[k])
            else:
                first_key[k] = i
        if fps[i]:
            if fps[i] in first_fp:
                uf.union(i, first_fp[fps[i]])
            else:
                first_fp[fps[i]] = i

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)

    # Nearly the same words under different titles and fingerprints: a
    # re-transcription, a typo'd copy, an extended take. Compare each song's
    # most-uploaded text with others sharing its rarest top words.
    reps = {root: _representative(rows, idx) for root, idx in groups.items()}
    vec = {root: content(toks[r]) for root, r in reps.items()}
    df = Counter()
    for v in vec.values():
        df.update(v.keys())
    posting: dict[str, list[int]] = defaultdict(list)
    for root, v in vec.items():
        top = sorted(v, key=lambda w: (-v[w], df[w]))[:6]
        for w in top:
            posting[w].append(root)
    # A text that holds another nearly whole is the same song (a re-transcription,
    # an extended take), unless it holds two songs unlike each other: then it is
    # a medley ("Brain Damage / Eclipse") and must not make them one.
    size = {root: sum(v.values()) for root, v in vec.items()}
    holds: dict[int, dict[int, float]] = defaultdict(dict)
    for w, roots in posting.items():
        if len(roots) < 2 or len(roots) > 300:
            continue
        for a_i in range(len(roots)):
            a = roots[a_i]
            if size[a] < 25:
                continue
            for b in roots[a_i + 1:]:
                if size[b] < 25 or b in holds[a] or a in holds[b]:
                    continue
                c = containment(vec[a], vec[b])
                if c >= 0.85:
                    big, small = (a, b) if size[a] >= size[b] else (b, a)
                    holds[big][small] = c
    # A text much longer than what it holds may be a medley whose top words all
    # come from one of its songs: look for the other among every text sharing a word.
    for big in list(holds):
        if not MEDLEY_GUARD or not holds[big] or size[big] < 1.4 * min(size[p] for p in holds[big]):
            continue
        cands = {r for w in vec[big] for r in posting.get(w, ())}
        for c_ in cands:
            if c_ != big and c_ not in holds[big] and 25 <= size[c_] <= size[big] \
                    and containment(vec[big], vec[c_]) >= 0.85:
                holds[big][c_] = 1.0
    uf2 = UnionFind(n)
    medleys: set[int] = set()
    main_key = {root: Counter(keys[i] for i in idx).most_common(1)[0][0] for root, idx in groups.items()}
    for big, parts in holds.items():
        ps = list(parts)
        # "Echoes" holds "Echoes, Part 1" and "Echoes, Part 2": its own parts, not a medley
        own_parts = all(main_key[p].startswith(main_key[big]) for p in ps)
        if MEDLEY_GUARD and not own_parts and \
                any(containment(vec[p], vec[q]) < 0.5 for i, p in enumerate(ps) for q in ps[i + 1:]):
            # it holds two songs unlike each other: it joins one of them only if
            # that one is most of it (an extended take), else it stays apart
            best = max(ps, key=lambda p: size[p])
            if size[best] >= 0.6 * size[big]:
                uf2.union(big, best)
            else:
                medleys.add(big)
            continue
        for p in ps:
            uf2.union(big, p)
    merged: dict[int, list[int]] = defaultdict(list)
    parts_of: dict[int, list[int]] = defaultdict(list)
    for root, idx in groups.items():
        merged[uf2.find(root)].extend(idx)
        parts_of[uf2.find(root)].append(root)

    songs: list[Song] = []
    for m, idx in merged.items():
        rep = _representative(rows, idx)
        title = _best_title(rows, idx, artist_words)
        fp_counts = Counter(fps[i] for i in idx if fps[i])
        songs.append(Song(rows=idx, rep=rep, title=title, key=title_key(title, artist_words),
                          uploads=len(idx), fp=fp_counts.most_common(1)[0][0] if fp_counts else None))
        if all(r in medleys for r in parts_of[m]):
            songs[-1].flags.append("holds two songs")

    keys_here = {s.key for s in songs}
    for s in songs:
        raw = [plain(rows[i]["title"]) for i in s.rows]
        # medleys, megamixes, mash-ups
        def most(rx: re.Pattern) -> bool:  # most of the uploads are titled so
            return 2 * sum(bool(rx.search(t)) for t in raw) > len(raw)

        if most(MASH_RE):
            s.reason = "medley or megamix"
            continue
        # "Teddy Bear / Don't Be Cruel": most uploads name songs listed on their own
        # (" - " separates them too in a text known to hold two songs)
        dash = "holds two songs" in s.flags
        if 2 * sum(_names_listed_songs(t, s.key, keys_here, artist_words, dash=dash) for t in raw) >= len(raw):
            s.reason = "medley of songs listed separately"
            continue
        # a remix the artist is credited for: somebody else's words
        own_remix = [t for t in raw if any(REMIX_WORD_RE.search(c) and own_words & set(_alnum_squash(c).split())
                                           for c in version_clauses(t))]
        if own_words and len(own_remix) == len(raw):
            s.reason = "their remix of another artist's song"
            continue
        if most(NON_SONG_RE):
            s.reason = "not a song"
            continue
        if most(SKIT_RE) or (most(INTERLUDE_RE) and (rows[s.rep]["wc"] or 0) < INTERLUDE_MAX_WORDS):
            s.reason = "skit or interlude"
            continue
        if re.search(r"\bvs\.?\s", s.title, re.I) and any(w in _alnum_squash(s.title).split() for w in own_words):
            s.reason = "mash-up"
            continue
        # an artist named in the title counts when they hold a real share of the song
        song_owners = {g for g, c, _t in owners(s.fp) if 2 * c >= s.uploads} \
            if owners is not None and s.fp else set()
        if artist_uploads is not None:
            credited = [other_artist_named(x, gkey, artist_uploads, song_owners) for x in raw]
            named = [c for c in credited if c]
            if named and len(named) * 2 > len(raw):
                s.reason = f"credited to {Counter(named).most_common(1)[0][0]}"
                continue
        # uploaded here once or twice, at home elsewhere
        if owners is not None and s.fp:
            others = [(g, c, t) for g, c, t in owners(s.fp)
                      if g != gkey and not _is_pseudo(g) and gkey not in g and g not in gkey]
            if others:
                g, c, t = max(others, key=lambda x: x[1])
                s.owner = (g, c, t)
                # most of its uploads name the other artist ("Broken Wings (Mr. Mister)"); one
                # "Hurt (Nine Inch Nails cover)" among Johnny Cash's 337 does not make it theirs
                named_here = len(g) >= 6 and 2 * sum(g in _alnum_squash(x).replace(" ", "") for x in raw) > len(raw)
                names_us = gkey in _alnum_squash(t).replace(" ", "")
                feat_here = any(re.search(r"\b(feat|ft|featuring|with)\b", x, re.I) for x in raw)
                if not names_us and not feat_here:
                    if ((s.uploads <= 2 and c >= max(5, 5 * s.uploads))
                            or (s.uploads <= 5 and c >= 10 * s.uploads)
                            or (named_here and c >= s.uploads)):
                        s.reason = "belongs to another artist"
                    elif c >= 2 * s.uploads:
                        s.flags.append("more uploads elsewhere")

    if review:
        _apply_review(songs, review, artist_words)
    return songs


def _apply_review(songs: list[Song], review: dict, artist_words: str) -> None:
    """Hand decisions win. A review holds "drop" ({title: why}), "keep"
    ([title], restoring a song the rules set aside), "rename" ({title: the
    song's real title}) and, for a catalogue curated in full, "only" ([title]);
    titles match by their key."""
    def k(t: str) -> str:
        return title_key(t, artist_words)

    only = {k(t) for t in review.get("only", [])}
    drop = {k(t): why for t, why in (review.get("drop") or {}).items()}
    keep = {k(t) for t in review.get("keep", [])}
    # Two songs can share a key (a mislabelled copy kept apart from the song):
    # then a drop takes only the one shown under the reviewed title itself.
    by_key: dict[str, list[Song]] = defaultdict(list)
    for s in songs:
        by_key[s.key].append(s)
    exact: dict[str, set[str]] = defaultdict(set)
    for t in review.get("drop") or {}:
        exact[k(t)].add(_alnum_squash(t))
    for s in songs:
        if only:
            s.reason = None if s.key in only else "not in the reviewed list"
        if s.key in drop:
            twins = by_key[s.key]
            if len(twins) > 1 and any(_alnum_squash(x.title) in exact[s.key] for x in twins) \
                    and _alnum_squash(s.title) not in exact[s.key]:
                continue
            s.reason = "reviewed: " + (drop[s.key] or "not theirs")
        elif s.key in keep:
            s.reason = None
    # a song shown under a wrong title ("Enrique Iglesias" for "Miente")
    rename = {k(t): new for t, new in (review.get("rename") or {}).items()}
    for s in songs:
        if s.key in rename:
            s.title = rename[s.key]
            s.key = k(s.title)
