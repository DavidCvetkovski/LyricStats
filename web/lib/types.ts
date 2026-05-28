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
  source: "cache" | "genius" | "ovh";
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
};

export type ArtistPayload = {
  name: string;
  genius_url: string | null;
  songs: SongMeta[];
  stats: ArtistStats;
};
