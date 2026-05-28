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
