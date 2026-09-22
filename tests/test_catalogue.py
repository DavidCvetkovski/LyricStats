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


def test_hindi_uploads_of_one_song_merge_though_the_tokenizer_left_short_words():
    # "लग जा गले" is stored as "लग ज गल": most words of a Hindi text are one or two letters
    gale = "लग गल हस यद इस जनम हमक आज घड़ नस आपक फर "
    retyped = gale.replace("घड़", "घड")  # a second transcription
    liye = "तर लय जय हम नम सब कह तम मन पर वफ़ दर "
    rows, toks = _rows([("Lag Ja Gale", gale * 3, 5, 200), ("Lagja Gale", retyped * 3, 2, 200),
                        ("Tere Liye", liye * 3, 4, 200)], artist="Lata Mangeshkar")
    songs = clean(rows, toks, display="Lata Mangeshkar", gkey="latamangeshkar")
    assert _kept(songs) == ["Lag Ja Gale", "Tere Liye"]


def test_skits_and_short_interludes_are_set_aside_but_a_sung_interlude_is_not():
    rows, toks = _rows([
        ("Love Story", SONG_A, 5, 200),
        ("Nicky (Skit)", SONG_B, 2, 474),
        ("Interlude: Race", "we are in a race between education and catastrophe", 2, 11),
        ("Interlude (Style)", SONG_C * 4, 2, 180),
    ], artist="Janet Jackson")
    songs = {s.title: s.reason for s in clean(rows, toks, display="Janet Jackson", gkey="janetjackson")}
    assert songs["Love Story"] is None
    assert songs["Nicky (Skit)"] == "skit or interlude"
    assert songs["Interlude: Race"] == "skit or interlude"
    assert songs["Interlude (Style)"] is None


def test_a_hyphenated_mega_mix_is_a_medley():
    rows, toks = _rows([("Love Story", SONG_A, 5, 200), ("The Grease Mega-Mix", SONG_B + SONG_C, 3, 500)])
    songs = {s.title: s.reason for s in clean(rows, toks, display="Taylor Swift", gkey="taylorswift")}
    assert songs["The Grease Mega-Mix"] == "medley or megamix"


def test_a_review_renames_a_song_shown_under_a_wrong_title():
    rows, toks = _rows([("Enrique Iglesias", SONG_A, 5, 200), ("Miente", SONG_A, 2, 200), ("Hero", SONG_B, 5, 200)],
                       artist="Enrique Iglesias")
    songs = clean(rows, toks, display="Enrique Iglesias", gkey="enriqueiglesias",
                  review={"rename": {"Enrique Iglesias": "Miente"}})
    assert _kept(songs) == ["Hero", "Miente"]


def test_one_mislabelled_upload_or_a_medley_does_not_make_two_songs_one():
    rows, toks = _rows([
        ("Step Out", SONG_A * 3, 40, 290), ("Underneath the Sky", SONG_B * 3, 30, 190),
        ("Underneath the Sky", SONG_A * 3, 1, 290),  # the words of Step Out, mislabelled
        ("Brain Damage", SONG_C * 3, 20, 180),
        ("Brain Damage / Underneath the Sky", (SONG_C + SONG_B) * 3, 2, 370),  # a medley of both
    ], artist="Oasis")
    songs = {s.title: s.reason for s in clean(rows, toks, display="Oasis", gkey="oasis")}
    assert songs["Step Out"] is None and songs["Underneath the Sky"] is None and songs["Brain Damage"] is None
    assert songs["Brain Damage / Underneath the Sky"] == "medley of songs listed separately"


def test_a_song_holding_its_own_parts_is_not_a_medley():
    rows, toks = _rows([("Echoes", (SONG_A + SONG_B) * 3, 30, 400), ("Echoes, Part 1", SONG_A * 3, 5, 200),
                        ("Echoes, Part 2", SONG_B * 3, 4, 200)], artist="Pink Floyd")
    assert _kept(clean(rows, toks, display="Pink Floyd", gkey="pinkfloyd")) == ["Echoes"]


