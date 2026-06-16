import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select
from collections import Counter
from lyricstats import db
from lyricstats.stats import STOPWORDS
from lyricstats.text import parse_sections, tokenize

_CHORUS_KINDS = {"chorus", "hook", "refrain"}


def lean_song_stats(lyrics: str):
    secs = parse_sections(lyrics)
    lines = [ln for s in secs for ln in s.lines]
    if not lines:
        return None
    toks = tokenize(" ".join(lines))
    wc = len(toks)
    if wc == 0:
        return None
    cnt = Counter(toks)
    total_lines = len(lines)
    chorus_lines = sum(len(s.lines) for s in secs if s.kind in _CHORUS_KINDS)
    uniq_lines = len({ln.strip().lower() for ln in lines if ln.strip()})
    return {
        "wc": wc,
        "uniq": len(cnt),
        "ttr": round(wc and len(cnt) / wc, 4),
        "chorus": round(chorus_lines / total_lines, 4) if total_lines else 0.0,
        "rep": round(1 - (uniq_lines / total_lines), 4) if total_lines else 0.0,
        "has_sec": 1 if any(s.kind != "other" for s in secs) else 0,
        "cnt": cnt,
    }


def _highlights(songs: list[tuple[str, int, float]]) -> dict:
    _DEMO_KW = (
        "(demo)",
        "[demo]",
        "(snippet)",
        "[snippet]",
        "(teaser)",
        "[teaser]",
        "(promo)",
        "[promo]",
        "(skit)",
        "[skit]",
    )
    eligible = [s for s in songs if s[1] >= 80 and not any(kw in s[0].lower() for kw in _DEMO_KW)]
    if not eligible:
        eligible = songs
    if not eligible:
        return {}
    longest = max(eligible, key=lambda s: s[1])
    shortest = min(eligible, key=lambda s: s[1])
    richest = max(eligible, key=lambda s: s[2])
    return {
        "longest_song": {"title": longest[0], "words": longest[1]},
        "shortest_song": {"title": shortest[0], "words": shortest[1]},
        "richest_song": {"title": richest[0], "ttr": richest[2]},
    }


def main():
    print("Merging live cache into ArtistAggregate...")
    with db.session() as s:
        artists = s.exec(select(db.Artist)).all()
        for a in artists:
            songs = s.exec(select(db.Song).where(db.Song.artist_id == a.id)).all()
            valid_songs = [s for s in songs if s.lyrics and s.lyrics.strip()]

            agg = s.exec(
                select(db.ArtistAggregate).where(
                    db.ArtistAggregate.name_key == db.normalize_key(a.name)
                )
            ).first()
            if not agg:
                continue

            total_live = max(len(valid_songs), a.total_songs if a.total_songs else 0)
            if total_live > agg.song_count:
                print(f"Updating {a.name}: {agg.song_count} -> {total_live}")

                rows = []
                for song in valid_songs:
                    st = lean_song_stats(song.lyrics)
                    if st:
                        rows.append(
                            {
                                "title": song.title,
                                "year": song.year,
                                "wc": st["wc"],
                                "uniq": st["uniq"],
                                "ttr": st["ttr"],
                                "chorus": st["chorus"],
                                "rep": st["rep"],
                                "has_sec": st["has_sec"],
                                "cnt": st["cnt"],
                            }
                        )

                n = len(rows)
                if n == 0:
                    continue

                total_words = sum(r["wc"] for r in rows)
                global_counts = Counter()
                for r in rows:
                    global_counts.update(r["cnt"])

                top_n = 30
                top_words = global_counts.most_common(top_n)
                top_words_no_stop = [
                    (w, c) for w, c in global_counts.most_common(top_n * 4) if w not in STOPWORDS
                ][:top_n]

                stats = {
                    "song_count": n,
                    "total_words": total_words,
                    "total_unique_words": len(global_counts),
                    "avg_words_per_song": round(total_words / n, 2),
                    "avg_ttr": round(sum(r["ttr"] for r in rows) / n, 4),
                    "avg_chorus_ratio": round(sum(r["chorus"] for r in rows) / n, 4),
                    "avg_repetition_ratio": round(sum(r["rep"] for r in rows) / n, 4),
                    "top_words": top_words,
                    "top_words_no_stop": top_words_no_stop,
                    **_highlights([(r["title"], r["wc"], r["ttr"]) for r in rows]),
                }

                songs_list = sorted(
                    (
                        [
                            r["title"],
                            r["year"],
                            r["wc"],
                            r["uniq"],
                            r["ttr"],
                            r["chorus"],
                            r["rep"],
                            int(r["has_sec"]),
                        ]
                        for r in rows
                    ),
                    key=lambda x: x[2],
                    reverse=True,
                )

                # agg.song_count should represent the TOTAL songs, even those without lyrics.
                agg.song_count = max(n, a.total_songs if a.total_songs else 0)
                agg.has_sections = any(r["has_sec"] for r in rows)
                agg.stats_json = json.dumps(stats, ensure_ascii=False)
                agg.songs_json = json.dumps(songs_list, ensure_ascii=False)
                agg.source = "live_cache"
                s.add(agg)
        s.commit()
        print("Done!")


if __name__ == "__main__":
    main()
