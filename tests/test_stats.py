from lyricstats.stats import aggregate, compute


SAMPLE = """[Verse 1]
I walk alone through the city night
Streetlights flicker like a dying star
Every step a story untold

[Chorus]
Hold on, hold on, don't let go
Hold on, hold on, don't let go

[Verse 2]
Memories fade but the music stays
Echoes loud in the silent room

[Chorus]
Hold on, hold on, don't let go
Hold on, hold on, don't let go
"""


def test_compute_basic_counts():
    s = compute(SAMPLE)
    assert s.word_count > 0
    assert s.unique_words > 0
    assert s.unique_words <= s.word_count
    assert s.line_count == 9  # 3 + 2 + 2 + 2
    assert s.section_count == 4


def test_compute_vocab_richness_in_unit_range():
    s = compute(SAMPLE)
    assert 0.0 < s.type_token_ratio <= 1.0


def test_compute_detects_chorus_share():
    s = compute(SAMPLE)
    # 4 of 9 lines are chorus
    assert 0.4 < s.chorus_ratio < 0.5


def test_compute_repetition_ratio_nonzero_for_repeated_chorus():
    s = compute(SAMPLE)
    assert s.repetition_ratio > 0


def test_compute_top_words_excludes_stopwords_in_filtered_list():
    s = compute(SAMPLE)
    filtered = {w for w, _ in s.top_words_no_stop}
    assert "the" not in filtered
    assert "on" not in filtered  # 'on' is heavily repeated but it's a stopword
    assert "hold" in filtered


def test_compute_empty_lyrics_returns_zeros():
    s = compute("")
    assert s.word_count == 0
    assert s.unique_words == 0


def test_aggregate_over_multiple_songs():
    a = aggregate([("Song A", SAMPLE), ("Song B", SAMPLE)])
    assert a.song_count == 2
    assert a.total_words == compute(SAMPLE).word_count * 2
    assert a.longest_song["words"] == compute(SAMPLE).word_count


def test_aggregate_excludes_short_and_demo_songs_from_highlights():
    long_song = "Normal Song Name\n" + "hello world " * 100
    short_song = "Short Song Name\n" + "hello world " * 20
    demo_song = "Some Track (Demo)\n" + "unique word " * 150

    a = aggregate(
        [("Long Song", long_song), ("Short Song", short_song), ("Demo Song (Demo)", demo_song)]
    )

    assert a.shortest_song["title"] == "Long Song"
    assert a.richest_song["title"] == "Long Song"
    assert a.longest_song["title"] == "Long Song"


def test_aggregate_fallback_when_no_songs_eligible_for_highlights():
    short_song_1 = "Short 1\n" + "hello world " * 20
    short_song_2 = "Short 2\n" + "hello world " * 30

    a = aggregate(
        [
            ("Short 1", short_song_1),
            ("Short 2", short_song_2),
        ]
    )

    assert a.longest_song["title"] == "Short 2"
    assert a.shortest_song["title"] == "Short 1"
