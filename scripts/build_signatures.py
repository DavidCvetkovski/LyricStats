#!/usr/bin/env python3
"""Each artist's signature: the word that is theirs, and a line that carries it.

The artist page used to show a "signature" picked by ratio alone, which
favoured ad-libs (hee, hoo, doo), the artist's own name, and words shouted a
hundred times in one song. A signature word has to recur across the catalogue,
and it has to be rarer in everybody else's songs than in this artist's. Both
come from the big local tables:

  data/lrclib/_artist_tok.db   one token counter per artist       → document frequency
  data/lrclib/_song_stat.db    one token counter + hook line per song → spread, quotes

Phases (run in this order; each is safe to repeat):

  uv run python scripts/build_signatures.py --df
      One pass over the artist tokens: in how many artists' catalogues each word
      is used at least five times. Saved to data/_word_df.json (~1 min).

  uv run python scripts/build_signatures.py --only "Michael Jackson" --show 8
      Print the candidates for a few artists without writing anything.

  uv run python scripts/build_signatures.py --write
      Every artist with ≥ 25 songs: compute the signature and the three extra
      percentiles and store them in stats_json of data/lyricstats.db.

  uv run python scripts/build_signatures.py --prod-plan output/signatures-prod.json
      The same for the production rows, using *their* song lists (some
      catalogues were curated by hand up there). Reads DATABASE_URL from
      .env.prod, reads only, and saves the patches to the file.

  uv run python scripts/build_signatures.py --prod-apply output/signatures-prod.json
      Merge the saved patches into production in one server-side statement.

What gets stored, under stats_json["signature"]:

  {"lang": "en",
   "word": "compton", "songs": 76, "uses": 136, "share": 0.205,
   "quote": {"line": "compton, compton, ain't no city quite like mine",
             "title": "Compton", "times": 4},
   "words": [["compton", 76, 136], ["hood", 77, 152], ...],   # runner-ups, same order
   "staple": {"word": "nigga", "songs": 250, "uses": 1240, "share": 0.644},
   "staples": [["nigga", 250, 1240], ["bitch", 198, 702], ...],  # up to 25
   "curated": false}

"word" is the signature: recurring across the catalogue and rare among artists
singing in the same language. "staple" is simply the word they say most, once
grammar and ad-libs are set aside, and "staples" the list it heads: the words
said most, each in more than one song, for the artist page's table. A quote's
title is the song's own, without "(Extended Mix)" or " - Live"; a mash-up, or a
remix the artist is credited for, never supplies the quote, because the words
in it are somebody else's. Rarity is judged per language (a small
function-word list tells the language from an artist's most frequent words),
otherwise every Bosnian pronoun would look rare next to the English majority.

and three more keys in stats_json["percentiles"]: question_share,
avg_repetition_ratio, avg_word_length, measured over the whole local table like
the six the importer already stores. A row that lacks those six (one written by
another pipeline, like a hand-curated catalogue) gets them from the same table.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lyricstats.db import normalize_key  # noqa: E402

APP_DB = ROOT / "data" / "lyricstats.db"
SONG_DB = ROOT / "data" / "lrclib" / "_song_stat.db"
TOK_DB = ROOT / "data" / "lrclib" / "_artist_tok.db"
DF_PATH = ROOT / "data" / "_word_df.json"
REVIEWS = ROOT / "data" / "reviews"

MIN_SONGS = 25
MIN_USES_FOR_DF = 5      # a word counts for an artist's document frequency from this many uses
MIN_IDF = 1.0            # words most same-language artists use are not a signature of anyone
EXTRA_PCTL = ("question_share", "avg_repetition_ratio", "avg_word_length")
# The importer's six (scripts/import_lrclib.py PCTL_KEYS); filled only where missing.
BASE_PCTL = ("total_unique_words", "avg_ttr", "avg_wpm", "avg_hook_share",
             "avg_rhyme", "avg_words_per_song")
STAPLES = 25
PATCH_BATCH = 5000

TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
# Ad-libs and onomatopoeia that belong to everyone: syllables that get sung, not said.
# (Distinctive ones — hee, doo, skrrt — are left to the rarity test.)
AD_LIB_RE = re.compile(
    r"^(?:[aeiouy]+h*|(?:la|na|da|dah|ooh|ohh|aah|ah|oh|uh|eh|ey|ay|yeah|yah|yo|mm|hmm|"
    r"ba|bum|whoa|woah|wah|ha|hey|oi|ra|ta|ti|di|du|lo|le|li|nah|yea|ye|wo|wa|ho|oo|"
    r"ai|ya|yu|yi|hi|hu|hah|heh|huh|hum|shh|ssh|tsk|brr|grr)+h?)$"
)
VOWEL_RE = re.compile(r"[aeiouyаеиоуыэюяіїєāáàâäãåéèêëíìîïóòôöõúùûüýÿæøœšžčćđ]")
JUNK_TITLE = ("remaster", "edit", "acoustic", "live", "version", "mix", "demo")

# Function words, a few dozen per language: enough to tell which language an
# artist mostly sings in from their most frequent words, and never a signature.
LANG_WORDS: dict[str, set[str]] = {
    "en": set("the a an and or but if of to in on at by for with as is are was were be been being "
              "i me my mine you your yours he him his she her hers it its we us our ours they them "
              "their theirs this that these those there here where when why how what which who "
              "whom whose will would can could shall should may might must do does did done have "
              "has had having go goes going gone went come comes came coming get gets got getting "
              "gotten let make made making take took taken keep kept give gave given put say said "
              "says saying tell told know knew known think thought feel felt want wanted need "
              "needed see saw seen look looked just only even still yet also very too so such than "
              "then now again away back down up out off over under into from about around through "
              "after before because cause 'cause while till until once ever never always all any "
              "some every each much many more most little few no not nor none don't doesn't didn't "
              "won't can't couldn't wouldn't shouldn't isn't aren't wasn't weren't ain't i'm i've "
              "i'll i'd you're you've you'll you'd he's she's it's we're we've we'll they're they've "
              "they'll that's there's here's what's who's let's gonna wanna gotta gimme lemme yeah "
              "yes oh ah uh well okay ok hey like way thing things something nothing everything "
              "anything someone everyone anyone one ones time times own same other another really "
              "right".split()),
    "bs": set("i je da se ne ti mi na sam za što sve kad ja to si ali kao od samo sa u o me te "
              "još ću će nema znam nije imam ona ovo sad bez ko jer ili dok sto nek nikad moj "
              "moja moje moju tvoj tvoja tvoje tvoju svoj svoja svoje nas vas nam vam ih im njen "
              "njena njegov naš vaš ovaj ova ono onaj taj ta tu tamo ovdje ovde gdje gde kako "
              "zašto zato ako jer pa ni niti čak već tek baš opet uvijek uvek nikada niko neko "
              "nešto ništa sve svi bio bila bilo bili biti budem bude smo ste su sad sada onda "
              "prije pre poslije posle mogu možeš može hoću hoćeš hoće neću nećeš neće nisam nisi "
              "nismo niste nisu imaš ima imamo imate imaju znaš zna znamo znate znaju šta sta "
              "kada zar li bi bih bismo biste neka eto evo ajde hajde daj ma ej hej joj jao "
              "jel jeli šta što čega čemu kome koga koji koja koje kojoj kojem".split()),
    "sc": set("и је да се не ти ми на сам за што све кад ја то си али као од само са у ме те".split()),
    "es": set("que de la el y no en un mi te tu es me se por lo con para una los más si yo como "
              "pero del al las todo mas nada ya sin eres soy está estoy".split()),
    "pt": set("que de não eu você um uma o a em do da é com para se me meu minha mais tudo vou tá "
              "pra sem ele ela nao voce ta te já só isso".split()),
    "fr": set("je tu le la les et pas que de un une des dans ne me te pour qui mais mon ma sur "
              "est on moi toi avec tout j'ai c'est t'as plus vous nous il elle ils elles se ce "
              "cette ces son sa ses leur au aux du en y ou où si comme bien été être avoir".split()),
    "de": set("ich du und die nicht das ist der wir es ein in zu sie mit auf mir dich was wie so "
              "dir mich den sind aber für nur wenn mein kann noch doch schon mal denn dann weil "
              "oder auch immer nie hier dort wo wer warum sich uns euch ihr ihn ihm ihnen sein "
              "seine meine dein deine kein keine alle alles nichts etwas jeder jede hat haben war "
              "waren wird werden muss will soll bin bist seid eine einen einem einer dem des "
              "vom zum zur ins ans bei nach vor über unter durch ohne gegen".split()),
    "it": set("che non di la il mi un per ti è se e come ma sei con una io tu ho più sono del "
              "quando ci le mai così sto già".split()),
    "ru": set("я не и ты в на что как мне а но с меня тебя так все это у за он она мы только нет "
              "да же о по из уже был есть".split()),
    "uk": set("не і я ти в на що як та мені це за але ми з у до так він вона від тільки".split()),
    "tr": set("bir bu ve ben sen de ne gibi da seni beni için çok ama her bana sana yok var o "
              "kadar daha hiç ki artık".split()),
    "pl": set("nie i się to w na że jak z co ja ty mi ci jest tak do o już bo ale tylko za mnie "
              "cię wszystko gdy".split()),
    "nl": set("ik je de het en niet een dat in is van op met jij mij we zo maar wat voor als dan "
              "er ze om te nog".split()),
    "sv": set("jag du och det att inte är en i på som för dig mig vi så men av har med om ett "
              "allt kan".split()),
    "id": set("yang aku kau dan tak ini di ku kamu tidak kita untuk ada itu dengan saya hanya "
              "akan jangan bisa semua".split()),
    "ro": set("și nu că de te mă cu în pe un o eu tu mai ce la e sa ca dar".split()),
}
# More grammar, set aside from signatures and staples but left out of the
# lists above so that telling an artist's language (and the rarity table
# built from it) stays as it was. web/lib/filler.ts carries the same words.
MORE_GRAMMAR: dict[str, set[str]] = {
    "en": set("gon bout 'bout tryna finna imma ima cuz 'em".split()),
    "bs": set("mene tebe zbog nje nju njoj njemu njega njih svaki svaka svako svakog malo "
              "mnom tobom".split()),
    "es": set("qué porque cuando donde dónde cómo quién eso esto esta este ese esa ella ellos "
              "ellas él nosotros usted hasta hay aquí ahí allí así ahora siempre nunca también "
              "muy mucho poco otra otro otros otras cada algo alguien nadie mismo misma entre "
              "desde sobre hacia contra les nos sus tus mis mío mía tuyo tuya conmigo contigo "
              "ser estar fue estás están voy vas vamos van hace hacer quiero quieres quiere "
              "tengo tienes tiene sabes puedo puedes puede ere vamo ver dice digo hago".split()),
    "pt": set("porque quando onde como quem isso isto essa esse esta este aqui agora sempre "
              "nunca também muito pouco outra outro cada algo alguém ninguém mesmo entre desde "
              "sobre nos seu sua seus suas teu tua comigo contigo sou ser estar foi são somos "
              "estão tô vai vamos vão faz fazer quero quer sei sabe tem tenho ter vem".split()),
    "de": set("aus von mehr hab habe hast hatte hätte kommt komm kommen gehen geht geh ganz gar "
              "sehr viel viele wieder nun jetzt heute bis als dies diese dieser dieses ihre "
              "unser unsere sag sagen sagt weiß weißt gibt lass lassen machen macht mach "
              "willst kannst können könnte musst müssen würde wär wäre sei selbst hin weg "
              "zurück nein".split()),
    "it": set("cosa perché ancora sempre niente tutto tutti questo questa quello quella anche "
              "dopo prima voglio vuoi vuole sai posso puoi può hai siamo siete stato stata mio "
              "mia tuo tua suo sua nostro loro lei lui noi voi cui ogni poi qui qua".split()),
}
ANY_FUNCTION_WORD: set[str] = set().union(*LANG_WORDS.values(), *MORE_GRAMMAR.values())
SCRIPTS = (
    ("cjk", re.compile(r"[぀-ヿ㐀-鿿가-힯]")),
    ("ar", re.compile(r"[؀-ۿ]")),
    ("he", re.compile(r"[֐-׿]")),
    ("el", re.compile(r"[Ͱ-Ͽ]")),
    ("th", re.compile(r"[฀-๿]")),
    ("hi", re.compile(r"[ऀ-ॿ]")),
    ("cy", re.compile(r"[Ѐ-ӿ]")),
)


def classify(top_words: list[str]) -> str:
    """The language an artist mostly sings in, from their most frequent words."""
    for tag, rx in SCRIPTS:
        if sum(1 for w in top_words if rx.search(w)) >= len(top_words) / 2:
            if tag != "cy":
                return tag
            break
    best, hits = "xx", 4
    for lang, words in LANG_WORDS.items():
        h = sum(1 for w in top_words if w in words)
        if h > hits:
            best, hits = lang, h
    return best


def adlib(w: str) -> bool:
    if AD_LIB_RE.match(w):
        return True
    if len(w) >= 4 and len(set(w)) <= 2:
        return True
    if w.isascii() and not VOWEL_RE.search(w):
        return True
    return False


def clean_title(title: str) -> str:
    """The importer's title cleaning, so catalogue titles match the raw rows."""
    if not title:
        return ""
    orig = title
    parts = title.split(" - ")
    if len(parts) > 1 and any(k in parts[-1].lower() for k in JUNK_TITLE):
        title = " - ".join(parts[:-1])

    def keep_feat(m: re.Match) -> str:
        return m.group(0) if re.search(r"\b(feat\.?|ft\.?|featuring)\b", m.group(0), re.I) else ""

    title = re.sub(r"\([^)]*\)|\[[^\]]*\]", keep_feat, title).strip()
    return title or orig