def test_a_medley_is_known_by_most_of_its_upload_titles():
    rows, toks = _rows([("Teddy Bear", SONG_A * 3, 20, 180), ("Don't Be Cruel", SONG_B * 3, 20, 200),
                        ("Teddy Bear / Don't Be Cruel", SONG_C * 3, 5, 200),
                        ("Teddy Bear-Don't Be Cruel", SONG_C * 3, 4, 200)], artist="Elvis Presley")
    songs = {s.title: s.reason for s in clean(rows, toks, display="Elvis Presley", gkey="elvispresley")}
    assert songs["Teddy Bear"] is None and songs["Don't Be Cruel"] is None
    assert [r for t, r in songs.items() if "Cruel" in t and "Teddy" in t] == ["medley of songs listed separately"]


def test_a_drop_takes_only_the_song_shown_under_its_title_when_two_share_a_key():
    from catalogue import Song, _apply_review
    main = Song(rows=[0], rep=0, title="If", key="if", uploads=92)
    copy = Song(rows=[1], rep=1, title="If (with Mitchell Ayres & His Orchestra)", key="if", uploads=1)
    _apply_review([main, copy], {"drop": {"If (with Mitchell Ayres & His Orchestra)": "second copy"}}, "perry como")
    assert main.reason is None and copy.reason == "reviewed: second copy"
    # two reviewed titles under one key each take their own copy
    go = Song(rows=[0], rep=0, title="Go", key="go", uploads=2)
    mix = Song(rows=[1], rep=1, title="Go (Amphetamix)", key="go", uploads=1)
    _apply_review([go, mix], {"drop": {"Go": "an instrumental", "Go [Amphetamix]": "a remix"}}, "moby")
    assert go.reason and mix.reason


def test_a_suite_holding_its_movements_stays_a_song():
    rows, toks = _rows([("2112", (SONG_A + SONG_B) * 3, 40, 500), ("Overture", SONG_A * 3, 5, 200),
                        ("The Temples of Syrinx", SONG_B * 3, 5, 200)], artist="Rush")
    assert _kept(clean(rows, toks, display="Rush", gkey="rush")) == ["2112", "Overture", "The Temples of Syrinx"]


def test_short_talk_and_announcements_are_set_aside_by_most_of_their_titles():
    rows, toks = _rows([
        ("Love Story", SONG_A, 5, 200),
        ("Nicki Minaj Speaks", SONG_B, 3, 67), ("Speaks", SONG_B, 1, 67),
        ("Intro to Both Sides Now", SONG_C * 2, 4, 80),
        ("RF Announcement", "robert fripp says hello to the audience tonight", 3, 60),
    ], artist="Nicki Minaj")
    songs = {s.title: s.reason for s in clean(rows, toks, display="Nicki Minaj", gkey="nickiminaj")}
    assert songs["Love Story"] is None
    assert songs["Nicki Minaj Speaks"] == "skit or interlude"
    assert songs["Intro to Both Sides Now"] == "skit or interlude"
    assert songs["RF Announcement"] == "not a song"


def test_titles_that_sound_like_talk_but_name_songs_stay():
    from catalogue import NON_SONG_RE
    for song in ("Message From A Black Man", "Trapped in the Closet Chapter 1", "Commercial for Levi",
                 "Radio Show", "No Spoken Word", "Making of a Soul"):
        assert not NON_SONG_RE.search(song), song
    for talk in ("The 49 Weeks (spoken word)", "Lady Killer (Commentary)", "US Radio Spot"):
        assert NON_SONG_RE.search(talk), talk


def test_a_spelling_of_a_duo_keeps_its_page_but_a_piece_or_a_scramble_of_it_does_not():
    import clean_catalogues as cc

    for alias, page in [("simongarfunkel", "Simon And Garfunkel"), ("beatles", "The Beatles"), ("ye", "Kanye West"),
                        ("hallandoates", "Daryl Hall And John Oates"), ("nilsson", "Harry Nilsson")]:
        assert not cc.is_fragment(alias, page), alias
    for alias, page in [("garfunkel", "Simon And Garfunkel"), ("nash", "Crosby Stills Nash"), ("blank", "Blank-Jones"),
                        ("lakeandpalmeremerson", "Emerson Lake and Palmer"), ("presleyelvis", "Elvis Presley"),
                        ("jrhankwilliams", "Hank Williams Jr.")]:
        assert cc.is_fragment(alias, page), alias
