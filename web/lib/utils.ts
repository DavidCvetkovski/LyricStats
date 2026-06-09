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
