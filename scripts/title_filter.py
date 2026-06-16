"""Shared title normalisation + non-song classifier inference.

Build-time only. Imported by both the trainer (train_title_classifier.py) and the
dataset fold (import_dataset.py). fastText is imported lazily inside the loader so
the lyricstats package — which this module never touches — stays free of an ML
dependency on Vercel. The model file lives under data/ and is never deployed.
"""

from __future__ import annotations

import os
import re

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "title_clf.bin")

_NORM_RE = re.compile(r"[^\w\s]", re.UNICODE)

# Real song *types* that must never be dropped, even if a junk phrase grazes the
# title (e.g. "The Interview Freestyle" is a freestyle, not an interview page).
_SONG_GUARD_RE = re.compile(r"\b(freestyle|interlude|skit|reprise|instrumental)\b", re.IGNORECASE)


def normalize(title: str) -> str:
    """Lowercase, strip punctuation to spaces — the text form fastText was
    trained on. Shared so training and inference can't drift."""
    s = (title or "").lower()
    s = _NORM_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


class TitleClassifier:
    """Thin wrapper over the trained fastText model. ``is_junk`` answers 'is this
    title a Genius non-song page?' with a confidence floor."""

    def __init__(self, model, threshold: float = 0.9) -> None:
        self._model = model
        self.threshold = threshold

    def is_junk(self, title: str) -> bool:
        if _SONG_GUARD_RE.search(title or ""):
            return False
        norm = normalize(title)
        if not norm:
            return False
        labels, probs = self._model.predict(norm)
        return labels[0] == "__label__junk" and probs[0] >= self.threshold


def load_classifier(path: str = MODEL_PATH, threshold: float = 0.9) -> TitleClassifier | None:
    """Load the model if present, else None so callers degrade gracefully to the
    deterministic blocklist (e.g. on a machine without fasttext / the model)."""
    if not os.path.exists(path):
        return None
    try:
        import fasttext  # noqa: PLC0415

        # fasttext prints a deprecation notice on load; silence it.
        fasttext.FastText.eprint = lambda *a, **k: None  # type: ignore[attr-defined]
        return TitleClassifier(fasttext.load_model(path), threshold)
    except Exception:  # noqa: BLE001 — any load failure → fall back to blocklist
        return None
