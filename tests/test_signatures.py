"""The signature word (scripts/build_signatures.py): a word that is theirs,
never an ad-lib, a spelling of grammar, a section label or a credit line."""

from __future__ import annotations

import scripts.import_lrclib  # noqa: F401  (puts scripts/ on the path)
import build_signatures as bs


class _DF(bs.DF):
    """Document frequencies without the table: every word rare, "love" common."""

    def __init__(self):
        self.langs = {"en": 1000}
        self.df = {"en": {"love": 900, "the": 1000, "you": 1000}}
        self.artists = 1000


def _toks(words: dict[str, int]) -> str:
    return " ".join(f"{w} {c}" for w, c in words.items())


def test_sung_vocables_and_interjections_are_ad_libs():
    for w in ("hoo", "hee", "woo", "whoo", "doo", "hoooo", "heehee", "wow", "ugh", "mwah", "sheesh"):
        assert bs.adlib(w), w
    for w in ("hoodoo", "wee", "boo", "home", "hold", "deep", "moon"):
        assert not bs.adlib(w), w


def test_english_spellings_of_grammar_count_only_for_english_singers():
    df = _DF()
    assert bs.function_word("en", "cos", df) and bs.function_word("en", "nothin", df)
    assert not bs.function_word("ro", "cos", df)  # Romanian "cos" is a word
    assert bs.function_word("es", "though", df)   # English grammar, any language


def test_a_broken_indic_word_is_read_back_whole_from_a_hook_line():
    whole = bs.whole_words(["मेरा आसमाँ जल गया रे", "जले बैरी मन, सुलगे बदन"])
    assert whole["आसम"] == "आसमाँ"  # the tokenizer cut it at the vowel sign
    assert whole["बदन"] == "बदन"    # no vowel sign: whole already


def test_the_signature_skips_ad_libs_labels_and_credit_footers():
    rows = []
    for i in range(20):
        words = {"love": 3, "hoo": 6, "chorus": 2, "difford": 1, "you": 5}
        if i < 12:
            words["river"] = 4
        rows.append((f"Song {i}", 100, _toks(words), "down by the river" if i < 12 else "", 3))
    sig = bs.signature("Squeeze", bs.SongRows(rows), list(range(20)), _DF())
    assert sig["word"] == "river"
    assert not {"hoo", "chorus", "difford"} & {w for w, *_ in sig["words"]}
    assert not {"hoo", "chorus", "difford"} & {w for w, *_ in sig["staples"]}
