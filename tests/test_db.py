"""Tests for the database layer: normalisation, aggregate CRUD, fuzzy suggest."""

from __future__ import annotations

import pytest

from lyricstats import db
from lyricstats.db import normalize_key


# ── normalize_key ────────────────────────────────────────────────────────────


def test_normalize_key_collapses_casing_punctuation_accents():
    assert normalize_key("JAY-Z") == normalize_key("jay z") == "jayz"
    assert normalize_key("Beyoncé") == normalize_key("beyonce") == "beyonce"
    assert normalize_key("Tyler, the Creator") == "tylerthecreator"
    assert normalize_key("P!nk") == "pnk"


def test_normalize_key_empty():
    assert normalize_key("") == ""
    assert normalize_key("   ") == ""


# ── aggregate CRUD ───────────────────────────────────────────────────────────


def test_aggregate_upsert_and_get(temp_db):
    db.upsert_artist_aggregate(
        name="Drake",
        display_name="Drake",
        song_count=100,
        has_sections=True,
        stats={"song_count": 100},
    )
    a = db.get_artist_aggregate("drake")
    assert a is not None
    assert a.display_name == "Drake"
    assert a.song_count == 100
    assert db.load_aggregate_stats(a) == {"song_count": 100}



def _agg(name: str, count: int) -> None:
    db.upsert_artist_aggregate(name=name, display_name=name, song_count=count, has_sections=False, stats={})


@pytest.mark.parametrize("typed, filed", [
    ("Emerson, Lake & Palmer", "Emerson Lake and Palmer"),
    ("Florence + the Machine", "Florence and the Machine"),
    ("Simon&Garfunkel", "Simon and Garfunkel"),
    ("Simon and Garfunkel", "Simon & Garfunkel"),
    ("simon-and-garfunkel", "Simon & Garfunkel"),
])
def test_aggregate_lookup_reads_an_ampersand_as_and_both_ways(temp_db, typed, filed):
    _agg(filed, 100)
    a = db.get_artist_aggregate(typed)
    assert a is not None and a.display_name == filed


def test_aggregate_exact_key_beats_a_bigger_joiner_variant(temp_db):
    _agg("Jack White", 143)
    _agg("Jack and White", 13)
    assert db.get_artist_aggregate("Jack and White").display_name == "Jack and White"
    assert db.get_artist_aggregate("Jack White").display_name == "Jack White"


def test_aggregate_joiner_counts_only_between_words(temp_db):
    _agg("Johnny Winter", 300)
    _agg("One", 50)
    assert db.get_artist_aggregate("Johnny Winter And") is None
    assert db.get_artist_aggregate("And One") is None
    assert db.get_artist_aggregate("Prozac+") is None


def test_joiner_variants():
    assert db._joiner_variants("Drake") == []
    assert db._joiner_variants("Emerson, Lake & Palmer") == ["emersonlakeandpalmer"]
    assert db._joiner_variants("Peter, Paul and Mary") == ["peterpaulmary"]
    assert db._joiner_variants("Band of Horses") == []
    assert db._joiner_variants("&") == [] and db._joiner_variants("") == []

def test_aggregate_lookup_is_accent_and_case_insensitive(temp_db):
    db.upsert_artist_aggregate(
        name="Beyoncé",
        display_name="Beyoncé",
        song_count=50,
        has_sections=True,
        stats={},
    )
    assert db.get_artist_aggregate("beyonce") is not None
    assert db.get_artist_aggregate("BEYONCÉ") is not None
    assert db.get_artist_aggregate("totally other") is None


def test_aggregate_key_collision_prefers_bigger_catalogue(temp_db):
    db.upsert_artist_aggregate(
        name="Jay Z", display_name="Jay Z", song_count=10, has_sections=False, stats={}
    )
    db.upsert_artist_aggregate(
        name="JAY-Z", display_name="JAY-Z", song_count=400, has_sections=False, stats={}
    )
    a = db.get_artist_aggregate("jayz")
    assert a.song_count == 400  # the larger catalogue wins the shared key


def test_aggregate_upsert_updates_existing(temp_db):
    db.upsert_artist_aggregate(
        name="X", display_name="X", song_count=1, has_sections=False, stats={}
    )
    db.upsert_artist_aggregate(
        name="X", display_name="X", song_count=99, has_sections=True, stats={}
    )
    a = db.get_artist_aggregate("x")
    assert a.song_count == 99 and a.has_sections is True


def test_reset_aggregates_clears_table(temp_db):
    db.upsert_artist_aggregate(
        name="X", display_name="X", song_count=20, has_sections=False, stats={}
    )
    db.reset_aggregates()
    assert db.get_artist_aggregate("x") is None


# ── fuzzy suggest (SQLite difflib path) ──────────────────────────────────────


def test_suggest_finds_close_typo(temp_db):
    db.upsert_artist_aggregate(
        name="Drake", display_name="Drake", song_count=100, has_sections=True, stats={}
    )
    db.upsert_artist_aggregate(
        name="Taylor Swift",
        display_name="Taylor Swift",
        song_count=200,
        has_sections=True,
        stats={},
    )
    s = db.suggest_artist_aggregates("drakee")
    assert s and s[0].display_name == "Drake"


def test_suggest_returns_empty_for_no_match(temp_db):
    db.upsert_artist_aggregate(
        name="Drake", display_name="Drake", song_count=100, has_sections=True, stats={}
    )
    assert db.suggest_artist_aggregates("zzxqwvb") == []