def decode(toks: str) -> dict[str, int]:
    p = toks.split()
    return {p[i]: int(p[i + 1]) for i in range(0, len(p) - 1, 2)}


def name_tokens(display: str) -> set[str]:
    s = unicodedata.normalize("NFKD", display.lower())
    return set(TOKEN_RE.findall(s)) | set(TOKEN_RE.findall(display.lower()))


# ── document frequency ───────────────────────────────────────────────────────


def build_df() -> None:
    """Per language: in how many artists' catalogues each word is used ≥ 5 times."""
    t0 = time.time()
    conn = sqlite3.connect(f"file:{TOK_DB}?mode=ro", uri=True)
    df: dict[str, Counter[str]] = defaultdict(Counter)
    langs: Counter[str] = Counter()
    n = 0
    for (toks,) in conn.execute("SELECT toks FROM artist_tok"):
        p = toks.split()
        it = iter(p)
        pairs = [(w, c) for w, c in zip(it, it)]
        # the 30 most-used words say which language this is
        top = [w for w, _c in sorted(pairs, key=lambda x: -int(x[1]))[:30]]
        lang = classify(top)
        langs[lang] += 1
        # counts are decimal strings; "≥ 5" is two digits or a single digit ≥ '5'
        df[lang].update(w for w, c in pairs if len(c) > 1 or c >= "5")
        n += 1
        if n % 25_000 == 0:
            print(f"  …{n:,} artists, {dict(langs.most_common(6))}", flush=True)
    conn.close()
    kept = {lang: {w: c for w, c in cnt.items() if c >= 2} for lang, cnt in df.items()}
    DF_PATH.write_text(json.dumps({"artists": n, "min_uses": MIN_USES_FOR_DF, "langs": langs,
                                   "df": kept}, ensure_ascii=False))
    print(f"df: {n:,} artists in {len(langs)} languages {dict(langs.most_common(8))}, "
          f"{sum(map(len, kept.values())):,} (lang, word) pairs, "
          f"{DF_PATH.stat().st_size / 1e6:.0f} MB in {time.time() - t0:.0f}s")


