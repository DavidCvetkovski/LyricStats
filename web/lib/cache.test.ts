import { describe, expect, it } from "vitest";
import { artistCache } from "./cache";
import type { ArtistPayload } from "./types";

describe("MemoryCacheStore", () => {
  it("should get null initially", () => {
    artistCache.clear();
    expect(artistCache.get("test-key")).toBeNull();
    expect(artistCache.getLast()).toBeNull();
  });

  it("should retrieve set value when key matches", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    expect(artistCache.get("test-key")).toBe(mockPayload);
    expect(artistCache.getLast()).toEqual({ key: "test-key", data: mockPayload });
  });

  it("should return null when key does not match", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    expect(artistCache.get("different-key")).toBeNull();
  });

  it("should clear cache", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    artistCache.clear();
    expect(artistCache.get("test-key")).toBeNull();
    expect(artistCache.getLast()).toBeNull();
  });
});
