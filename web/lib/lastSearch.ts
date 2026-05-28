/**
 * Tiny localStorage helpers for remembering the user's last search on each
 * page. When the user clicks a nav link (which clears URL params), we
 * restore from here so their progress isn't lost.
 */

const SONG_KEY = "lyricstats:last-song";
const ARTIST_KEY = "lyricstats:last-artist";

export type LastSong = { artist: string; title: string };
export type LastArtist = { name: string; min: number };

export function saveLastSong(v: LastSong): void {
  try {
    localStorage.setItem(SONG_KEY, JSON.stringify(v));
  } catch {
    /* private mode etc. — ignore */
  }
}

export function loadLastSong(): LastSong | null {
  try {
    const raw = localStorage.getItem(SONG_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as LastSong;
    return v.artist && v.title ? v : null;
  } catch {
    return null;
  }
}

export function saveLastArtist(v: LastArtist): void {
  try {
    localStorage.setItem(ARTIST_KEY, JSON.stringify(v));
  } catch {
    /* ignore */
  }
}

export function loadLastArtist(): LastArtist | null {
  try {
    const raw = localStorage.getItem(ARTIST_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as LastArtist;
    return v.name ? v : null;
  } catch {
    return null;
  }
}
