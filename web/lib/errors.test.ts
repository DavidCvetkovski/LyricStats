import { describe, expect, it } from "vitest";
import { friendlyError } from "./errors";

describe("friendlyError", () => {
  it("maps 'Failed to fetch' to an offline-style message", () => {
    const e = friendlyError(new Error("Failed to fetch"));
    expect(e.headline.toLowerCase()).toContain("reach the server");
    expect(e.suggestion).toMatch(/backend|api/i);
  });

  it("maps a 401 invalid_token response to a token-rotation message", () => {
    const e = friendlyError(
      new Error(
        'API 401: {"error":"invalid_token","error_description":"The access token provided is expired"}',
      ),
    );
    expect(e.headline.toLowerCase()).toContain("genius");
    expect(e.suggestion).toMatch(/token|rotate|generate/i);
  });

  it("maps a Genius 'Could not find lyrics' 404 to a not-found message", () => {
    const e = friendlyError(
      new Error(
        "API 404: Could not find lyrics for 'The Technicolors — Howl' on Genius or lyrics.ovh.",
      ),
    );
    expect(e.headline.toLowerCase()).toContain("couldn't find");
    expect(e.suggestion).toMatch(/spelling|different|the/i);
  });

  it("maps a 429 to a rate-limit message", () => {
    const e = friendlyError(new Error("API 429: Too Many Requests"));
    expect(e.headline.toLowerCase()).toContain("slow down");
    expect(e.suggestion).toMatch(/wait|already on file/i);
  });

  it("maps a broken NDJSON stream to a connection-cut message", () => {
    const e = friendlyError(new Error("Stream ended without a result"));
    expect(e.headline.toLowerCase()).toContain("cut out");
    expect(e.suggestion).toMatch(/again|fewer/i);
  });

  it("falls back to a calm generic message for unknown errors", () => {
    const e = friendlyError(new Error("RANDOM_OPAQUE_BACKEND_BURP_X712"));
    // Must not leak the raw token / opcode into the headline
    expect(e.headline).not.toContain("RANDOM_OPAQUE");
    expect(e.headline.length).toBeLessThan(80);
    expect(e.detail.length).toBeLessThan(120);
  });

  it("handles non-Error throwables (strings, numbers, undefined)", () => {
    expect(friendlyError("just a string").headline).toBeTruthy();
    expect(friendlyError(42).headline).toBeTruthy();
    expect(friendlyError(undefined).headline).toBeTruthy();
    expect(friendlyError(null).headline).toBeTruthy();
  });

  it("does not throw on a deeply nested object", () => {
    expect(() => friendlyError({ x: { y: { z: "boom" } } })).not.toThrow();
  });
});
