"""Tests for the dataset import pipeline (scripts/import_dataset.py).

Pure-function coverage of non-song filtering, token (de)serialisation, the lean
per-song stat extractor, and per-artist folding (merge + filter + min-songs).
"""

from __future__ import annotations

import json
from collections import Counter

import scripts.import_dataset as imp


# ── non-song filtering ───────────────────────────────────────────────────────


def test_is_non_song_by_title():
    assert imp.is_non_song("Drake  DJ Semtex Interview")
    assert imp.is_non_song("Lemonade Film Script")
    assert imp.is_non_song("Beyoncé VMAs 2014")
    assert imp.is_non_song("Jay-Z Discography")
    assert imp.is_non_song("Grammy Acceptance Speech")


def test_is_non_song_keeps_real_songs():
    assert not imp.is_non_song("Lemon Pepper Freestyle")
    assert not imp.is_non_song("All Me")
    assert not imp.is_non_song("Get Me Bodied Timbaland Remix")


def test_is_non_song_word_cap():
    assert imp.is_non_song("A Totally Normal Title", 5000)      # too long → non-song
    assert not imp.is_non_song("A Totally Normal Title", 300)   # song-length → kept


def test_is_non_song_new_prose_phrases():
    assert imp.is_non_song("The Future of Music Is a Love Story")
    assert imp.is_non_song("Famous Lyric Phone Conversation")
    assert imp.is_non_song("First Phone Call With Tim McGraw")
    assert imp.is_non_song("Break the Simulation Philosophy Book")


def test_is_non_song_guard_keeps_song_types():
    # The song-type guard runs first, so it beats a blocklist word and the
    # length cap — a freestyle/interlude is always a song.
    assert not imp.is_non_song("Grammy Family Freestyle")            # "grammy" in blocklist
    assert not imp.is_non_song("Phone Conversation Interlude")       # new prose phrase
    assert not imp.is_non_song("An Extremely Long Freestyle", 9000)  # beats length cap


class _StubClf:
    """Minimal classifier stand-in for the optional clf arg of is_non_song."""

    def __init__(self, junk: bool) -> None:
        self._junk = junk

    def is_junk(self, title: str) -> bool:
        return self._junk


def test_is_non_song_consults_classifier_when_blocklist_misses():
    # A title the deterministic blocklist doesn't catch:
    assert not imp.is_non_song("Some Obscure Title")                     # no clf → kept
    assert imp.is_non_song("Some Obscure Title", clf=_StubClf(True))     # clf flags → dropped
    assert not imp.is_non_song("Some Obscure Title", clf=_StubClf(False))


def test_is_non_song_guard_beats_classifier():
    # Even if the model flags it, the freestyle guard keeps it.
    assert not imp.is_non_song("Mystery Freestyle", clf=_StubClf(True))


# ── token (de)serialisation ──────────────────────────────────────────────────


def test_encode_decode_tokens_roundtrip():
    c = Counter({"love": 5, "you": 3, "night": 1})
    assert imp.decode_tokens(imp.encode_tokens(c)) == c


def test_decode_tokens_empty():
    assert imp.decode_tokens("") == Counter()


# ── lean per-song stats ──────────────────────────────────────────────────────


def test_lean_song_stats_basic():
    lyrics = "[Chorus]\nla la la\nla la la\n[Verse 1]\nhello world goodbye world"
    st = imp.lean_song_stats(lyrics)
    assert st is not None
    assert st["wc"] > 0
    assert st["has_sec"] == 1                 # [Chorus]/[Verse] present
    assert 0.0 <= st["ttr"] <= 1.0
    assert st["rep"] > 0                       # repeated "la la la" lines


def test_lean_song_stats_untagged_has_no_sections():
    st = imp.lean_song_stats("just some plain words here with no tags")
    assert st is not None
    assert st["has_sec"] == 0


def test_lean_song_stats_empty_returns_none():
    assert imp.lean_song_stats("") is None
    assert imp.lean_song_stats("\n\n   \n") is None


# ── per-artist folding ───────────────────────────────────────────────────────


def _row(artist, title, wc, toks="hello 2 world 1"):
    return {"artist": artist, "title": title, "year": 2020, "wc": wc,
            "uniq": 2, "ttr": 0.5, "chorus": 0.2, "rep": 0.1,
            "has_sec": 1, "toks": toks}


def test_build_aggregate_merges_casing_and_drops_non_songs():
    rows = [_row("Drake", f"Song {i}", 200) for i in range(16)]
    rows.append(_row("DRAKE", "Casing Variant", 200))     # merges into Drake
    rows.append(_row("Drake", "Long Interview", 5000))    # dropped (title + length)

    agg = imp._build_aggregate(rows, min_songs=15, top_n=10)
    assert agg is not None
    assert agg.display_name == "Drake"                    # most common casing wins
    assert agg.song_count == 17                           # interview excluded
    titles = [s[0] for s in json.loads(agg.songs_json)]
    assert "Long Interview" not in titles


def test_build_aggregate_below_min_songs_returns_none():
    rows = [_row("X", f"S{i}", 100) for i in range(5)]
    assert imp._build_aggregate(rows, min_songs=15, top_n=10) is None


def test_build_aggregate_songs_sorted_desc_by_words():
    rows = [_row("A", "short", 50), _row("A", "long", 900), _row("A", "mid", 400)]
    rows += [_row("A", f"pad{i}", 100) for i in range(15)]
    agg = imp._build_aggregate(rows, min_songs=15, top_n=10)
    songs = json.loads(agg.songs_json)
    word_counts = [s[2] for s in songs]
    assert word_counts == sorted(word_counts, reverse=True)
