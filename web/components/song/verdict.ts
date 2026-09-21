import type { SongPayload } from "@/lib/types";
import { mmss, pct } from "@/lib/format";

/**
 * The deck under the title: two or three plain sentences assembled from the
 * song's own figures and where they fall among the archive. Only claims the
 * numbers support; a song with no standing among the archive gets nothing.
 */
export function verdict(song: SongPayload): string | null {
  const r = song.reading;
  const p = song.percentiles;
  if (!r) return null;
  const parts: string[] = [];

  if (p.wc != null) {
    if (p.wc >= 80) parts.push(`Long for a song: ${r.wc.toLocaleString()} words, more than ${p.wc}% of everything we have read.`);
    else if (p.wc <= 20) parts.push(`Short: ${r.wc} words, fewer than ${100 - p.wc}% of everything we have read.`);
    else parts.push(`${r.wc} words, an ordinary length.`);
  }

  if (r.rep === 0) {
    parts.push("No line is sung twice.");
  } else if (p.rep != null && p.rep >= 75) {
    parts.push(`It leans on repetition: ${pct(r.rep)} of its lines come back, more than in ${p.rep}% of songs.`);
  } else if (p.rep != null && p.rep <= 25) {
    parts.push(`It rarely repeats itself: only ${pct(r.rep)} of its lines come back.`);
  }

  if (r.first != null && r.first >= 30) {
    parts.push(`The first word waits ${mmss(r.first)}.`);
  } else if (r.wpm != null && p.wpm != null && p.wpm >= 85) {
    parts.push(`And it moves: ${Math.round(r.wpm)} words a minute, faster than ${p.wpm}% of songs.`);
  } else if (r.wpm != null && p.wpm != null && p.wpm <= 15) {
    parts.push(`It takes its time: ${Math.round(r.wpm)} words a minute, slower than ${100 - p.wpm}% of songs.`);
  }

  return parts.length ? parts.join(" ") : null;
}
