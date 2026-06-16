export type SongStats = {
  word_count: number;
  char_count_no_spaces: number;
  line_count: number;
  section_count: number;
  unique_words: number;
  type_token_ratio: number;
  hapax_count: number;
  hapax_ratio: number;
  avg_word_length: number;
  longest_words: string[];
  word_length_hist: Record<string, number>;
  avg_words_per_line: number;
  longest_line_words: number;
  shortest_line_words: number;
  top_words: [string, number][];
  top_words_no_stop: [string, number][];
  section_kinds: Record<string, number>;
  section_sequence: string[];
  chorus_ratio: number;
  repetition_ratio: number;
  language_mix: Record<string, number>;
  profanity_count: number;
};

export type SongPayload = {
  artist: string;
  title: string;
  album: string | null;
  year: number | null;
  source: "cache" | "genius" | "lrclib" | "ovh";
  lyrics: string;
  stats: SongStats;
};

export type SongMeta = {
  title: string;
  album: string | null;
  year: number | null;
  word_count: number;
  unique_words: number;
  type_token_ratio: number;
  chorus_ratio: number;
  repetition_ratio: number;
  line_count: number;
  has_sections: boolean;
};

export type ArtistStats = {
  song_count: number;
  total_words: number;
  total_unique_words: number;
  avg_words_per_song: number;
  avg_ttr: number;
  avg_chorus_ratio: number;
  avg_repetition_ratio: number;
  top_words: [string, number][];
  top_words_no_stop: [string, number][];
  longest_song: { title?: string; words?: number };
  shortest_song: { title?: string; words?: number };
  richest_song: { title?: string; ttr?: number };
  // extended stats from dataset pipeline
  avg_hook_share?: number;
  avg_wpm?: number;
  avg_rhyme?: number;
  question_share?: number;
  exclaim_share?: number;
  one_word_line_share?: number;
  avg_word_length?: number;
  title_drops_total?: number;
  synced_share?: number;
  avg_first_word_s?: number;
  longest_word?: string;
  // highlights
  career_line?: { line: string; count: number; title: string } | null;
  fastest_song?: { title: string; wpm: number } | null;
  slowest_song?: { title: string; wpm: number } | null;
  biggest_title_drop?: { title: string; count: number } | null;
  fastest_burst?: { title: string; words15s: number } | null;
  longest_intro?: { title: string; s: number } | null;
  longest_silence?: { title: string; s: number } | null;
  density_curve?: number[] | null;
  signature_words?: [string, number, number][] | null;
  exclusive_words?: [string, number][] | null;
  percentiles?: Record<string, number | null> | null;
  lang_mix?: Record<string, number>;
};

export type ArtistPayload = {
  name: string;
  genius_url: string | null;
  songs: SongMeta[];
  stats: ArtistStats;
  cached_total: number;
  sampled: number;
  // Present for precomputed dataset artists (whole-career aggregate, no
  // per-song catalogue). `has_sections` is carried here because there's no
  // per-song list to infer it from.
  has_sections?: boolean;
  source?: "dataset" | "cache" | "genius";
  // True when this artist isn't in the preloaded dataset and we could only
  // gather a partial catalogue (fewer than the ~20-song floor).
  limited?: boolean;
};
