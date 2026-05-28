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
      <div className="mx-auto max-w-6xl px-6 pt-7 pb-6">
        {/* Folio strip — vol · date · established */}
        <div className="flex items-center justify-between gap-6 text-[0.7rem] uppercase tracking-[0.18em] text-ink-mute">
          <span>Vol. I · No. 1</span>
          <span className="hidden sm:inline">{today}</span>
          <span>Established 2026</span>
        </div>

        {/* Wordmark */}
        <Link href="/" className="block mt-7 text-center">
          <h1
            className="display text-ink leading-[0.88]"
            style={{
              fontSize: "clamp(3rem, 8vw, 6rem)",
              // larger optical size + softer terminals so the 'y' descender
              // doesn't crowd the subtitle below at any viewport
              fontVariationSettings: '"opsz" 144, "SOFT" 50',
            }}
          >
            LyricStats
          </h1>
          <p className="smallcaps mt-6 text-[0.68rem]">
            A Quarterly Statistical Review of Popular Lyrics
          </p>
        </Link>

        {/* Hairline rule above nav — breathing room + a subtle separator */}
        <hr className="hairline mt-8 mb-5 mx-auto max-w-xs opacity-60" />

        {/* Navigation — at the bottom, spaced */}
        <nav className="flex items-center justify-center gap-x-8 sm:gap-x-12 text-[0.74rem] uppercase tracking-[0.18em]">
          <Link href="/" className="hover:text-accent transition-colors">
            Front Page
          </Link>
          <Link
            href="/song"
            className="hover:text-accent transition-colors relative before:content-['❖'] before:text-accent before:absolute before:-left-6 before:top-1/2 before:-translate-y-1/2 before:text-[0.6rem]"
          >
            On a Song
          </Link>
          <Link href="/artist" className="hover:text-accent transition-colors">
            The Artist
          </Link>
        </nav>
      </div>
    </header>
  );
}
