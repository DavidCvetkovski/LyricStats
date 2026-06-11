import Link from "next/link";
import { DateLine } from "./DateLine";

export function Masthead() {
  return (
    <header className="border-b border-rule-strong">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-5 sm:pt-7 pb-5 sm:pb-6">
        {/* Folio strip — vol · date · established. On mobile keeps just two
            ends so the row never wraps and the type stays readable. */}
        <div className="flex items-center justify-between gap-3 sm:gap-6 text-[0.62rem] sm:text-[0.7rem] uppercase tracking-[0.16em] sm:tracking-[0.18em] text-ink-mute">
          <span className="truncate">Vol. I · No. 1</span>
          <span className="hidden md:inline truncate">
            <DateLine />
          </span>
          <span className="truncate">Est. 2026</span>
        </div>

        {/* Wordmark — clamp shrinks more aggressively on small viewports */}
        <Link href="/" className="block mt-5 sm:mt-7 text-center">
          <h1
            className="display text-ink leading-[0.88]"
            style={{
              fontSize: "clamp(2.5rem, 11vw, 6rem)",
              fontVariationSettings: '"opsz" 144, "SOFT" 50',
            }}
          >
            LyricStats
          </h1>
          <p
            className="smallcaps mt-4 sm:mt-6"
            style={{ fontSize: "clamp(0.58rem, 2vw, 0.68rem)" }}
          >
            A Quarterly Statistical Review of Popular Lyrics
          </p>
        </Link>

        <hr className="hairline mt-6 sm:mt-8 mb-4 sm:mb-5 mx-auto max-w-xs opacity-60" />

        {/* Nav — wraps gracefully on narrow phones; diamond ornament is hidden
            on the smallest sizes so links don't shoulder-bump. */}
        <nav className="flex flex-wrap items-center justify-center gap-x-5 sm:gap-x-10 md:gap-x-12 gap-y-2 text-[0.66rem] sm:text-[0.74rem] uppercase tracking-[0.16em] sm:tracking-[0.18em]">
          <Link href="/" className="hover:text-accent transition-colors">
            Front Page
          </Link>
          <Link
            href="/song"
            className="hover:text-accent transition-colors relative sm:before:content-['❖'] sm:before:text-accent sm:before:absolute sm:before:-left-6 sm:before:top-1/2 sm:before:-translate-y-1/2 sm:before:text-[0.6rem]"
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