class DF:
    def __init__(self, path: Path = DF_PATH):
        if not path.exists():
            sys.exit(f"{path} missing: run with --df first")
        d = json.loads(path.read_text())
        self.langs: dict[str, int] = d["langs"]
        self.df: dict[str, dict[str, int]] = d["df"]
        self.artists: int = d["artists"]

    def idf(self, lang: str, w: str) -> float:
        n = self.langs.get(lang) or self.artists
        return math.log((n + 1) / (self.df.get(lang, {}).get(w, 0) + 1))

    def share(self, lang: str, w: str) -> float:
        n = self.langs.get(lang) or self.artists
        return self.df.get(lang, {}).get(w, 0) / n


def function_word(lang: str, w: str, df: DF) -> bool:
    """Grammar, not vocabulary: on the language's list, or, for a language
    without one, used by most of its artists."""
    if w in ANY_FUNCTION_WORD:
        return True
    if lang in LANG_WORDS:
        return False
    return df.share(lang, w) >= 0.5


def foreign(lang: str, w: str, df: DF) -> bool:
    """A word that belongs to another language's artists far more than to
    this one's: a mis-filed song's vocabulary, not a signature."""
    mine = df.share(lang, w)
    home, best = lang, mine
    for other in df.langs:
        if other != lang:
            s = df.share(other, w)
            if s > best:
                home, best = other, s
    return home != lang and best >= 0.02 and mine < 0.003


