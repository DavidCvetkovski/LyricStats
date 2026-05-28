"""Configuration — reads env vars / Streamlit secrets."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _from_streamlit_secrets(key: str) -> str | None:
    """Read from st.secrets if Streamlit is running, else None."""
    try:
        import streamlit as st  # noqa: PLC0415

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return None


def get(key: str, default: str | None = None) -> str | None:
    return os.getenv(key) or _from_streamlit_secrets(key) or default


GENIUS_TOKEN: str | None = get("GENIUS_TOKEN")
DB_PATH: Path = Path(get("LYRICSTATS_DB", "./data/lyricstats.db") or "./data/lyricstats.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
