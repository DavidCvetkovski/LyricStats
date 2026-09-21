import type { Reading } from "@/lib/types";
import { mmss } from "@/lib/format";

const W = 600;
const H = 200;
const TOP = 34;
const BASE = 156;

/**
 * Words sung in each tenth of the recording, on the song's own clock: minute
 * ticks along the bottom, the first word marked, the longest silence shaded.
 */
export function Clock({ reading: r }: { reading: Reading }) {
  const dur = r.duration!;
  const curve = r.curve!;
  const max = Math.max(1, ...curve);
  const bw = W / curve.length;
  const x = (t: number) => Math.max(0, Math.min(W, (t / dur) * W));
  const minutes: number[] = [];
  for (let t = 60; t < dur - 20; t += 60) minutes.push(t);
  const silence = r.gap != null && r.gap_at != null && r.gap >= 5;
  const first = r.first != null ? x(r.first) : null;
  const firstOnRight = first != null && first > W * 0.7;

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="song-clock w-full overflow-visible"
        role="img"
        aria-label={`Words sung per tenth of the song: ${curve.join(", ")}. First word at ${mmss(r.first)}.`}
      >
        {silence && (
          <rect
            className="silence"
            x={x(r.gap_at!)}
            y={TOP}
            width={Math.max(2, x(r.gap_at! + r.gap!) - x(r.gap_at!))}
            height={BASE - TOP}
          />
        )}
        {curve.map((v, i) => {
          const h = (v / max) * (BASE - TOP);
          return (
            <rect
              key={i}
              className="bar"
              x={i * bw + 2}
              y={BASE - h}
              width={bw - 4}
              height={h}
            />
          );
        })}
        <line className="axis" x1={0} y1={BASE} x2={W} y2={BASE} />
        {minutes.map((t) => (
          <g key={t}>
            <line className="axis" x1={x(t)} y1={BASE} x2={x(t)} y2={BASE + 6} />
            <text className="tick" x={x(t)} y={BASE + 22} textAnchor="middle">
              {mmss(t)}
            </text>
          </g>
        ))}
        <text className="tick" x={0} y={BASE + 22}>
          0:00
        </text>
        <text className="tick" x={W} y={BASE + 22} textAnchor="end">
          {mmss(dur)}
        </text>
        {first != null && (
          <g>
            <line className="marker" x1={first} y1={TOP - 16} x2={first} y2={BASE} />
            <text
              className="label"
              x={first + (firstOnRight ? -8 : 8)}
              y={TOP - 6}
              textAnchor={firstOnRight ? "end" : "start"}
            >
              first word · {mmss(r.first)}
            </text>
          </g>
        )}
      </svg>
      <figcaption className="mt-2 text-[0.78rem] italic text-ink-mute">
        Words sung in each tenth of the recording.
        {silence
          ? ` The shaded stretch is the longest silence: ${Math.round(r.gap!)} seconds from ${mmss(r.gap_at)}.`
          : ""}
      </figcaption>
    </figure>
  );
}
