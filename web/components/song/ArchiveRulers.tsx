import type { Reading, SongPayload } from "@/lib/types";
import { mmss, pct } from "@/lib/format";

type Row = {
  key: keyof Reading;
  label: string;
  more: string;
  less: string;
  fmt: (v: number) => string;
};

export const RULERS: Row[] = [
  { key: "wc", label: "Length", more: "longer than", less: "shorter than", fmt: (v) => `${v.toLocaleString()} words` },
  { key: "ttr", label: "Variety", more: "more varied than", less: "plainer than", fmt: pct },
  { key: "rep", label: "Repetition", more: "more repetitive than", less: "less repetitive than", fmt: pct },
  { key: "hook", label: "Hook", more: "more hook than", less: "less hook than", fmt: pct },
  { key: "wpm", label: "Pace", more: "faster than", less: "slower than", fmt: (v) => `${Math.round(v)} a minute` },
  { key: "first", label: "First word", more: "later than", less: "sooner than", fmt: mmss },
  { key: "gap", label: "Longest silence", more: "longer than", less: "shorter than", fmt: (v) => `${Math.round(v)} s` },
  { key: "drops", label: "Title drops", more: "more than", less: "fewer than", fmt: (v) => `${v}` },
];

/** "longer than 78% of songs", or below the middle, "shorter than 61% of songs". */
export function phrase(row: Row, p: number): string {
  return p >= 50 ? `${row.more} ${p}% of songs` : `${row.less} ${100 - p}% of songs`;
}

/**
 * One ruler per measure: a hairline from the smallest song to the largest,
 * with this song's mark at its percentile.
 */
export function ArchiveRulers({ song }: { song: SongPayload }) {
  const r = song.reading;
  if (!r) return null;
  const rows = RULERS.filter((row) => {
    const v = r[row.key];
    return typeof v === "number" && song.percentiles[row.key] != null;
  });
  return (
    <div className="divide-y divide-rule border-y border-rule">
      {rows.map((row) => {
        const value = r[row.key] as number;
        const p = song.percentiles[row.key]!;
        return (
          <div
            key={row.key}
            className="grid grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[11rem_minmax(0,1fr)_14rem] items-center gap-x-5 gap-y-2 py-4"
          >
            <div className="min-w-0">
              <span className="smallcaps block">{row.label}</span>
              <span className="figure text-2xl text-ink block">{row.fmt(value)}</span>
            </div>
            <div className="song-ruler col-span-2 sm:col-span-1" role="img" aria-label={`${row.label}: ${phrase(row, p)}`}>
              <i style={{ left: `${p}%` }} />
            </div>
            <span className="font-serif italic text-ink-soft text-right sm:text-left row-start-1 col-start-2 sm:row-auto sm:col-auto">
              {phrase(row, p)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
