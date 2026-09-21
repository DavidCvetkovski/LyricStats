"use client";

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import type { SongPayload } from "@/lib/types";
import { mmss } from "@/lib/format";

const HEADER = /^\[[^\]]+\]$/;
/** A pause between two sung lines long enough to draw as a rule. */
const SILENCE = 8;
/** Lines shown while the sheet is folded. */
const PREVIEW = 6;

type Row =
  | { kind: "blank"; key: number }
  | { kind: "header"; key: number; text: string }
  | { kind: "line"; key: number; i: number; text: string };

/** The text as rows, numbered the way the reading counts lines. */
function rowsOf(lyrics: string): Row[] {
  let i = 0;
  return lyrics
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((raw, key): Row => {
      const text = raw.trim();
      if (!text) return { kind: "blank", key };
      if (HEADER.test(text)) return { kind: "header", key, text: text.slice(1, -1) };
      return { kind: "line", key, i: i++, text };
    });
}

/** The title as it is counted: parentheses dropped, any spacing between the words. */
function titlePattern(title: string): RegExp | null {
  const words = title
    .replace(/[([].*?[)\]]/g, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const joined = words.join(" ");
  if (!words.length || joined.length < 3 || joined.length > 60 || words.length > 6) return null;
  return new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+")})`, "gi");
}

function markTitle(text: string, re: RegExp | null): ReactNode {
  if (!re) return text;
  const parts = text.split(re);
  if (parts.length === 1) return text;
  return parts.map((part, k) =>
    k % 2 === 1 ? (
      <mark key={k} className="song-drop">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

/** The first few sung lines, with the furniture between them. */
function preview(rows: Row[], lines: number): Row[] {
  const out: Row[] = [];
  let seen = 0;
  for (const row of rows) {
    if (row.kind === "line") {
      if (seen === lines) break;
      seen++;
    } else if (!out.length) {
      continue;
    }
    out.push(row);
  }
  return out;
}

/**
 * The words, with the reading's marks in the margins: the returning line
 * underlined and counted, the title highlighted where it is sung, the time
 * each line lands when the transcription is timed, and the silences between
 * lines drawn as rules. Folded to its first lines until asked for, opened by
 * a #text link, and readable plain for copying.
 */
export function TextSheet({ song }: { song: SongPayload }) {
  const r = song.reading!;
  const [open, setOpen] = useState(false);
  const [plain, setPlain] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (window.location.hash === "#text") setOpen(true);
  }, []);

  const rows = useMemo(() => rowsOf(song.lyrics), [song.lyrics]);
  const titleRe = useMemo(() => titlePattern(song.title), [song.title]);
  const hooks = useMemo(() => new Set((r.top_line_n ?? 0) >= 3 ? r.top_line_at ?? [] : []), [r]);
  const drops = useMemo(() => new Set(r.drop_at ?? []), [r]);
  const times = r.line_at ?? null;
  const firstHook = (r.top_line_n ?? 0) >= 3 ? r.top_line_at?.[0] : undefined;
  const lineCount = r.line_count ?? rows.filter((row) => row.kind === "line").length;

  // Silence before line i: the pause since the line before it, when both are
  // timed; and the longest silence of the recording, which the clock places.
  const silence = useMemo(() => {
    const out = new Map<number, number>();
    if (!times) return out;
    times.forEach((t, i) => {
      const prev = i > 0 ? times[i - 1] : null;
      if (t != null && prev != null && t - prev >= SILENCE) out.set(i, t - prev);
    });
    if (r.gap != null && r.gap_at != null && r.gap >= SILENCE) {
      // After the stamped line the silence follows, and after any line sung
      // with it (unstamped): the rule goes above the next stamped line.
      const before = times.findIndex((t) => t != null && Math.abs(t - r.gap_at!) < 0.6);
      let next = before + 1;
      while (before >= 0 && next < times.length && times[next] == null) next++;
      if (before >= 0 && next < times.length) out.set(next, r.gap);
    }
    return out;
  }, [times, r.gap, r.gap_at]);

  const marked = open && !plain;
  const visible = open ? rows : preview(rows, PREVIEW);

  async function copy() {
    try {
      await navigator.clipboard.writeText(song.lyrics);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* the text is on the page either way */
    }
  }

  // A silence is drawn above the line it precedes, or above that line's
  // section heading when one sits between.
  const pauseRow = new Map<number, number>();
  if (marked) {
    visible.forEach((row, k) => {
      if (row.kind !== "line" || !silence.has(row.i)) return;
      let at = k;
      for (let j = k - 1; j >= 0 && visible[j].kind !== "line"; j--) {
        if (visible[j].kind === "header") at = j;
      }
      pauseRow.set(at, silence.get(row.i)!);
    });
  }

  let order = 0;
  const body = visible.map((row, k) => {
    const style = { "--i": order++ } as CSSProperties;
    const pause = pauseRow.get(k);
    const rule =
      pause != null ? (
        <div
          className={`song-silence ${r.gap != null && Math.abs(pause - r.gap) < 0.6 ? "is-longest" : ""}`}
          style={style}
        >
          {r.gap != null && Math.abs(pause - r.gap) < 0.6 ? "the longest silence · " : ""}
          {Math.round(pause)} s
        </div>
      ) : null;
    if (row.kind === "blank") return <div key={row.key} className="h-5" aria-hidden />;
    if (row.kind === "header") {
      return (
        <div key={row.key} className="contents">
          {rule}
          <div className="song-header" style={style}>
            {row.text}
          </div>
        </div>
      );
    }
    const isHook = marked && hooks.has(row.i);
    const t = marked && times ? times[row.i] : null;
    return (
      <div key={row.key} className="contents">
        {rule}
        <div className={`song-line ${isHook ? "is-hook" : ""}`} style={style}>
          <span className="song-gutter">{t != null ? mmss(t) : ""}</span>
          <span className="song-words">{marked && drops.has(row.i) ? markTitle(row.text, titleRe) : row.text}</span>
          <span className="song-note">{isHook && row.i === firstHook ? `×${r.top_line_n}` : ""}</span>
        </div>
      </div>
    );
  });

  return (
    <div className={`song-sheet ${open ? "is-open" : ""}`}>
      <div className="flex items-baseline justify-between gap-4 border-b border-rule-strong pb-3">
        <p className="smallcaps">The text{marked && times ? " · on the clock" : ""}</p>
        <p className="smallcaps">{lineCount} lines</p>
      </div>

      {marked && r.first != null && r.first >= 10 && (
        <p className="song-silence mt-6">{mmss(r.first)} of music before the first word</p>
      )}

      <div translate="no" className={`song-sheet-body notranslate ${open ? "" : "is-folded"} ${marked && times ? "" : "no-clock"}`}>
        {body}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
        {open ? (
          <>
            <button type="button" className="pill pill-ghost" onClick={() => setOpen(false)}>
              Fold the words
            </button>
            <button type="button" className="song-sheet-tool" aria-pressed={plain} onClick={() => setPlain((p) => !p)}>
              {plain ? "Show the marks" : "Plain text"}
            </button>
            <button type="button" className="song-sheet-tool" onClick={copy}>
              {copied ? "Copied" : "Copy the text"}
            </button>
          </>
        ) : (
          <button type="button" className="pill" onClick={() => setOpen(true)}>
            Read the words · {lineCount} lines →
          </button>
        )}
      </div>

      {marked && (
        <p className="mt-5 text-[0.78rem] italic text-ink-mute">
          {hooks.size ? "Underlined in oxblood: the line that comes back. " : ""}
          {drops.size ? "Highlighted: the title, where it is sung. " : ""}
          {times ? "The minutes in the margin are from the timed transcription." : ""}
        </p>
      )}
    </div>
  );
}
