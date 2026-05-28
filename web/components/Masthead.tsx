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
      <div className="mx-auto max-w-6xl px-6 pt-6 pb-8">
        {/* Top folio strip — vol · nav · est */}
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 text-[0.7rem] uppercase tracking-[0.18em] text-ink-mute">
          <span className="justify-self-start">
            Vol. I · No. 1
            <span className="hidden md:inline">
              <span className="mx-2 text-rule-strong">|</span>
              {today}
            </span>
          </span>

          <nav className="justify-self-center flex items-center gap-4 sm:gap-5 text-ink whitespace-nowrap">
            <Link href="/" className="hover:text-accent transition-colors">
              Front Page
            </Link>
            <span aria-hidden className="text-rule-strong">·</span>
            <Link href="/song" className="hover:text-accent transition-colors">
              On a Song
            </Link>
            <span aria-hidden className="text-rule-strong">·</span>
            <Link href="/artist" className="hover:text-accent transition-colors">
              The Artist
            </Link>
          </nav>

          <span className="justify-self-end">Established 2026</span>
        </div>

        {/* Wordmark */}
        <Link href="/" className="block mt-6 text-center group">
          <h1
            className="display text-ink leading-[0.9]"
            style={{
              fontSize: "clamp(3rem, 8vw, 6rem)",
              // less dramatic optical size + softer terminals so the 'y' descender
              // doesn't read as quite so heavy beneath the title
              fontVariationSettings: '"opsz" 144, "SOFT" 50',
            }}
          >
            LyricStats
          </h1>
          <p className="smallcaps mt-5 text-[0.68rem]">
            A Quarterly Statistical Review of Popular Lyrics
          </p>
        </Link>
      </div>
    </header>
  );
}
