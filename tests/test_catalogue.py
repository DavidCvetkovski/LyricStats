"""The catalogue cleaning (scripts/catalogue.py): one version per song, only
the artist's own songs, every decision with a reason."""

from __future__ import annotations

from collections import Counter

import scripts.import_lrclib  # noqa: F401  (puts scripts/ on the path for catalogue)
from catalogue import clean, display_title, other_artist_named, title_key

SONG_A = "romeo juliet baby marry castle princess scarlet letter balcony father "
SONG_B = "band aids bullet holes mad scars blood trouble friends enemies "
SONG_C = "midnights james dean daydream tshirt lipstick classic style skirt "


def _rows(spec, artist="Taylor Swift"):
    """spec: [(title, lyrics, repeats, wc)] → rows + shared Counters."""
    rows, toks = [], []
    for title, lyrics, repeats, wc in spec:
        c = Counter(lyrics.split())
        for _ in range(repeats):
            rows.append({"title": title, "artist": artist, "wc": wc, "has_synced": 1, "toks": ""})
            toks.append(c)
    return rows, toks


def _kept(songs):
    return sorted(s.title for s in songs if s.reason is None)


def test_titles_lose_track_numbers_credits_and_download_junk_but_not_their_numbers():
    a = "michael jackson"
    for raw in ["01 Billie Jean", "1-01 Billie Jean", "B2 Billie Jean", "175.Billie Jean",
                "Michael Jackson - Billie Jean", "13-michael_jackson-billie_jean",
                "Billie Jean - SpotubeDL.com", "Billie Jean 2005", "Billie Jean (Single Version)"]:
        assert title_key(raw, a) == "billie jean", raw
    for keep in ["7 Rings", "99 Problems", "22", "1979"]:
        assert display_title(keep, a) == keep
    # a credit needs a separator: "Michael Jackson x Mark Ronson" is a different track
    assert title_key("Michael Jackson x Mark Ronson: Diamonds", a).startswith("michael jackson")


def test_uploads_of_one_song_merge_and_the_most_uploaded_transcription_stands_for_it():
    rows, toks = _rows([
        ("Love Story", SONG_A * 3, 30, 400),
        ("Love Story (Extended Mix)", SONG_A * 5, 2, 700),
        ("05 Love Story", SONG_A * 3, 4, 400),
        ("Lvoe Story", SONG_A * 3, 1, 400),  # typo: same words
    ])
    songs = clean(rows, toks, display="Taylor Swift", gkey="taylorswift")
    kept = [s for s in songs if s.reason is None]
    assert len(kept) == 1
    assert kept[0].title == "Love Story"
    assert rows[kept[0].rep]["wc"] == 400  # not the extended mix
    assert kept[0].uploads == 37


def test_distinct_songs_stay_distinct():
    rows, toks = _rows([("Love Story", SONG_A, 3, 50), ("Bad Blood", SONG_B, 3, 50), ("Style", SONG_C, 3, 50)])
    assert _kept(clean(rows, toks, display="Taylor Swift", gkey="taylorswift")) == ["Bad Blood", "Love Story", "Style"]


def test_medleys_megamixes_and_own_remixes_are_set_aside():
    rows, toks = _rows([
        ("Love Story", SONG_A, 5, 50),
        ("Bad Blood", SONG_B, 5, 50),
        ("Love Story / Bad Blood", SONG_A + "zzz " * 3 + SONG_B, 1, 100),
        ("Greatest Hits Megamix", SONG_C + "yyy " * 9, 1, 60),
        ("Other Song (Taylor Swift Remix)", "entirely different words here about nothing much at all", 2, 60),
        ("Style (Taylor's Version)", SONG_C, 3, 50),  # her own re-recording, not a remix
    ])
    songs = {s.title: s.reason for s in clean(rows, toks, display="Taylor Swift", gkey="taylorswift")}
    assert songs["Love Story"] is None and songs["Bad Blood"] is None
    assert songs["Style"] is None
    assert songs["Love Story / Bad Blood"] == "medley of songs listed separately"
    assert songs["Greatest Hits Megamix"] == "medley or megamix"
    assert songs["Other Song"] == "their remix of another artist's song"


def test_a_stray_upload_that_lives_elsewhere_is_set_aside_but_a_song_of_their_own_is_not():
    rows, toks = _rows([("Party Animal", SONG_B, 1, 50), ("Levels", SONG_A, 40, 50)], artist="Avicii")

    def owners(fp):
        if "bullet" in fp:  # Party Animal: 60 uploads under R.I.O.
            return [("rio", 60, "Party Animal"), ("avicii", 1, "Party Animal")]
        return [("avicii", 40, "Levels"), ("someoneelse", 200, "Levels")]  # covered a lot, still his

    songs = {s.title: s.reason for s in clean(rows, toks, display="Avicii", gkey="avicii", owners=owners)}
    assert songs["Party Animal"] == "belongs to another artist"
    assert songs["Levels"] is None


def test_a_famous_cover_stays_though_one_upload_names_the_original_artist():
    rows, toks = _rows([("Hurt", SONG_A, 30, 50), ("Hurt (Nine Inch Nails Cover)", SONG_A, 1, 50),
                        ("Broken Wings (Mr. Mister)", SONG_B, 1, 50)], artist="Johnny Cash")

    def owners(fp):
        if "romeo" in fp:
            return [("nineinchnails", 70, "Hurt"), ("johnnycash", 31, "Hurt")]
        return [("mrmister", 40, "Broken Wings")]

    songs = {s.title: s for s in clean(rows, toks, display="Johnny Cash", gkey="johnnycash", owners=owners)}
    assert songs["Hurt"].reason is None
    assert "more uploads elsewhere" in songs["Hurt"].flags
    assert songs["Broken Wings (Mr. Mister)"].reason == "belongs to another artist"


def test_a_title_crediting_another_artist_needs_that_artist_to_hold_the_song():
    uploads = {"cultureclub": 5000, "love": 3000, "metallica": 9000}.get
    assert other_artist_named("Culture Club / Time", "queen", lambda k: uploads(k) or 0, {"cultureclub"}) == "Culture Club"
    assert other_artist_named("Sad But True (Metallica)", "queen", lambda k: uploads(k) or 0, {"metallica"}) == "Metallica"
    # "Love" is a band, but here it is a word; "Nightmare" a subtitle
    assert other_artist_named("Love - Part 2", "queen", lambda k: uploads(k) or 0, set()) is None
    assert other_artist_named("Alive (Nightmare)", "kidcudi", lambda k: 5000, {"kidcudi"}) is None
    assert other_artist_named("Crazy in Love (feat. Jay-Z)", "beyonce", lambda k: uploads(k) or 0, set()) is None


def test_a_review_drops_keeps_or_lists_the_whole_catalogue():
    rows, toks = _rows([("Love Story", SONG_A, 5, 50), ("Bad Blood", SONG_B, 5, 50), ("Style", SONG_C, 5, 50)])
    songs = clean(rows, toks, display="Taylor Swift", gkey="taylorswift", review={"drop": {"Bad Blood": "a test"}})
    assert {s.title: s.reason for s in songs}["Bad Blood"] == "reviewed: a test"
    songs = clean(rows, toks, display="Taylor Swift", gkey="taylorswift", review={"only": ["Style", "Love Story"]})
    assert _kept(songs) == ["Love Story", "Style"]
