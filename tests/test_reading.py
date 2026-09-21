"""The per-song reading: shared by the LRCLIB importer and the API."""

from lyricstats.reading import parse_synced, reading, song_stats

LRC = "\n".join(
    [
        "[00:10.00] one two three",
        "[00:12.00] four five",
        "[00:20.00] six",
        "[00:50.00] seven eight nine ten",
    ]
)

PLAIN = "[Chorus]\nHold on, hold on\nHold on, hold on\nHold on, hold on\nNever let go\nIs it over?\n"


def test_parse_synced_places_the_longest_silence():
    out = parse_synced(LRC, 60.0)
    assert out["first"] == 10.0
    assert out["gap"] == 30.0
    assert out["gap_at"] == 20.0
    assert out["fast15"] == 6  # the 10s–20s window holds 6 words
    assert out["last"] == 50.0
    assert sum(int(x) for x in out["curve"].split(",")) == 10


def test_parse_synced_needs_four_timed_lines():
    assert parse_synced("[00:01.00] a\n[00:02.00] b", 30.0) is None


def test_song_stats_skips_section_headers_and_finds_the_hook():
    st = song_stats("Hold On", PLAIN, None, 120.0)
    assert st["line_count"] == 5
    assert st["wc"] == 18
    assert st["uniq"] == 8
    assert st["once"] == 6
    assert st["top_line"] == "hold on, hold on"
    assert st["top_line_n"] == 3
    assert st["top_line_at"] == [0, 1, 2]
    assert st["hook"] == 0.6
    assert st["rep"] == 0.4
    assert st["drops"] == 6
    assert st["q"] == 0.2
    assert st["wpm"] == 9.0
    assert st["line_words"] == [4, 4, 4, 3, 3]
    assert st["first"] is None


def test_reading_is_the_public_slice_with_a_curve_list():
    r = reading("Hold On", PLAIN, LRC, 60.0)
    assert "cnt" not in r
    assert r["curve"] == [0, 3, 2, 1, 0, 0, 0, 0, 4, 0]
    assert r["duration"] == 60.0
    assert r["gap_at"] == 20.0


TIMED = "\n".join(
    [
        "[00:10.00] Hold on, hold on",
        "[00:12.50] Hold on, hold on",
        "[00:15.00] Hold on, hold on",
        "[00:20.00] Never let go",
        "[00:31.00] Is it over?",
    ]
)


def test_line_times_follow_the_counted_lines():
    r = reading("Hold On", PLAIN, TIMED, 60.0)
    assert r["line_at"] == [10.0, 12.5, 15.0, 20.0, 31.0]
    assert r["drop_at"] == [0, 1, 2]
    assert r["first"] == 10.0


def test_line_times_survive_punctuation_and_an_extra_stamped_line():
    timed = TIMED.replace("Never let go", "never  let go!").replace(
        "[00:20.00]", "[00:18.00] (ad lib)\n[00:20.00]"
    )
    r = reading("Hold On", PLAIN, timed, 60.0)
    assert r["line_at"] == [10.0, 12.5, 15.0, 20.0, 31.0]


def test_line_times_bridge_a_split_line_and_a_respelling():
    plain = "Something evil's lurking in the dark\nUnder the moonlight\nYou see a sight that almost stops your heart\nYou try to scream\nBut terror takes the sound\n"
    timed = "\n".join(
        [
            "[00:10.00] Something evil's lurkin' in the dark",  # respelt
            "[00:14.00] Under the",  # split in two
            "[00:15.00] moonlight",
            "[00:18.00] You see a sight that almost stops your heart",
            "[00:22.00] You try to scream",
            "[00:25.00] But terror takes the sound",
        ]
    )
    r = reading("Thriller", plain, timed, 60.0)
    assert r["line_at"] == [10.0, 14.0, 18.0, 22.0, 25.0]


def test_line_times_are_dropped_when_the_texts_do_not_match():
    r = reading("Hold On", PLAIN, LRC, 60.0)
    assert r["line_at"] is None
    assert r["first"] == 10.0  # the clock still comes from the stamps


def test_reading_refuses_an_empty_text_and_a_libretto():
    assert reading("x", "") is None
    assert reading("x", "word " * 2001) is None
