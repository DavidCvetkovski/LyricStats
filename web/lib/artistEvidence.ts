import type { ArtistStats } from "./types";
import { isFiller } from "./filler";

/**
 * A frequency label for artists without a computed signature: the most-used
 * word that carries meaning. Not an inferred noun, language or vocal trait.
 */
export function recurringWord(stats: ArtistStats): [string, number] | null {
  return (
    stats.top_words_no_stop.find(
      ([word, count]) => !isFiller(word) && !/['’]/.test(word) && Number.isFinite(count) && count > 0,
    ) ?? null
  );
}
