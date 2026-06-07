"""Compute stats for a song's lyrics.

Language-agnostic stats live here. Anything English-only (CMU rhymes, VADER
sentiment, Flesch readability) is left as a stub for Epoch 4.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from .text import Section, all_lines, char_count, parse_sections, tokenize


# Multilingual stopword list — small, hand-rolled. Covers EN + BHS.
# Kept short on purpose: top-words still surface real content if you remove these.
STOPWORDS: set[str] = {
    # English
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "at", "by", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "being", "i", "you", "he", "she",
    "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "so", "do", "don", "t", "s", "m", "re", "ve",
    "ll", "d", "yeah", "oh", "uh", "yo", "ay", "hey", "na", "la",
    # BHS (bosnian/serbian/croatian)
    "i", "u", "na", "se", "je", "su", "te", "to", "ti", "ja", "mi", "vi", "on", "ona", "ono",
    "oni", "one", "moj", "tvoj", "njegov", "njen", "naš", "vaš", "njihov", "što", "šta", "ko",
    "ali", "ili", "pa", "da", "ne", "nije", "neka", "ako", "kao", "samo", "sad", "još", "već",
    "sve", "svi", "kad", "tad", "tu", "tamo", "ovde", "ovo", "ono", "taj", "ova", "onaj",
    "bez", "od", "do", "za", "po", "iz", "kroz", "uz", "niz", "pred", "pod", "nad", "među",
    "bih", "bi", "bismo", "biste", "ću", "ćeš", "će", "ćemo", "ćete",
    "jer", "biti", "samo", "jako", "si", "sam", "smo", "ste", "kô", "k'o", "ko",
    "već", "još", "li", "nek",
}


@dataclass
class SongStats:
    # core counts
    word_count: int = 0
    char_count_no_spaces: int = 0
    line_count: int = 0
    section_count: int = 0

    # vocabulary
    unique_words: int = 0
    type_token_ratio: float = 0.0  # unique / total
    hapax_count: int = 0           # words used exactly once
    hapax_ratio: float = 0.0

    # word length
    avg_word_length: float = 0.0
    longest_words: list[str] = field(default_factory=list)
    word_length_hist: dict[int, int] = field(default_factory=dict)

    # line length
    avg_words_per_line: float = 0.0
    longest_line_words: int = 0
    shortest_line_words: int = 0

    # top words
    top_words: list[tuple[str, int]] = field(default_factory=list)
    top_words_no_stop: list[tuple[str, int]] = field(default_factory=list)

    # structure
    section_kinds: dict[str, int] = field(default_factory=dict)
    section_sequence: list[str] = field(default_factory=list)  # order, e.g. ["intro","verse","chorus","verse","chorus"]
    chorus_ratio: float = 0.0  # share of total lines that live in chorus sections

    # repetition
    repetition_ratio: float = 0.0  # 1 - (unique lines / total lines)

    # ---- placeholders for Epoch 4 ----
    language_mix: dict[str, float] = field(default_factory=dict)  # {"bs": 0.7, "en": 0.3}
    profanity_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute(lyrics: str, *, top_n: int = 20, longest_n: int = 10) -> SongStats:
    sections = parse_sections(lyrics)
    lines = all_lines(lyrics)
    tokens = tokenize(" ".join(lines))

    stats = SongStats()
    if not tokens:
        return stats

    # core counts
    stats.word_count = len(tokens)
    stats.char_count_no_spaces = char_count("\n".join(lines))
    stats.line_count = len(lines)
    stats.section_count = len(sections)

    # vocabulary
    counts = Counter(tokens)
    stats.unique_words = len(counts)
    stats.type_token_ratio = round(stats.unique_words / stats.word_count, 4)
    hapax = [w for w, c in counts.items() if c == 1]
    stats.hapax_count = len(hapax)
    stats.hapax_ratio = round(stats.hapax_count / stats.unique_words, 4)

    # word length
    lengths = [len(t) for t in tokens]
    stats.avg_word_length = round(sum(lengths) / len(lengths), 2)
    # longest unique words
    uniq_sorted = sorted(set(tokens), key=lambda w: (-len(w), w))
    stats.longest_words = uniq_sorted[:longest_n]
    hist: Counter[int] = Counter(lengths)
    stats.word_length_hist = dict(sorted(hist.items()))

    # line length
    line_word_counts = [len(tokenize(line)) for line in lines]
    line_word_counts = [n for n in line_word_counts if n > 0]
    if line_word_counts:
        stats.avg_words_per_line = round(sum(line_word_counts) / len(line_word_counts), 2)
        stats.longest_line_words = max(line_word_counts)
        stats.shortest_line_words = min(line_word_counts)

    # top words
    stats.top_words = counts.most_common(top_n)
    stats.top_words_no_stop = [
        (w, c) for w, c in counts.most_common(top_n * 3) if w not in STOPWORDS
    ][:top_n]

    # structure
    kinds: Counter[str] = Counter()
    sequence: list[str] = []
    chorus_lines = 0
    for sec in sections:
        kinds[sec.kind] += 1
        sequence.append(sec.kind)
        if sec.kind in {"chorus", "hook", "refrain"}:
            chorus_lines += len(sec.lines)
    stats.section_kinds = dict(kinds)
    stats.section_sequence = sequence
    stats.chorus_ratio = round(chorus_lines / stats.line_count, 4) if stats.line_count else 0.0

    # repetition (line-level)
    unique_lines = len({line.strip().lower() for line in lines if line.strip()})
    stats.repetition_ratio = round(1 - (unique_lines / stats.line_count), 4)

    return stats


# ---- artist-level aggregation ----------------------------------------------


@dataclass
class ArtistStats:
    song_count: int = 0
    total_words: int = 0
    total_unique_words: int = 0
    avg_words_per_song: float = 0.0
    avg_ttr: float = 0.0
    avg_chorus_ratio: float = 0.0
    avg_repetition_ratio: float = 0.0
    top_words: list[tuple[str, int]] = field(default_factory=list)
    top_words_no_stop: list[tuple[str, int]] = field(default_factory=list)
    longest_song: dict[str, Any] = field(default_factory=dict)
    shortest_song: dict[str, Any] = field(default_factory=dict)
    richest_song: dict[str, Any] = field(default_factory=dict)  # highest TTR

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate(songs_with_lyrics: list[tuple[str, str]], *, top_n: int = 30) -> ArtistStats:
    """Aggregate stats over (title, lyrics) pairs."""
    out = ArtistStats()
    if not songs_with_lyrics:
        return out

    per_song: list[tuple[str, SongStats]] = []
    global_counts: Counter[str] = Counter()
    vocab: set[str] = set()

    for title, lyrics in songs_with_lyrics:
        s = compute(lyrics)
        if s.word_count == 0:
            continue
        per_song.append((title, s))
        tokens = tokenize(" ".join(all_lines(lyrics)))
        global_counts.update(tokens)
        vocab.update(tokens)

    if not per_song:
        return out

    out.song_count = len(per_song)
    out.total_words = sum(s.word_count for _, s in per_song)
    out.total_unique_words = len(vocab)
    out.avg_words_per_song = round(out.total_words / out.song_count, 2)
    out.avg_ttr = round(sum(s.type_token_ratio for _, s in per_song) / out.song_count, 4)
    out.avg_chorus_ratio = round(
        sum(s.chorus_ratio for _, s in per_song) / out.song_count, 4
    )
    out.avg_repetition_ratio = round(
        sum(s.repetition_ratio for _, s in per_song) / out.song_count, 4
    )
    out.top_words = global_counts.most_common(top_n)
    out.top_words_no_stop = [
        (w, c) for w, c in global_counts.most_common(top_n * 3) if w not in STOPWORDS
    ][:top_n]

    # Filter out short songs/demos/snippets from highlights to avoid skewing stats (e.g. 21-word demos winning widest vocabulary)
    highlights_eligible = [
        (title, s) for title, s in per_song
        if s.word_count >= 80 and not any(
            kw in title.lower()
            for kw in ["(demo)", "[demo]", "(snippet)", "[snippet]", "(teaser)", "[teaser]", "(promo)", "[promo]", "(skit)", "[skit]"]
        )
    ]
    if not highlights_eligible:
        highlights_eligible = per_song

    longest = max(highlights_eligible, key=lambda ps: ps[1].word_count)
    shortest = min(highlights_eligible, key=lambda ps: ps[1].word_count)
    richest = max(highlights_eligible, key=lambda ps: ps[1].type_token_ratio)
    out.longest_song = {"title": longest[0], "words": longest[1].word_count}
    out.shortest_song = {"title": shortest[0], "words": shortest[1].word_count}
    out.richest_song = {"title": richest[0], "ttr": richest[1].type_token_ratio}
    return out
