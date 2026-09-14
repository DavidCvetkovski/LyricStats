/**
 * Turn raw fetch / API errors into human-friendly editorial copy.
 *
 * Backend returns either:
 *   - 404 with body {"detail":"Could not find lyrics for 'X — Y' on Genius or lyrics.ovh."}
 *   - 500 with body {"detail":"<technical>"}
 *   - 401 (rare, Genius token issue) — buried inside FetchError messages
 *
 * The client also raises:
 *   - "Failed to fetch" — backend is down
 *   - "Stream ended without a result" — connection cut mid-fetch
 *   - "AbortError" — user navigated away
 */

export type FriendlyError = {
  headline: string; // short, italic serif
  detail: string; // small ink-mute caption underneath
  suggestion?: string; // optional next step
};

const NETWORK_PATTERNS = [
  /failed to fetch/i,
  /networkerror/i,
  /load failed/i,
  /ECONN/i,
  /net::ERR_/i,
];

const AUTH_PATTERNS = [
  /invalid_token/i,
  /401/,
  /token.*(expired|revoked|invalid)/i,
  /genius_token/i,
];

const NOT_FOUND_PATTERNS = [
  /could not find lyrics/i,
  /no songs found/i,
  /not found on genius/i,
  /no cached data/i,
  /api 404/i,
];

const RATE_LIMIT_PATTERNS = [/429/, /rate.?limit/i, /too many requests/i];

const STREAM_BROKEN_PATTERNS = [
  /stream ended without/i,
  /unexpected end of stream/i,
];

export function friendlyError(err: unknown): FriendlyError {
  const raw =
    err instanceof Error
      ? err.message
      : typeof err === "string"
        ? err
        : String(err);

  if (NETWORK_PATTERNS.some((p) => p.test(raw))) {
    return {
      headline: "Couldn't reach the server.",
      detail: "The song service is unavailable at the moment.",
      suggestion: "Try again shortly, or use your own text on the song page.",
    };
  }

  if (AUTH_PATTERNS.some((p) => p.test(raw))) {
    return {
      headline: "The lyric service is unavailable.",
      detail:
        "We couldn’t open the lyric service.",
      suggestion:
        "Please try again later, or use your own text.",
    };
  }

  if (RATE_LIMIT_PATTERNS.some((p) => p.test(raw))) {
    return {
      headline: "The lyric service is asking us to slow down.",
      detail: "The lyric provider is temporarily limiting requests.",
      suggestion: "Wait a minute and try again — or try a song that's already cached.",
    };
  }

  if (NOT_FOUND_PATTERNS.some((p) => p.test(raw))) {
    return {
      headline: "Couldn't find lyrics for this song.",
      detail:
        "The song may be filed under a slightly different spelling, or it is not indexed in the lyric database.",
      suggestion: "Try a different spelling, drop a 'The', or choose another song.",
    };
  }

  if (STREAM_BROKEN_PATTERNS.some((p) => p.test(raw))) {
    return {
      headline: "The connection cut out mid-fetch.",
      detail: "The connection ended before the reading was ready.",
      suggestion: "Try again in a moment, or view a smaller catalogue.",
    };
  }

  // Generic fallback — never leak raw JSON or stack traces
  return {
    headline: "Something didn't go through.",
    detail: "We had a small problem fetching this one.",
    suggestion: "Try again — or pick a different song / artist.",
  };
}
