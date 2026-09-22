import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Set the environment variable before dynamically importing the module
process.env.NEXT_PUBLIC_API_BASE = "https://api.lyricstats.dev";

describe("api client library", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetModules();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
    vi.useRealTimers();
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
    expect(vi.mocked(fetch).mock.calls[0][1]?.cache).toBe("default");
  });

  it("forwards song cancellation and only bypasses HTTP caching for a forced refresh", async () => {
    const { getSong } = await import("./api");
    const controller = new AbortController();
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({}) } as Response);

    await getSong("Artist", "Title", { force: true, signal: controller.signal });

    expect(vi.mocked(fetch).mock.calls[0][0]).toContain("force=1");
    expect(vi.mocked(fetch).mock.calls[0][1]).toMatchObject({
      cache: "no-store",
      signal: controller.signal,
    });
  });

  it("asks for an artist's titles by name", async () => {
    const { getArtistTitles } = await import("./api");
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ name: "Michael Jackson", titles: ["Thriller"] }),
    } as Response);

    const out = await getArtistTitles("michael jackson");

    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/api/artist/titles?name=michael+jackson");
    expect(options).toMatchObject({ cache: "default" });
    expect(out.titles).toEqual(["Thriller"]);
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
    expect(vi.mocked(fetch).mock.calls[0][1]?.cache).toBe("no-store");
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

  it("reuses equivalent suggestions and complete prefixes without API calls", async () => {
    const { suggestArtists } = await import("./api");
    const suggestions = [
      { name: "Jay-Z", song_count: 100 },
      { name: "Jay Sean", song_count: 50 },
    ];
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ suggestions }) } as Response);

    await expect(suggestArtists("Jay", 20)).resolves.toEqual(suggestions);
    await expect(suggestArtists(" JÁY ", 20)).resolves.toEqual(suggestions);
    await expect(suggestArtists("jay z", 20)).resolves.toEqual([suggestions[0]]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not narrow capped results which could hide a deeper match", async () => {
    const { suggestArtists } = await import("./api");
    const suggestions = [{ name: "Jay-Z", song_count: 100 }];
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ suggestions }) } as Response);

    await suggestArtists("Jay", 1);
    await suggestArtists("Jay Sean", 1);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("keeps differing suggestion limits separate", async () => {
    const { suggestArtists } = await import("./api");
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ suggestions: [] }) } as unknown as Response);
    await suggestArtists("Jay", 1);
    await suggestArtists("Jay", 20);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("refreshes suggestions after five minutes", async () => {
    vi.useFakeTimers();
    const { suggestArtists } = await import("./api");
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ suggestions: [] }) } as unknown as Response);
    await suggestArtists("Jay", 20);
    vi.advanceTimersByTime(5 * 60 * 1000);
    await suggestArtists("Jay", 20);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not fetch short or cancelled suggestion queries", async () => {
    const { suggestArtists } = await import("./api");
    await expect(suggestArtists("J")).resolves.toEqual([]);
    const controller = new AbortController();
    controller.abort();
    await expect(suggestArtists("Jay", 20, controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not retain a response if its request was cancelled", async () => {
    const { suggestArtists } = await import("./api");
    const controller = new AbortController();
    let resolveResponse!: (value: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { resolveResponse = resolve; }));
    const first = suggestArtists("Jay", 20, controller.signal);
    controller.abort();
    resolveResponse({ ok: true, json: async () => ({ suggestions: [] }) } as unknown as Response);
    await first;
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ suggestions: [] }) } as unknown as Response);
    await suggestArtists("Jay", 20);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("asks the server again for a name with a joiner instead of narrowing a cached list", async () => {
    const { suggestArtists, getCachedArtistSuggestions } = await import("./api");
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions: [{ name: "Mumford", song_count: 20 }] }),
    } as Response);
    await suggestArtists("Mumf", 8);
    expect(getCachedArtistSuggestions("Mumford", 8)).toEqual([{ name: "Mumford", song_count: 20 }]);
    expect(getCachedArtistSuggestions("Mumford & So", 8)).toBeNull();
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions: [{ name: "Mumford And Sons", song_count: 170 }] }),
    } as Response);
    await suggestArtists("Mumford & So", 8);
    expect(getCachedArtistSuggestions("Mumford & So", 8)).toEqual([{ name: "Mumford And Sons", song_count: 170 }]);
    expect(getCachedArtistSuggestions("Mumford So", 8)).not.toEqual([{ name: "Mumford And Sons", song_count: 170 }]);
  });
});
