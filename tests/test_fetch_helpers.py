"""Unit tests for the small adapters around lyricsgenius objects.

These exist because lyricsgenius v3 doesn't have `.id`, `.year`, and exposes
`.album` as a dict — easy to get wrong with naive getattr.
"""

from types import SimpleNamespace

from lyricstats.fetch import _album_name, _id_from_api_path, _song_year


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
