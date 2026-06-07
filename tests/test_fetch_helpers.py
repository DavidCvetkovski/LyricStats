"""Unit tests for the small adapters around lyricsgenius objects.

These exist because lyricsgenius v3 doesn't have `.id`, `.year`, and exposes
`.album` as a dict — easy to get wrong with naive getattr.
"""

from types import SimpleNamespace
from unittest.mock import patch

from lyricstats.fetch import (
    _album_name,
    _artist_is_main,
    _id_from_api_path,
    _meta_from_api_song,
    _song_year,
    artist_songs_api,
    search_song_api,
)


def test_id_from_api_path_artist():
    obj = SimpleNamespace(api_path="/artists/53624")
    assert _id_from_api_path(obj) == 53624


def test_id_from_api_path_song():
    obj = SimpleNamespace(api_path="/songs/12345")
    assert _id_from_api_path(obj) == 12345


def test_id_from_api_path_missing():
    assert _id_from_api_path(SimpleNamespace()) is None
    assert _id_from_api_path(SimpleNamespace(api_path=None)) is None
    assert _id_from_api_path(SimpleNamespace(api_path="/no/match/here")) is None


def test_album_name_dict():
    obj = SimpleNamespace(album={"name": "Unorthodox", "full_title": "Unorthodox EP"})
    assert _album_name(obj) == "Unorthodox"


def test_album_name_dict_falls_back_to_full_title():
    obj = SimpleNamespace(album={"full_title": "Only Full"})
    assert _album_name(obj) == "Only Full"


def test_album_name_string():
    obj = SimpleNamespace(album="Plain String Album")
    assert _album_name(obj) == "Plain String Album"


def test_album_name_missing():
    assert _album_name(SimpleNamespace()) is None
    assert _album_name(SimpleNamespace(album=None)) is None


def test_song_year_from_release_date():
    obj = SimpleNamespace(release_date="2022-05-14")
    assert _song_year(obj) == 2022


def test_song_year_from_year_attr():
    obj = SimpleNamespace(year="2019")
    assert _song_year(obj) == 2019


def test_song_year_missing():
    assert _song_year(SimpleNamespace()) is None


# ── main-artist (primary_artists) handling ──────────────────────────────────


def _api_song(title, primary_singular, primaries, sid=1):
    """Shape a minimal Genius API song object."""
    return {
        "id": sid,
        "title": title,
        "url": f"https://genius.com/{sid}",
        "primary_artist": {"id": primary_singular[0], "name": primary_singular[1]},
        "primary_artists": [{"id": i, "name": n} for i, n in primaries],
    }


def test_meta_captures_plural_primary_artists():
    # "Gad" / "Balkan" shape: Genius lists Voyage as the singular primary but
    # Nucci is a co-lead in the plural list.
    d = _api_song("Gad", (100, "Voyage"), [(100, "Voyage"), (200, "Nucci")])
    meta = _meta_from_api_song(d)
    assert meta["primary_artist_ids"] == [100, 200]
    assert meta["primary_artist_names"] == ["Voyage", "Nucci"]


def test_meta_falls_back_to_singular_when_plural_absent():
    d = {
        "id": 5,
        "title": "Solo",
        "primary_artist": {"id": 100, "name": "Voyage"},
        # no primary_artists key
    }
    meta = _meta_from_api_song(d)
    assert meta["primary_artist_ids"] == [100]
    assert meta["primary_artist_names"] == ["Voyage"]


def test_artist_is_main_matches_partial_and_exact():
    assert _artist_is_main("Nucci", ["Voyage", "Nucci"]) is True
    assert _artist_is_main("jala", ["Jala Brat"]) is True          # partial
    assert _artist_is_main("Buba Corelli", ["Jala Brat"]) is False  # not a lead
    assert _artist_is_main("", ["Voyage"]) is False


def test_artist_songs_api_keeps_only_main_artist_songs():
    # Voyage (id 100): a co-led song (keep) + a song where Voyage is only
    # featured, i.e. not in primary_artists (drop).
    lead = _api_song("Gad", (100, "Voyage"), [(100, "Voyage"), (200, "Nucci")], sid=1)
    featured = _api_song("Someone Else's Hit", (300, "Other"), [(300, "Other")], sid=2)
    page = {"response": {"songs": [lead, featured], "next_page": None}}

    with patch("lyricstats.fetch._genius_api_get", return_value=page):
        pool, reached_end = artist_songs_api(100)

    titles = [m["title"] for m in pool]
    assert titles == ["Gad"]           # featured-only song dropped
    assert reached_end is True


def test_search_song_api_skips_featured_only_hit():
    # First hit: artist is only featured → skip. Second hit: artist is a lead → return.
    feat_hit = {"result": _api_song("Big Hit", (300, "Other"), [(300, "Other")], sid=9)}
    lead_hit = {"result": _api_song("Gad", (100, "Voyage"), [(100, "Voyage"), (200, "Nucci")], sid=1)}
    resp = {"response": {"hits": [feat_hit, lead_hit]}}

    with patch("lyricstats.fetch._genius_api_get", return_value=resp):
        meta = search_song_api("Nucci", "Gad")

    assert meta is not None
    assert meta["title"] == "Gad"
    assert 200 in meta["primary_artist_ids"]


def test_search_song_api_returns_none_when_artist_not_main():
    hit = {"result": _api_song("Big Hit", (300, "Other"), [(300, "Other")], sid=9)}
    resp = {"response": {"hits": [hit]}}
    with patch("lyricstats.fetch._genius_api_get", return_value=resp):
        assert search_song_api("Nucci", "Big Hit") is None


def test_fetch_one_by_id_when_cached_by_genius_id():
    from unittest.mock import MagicMock, patch
    from lyricstats import db, fetch

    artist = db.Artist(id=1, name="test artist")
    song_id = 99999

    mock_song = MagicMock()
    mock_song.lyrics = "test lyrics"
    mock_song.genius_id = song_id

    mock_exec = MagicMock()
    mock_exec.first.return_value = mock_song

    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.exec.return_value = mock_exec

    with patch("lyricstats.db.session", return_value=mock_session), \
         patch("lyricstats.fetch.get_lyrics") as mock_get_lyrics:

        result = fetch.fetch_one_by_id(artist, song_id, "test title")

        assert result is True
        mock_get_lyrics.assert_not_called()


def test_fetch_one_by_id_when_cached_by_title():
    from unittest.mock import MagicMock, patch
    from lyricstats import db, fetch

    artist = db.Artist(id=1, name="test artist")
    song_id = 99999

    mock_song = MagicMock()
    mock_song.lyrics = "test lyrics"
    mock_song.genius_id = None

    mock_exec = MagicMock()
    mock_exec.first.return_value = None  # not found by genius_id

    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.exec.return_value = mock_exec

    with patch("lyricstats.db.session", return_value=mock_session), \
         patch("lyricstats.db.find_song", return_value=mock_song) as mock_find_song, \
         patch("lyricstats.fetch.get_lyrics") as mock_get_lyrics:

        result = fetch.fetch_one_by_id(artist, song_id, "test title")

        assert result is True
        mock_find_song.assert_called_once_with(artist.name, "test title")
        mock_get_lyrics.assert_not_called()
