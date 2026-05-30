"""Edge cases the user can actually hit.

Focused on stats, sampling, parsing, and helpers — the bits where bad
input shouldn't crash the API.
"""

from __future__ import annotations

from lyricstats import stats
from lyricstats.text import all_lines, parse_sections, tokenize


# ─── stats.compute edge cases ──────────────────────────────────────────────


def test_compute_pure_whitespace():
    s = stats.compute("   \n\n\t\n   ")
    assert s.word_count == 0
    assert s.unique_words == 0
    assert s.line_count == 0
    assert s.section_count == 0


def test_compute_only_section_headers_no_content():
    # Section headers but every section is empty — should NOT crash and
    # should report no words.
    lyrics = "[Verse 1]\n\n[Chorus]\n\n[Verse 2]\n"
    s = stats.compute(lyrics)
    assert s.word_count == 0
    assert s.unique_words == 0
    assert s.type_token_ratio == 0
    assert s.section_sequence == []


def test_compute_single_word_song():
    s = stats.compute("yeah")
    assert s.word_count == 1
    assert s.unique_words == 1
    assert s.type_token_ratio == 1.0
    assert s.hapax_count == 1
    assert s.avg_word_length == 4
    assert s.avg_words_per_line == 1
    assert s.section_sequence == ["other"]  # untagged → 'other'


def test_compute_single_repeated_word():
    # 'na na na na na' — minimal vocabulary, max repetition.
    s = stats.compute("na na na na na")
    assert s.word_count == 5
    assert s.unique_words == 1
    assert s.type_token_ratio == 0.2


def test_compute_handles_extreme_unicode():
    # Diacritics, apostrophes, mixed scripts. Should tokenise cleanly,
    # no exceptions, and lowercasing must preserve combining marks.
    lyrics = "Šta će biti, čovječe — ne znaš ti.\nĐani, đe si bio sinoć?"
    s = stats.compute(lyrics)
    assert s.word_count > 0
    # Critical: these must survive as distinct tokens, not get split or stripped
    joined = " ".join(w for w, _ in s.top_words)
    assert "ćeš" in joined or "će" in joined or "đe" in joined


def test_compute_with_emoji_only_line():
    # Emoji/symbols don't count as words, but shouldn't crash the parser.
    s = stats.compute("hold on\n🎤🎤🎤\nlet me go")
    assert s.word_count > 0
    # Line count is content lines, emoji-only line is still a line because
    # parse_sections only drops empty/header lines, not symbol-only.
    assert s.line_count >= 2


def test_compute_extremely_long_line():
    # Stress test: 5000 words on one line.
    line = " ".join(["word"] * 5000)
    s = stats.compute(line)
    assert s.word_count == 5000
    assert s.unique_words == 1
    assert s.longest_line_words == 5000


def test_compute_apostrophes_preserve_contractions():
    # "don't", "ain't" should be single tokens, not split.
    s = stats.compute("don't ain't won't y'all")
    assert s.word_count == 4
    assert "don't" in {w for w, _ in s.top_words} or "don’t" in {
        w for w, _ in s.top_words
    }


def test_compute_top_words_no_stop_does_not_overflow_when_few_content_words():
    # If almost every token is a stopword, top_words_no_stop should still
    # be a valid (possibly short or empty) list and not raise.
    s = stats.compute("the the the the and and and a a")
    assert isinstance(s.top_words_no_stop, list)
    assert len(s.top_words_no_stop) <= 10


# ─── stats.aggregate edge cases ────────────────────────────────────────────


def test_aggregate_with_empty_song_list():
    a = stats.aggregate([])
    assert a.song_count == 0
    assert a.total_words == 0
    assert a.avg_ttr == 0.0
    assert a.longest_song == {}


def test_aggregate_filters_out_zero_word_songs():
    # An empty-lyrics song shouldn't crash and shouldn't count in averages
    pairs = [("Real Song", "hello world hello"), ("Instrumental", "")]
    a = stats.aggregate(pairs)
    assert a.song_count == 1  # the empty one was filtered
    assert a.total_words == 3


def test_aggregate_handles_all_identical_songs():
    pairs = [("A", "same words same"), ("B", "same words same")]
    a = stats.aggregate(pairs)
    assert a.song_count == 2
    # Same content → same longest, shortest, richest
    assert a.longest_song["words"] == a.shortest_song["words"]


# ─── text parsing edge cases ───────────────────────────────────────────────


def test_parse_sections_unicode_section_header():
    lyrics = "[Refren: Maya Berović]\nNa rukama tvojim\n[Stih 2: Jala]\nbar"
    secs = parse_sections(lyrics)
    assert [s.kind for s in secs] == ["chorus", "verse"]


def test_parse_sections_drops_question_mark_placeholder():
    lyrics = "[Verse 1]\nline\n[?]\nanother"
    lines = all_lines(lyrics)
    assert "[?]" not in lines
    assert "line" in lines
    assert "another" in lines


def test_tokenize_strips_punctuation_around_words():
    assert tokenize("Hello, world! Yo... what's up?") == [
        "hello",
        "world",
        "yo",
        "what's",
        "up",
    ]


def test_tokenize_ignores_pure_numbers():
    # We tokenise letter-runs only; 2024 should not become a token.
    toks = tokenize("year 2024 was wild")
    assert "2024" not in toks
    assert "year" in toks and "wild" in toks


# ─── backend sampling ──────────────────────────────────────────────────────


def test_pick_n_deterministic_for_same_seed():
    from backend.main import _pick_n

    class Fake:
        def __init__(self, id_: int, title: str):
            self.id = id_
            self.title = title

    songs = [Fake(i, f"song-{i}") for i in range(20)]
    a = _pick_n(songs, 5, "artist|5|alpha")
    b = _pick_n(songs, 5, "artist|5|alpha")
    assert [s.id for s in a] == [s.id for s in b]


def test_pick_n_different_seed_gives_different_sample():
    from backend.main import _pick_n

    class Fake:
        def __init__(self, id_: int, title: str):
            self.id = id_
            self.title = title

    songs = [Fake(i, f"song-{i}") for i in range(40)]
    a = _pick_n(songs, 5, "artist|5|alpha")
    b = _pick_n(songs, 5, "artist|5|beta")
    # Overwhelmingly likely to differ for 5-of-40 with two distinct seeds
    assert {s.id for s in a} != {s.id for s in b}


def test_pick_n_when_population_equals_n_still_shuffles():
    from backend.main import _pick_n

    class Fake:
        def __init__(self, id_: int, title: str):
            self.id = id_
            self.title = title

    songs = [Fake(i, f"song-{i}") for i in range(5)]
    # Pick all 5 — result must be a permutation, not the input order.
    a = _pick_n(songs, 5, "artist|5|x")
    b = _pick_n(songs, 5, "artist|5|y")
    assert sorted(s.id for s in a) == [0, 1, 2, 3, 4]
    # Different seed → different order with high probability
    assert [s.id for s in a] != [s.id for s in b] or len(set([0, 1, 2, 3, 4])) == 1