# ── per-artist rows ──────────────────────────────────────────────────────────


class SongRows:
    """The per-song rows of one artist, decoded lazily and once."""

    def __init__(self, rows: list[tuple]):
        self.rows = rows  # (title, wc, toks, top_line, top_line_n)
        self._cnt: dict[int, dict[str, int]] = {}

    def counts(self, i: int) -> dict[str, int]:
        c = self._cnt.get(i)
        if c is None:
            c = self._cnt[i] = decode(self.rows[i][2])
        return c

    def pick(self, titles: list[tuple[str, int | None]]) -> list[int]:
        """One row per catalogue title: the same title key, the same word count if possible."""
        wanted: dict[str, int | None] = {}
        for title, wc in titles:
            for key in (normalize_key(title), normalize_key(clean_title(title))):
                if key and key not in wanted:
                    wanted[key] = wc
        picked: dict[str, int] = {}
        for i, (title, wc, _toks, _tl, _tln) in enumerate(self.rows):
            for key in (normalize_key(title), normalize_key(clean_title(title))):
                if key not in wanted:
                    continue
                if key not in picked or (wc == wanted[key] and self.rows[picked[key]][1] != wc):
                    picked[key] = i
                break
        return sorted(set(picked.values()))


def fetch_rows(song: sqlite3.Connection, name: str, gkey: str) -> SongRows:
    seen: set[int] = set()
    rows: list[tuple] = []
    for sql, arg in (("gkey = ?", gkey), ("akey = ?", name)):
        for rowid, *rest in song.execute(
            f"SELECT rowid, title, wc, toks, top_line, top_line_n FROM song_stat WHERE {sql}", (arg,)
        ):
            if rowid not in seen:
                seen.add(rowid)
                rows.append(tuple(rest))
    return SongRows(rows)


