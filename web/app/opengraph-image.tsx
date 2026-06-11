import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt =
  "LyricStats · A quarterly statistical review of popular lyrics";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PAPER = "#f6f1e8";
const INK = "#1a1614";
const INK_SOFT = "#4a423d";
const OXBLOOD = "#7a1f2b";

export default async function Image() {
  const [fraunces, pinyon] = await Promise.all([
    readFile(join(process.cwd(), "assets/fonts/Fraunces-SemiBold.ttf")),
    readFile(join(process.cwd(), "assets/fonts/PinyonScript-Regular.ttf")),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: PAPER,
          border: `3px solid ${INK}`,
          boxShadow: `inset 0 0 0 9px ${PAPER}, inset 0 0 0 10px ${INK}`,
          padding: 48,
        }}
      >
        <div
          style={{
            fontFamily: "Pinyon",
            fontSize: 88,
            color: OXBLOOD,
            lineHeight: 1,
          }}
        >
          LS
        </div>
        <div
          style={{
            fontFamily: "Fraunces",
            fontSize: 132,
            color: INK,
            marginTop: 8,
            lineHeight: 1.05,
          }}
        >
          LyricStats
        </div>
        <div
          style={{
            width: 520,
            height: 2,
            background: OXBLOOD,
            marginTop: 36,
            marginBottom: 32,
          }}
        />
        <div
          style={{
            fontSize: 25,
            color: INK_SOFT,
            letterSpacing: 5,
            textTransform: "uppercase",
            textAlign: "center",
          }}
        >
          A Quarterly Statistical Review of Popular Lyrics
        </div>
        <div
          style={{
            fontSize: 26,
            color: OXBLOOD,
            letterSpacing: 4,
            textTransform: "uppercase",
            marginTop: 28,
          }}
        >
          Issue 01 · The Monsters of Sarajevo
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Fraunces", data: fraunces, style: "normal", weight: 600 },
        { name: "Pinyon", data: pinyon, style: "normal", weight: 400 },
      ],
    }
  );
}
