export function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase());
}

/**
 * Aggressive match key — mirrors the backend's `normalize_key`: strip accents,
 * lowercase, drop everything but letters/digits. So "JAY-Z" and "jay z" both
 * collapse to "jayz". Used to filter cached suggestions client-side.
 */
export function artistKey(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

const NAME_TOKENS = /[\p{L}\p{N}]+|[&+]/gu;

/**
 * Other keys a name joined by "&", "+" or "and" may be filed under — mirrors
 * `_joiner_variants` in lyricstats/db.py. "Mumford & Sons" → "mumfordandsons",
 * "Simon and Garfunkel" → "simongarfunkel". Only a joiner between two words
 * counts, so "And One" and "Prozac+" have none.
 */
export function joinerVariants(name: string): string[] {
  const s = name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const toks = s.match(NAME_TOKENS) ?? [];
  const inner = (i: number) => i > 0 && i < toks.length - 1;
  const spelled = toks.map((t, i) => (inner(i) && (t === "&" || t === "+") ? "and" : t));
  const dropped = spelled.filter((t, i) => !(inner(i) && t === "and"));
  const exact = artistKey(name);
  const out: string[] = [];
  for (const words of [spelled, dropped]) {
    const key = artistKey(words.filter((t) => t !== "&" && t !== "+").join(""));
    if (key && key !== exact && !out.includes(key)) out.push(key);
  }
  return out;
}

/** Does an artist name match what was typed, under any of its spellings? */
export function nameMatches(name: string, typed: string): boolean {
  const have = artistKey(name);
  return [artistKey(typed), ...joinerVariants(typed)].some((k) => have.includes(k));
}

/** Lower-case word tokens, any script, vowel signs kept inside a word
 * (lyricstats/text.py TOKEN_RE); apostrophes stay inside a word. */
export function wordsIn(text: string): string[] {
  return text.normalize("NFC").toLowerCase().match(/\p{L}[\p{L}\p{M}]*(?:['’]\p{L}[\p{L}\p{M}]*)*/gu) ?? [];
}
