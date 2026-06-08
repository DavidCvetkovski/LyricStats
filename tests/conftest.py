"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel, create_engine

from lyricstats import db


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """An isolated SQLite database for a single test.

    Patches ``db._engine`` so every ``db.session()`` / helper in the codebase
    transparently uses the throwaway database — no mocking of individual calls,
    and no risk of touching the real ./data/lyricstats.db.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "_engine", engine)
    yield engine
