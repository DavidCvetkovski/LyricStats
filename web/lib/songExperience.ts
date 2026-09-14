import type { ArtistPayload, SongPayload } from "./types";

export function songSearchKey(artist: string, title: string): string {
  return JSON.stringify([artist.trim().toLowerCase(), title.trim().toLowerCase()]);
}

/** Reuse a catalogue the reader already opened; no lyric lookup is needed. */
export function catalogueSong(
  catalogue: ArtistPayload | null | undefined,
  artist: string,
  title: string,
): SongPayload | null {
  if (!catalogue || catalogue.name.trim().toLowerCase() !== artist.trim().toLowerCase()) return null;
  const track = catalogue.songs.find((s) => s.title.trim().toLowerCase() === title.trim().toLowerCase());
  if (!track) return null;
  return {
    artist: catalogue.name, title: track.title, album: track.album, year: track.year,
    source: "dataset", analysis_complete: false, has_sections: track.has_sections,
    lyrics: "",
    stats: {
      word_count: track.word_count, unique_words: track.unique_words,
      type_token_ratio: track.type_token_ratio, chorus_ratio: track.chorus_ratio,
      repetition_ratio: track.repetition_ratio,
      // Absent analysis is deliberately hidden by the catalogue-summary view.
      char_count_no_spaces: 0, line_count: 0, section_count: 0, hapax_count: 0,
      hapax_ratio: 0, avg_word_length: 0, longest_words: [], word_length_hist: {},
      avg_words_per_line: 0, longest_line_words: 0, shortest_line_words: 0,
      top_words: [], top_words_no_stop: [], section_kinds: {}, section_sequence: [],
      language_mix: {}, profanity_count: 0,
    },
  };
}

/** Display aid only: count matching visible lines, preserving punctuation. */
export function lyricLines(lyrics: string) {
  const lines = lyrics.split(/\r?\n/).map((text) => {
    const clean = text.trim();
    return { text, key: clean.toLowerCase(), heading: /^\[.*\]$/.test(clean) };
  });
  const counts = new Map<string, number>();
  for (const line of lines) {
    if (line.key && !line.heading) counts.set(line.key, (counts.get(line.key) ?? 0) + 1);
  }
  return lines.map((line) => ({ ...line, repeated: !line.heading && (counts.get(line.key) ?? 0) > 1 }));
}
