import { describe, expect, it } from "vitest";
import { catalogueSong, lyricLines, songSearchKey } from "./songExperience";
import type { ArtistPayload } from "./types";

const artist = {
  name: "Beyoncé", songs: [{ title: "Halo", album: "Example", year: 2008,
    word_count: 300, unique_words: 120, type_token_ratio: 0.4,
    chorus_ratio: 0.5, repetition_ratio: 0.3, has_sections: true }],
} as ArtistPayload;

describe("catalogue song summaries", () => {
  it("reuses real catalogue metrics while marking the analysis incomplete", () => {
    const summary = catalogueSong(artist, " BEYONCÉ ", " halo ");
    expect(summary?.stats.word_count).toBe(300);
    expect(summary?.stats.type_token_ratio).toBe(0.4);
    expect(summary?.has_sections).toBe(true);
    expect(summary?.analysis_complete).toBe(false);
    expect(summary?.lyrics).toBe("");
  });
  it("does not substitute another artist or another version of the song", () => {
    expect(catalogueSong(artist, "Someone else", "Halo")).toBeNull();
    expect(catalogueSong(artist, "Beyoncé", "Halo (Live)")).toBeNull();
    expect(catalogueSong(null, "Beyoncé", "Halo")).toBeNull();
  });
  it("uses unambiguous keys even for names containing the old separator", () => {
    expect(songSearchKey(" A ", " B ")).toBe(songSearchKey("a", "b"));
    expect(songSearchKey("a|b", "c")).not.toBe(songSearchKey("a", "b|c"));
  });
});

describe("repeated lyric lines", () => {
  it("ignores section headings and blanks, and matches without changing punctuation", () => {
    const lines = lyricLines("[Chorus]\nCome home\n\n come HOME \nCome home!\n[Chorus]");
    expect(lines.map((line) => line.repeated)).toEqual([false, true, false, true, false, false]);
    expect(lines[1].text).toBe("Come home");
  });
  it("handles empty lyrics and non-English text", () => {
    expect(lyricLines("")[0].repeated).toBe(false);
    expect(lyricLines("Noć\r\nNOĆ").every((line) => line.repeated)).toBe(true);
  });
});
