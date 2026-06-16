import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Set the environment variable before dynamically importing the module
process.env.NEXT_PUBLIC_API_BASE = "https://api.lyricstats.dev";

describe("api client library", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("points to the correct NEXT_PUBLIC_API_BASE", async () => {
    const { suggestArtists } = await import("./api");

    // Mock successful JSON response
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions: [] }),
    });

    await suggestArtists("Taylor");

    expect(global.fetch).toHaveBeenCalled();
    const calledUrl = (global.fetch as any).mock.calls[0][0];
    
    // It should request the configured NEXT_PUBLIC_API_BASE (https://api.lyricstats.dev)
    expect(calledUrl).toContain("https://api.lyricstats.dev/api/artist/suggest");
  });

  it("handles getSong request structure correctly", async () => {
    const { getSong } = await import("./api");

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ title: "All Too Well" }),
    });

    await getSong("Taylor Swift", "All Too Well");

    expect(global.fetch).toHaveBeenCalled();
    const calledUrl = (global.fetch as any).mock.calls[0][0];
    expect(calledUrl).toContain("https://api.lyricstats.dev/api/song");
    expect(calledUrl).toContain("artist=Taylor+Swift");
    expect(calledUrl).toContain("title=All+Too+Well");
  });

  it("handles getArtistPool query parameters correctly", async () => {
    const { getArtistPool } = await import("./api");

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ name: "Taylor Swift", to_fetch: [] }),
    });

    await getArtistPool("Taylor Swift", 50, true, "word_count");

    expect(global.fetch).toHaveBeenCalled();
    const calledUrl = (global.fetch as any).mock.calls[0][0];
    expect(calledUrl).toContain("https://api.lyricstats.dev/api/artist/pool");
    expect(calledUrl).toContain("name=Taylor+Swift");
    expect(calledUrl).toContain("min=50");
    expect(calledUrl).toContain("fresh=1");
    expect(calledUrl).toContain("shuffle=word_count");
  });

  it("throws friendly error when API returns non-OK status", async () => {
    const { suggestArtists } = await import("./api");

    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: async () => "Artist not found in dataset",
    });

    await expect(suggestArtists("Taylor")).rejects.toThrow("API 404: Artist not found in dataset");
  });
});
