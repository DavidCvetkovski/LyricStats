/**
 * URL slugs for song pages: /song/<artist>/<title>.
 *
 * Accents stripped, lowercased, one hyphen between runs of letters and
 * digits. "Beyoncé" → "beyonce", "HUMBLE." → "humble", "Jala Brat" →
 * "jala-brat". Mirrors slugify() in lyricstats/db.py, which is what turns
 * the slug back into the artist and title on the API side.
 */
export function slugify(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** The song page for an artist and title, by name. */
export function songPath(artist: string, title: string): string {
  return `/song/${slugify(artist)}/${slugify(title)}`;
}
