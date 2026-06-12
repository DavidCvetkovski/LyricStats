"""Tests for the LRCLIB import pipeline (scripts/import_lrclib.py).

Covers the title canonicalisation that dedupes release variants, the
truncation-stub suppression, NUL handling, and the synced-lyrics parser.
"""

from __future__ import annotations

import scripts.import_lrclib as imp


# ── canonical_title: variants of one song share a key ────────────────────────


def test_taylors_version_variants_merge():
    base = imp.canonical_title("Slut!")
    variants = [
        '"Slut!"',
        '"Slut!" (Taylor\'s Version)',
        '"Slut!" (Acoustic Version) (Taylor\'s Version) (From The Vault)',
        '"Slut!" (Acoustic Version) [Taylor\'s Version]',
        '"Slut!" (From The Vault)',
        "Slut! - Acoustic",
        "Slut! (Live)",
        "Slut! (sped up)",
    ]
    for v in variants:
        assert imp.canonical_title(v) == base, v


def test_dash_suffix_and_descriptor_merge():
    assert imp.canonical_title("Love Story - Live at the BBC") == \
        imp.canonical_title("Love Story")
    assert imp.canonical_title("Halo (Remastered 2011)") == \
        imp.canonical_title("Halo")
    assert imp.canonical_title('"Change" music video') == \
        imp.canonical_title("Change")
    assert imp.canonical_title("Anti-Hero") == \
        imp.canonical_title("Anti-Hero (Taylor's Version)")


def test_leading_bracket_titles():
    assert imp.canonical_title("(I Can't Get No) Satisfaction") == \
        imp.canonical_title("Satisfaction")


def test_different_songs_stay_distinct():
    assert imp.canonical_title("Red") != imp.canonical_title("Red 2")
    assert imp.canonical_title("Style") != imp.canonical_title("Stylo")
    assert imp.canonical_title("Forever") != imp.canonical_title("Forever Young")


def test_descriptor_only_titles_keep_a_key():
    # A song literally titled "Live" must not collapse to an empty key.
    assert imp.canonical_title("Live") == "live"
    assert imp.canonical_title("(Untitled)") != ""
    assert imp.canonical_title("Acoustic") == "acoustic"


def test_diacritics_and_nul_handling():
    assert imp.canonical_title("Noći bez sna") == imp.canonical_title("Noci bez sna")
    assert "\x00" not in imp.canonical_title("Bad\x00 Song")


# ── drop_truncation_stubs ────────────────────────────────────────────────────


def _agg(display: str, count: int) -> tuple:
    return ("key", display, {"song_count": count}, [])


def test_truncation_stub_dropped():
    aggs = [_agg("Beyoncé", 2067), _agg("beyonc", 52), _agg("Beyond", 898)]
    kept, n = imp.drop_truncation_stubs(aggs)
    names = [a[1] for a in kept]
    assert n == 1
    assert "beyonc" not in names
    assert "Beyoncé" in names and "Beyond" in names


def test_ascii_prefix_artists_survive():
    # Emin is a real artist, not a truncated Eminem; ascii continuation → keep.
    aggs = [_agg("Eminem", 2479), _agg("Emin", 175)]
    kept, n = imp.drop_truncation_stubs(aggs)
    assert n == 0 and len(kept) == 2


def test_small_ratio_survives():
    # Similar sizes → not a stub even with non-ascii continuation.
    aggs = [_agg("Beyoncé", 60), _agg("beyonc", 52)]
    kept, n = imp.drop_truncation_stubs(aggs)
    assert n == 0


# ── synced-lyrics parser (regression: timing stats feed WPM and bursts) ─────


def test_parse_synced_basics():
    lrc = "\n".join([
        "[00:10.00] one two three",
        "[00:12.00] four five",
        "[00:20.00] six",
        "[00:50.00] seven eight nine ten",
    ])
    out = imp.parse_synced(lrc, 60.0)
    assert out["first"] == 10.0
    assert out["gap"] == 30.0
    assert out["fast15"] == 6  # the 10s–20s window holds 6 words
    assert sum(int(x) for x in out["curve"].split(",")) == 10


def test_backfill_years():
    import json

    class MockCursor:
        def fetchone(self):
            return (json.dumps([["Slut!", 2023], ["Style", 2014]]),)

    class MockConn:
        def execute(self, sql, params):
            return MockCursor()

    songs_list = [
        ["\"Slut!\" (Taylor's Version)", None, 100, 50, 0.5, 0.0, 0.2, 0],
        ["Style - Remix", None, 120, 60, 0.5, 0.0, 0.2, 0],
        ["Shake It Off", None, 150, 70, 0.4, 0.0, 0.3, 0],
    ]
    stats = {}
    imp.backfill_years("Taylor Swift", stats, songs_list, MockConn())
    assert songs_list[0][1] == 2023
    assert songs_list[1][1] == 2014
    assert songs_list[2][1] is None
    assert stats["years_known"] == 2

