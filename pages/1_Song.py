"""Single-song page: fetch one track and show its stats."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lyricstats import db, fetch, stats
from lyricstats.text import parse_sections

st.set_page_config(page_title="Song — LyricStats", page_icon="🎵", layout="wide")
st.title("🎵 Song")

with st.form("song_form"):
    c1, c2, c3 = st.columns([3, 3, 1])
    artist = c1.text_input("Artist", placeholder="e.g. Jala Brat")
    title = c2.text_input("Song title", placeholder="e.g. Bombaclat")
    force = c3.checkbox("Re-fetch", help="Bypass the cache and hit Genius again.")
    submitted = st.form_submit_button("Fetch & analyse", type="primary")

if not submitted:
    st.stop()

if not artist or not title:
    st.error("Both artist and song title are required.")
    st.stop()

with st.status(f"Fetching '{title}' by {artist}…", expanded=False) as status:
    try:
        song = fetch.fetch_song(artist, title, force=force)
        status.update(label=f"Got lyrics from **{song.source}**", state="complete")
    except fetch.FetchError as e:
        status.update(label="Fetch failed", state="error")
        st.error(str(e))
        st.stop()

# Header
hl, hr = st.columns([3, 1])
with hl:
    st.subheader(f"{song.title}")
    meta = " · ".join(
        x for x in [song.artist.title(), song.album, str(song.year) if song.year else ""] if x
    )
    st.caption(meta or song.artist.title())
with hr:
    st.metric("Source", song.source)

# Compute stats (cache result)
db_song = db.find_song(song.artist, song.title)
cached = db.load_stats(db_song) if db_song else None
if cached:
    s = stats.SongStats(**cached)
else:
    s = stats.compute(song.lyrics)
    if db_song:
        db.save_stats(db_song, s.to_dict())

# Metric cards
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Words", f"{s.word_count:,}")
m2.metric("Unique words", f"{s.unique_words:,}")
m3.metric("Vocab richness", f"{s.type_token_ratio:.2%}", help="Type-token ratio (unique / total)")
m4.metric("Lines", f"{s.line_count:,}")
m5.metric("Sections", f"{s.section_count:,}")

m6, m7, m8, m9, m10 = st.columns(5)
m6.metric("Avg word length", f"{s.avg_word_length:.2f}")
m7.metric("Avg words/line", f"{s.avg_words_per_line:.2f}")
m8.metric("Hapax (used once)", f"{s.hapax_count:,}", help=f"{s.hapax_ratio:.0%} of vocab")
m9.metric("Chorus share", f"{s.chorus_ratio:.0%}")
m10.metric("Line repetition", f"{s.repetition_ratio:.0%}")

st.divider()

# Charts
left, right = st.columns(2)

with left:
    st.markdown("**Top words** (with stopwords filtered)")
    if s.top_words_no_stop:
        df = pd.DataFrame(s.top_words_no_stop, columns=["word", "count"])
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="count"),
                y=alt.Y("word:N", sort="-x", title=None),
                tooltip=["word", "count"],
            )
            .properties(height=400)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No content words found.")

with right:
    st.markdown("**Word length distribution**")
    if s.word_length_hist:
        hist_df = pd.DataFrame(
            [(int(k), v) for k, v in s.word_length_hist.items()],
            columns=["length", "count"],
        )
        chart = (
            alt.Chart(hist_df)
            .mark_bar()
            .encode(
                x=alt.X("length:O", title="characters"),
                y=alt.Y("count:Q", title="count"),
                tooltip=["length", "count"],
            )
            .properties(height=400)
        )
        st.altair_chart(chart, use_container_width=True)

st.markdown("**Longest words**")
st.write(", ".join(s.longest_words) if s.longest_words else "—")

if s.section_kinds:
    st.markdown("**Section breakdown**")
    sk_df = pd.DataFrame(
        [(k, v) for k, v in s.section_kinds.items()], columns=["kind", "count"]
    )
    st.dataframe(sk_df, hide_index=True, use_container_width=False)

# Lyrics (collapsed)
with st.expander("Show lyrics (via Genius)"):
    sections = parse_sections(song.lyrics)
    if not sections:
        st.write(song.lyrics)
    else:
        for sec in sections:
            if sec.name:
                st.markdown(f"**[{sec.name}]**")
            st.text(sec.text)
            st.write("")