def test_suggest_ignores_too_short(temp_db):
    db.upsert_artist_aggregate(
        name="Drake", display_name="Drake", song_count=100, has_sections=True, stats={}
    )
    assert db.suggest_artist_aggregates("dr") == []


# ── typeahead search (autocomplete) ──────────────────────────────────────────


def test_search_prefix_ranks_by_song_count(temp_db):
    db.upsert_artist_aggregate(
        name="Taylor Swift",
        display_name="Taylor Swift",
        song_count=477,
        has_sections=True,
        stats={},
    )
    db.upsert_artist_aggregate(
        name="Taylor Dayne",
        display_name="Taylor Dayne",
        song_count=86,
        has_sections=False,
        stats={},
    )
    out = db.search_artist_aggregates("tayl")
    assert [a.display_name for a in out] == ["Taylor Swift", "Taylor Dayne"]


def test_search_prefix_matches_before_substring(temp_db):
    # "kanye" is a prefix of Kanye West but only a substring of the collab.
    db.upsert_artist_aggregate(
        name="Kanye West", display_name="Kanye West", song_count=843, has_sections=True, stats={}
    )
    db.upsert_artist_aggregate(
        name="JAY-Z & Kanye West",
        display_name="JAY-Z & Kanye West",
        song_count=20,
        has_sections=True,
        stats={},
    )
    out = db.search_artist_aggregates("kanye")
    assert [a.display_name for a in out] == ["Kanye West", "JAY-Z & Kanye West"]


def test_search_ignores_punctuation_and_case(temp_db):
    db.upsert_artist_aggregate(
        name="JAY-Z", display_name="JAY-Z", song_count=400, has_sections=False, stats={}
    )
    assert [a.display_name for a in db.search_artist_aggregates("jay z")] == ["JAY-Z"]



def test_search_finds_a_name_filed_under_and_while_typing_an_ampersand(temp_db):
    _agg("Mumford And Sons", 170)
    _agg("Mumford", 20)
    assert [a.display_name for a in db.search_artist_aggregates("Mumford &")] == ["Mumford And Sons", "Mumford"]
    assert [a.display_name for a in db.search_artist_aggregates("Mumford & So")] == ["Mumford And Sons"]
    assert [a.display_name for a in db.search_artist_aggregates("mumford & sons")] == ["Mumford And Sons"]


def test_search_offers_a_name_once(temp_db):
    db.upsert_artist_aggregate(name="The Beatles", display_name="The Beatles", song_count=318,
                               has_sections=False, stats={})
    db.upsert_artist_aggregate(name="beatles (the)", display_name="The Beatles", song_count=318,
                               has_sections=False, stats={})
    assert [a.display_name for a in db.search_artist_aggregates("beatles")] == ["The Beatles"]

def test_search_respects_limit(temp_db):
    for i in range(5):
        db.upsert_artist_aggregate(
            name=f"Dra {i}", display_name=f"Dra {i}", song_count=i, has_sections=False, stats={}
        )
    assert len(db.search_artist_aggregates("dra", limit=2)) == 2


def test_search_ignores_too_short(temp_db):
    db.upsert_artist_aggregate(
        name="Drake", display_name="Drake", song_count=100, has_sections=True, stats={}
    )
    assert db.search_artist_aggregates("d") == []


# ── artist / song CRUD ───────────────────────────────────────────────────────


def test_get_or_create_artist_is_idempotent(temp_db):
    a1 = db.get_or_create_artist("Test Artist", genius_id=5, genius_url="http://x")
    a2 = db.get_or_create_artist("test artist")  # different casing, same artist
    assert a1.id == a2.id


def test_upsert_and_find_song(temp_db):
    a = db.get_or_create_artist("Test Artist")
    db.upsert_song(a, title="Song A", lyrics="hello world hello", year=2020)
    found = db.find_song("test artist", "Song A")
    assert found is not None
    assert found.lyrics == "hello world hello"
    assert len(db.list_songs(a)) == 1


def test_find_song_matches_literal_wildcards_and_uses_one_read(temp_db):
    from sqlalchemy import event

    artist = db.get_or_create_artist("Artist")
    db.upsert_song(artist, title="1000", lyrics="wrong song")
    db.upsert_song(artist, title="100%", lyrics="the requested song")
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(temp_db, "before_cursor_execute", capture)
    try:
        result = db.find_song("ARTIST", "100%")
    finally:
        event.remove(temp_db, "before_cursor_execute", capture)
    assert result.title == "100%"
    assert result.lyrics == "the requested song"
    assert len(statements) == 1
    assert db.find_song("Artist", "100_") is None


@pytest.mark.parametrize("title", ["Šta će biti", "Émotion", "Љубов"])
def test_find_song_preserves_exact_unicode_titles(temp_db, title):
    artist = db.get_or_create_artist("Artist")
    db.upsert_song(artist, title=title, lyrics="the requested song")

    found = db.find_song("artist", f"  {title}  ")

    assert found is not None
    assert found.title == title


def test_upsert_song_replaces_lyrics_and_invalidates_stats(temp_db):
    a = db.get_or_create_artist("A")
    s1 = db.upsert_song(a, title="T", lyrics="old")
    db.save_stats(s1, {"word_count": 1})
    db.upsert_song(a, title="T", lyrics="new lyrics here")
    found = db.find_song("a", "T")
    assert found.lyrics == "new lyrics here"
    assert db.load_stats(found) is None  # cache invalidated on re-upsert
