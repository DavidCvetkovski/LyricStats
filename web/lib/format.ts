/** Seconds as m:ss ("0:58", "5:57"). */
export function mmss(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** A ratio as a whole percentage ("43%"). */
export function pct(ratio: number | null | undefined): string {
  if (ratio == null) return "";
  return `${Math.round(ratio * 100)}%`;
}

/** 1 → "1st", 2 → "2nd", 11 → "11th", 22 → "22nd". */
export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** Lower-case names from the live cache get their capitals back. */
export function artistName(name: string): string {
  if (name !== name.toLowerCase()) return name;
  return name.replace(/\S+/g, (w) => w[0].toUpperCase() + w.slice(1));
}

/** "4.7 million", "3,392", "12" */
export function bigNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")} million`;
  return n.toLocaleString("en-GB");
}
