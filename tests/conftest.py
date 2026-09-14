"""Shared pytest fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest
from sqlmodel import SQLModel, create_engine

# db initializes the SQLite schema at import time, before pytest fixtures run.
# Set both overrides before importing it so test collection cannot connect to
# a developer's .env database. Keep this small bootstrap DB in the OS temp dir.
os.environ["DATABASE_URL"] = ""
os.environ["LYRICSTATS_DB"] = os.path.join(
    tempfile.mkdtemp(prefix="lyricstats-tests-"), "bootstrap.db"
)

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