# ── the signature ────────────────────────────────────────────────────────────


JUNK_QUOTE_TITLE = re.compile(r"\b(vs\.?|remix|mix|mashup|megamix|medley|karaoke|live|edit|version)\b", re.I)
MASH_UP = re.compile(r"\b(vs\.?|mashup|megamix|medley)\b", re.I)
VERSION_WORDS = re.compile(
    r"\b(remix(?:ed)?|mix|version|edit|live|session|remaster(?:ed)?|demo|acoustic|extended|"
    r"radio|karaoke|instrumental|unplugged|sped up|slowed|rework|dub|bootleg|vip)\b", re.I)
VERSION_TAIL = re.compile(
    r"^live\b|\b(remix(?:ed)?|mix|version|edit|session|remaster(?:ed)?|demo|acoustic|rework|"
    r"dub|bootleg)$", re.I)


def version_clauses(title: str) -> list[str]:
    """The parts of a title that name a version: "(Extended Mix)", " - Live"."""
    out = [m.group(0) for m in re.finditer(r"[(\[][^)\]]*[)\]]", title) if VERSION_WORDS.search(m.group(0))]
    parts = title.split(" - ")
    if len(parts) > 1 and VERSION_TAIL.search(parts[-1].strip()):
        out.append(parts[-1])
    return out


def display_title(title: str) -> str:
    """The song's own title, without the version it was taken from."""
    t = title
    for clause in version_clauses(title):
        t = t.replace(" - " + clause, "") if not clause.startswith(("(", "[")) else t.replace(clause, "")
    t = re.sub(r"\s{2,}", " ", t).strip(" -")
    return t or title


def hook_quote(lines: list[tuple[int, str, str]], own: set[str] = frozenset()) -> dict | None:
    """The best hook line among those that carry the word.

    A mash-up, or a remix credited to the artist (`own` holds their name's
    words), is skipped: the words in it belong to whoever sang the original.
    Live takes and other versions count, below any studio recording, and the
    quote names the song rather than the version.
    """
    best, best_score = None, -math.inf
    for times, line, title in lines:
        n = len(line.split())
        if n < 3 or n > 16 or line.startswith("[") or line.isupper():
            continue
        if MASH_UP.search(title):
            continue
        clauses = version_clauses(title)
        if own and any(own & set(TOKEN_RE.findall(c.lower())) for c in clauses):
            continue
        score = times + (4 if 5 <= n <= 12 else 0) + min(n, 8) / 10
        if JUNK_QUOTE_TITLE.search(title):
            score -= 1000  # a live take or a remix only when nothing else carries the word
        if score > best_score:
            best, best_score = {"line": line, "title": display_title(title), "times": times}, score
    return best


