"""Placing a song among the archive from the quantile table."""

from lyricstats import percentiles as pc

TABLE = {
    "archive_songs": 1000,
    "metrics": {
        "wc": [float(i * 10) for i in range(101)],
        # Most songs never say their title: a plateau of zeros, then a tail.
        "drops": [0.0] * 60 + [float(i) for i in range(1, 42)],
    },
}


def test_percentile_bisects_the_table(monkeypatch):
    monkeypatch.setattr(pc, "_table", lambda: TABLE)
    assert pc.percentile("wc", 500) == 50
    assert pc.percentile("wc", 0) == 0
    assert pc.percentile("wc", 5000) == 100
    assert pc.percentile("wc", None) is None
    assert pc.percentile("nope", 3) is None


def test_ties_read_as_the_middle_of_their_plateau(monkeypatch):
    monkeypatch.setattr(pc, "_table", lambda: TABLE)
    assert pc.percentile("drops", 0) == 30
    assert pc.percentiles({"wc": 100, "drops": 41, "ttr": 0.5}) == {"wc": 10, "drops": 100}
    assert pc.archive_songs() == 1000


def test_shipped_table_covers_the_reading():
    metrics = pc._table()["metrics"]
    for name in ("wc", "uniq", "ttr", "rep", "hook", "rhyme", "wpm", "first", "gap", "fast15"):
        assert len(metrics[name]) == 101, name
    assert pc.archive_songs() > 1_000_000
    assert 200 < pc._table()["metrics"]["wc"][50] < 300
