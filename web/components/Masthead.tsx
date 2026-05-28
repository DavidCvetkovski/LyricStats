import Link from "next/link";

export function Masthead() {
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <header className="border-b border-rule-strong">
      <div className="mx-auto max-w-6xl px-6 pt-7 pb-5">
        <div className="flex items-center justify-between gap-6 text-[0.72rem] uppercase tracking-[0.18em] text-ink-mute">
          <span>Vol. I · No. 1</span>
          <span className="hidden sm:inline">{today}</span>
          <span>Established 2026</span>
        </div>
        <Link href="/" className="block mt-4 text-center">
          <h1
            className="display text-ink"
            style={{ fontSize: "clamp(3rem, 8vw, 6rem)" }}
          >
            LyricStats
          </h1>
          <p className="smallcaps mt-2">
            A Quarterly Statistical Review of Popular Lyrics
          </p>
        </Link>
        <nav className="mt-6 flex items-center justify-center gap-6 text-[0.78rem] uppercase tracking-[0.15em]">
          <Link href="/" className="hover:text-accent transition-colors">
            Front Page
          </Link>
          <span className="text-rule-strong">·</span>
          <Link href="/song" className="hover:text-accent transition-colors">
            On a Song
          </Link>
          <span className="text-rule-strong">·</span>
          <Link href="/artist" className="hover:text-accent transition-colors">
            The Artist
          </Link>
        </nav>
      </div>
    </header>
  );
}
