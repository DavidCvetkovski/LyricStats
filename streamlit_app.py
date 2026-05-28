"""LyricStats — entry page."""

from __future__ import annotations

import streamlit as st

from lyricstats.config import GENIUS_TOKEN

st.set_page_config(page_title="LyricStats", page_icon="🎤", layout="wide")

st.title("🎤 LyricStats")
st.markdown(
    """
    Stats for lyrics — per **song** and per **artist**.

    - **Song** — fetch one track and see word counts, vocabulary, structure, top words.
    - **Artist** — pull a whole catalogue and aggregate stats across it.

    Open a page from the sidebar to get started.
    """
)

with st.sidebar:
    st.header("Status")
    if GENIUS_TOKEN:
        st.success("Genius API token detected ✓")
    else:
        st.warning(
            "No `GENIUS_TOKEN` set. Add one to `.env` "
            "(get a free token at https://genius.com/api-clients)."
        )
    st.caption("Lyrics via Genius, with lyrics.ovh as fallback. Cached locally in SQLite.")

st.divider()
st.markdown(
    "Try **Jala Brat**, **Buba Corelli**, or any artist you like."
    " First fetch can take a minute; after that, everything is instant."
)
