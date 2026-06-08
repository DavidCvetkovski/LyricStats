"""Tests for the build-time non-song title classifier helpers (scripts/title_filter.py).

The trained fastText model is a build artifact, not a test fixture, so these
cover the deterministic parts: text normalisation, the song-type guard that
overrides any model verdict, the confidence threshold, and graceful loading when
the model is absent. The prediction path is exercised with a stub model.
"""

from __future__ import annotations

import scripts.title_filter as tf


class _StubModel:
    """Mimics a fastText model's predict() → (labels, probs)."""

    def __init__(self, label: str, prob: float) -> None:
        self._label, self._prob = label, prob

    def predict(self, text: str):
        return ([f"__label__{self._label}"], [self._prob])


# ── normalisation ────────────────────────────────────────────────────────────


def test_normalize_lowercases_and_strips_punctuation():
    assert tf.normalize("Shake It Off!!") == "shake it off"
    assert tf.normalize("A/B - C") == "a b c"
    assert tf.normalize("  multiple   spaces  ") == "multiple spaces"


def test_normalize_keeps_unicode_letters():
    assert tf.normalize("Mötley Crüe") == "mötley crüe"
    assert tf.normalize("") == ""


# ── confidence threshold ─────────────────────────────────────────────────────


def test_is_junk_true_above_threshold():
    clf = tf.TitleClassifier(_StubModel("junk", 0.95), threshold=0.9)
    assert clf.is_junk("Reputation Tour Costumes") is True


def test_is_junk_false_below_threshold():
    clf = tf.TitleClassifier(_StubModel("junk", 0.7), threshold=0.9)
    assert clf.is_junk("Borderline Title") is False


def test_is_junk_false_when_model_says_song():
    clf = tf.TitleClassifier(_StubModel("song", 0.99), threshold=0.9)
    assert clf.is_junk("Shake It Off") is False


# ── song-type guard overrides the model ──────────────────────────────────────


def test_guard_keeps_song_types_even_when_model_screams_junk():
    clf = tf.TitleClassifier(_StubModel("junk", 1.0), threshold=0.9)
    for title in ("The Interview Freestyle", "Black Hoodies Interlude",
                  "Steve Berman Skit", "Outro Reprise", "Piano Instrumental"):
        assert clf.is_junk(title) is False, title


def test_empty_title_is_not_junk():
    clf = tf.TitleClassifier(_StubModel("junk", 1.0), threshold=0.9)
    assert clf.is_junk("") is False


# ── graceful loading ─────────────────────────────────────────────────────────


def test_load_classifier_missing_model_returns_none():
    assert tf.load_classifier("does/not/exist.bin") is None
