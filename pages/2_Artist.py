"""Artist page: pull a catalogue, show aggregate stats and a sortable song table."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lyricstats import db, fetch, stats

st.set_page_config(page_title="Artist — LyricStats", page_icon="🎤", layout="wide")
st.title("🎤 Artist")

with st.form("artist_form"):
    c1, c2, c3 = st.columns([4, 1, 1])
    name = c1.text_input("Artist", placeholder="e.g. Buba Corelli")
    max_songs = c2.number_input("Max songs", min_value=5, max_value=100, value=20, step=5)
    fetch_now = c3.checkbox(
        "Fetch from Genius", value=True,
        help="Uncheck to only read what's already cached locally.",
    )
    submitted = st.form_submit_button("Analyse", type="primary")

if not submitted:
    st.stop()

if not name:
    st.error("Artist name is required.")
    st.stop()

if fetch_now:
    progress_bar = st.progress(0.0, text="Starting…")
    placeholder = st.empty()

    def _progress(done: int, total: int, current: str) -> None:
        pct = done / max(total, 1)
        progress_bar.progress(min(pct, 1.0), text=f"{done}/{total} — {current}")

    try:
        with st.spinner(f"Fetching catalogue for {name}…"):
            n = fetch.fetch_artist_catalogue(name, max_songs=int(max_songs), progress=_progress)
        progress_bar.empty()
        placeholder.success(f"Fetched {n} songs.")
    except fetch.FetchError as e:
        progress_bar.empty()
        st.error(str(e))
        st.stop()

artist = db.get_artist(name)
if not artist:
    st.warning(
        f"No cached data for '{name}'. Check the 'Fetch from Genius' box and try again."
    )
    st.stop()

songs = db.list_songs(artist)
if not songs:
    st.warning("Artist exists in cache but no songs found.")
    st.stop()

st.subheader(artist.name.title())
st.caption(f"{len(songs)} song(s) in cache")

# Per-song stats — compute (cached on song row) and aggregate
rows = []
pairs: list[tuple[str, str]] = []
for s in songs:
    cached = db.load_stats(s)
    if cached:
        st_obj = stats.SongStats(**cached)
    else:
        st_obj = stats.compute(s.lyrics)
        db.save_stats(s, st_obj.to_dict())
    rows.append(
        {
            "title": s.title,
            "album": s.album or "",
            "year": s.year,
            "words": st_obj.word_count,
            "unique": st_obj.unique_words,
            "ttr": st_obj.type_token_ratio,
            "avg_word_len": st_obj.avg_word_length,
            "lines": st_obj.line_count,
            "chorus_ratio": st_obj.chorus_ratio,
            "repetition": st_obj.repetition_ratio,
        }
    )
    pairs.append((s.title, s.lyrics))

agg = stats.aggregate(pairs)

# Aggregate metric cards
m1, m2, m3, m4 = st.columns(4)
m1.metric("Songs analysed", agg.song_count)
m2.metric("Total words", f"{agg.total_words:,}")
m3.metric("Catalogue vocabulary", f"{agg.total_unique_words:,}")
m4.metric("Avg words/song", f"{agg.avg_words_per_song:.0f}")

m5, m6, m7, m8 = st.columns(4)
m5.metric("Avg vocab richness", f"{agg.avg_ttr:.2%}")
m6.metric("Avg chorus share", f"{agg.avg_chorus_ratio:.0%}")
m7.metric("Avg repetition", f"{agg.avg_repetition_ratio:.0%}")
if agg.longest_song:
    m8.metric("Longest song", agg.longest_song["title"], f"{agg.longest_song['words']} words")

if agg.richest_song:
    st.caption(
        f"📚 Highest vocab richness: **{agg.richest_song['title']}** "
        f"({agg.richest_song['ttr']:.2%})  ·  📉 Shortest: "
        f"**{agg.shortest_song.get('title', '—')}** "
        f"({agg.shortest_song.get('words', 0)} words)"
    )

st.divider()

# Top words across catalogue
st.markdown("### Top words across catalogue (stopwords filtered)")
if agg.top_words_no_stop:
    df = pd.DataFrame(agg.top_words_no_stop, columns=["word", "count"])
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("count:Q"),
            y=alt.Y("word:N", sort="-x", title=None),
            tooltip=["word", "count"],
        )
        .properties(height=500)
    )
    st.altair_chart(chart, use_container_width=True)

# Sortable songs table
st.markdown("### Songs")
df = pd.DataFrame(rows).sort_values("words", ascending=False)
st.dataframe(
    df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "ttr": st.column_config.NumberColumn("vocab richness", format="%.2f"),
        "chorus_ratio": st.column_config.NumberColumn("chorus", format="%.0%%"),
        "repetition": st.column_config.NumberColumn("repetition", format="%.0%%"),
    },
)