def signature(display: str, rows: SongRows, idx: list[int], df: DF,
              *, curated: dict | None = None, show: int = 0) -> dict | None:
    n = len(idx)
    if n < 3:
        return None
    spread: Counter[str] = Counter()
    uses: Counter[str] = Counter()
    lines: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for i in idx:
        cnt = rows.counts(i)
        spread.update(cnt.keys())
        for w, c in cnt.items():
            uses[w] += c
        title, _wc, _toks, tl, tln = rows.rows[i]
        if tl and tln and tln >= 3:
            for w in set(TOKEN_RE.findall(tl.lower())):
                lines[w].append((tln, tl, title))

    lang = classify([w for w, _c in uses.most_common(30)])
    forbidden = name_tokens(display)
    own = {w for w in forbidden if len(w) >= 3 and not VERSION_WORDS.fullmatch(w)}
    floor = max(3, math.ceil(0.06 * n))

    def usable(w: str) -> bool:
        return (len(w) >= 3 and "'" not in w and "’" not in w and w not in forbidden
                and not adlib(w) and not function_word(lang, w, df) and not foreign(lang, w, df))

    # The staple: the word they say most, of the words that carry meaning,
    # provided it turns up in a tenth of the catalogue.
    staple = None
    for w, u in uses.most_common(400):
        if spread[w] >= max(3, math.ceil(0.1 * n)) and usable(w):
            staple = {"word": w, "songs": spread[w], "uses": u, "share": round(spread[w] / n, 3)}
            break
    # The table under it: the words said most, each in more than one song so
    # that one chant does not make a staple.
    staples = [[w, spread[w], u] for w, u in uses.most_common(800)
               if spread[w] >= max(2, math.ceil(0.03 * n)) and usable(w)][:STAPLES]

    # The signature: recurrence across the catalogue, weighted by how much
    # rarer the word is among artists of the same language, with a nudge for
    # how heavily it is used.
    cands: list[tuple[float, str]] = []
    for w, sp in spread.items():
        if sp < floor or uses[w] < 10 or not usable(w):
            continue
        idf = df.idf(lang, w)
        if idf < MIN_IDF:
            continue
        cands.append(((sp / n) * idf ** 2 * math.log(1 + uses[w]), w))
    cands.sort(reverse=True)
    if show:
        print(f"## {display} [{lang}]: {n} songs, {len(cands)} candidates; "
              f"staple {staple['word'] if staple else '-'} "
              f"({staple['songs']} songs, {staple['uses']} uses)" if staple else "")
        for score, w in cands[:show]:
            q = hook_quote(lines.get(w, []), own)
            print(f"   {w:16s} {score:6.2f}  in {spread[w]:4d} songs  {uses[w]:5d} uses  "
                  f"share {df.share(lang, w):5.1%} idf {df.idf(lang, w):4.2f}  "
                  f"{q['line'][:58] + ' — ' + q['title'][:24] if q else ''}")
    if not cands and not staple:
        return None

    words = [[w, spread[w], uses[w]] for _s, w in cands[:12]]
    word = cands[0][1] if cands else staple["word"]
    quote = hook_quote(lines.get(word, []), own)
    is_curated = False
    if curated and curated.get("word") and spread.get(curated["word"], 0) >= 1:
        cw = curated["word"]
        is_curated = True
        word = cw
        if not any(x[0] == cw for x in words):
            words.insert(0, [cw, spread[cw], uses[cw]])
        else:
            words.sort(key=lambda x: x[0] != cw)
        cq = curated.get("quote")
        ck = normalize_key(cq["song_title"]) if cq and cq.get("song_title") else ""
        if ck and any(
            normalize_key(rows.rows[i][0]).startswith(ck) or ck.startswith(normalize_key(rows.rows[i][0]))
            for i in idx
        ):
            quote = {"line": cq["quote"], "title": cq["song_title"], "times": 0}
        else:
            quote = hook_quote(lines.get(cw, []), own)
    return {
        "lang": lang,
        "word": word,
        "songs": spread[word],
        "uses": uses[word],
        "share": round(spread[word] / n, 3),
        "quote": quote,
        "words": words,
        "staple": staple,
        "staples": staples,
        "curated": is_curated,
    }


