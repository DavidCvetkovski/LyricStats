"""Tests for the FastAPI endpoints (called directly, against an isolated DB).

Covers the artist-aggregate precedence, the `limited` flag, the dataset
catalogue payload, fuzzy suggestions, and the ingest auth guard.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from backend import main
from backend.main import IngestSong
from lyricstats import db


def _add_dataset(name: str, song_count: int, songs=None) -> None:
    stats = {
        "song_count": song_count,
        "total_words": song_count * 100,
        "total_unique_words": 500,
        "avg_words_per_song": 100.0,
        "avg_ttr": 0.4,
        "avg_chorus_ratio": 0.2,
        "avg_repetition_ratio": 0.2,
        "top_words": [],
        "top_words_no_stop": [],
        "longest_song": {},
        "shortest_song": {},
        "richest_song": {},
    }
    if songs is None:
        songs = [[f"Song {i}", 2020, 100, 50, 0.5, 0.5, 0.5, 1] for i in range(song_count)]
    agg = db.ArtistAggregate(
        name=name.strip().lower(),
        name_key=db.normalize_key(name),
        display_name=name,
        song_count=song_count,
        has_sections=True,
        stats_json=json.dumps(stats),
        songs_json=json.dumps(songs),
    )
    with db.session() as s:
        s.add(agg)
        s.commit()


def _add_lyrics_artist(name: str, n_songs: int, words: int = 30) -> None:
    a = db.get_or_create_artist(name)
    for i in range(n_songs):
        db.upsert_song(a, title=f"Live Song {i}", lyrics=("la na song word here " * (words // 5)))


# ── health ───────────────────────────────────────────────────────────────────


def test_health():
    assert main.health()["ok"] is True


# ── dataset payload ──────────────────────────────────────────────────────────


def test_dataset_payload_expands_catalogue(temp_db):
    songs = [["Song A", 2020, 300, 150, 0.5, 0.2, 0.1, 1]]
    _add_dataset("Drake", 1, songs)
    p = main._dataset_payload(db.get_artist_aggregate("Drake"))
    assert p["source"] == "dataset"
    assert p["limited"] is False
    assert len(p["songs"]) == 1
    assert p["songs"][0]["title"] == "Song A"
    assert p["songs"][0]["word_count"] == 300
    assert p["songs"][0]["has_sections"] is True


# ── artist() precedence + limited flag ───────────────────────────────────────


def test_artist_prefers_richer_dataset_over_thin_cache(temp_db):
    _add_dataset("Drake", 100)
    _add_lyrics_artist("Drake", 1)  # a stray cached song must not shadow
    out = main.artist(name="Drake", min=500)
    assert out["source"] == "dataset"
    assert out["stats"]["song_count"] == 101


def test_artist_limited_when_under_floor(temp_db):
    _add_lyrics_artist("Tiny Artist", 3)
    out = main.artist(name="Tiny Artist", min=500)
    assert out["limited"] is True
    assert out["stats"]["song_count"] == 3


def test_artist_not_limited_when_enough(temp_db):
    _add_lyrics_artist("Big Artist", 25)
    out = main.artist(name="Big Artist", min=500)
    assert out["limited"] is False
    assert out["stats"]["song_count"] >= main.MIN_VIEW


def test_artist_404_when_unknown(temp_db):
    with pytest.raises(HTTPException) as e:
        main.artist(name="Nobody At All", min=500)
    assert e.value.status_code == 404


# ── pool planning ────────────────────────────────────────────────────────────


def test_pool_dataset_exact_skips_fetch(temp_db):
    _add_dataset("Drake", 100)
    res = main.artist_pool(name="Drake", min=500, fresh=False, shuffle="")
    assert res["to_fetch"] == []
    assert res["cached_total"] == 100


def test_pool_typo_offers_suggestion(temp_db):
    _add_dataset("Drake", 100)
    res = main.artist_pool(name="drakee", min=500, fresh=False, shuffle="")
    assert res.get("suggestion") == "Drake"
    assert res["to_fetch"] == []


def test_pool_exhausted_catalogue_serves_cache(temp_db):
    a = db.get_or_create_artist("Niche")
    with db.session() as s:
        row = s.get(db.Artist, a.id)
        row.total_songs = 6  # Genius has 6
        s.add(row)
        s.commit()
    db.upsert_song(a, title="Only One", lyrics="hello world")
    for i in range(5):
        db.upsert_song(a, title=f"Empty {i}", lyrics="")  # the rest had no lyrics
    res = main.artist_pool(name="Niche", min=500, fresh=False, shuffle="")
    assert res["to_fetch"] == []  # already exhausted Genius → no re-fetch


def test_pool_live_fetch_targets_min_view(temp_db, monkeypatch):
    fake_artist = db.get_or_create_artist("New Band")
    sample = [
        {"id": i, "title": f"T{i}", "url": None, "album": None, "year": None} for i in range(1, 6)
    ]
    called = {}

    def fake_resolve(name, n, **kw):
        called["n"] = n
        return fake_artist, sample

    monkeypatch.setattr(main.fetch, "resolve_and_sample", fake_resolve)
    res = main.artist_pool(name="New Band", min=500, fresh=False, shuffle="")
    assert called["n"] == 500  # targets the requested floor
    assert len(res["to_fetch"]) == 5


# ── ingest auth guard ────────────────────────────────────────────────────────


def test_ingest_rejects_bad_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", "secret")
    with pytest.raises(HTTPException) as e:
        main.ingest(IngestSong(artist="A", title="T", lyrics="x"), x_seed_key="wrong")
    assert e.value.status_code == 403


def test_ingest_disabled_without_seed_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", None)
    with pytest.raises(HTTPException) as e:
        main.ingest(IngestSong(artist="A", title="T", lyrics="x"), x_seed_key="")
    assert e.value.status_code == 503


def test_ingest_accepts_valid_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", "secret")
    out = main.ingest(IngestSong(artist="A", title="T", lyrics="hello world"), x_seed_key="secret")
    assert out["ok"] is True
    assert db.find_song("a", "T") is not None
