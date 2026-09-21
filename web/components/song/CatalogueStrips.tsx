import type { Catalogue, CatalogueMetric } from "@/lib/types";
import { ordinal, pct } from "@/lib/format";

type Row = {
  key: "words" | "variety" | "repetition";
  label: string;
  fmt: (v: number) => string;
  most: string; // "longest"
  least: string; // "shortest"
};

const ROWS: Row[] = [
  { key: "words", label: "Words", fmt: (v) => v.toLocaleString(), most: "longest", least: "shortest" },
  { key: "variety", label: "Variety", fmt: pct, most: "most varied", least: "least varied" },
  { key: "repetition", label: "Repetition", fmt: pct, most: "most repetitive", least: "least repetitive" },
];

/** "3rd longest of 385" or, past the middle, "12th shortest of 385". */
export function standing(m: CatalogueMetric, songs: number, row: Row): string {
  if (m.rank <= songs / 2) return `${ordinal(m.rank)} ${row.most} of ${songs}`;
  return `${ordinal(songs - m.rank + 1)} ${row.least} of ${songs}`;
}

/**
 * Three bands, one per measure: every song of the artist as a faint mark
 * placed by its value, the median as a rule, this song in oxblood.
 */
export function CatalogueStrips({ catalogue }: { catalogue: Catalogue }) {
  return (
    <div className="space-y-9">
      {ROWS.map((row) => {
        const m = catalogue[row.key];
        if (!m) return null;
        const span = m.high - m.low || 1;
        const at = (v: number) => `${Math.max(0, Math.min(100, ((v - m.low) / span) * 100))}%`;
        return (
          <div key={row.key}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <span className="smallcaps">
                {row.label} · <b className="text-ink font-medium">{row.fmt(m.value)}</b>
              </span>
              <span className="font-serif italic text-ink-soft">{standing(m, catalogue.songs, row)}</span>
            </div>
            <div
              className="song-band"
              role="img"
              aria-label={`${row.label}: ${row.fmt(m.value)}, ${standing(m, catalogue.songs, row)} songs; the catalogue runs from ${row.fmt(m.low)} to ${row.fmt(m.high)} with a median of ${row.fmt(m.median)}`}
            >
              {m.points.map((v, i) => (
                <i key={i} style={{ left: at(v) }} />
              ))}
              <b className="median" style={{ left: at(m.median) }} />
              <b className="me" style={{ left: at(m.value) }} />
            </div>
            <div className="mt-1.5 flex justify-between text-[0.7rem] text-ink-mute">
              <span>{row.fmt(m.low)}</span>
              <span>median {row.fmt(m.median)}</span>
              <span>{row.fmt(m.high)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