def load_reviews() -> dict[str, dict]:
    """Hand-curated motifs (data/reviews/*.json) win over the score."""
    out: dict[str, dict] = {}
    if not REVIEWS.exists():
        return out
    for path in REVIEWS.glob("*.json"):
        try:
            r = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        motif = r.get("motif") or {}
        if not motif.get("changed") or not motif.get("word"):
            continue
        key = normalize_key(r.get("display_name") or r.get("artist") or path.stem)
        out[key] = {"word": str(motif["word"]).strip().lower(), "quote": r.get("motif_quote")}
    return out


# ── percentiles ──────────────────────────────────────────────────────────────


def extra_percentiles(app: sqlite3.Connection) -> dict[str, list[float]]:
    dists: dict[str, list[float]] = {}
    for key in EXTRA_PCTL + BASE_PCTL:
        vals = [r[0] for r in app.execute(
            f"SELECT json_extract(stats_json, '$.{key}') FROM artistaggregate") if r[0] is not None]
        dists[key] = sorted(vals)
    return dists


def pctl(dists: dict[str, list[float]], key: str, v: float | None) -> int | None:
    vals = dists.get(key)
    if not vals or v is None:
        return None
    return int(round(100 * bisect.bisect_left(vals, v) / len(vals)))


# ── production ───────────────────────────────────────────────────────────────


def prod_url() -> str:
    """DATABASE_URL from .env.prod, the way scripts/push_aggregates.py reads it."""
    url = os.environ.get("DATABASE_URL")
    env = ROOT / ".env.prod"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("DATABASE_URL="):
                url = line.strip().split("=", 1)[1].split("#", 1)[0].strip().strip("'\"")
    if not url:
        sys.exit("DATABASE_URL not set and not found in .env.prod")
    return url.replace("postgresql+psycopg://", "postgresql://").replace("postgres://", "postgresql://")


def prod_titles() -> dict[str, list[tuple[str, int | None]]]:
    import psycopg

    out: dict[str, list[tuple[str, int | None]]] = {}
    with psycopg.connect(prod_url(), connect_timeout=15) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor(name="titles") as cur:
            cur.itersize = 2000
            cur.execute("SELECT name, songs_json FROM artistaggregate")
            for name, songs_json in cur:
                songs = json.loads(songs_json or "[]")
                out[name] = [(s[0], s[2] if len(s) > 2 else None) for s in songs if s]
    return out


