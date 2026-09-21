import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";
import { artistName, mmss, pct } from "@/lib/format";
import { fetchSong } from "@/lib/server";

export const alt = "A close reading on LyricStats";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PAPER = "#f6f1e8";
const INK = "#1a1614";
const INK_SOFT = "#4a423d";
const INK_MUTE = "#71675e";
const OXBLOOD = "#7a1f2b";

function decode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export default async function Image({ params }: { params: Promise<{ artist: string; title: string }> }) {
  const { artist, title } = await params;
  const [fraunces, song] = await Promise.all([
    readFile(join(process.cwd(), "assets/fonts/Fraunces-SemiBold.ttf")),
    fetchSong(decode(artist), decode(title)).catch(() => null),
  ]);

  const name = song?.title ?? "A close reading";
  const by = song ? `by ${artistName(song.artist)}` : "LyricStats";
  const r = song?.reading;
  const figures: [string, string][] = r
    ? [
        [r.wc.toLocaleString(), "words"],
        [r.uniq.toLocaleString(), "distinct"],
        r.first != null && r.first >= 20
          ? [mmss(r.first), "first word"]
          : r.top_line_n && r.top_line_n >= 3
            ? [String(r.top_line_n), "times the hook returns"]
            : [pct(r.rep), "lines repeated"],
      ]
    : [];
  const titleSize = name.length > 26 ? 60 : name.length > 14 ? 84 : 112;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: PAPER,
          border: `3px solid ${INK}`,
          boxShadow: `inset 0 0 0 9px ${PAPER}, inset 0 0 0 10px ${INK}`,
          padding: "56px 64px",
          fontFamily: "Fraunces",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, letterSpacing: 4, color: OXBLOOD }}>
          <span>LYRICSTATS</span>
          <span>A CLOSE READING</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: titleSize, color: INK, lineHeight: 1.02, letterSpacing: -2 }}>{name}</div>
          <div style={{ fontSize: 34, color: INK_SOFT, marginTop: 18 }}>{by}</div>
        </div>
        <div style={{ display: "flex", gap: 56, borderTop: `2px solid ${OXBLOOD}`, paddingTop: 28 }}>
          {figures.map(([value, label]) => (
            <div key={label} style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: 56, color: INK, lineHeight: 1 }}>{value}</span>
              <span style={{ fontSize: 20, color: INK_MUTE, letterSpacing: 3, marginTop: 10 }}>
                {label.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [{ name: "Fraunces", data: fraunces, style: "normal", weight: 600 }],
    },
  );
}