def prod_apply(path: Path) -> None:
    """Merge the patches in batches, vacuuming between them.

    Every update writes a new copy of the row; vacuuming after each batch
    lets the next one reuse the space instead of growing the table by a
    whole copy of itself, which the database's storage cap would not allow.
    """
    import psycopg

    plan = json.loads(path.read_text())
    patches = list(plan["patches"].items())
    print(f"Applying {len(patches):,} patches from {path} …", flush=True)
    total = 0
    with psycopg.connect(prod_url(), connect_timeout=15, autocommit=True) as conn:
        conn.execute("CREATE TEMP TABLE sig_patch (name text PRIMARY KEY, patch text NOT NULL)")
        for start in range(0, len(patches), PATCH_BATCH):
            batch = patches[start:start + PATCH_BATCH]
            with conn.transaction():
                conn.execute("TRUNCATE sig_patch")
                with conn.cursor().copy("COPY sig_patch (name, patch) FROM STDIN") as cp:
                    for name, patch in batch:
                        text = json.dumps(patch, ensure_ascii=False)
                        cp.write_row((name, text.replace("\\u0000", "").replace("\x00", "")))
                # A few stored rows carry NUL escapes from broken submissions,
                # which jsonb refuses; they are dropped before the merge.
                cur = conn.execute(
                    "UPDATE artistaggregate a SET stats_json = "
                    "(replace(a.stats_json, '\\u0000', '')::jsonb || p.patch::jsonb)::text "
                    "FROM sig_patch p WHERE a.name = p.name"
                )
                total += cur.rowcount
            conn.execute("VACUUM artistaggregate")
            size = conn.execute(
                "SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
            print(f"  {min(start + PATCH_BATCH, len(patches)):,}/{len(patches):,} merged, "
                  f"{total:,} rows updated, database {size}", flush=True)
    print("done")


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--df", action="store_true", help="build the document-frequency table and stop")
    ap.add_argument("--min-songs", type=int, default=MIN_SONGS)
    ap.add_argument("--only", action="append", help="artist display name (repeatable)")
    ap.add_argument("--show", type=int, default=0, help="print this many candidates per artist")
    ap.add_argument("--write", action="store_true", help="store signatures + percentiles in the local DB")
    ap.add_argument("--prod-plan", type=Path, help="compute patches for production rows into this file")
    ap.add_argument("--prod-apply", type=Path, help="apply a saved production plan")
    args = ap.parse_args()

    if args.df:
        build_df()
        return
    if args.prod_apply:
        prod_apply(args.prod_apply)
        return

    df = DF()
    reviews = load_reviews()
    app = sqlite3.connect(APP_DB)
    song = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    dists = extra_percentiles(app)

    where, params = "song_count >= ?", [args.min_songs]
    if args.only:
        where = "name IN (%s)" % ",".join("?" * len(args.only))
        params = [n.strip().lower() for n in args.only]
    rows = app.execute(
        f"SELECT id, name, name_key, display_name, song_count, stats_json, songs_json "
        f"FROM artistaggregate WHERE {where} ORDER BY id", params).fetchall()
    print(f"{len(rows):,} artists; df over {df.artists:,} artists in {len(df.langs)} languages",
          flush=True)

    prod: dict[str, list[tuple[str, int | None]]] = {}
    if args.prod_plan:
        t0 = time.time()
        prod = prod_titles()
        print(f"production: {len(prod):,} rows read in {time.time() - t0:.0f}s", flush=True)

    t0 = time.time()
    local_updates: list[tuple[str, int]] = []
    prod_patches: dict[str, dict] = {}
    found = 0
    for k, (rid, name, name_key, display, _count, stats_json, songs_json) in enumerate(rows, 1):
        stats = json.loads(stats_json)
        songs = json.loads(songs_json or "[]")
        titles = [(s[0], s[2] if len(s) > 2 else None) for s in songs if s]
        srows = fetch_rows(song, name, name_key)
        curated = reviews.get(name_key)
        pct = dict(stats.get("percentiles") or {})
        for key in EXTRA_PCTL:
            pct[key] = pctl(dists, key, stats.get(key))
        for key in BASE_PCTL:
            if pct.get(key) is None:
                pct[key] = pctl(dists, key, stats.get(key))

        sig = signature(display, srows, srows.pick(titles), df, curated=curated, show=args.show)
        if sig:
            found += 1
        if args.write:
            stats["signature"] = sig
            stats["percentiles"] = pct
            local_updates.append((json.dumps(stats, ensure_ascii=False), rid))

        if name in prod:
            ptitles = prod[name]
            same = {normalize_key(t) for t, _ in ptitles} == {normalize_key(t) for t, _ in titles}
            psig = sig if same else signature(display, srows, srows.pick(ptitles), df, curated=curated)
            prod_patches[name] = {"signature": psig, "percentiles": pct}

        if k % 1000 == 0:
            print(f"  …{k:,}/{len(rows):,} artists, {found:,} signatures, "
                  f"{(time.time() - t0) / 60:.1f} min", flush=True)
            if args.write and local_updates:
                app.executemany("UPDATE artistaggregate SET stats_json = ? WHERE id = ?", local_updates)
                app.commit()
                local_updates.clear()

    if args.write and local_updates:
        app.executemany("UPDATE artistaggregate SET stats_json = ? WHERE id = ?", local_updates)
        app.commit()
    print(f"{found:,} of {len(rows):,} artists got a signature in {(time.time() - t0) / 60:.1f} min"
          + (" (written)" if args.write else ""))

    if args.prod_plan:
        missing = [n for n in prod if n not in prod_patches]
        args.prod_plan.parent.mkdir(parents=True, exist_ok=True)
        args.prod_plan.write_text(json.dumps(
            {"built": time.strftime("%Y-%m-%d %H:%M"), "patches": prod_patches,
             "unmatched_prod_rows": missing}, ensure_ascii=False))
        print(f"production plan: {len(prod_patches):,} patches, {len(missing):,} prod rows "
              f"without a local aggregate → {args.prod_plan}")


if __name__ == "__main__":
    main()
