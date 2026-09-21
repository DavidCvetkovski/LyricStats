import Link from "next/link";
import type { ReactNode } from "react";
import { Count, Reveal } from "@/components/EditorialMotion";
import { WordTable } from "@/components/WordTable";
import type { SongPayload } from "@/lib/types";
import { artistName, bigNumber, mmss, pct } from "@/lib/format";
import { ArchiveRulers, RULERS, phrase } from "./ArchiveRulers";
import { CatalogueStrips, standing } from "./CatalogueStrips";
import { Clock } from "./Clock";
import { HookStrip } from "./HookStrip";
import { Lyrics } from "./Lyrics";
import { verdict } from "./verdict";

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"];

const SOURCE_NAMES: Partial<Record<SongPayload["source"], string>> = {
  genius: "the Genius",
  lrclib: "the LRCLIB",
  ovh: "the lyrics.ovh",
};

/** The archive headline, per measure: [above the middle, below the middle]. */
const ARCHIVE_LEADS: Record<string, [string, string]> = {
  wc: ["Longer than {p}% of the songs", "Shorter than {p}% of the songs"],
  ttr: ["More varied than {p}% of the songs", "Plainer than {p}% of the songs"],
  rep: ["More repetitive than {p}% of the songs", "Less repetitive than {p}% of the songs"],
  hook: ["More hook than {p}% of the songs", "Less hook than {p}% of the songs"],
  wpm: ["Faster than {p}% of the songs", "Slower than {p}% of the songs"],
  first: ["Its first word comes later than in {p}% of the songs", "Its first word comes sooner than in {p}% of the songs"],
  gap: ["Its longest silence outlasts {p}% of the songs", "Its longest silence is shorter than in {p}% of the songs"],
  drops: ["It sings its own title more than {p}% of the songs", "It sings its own title less than {p}% of the songs"],
};

/** "lines 18, 24, 31, 37 and 42" */
function lineList(at: number[]): string {
  const n = at.map((i) => i + 1);
  if (n.length === 1) return `line ${n[0]}`;
  return `lines ${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`;
}

export function SongReading({ song }: { song: SongPayload }) {
  const r = song.reading;
  const p = song.percentiles;
  const by = artistName(song.artist);
  const full = song.analysis_complete && !!r && song.lyrics.trim().length > 0;
  const hook = full && !!r.top_line && (r.top_line_n ?? 0) >= 3;
  const clock = full && Array.isArray(r.curve) && !!r.duration;
  const archive = song.archive_songs > 0 && Object.keys(p).length > 0;

  const beats: { id: string; label: string }[] = [];
  if (full) beats.push({ id: "hook", label: hook ? "The hook" : "The lines" });
  if (clock) beats.push({ id: "clock", label: "The clock" });
  if (full) beats.push({ id: "words", label: "The words" });
  if (song.catalogue) beats.push({ id: "catalogue", label: "In the catalogue" });
  if (archive) beats.push({ id: "archive", label: "Among the archive" });
  if (full) beats.push({ id: "text", label: "The text" });
  const numeral = (id: string) => ROMAN[beats.findIndex((b) => b.id === id)] ?? "";

  const artistHref = `/artist?${new URLSearchParams({ name: song.artist, min: "500" }).toString()}`;
  const deck = verdict(song);

  return (
    <article className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      <p className="smallcaps">
        <Link href="/song" className="hover:text-accent transition-colors">
          Section II — On a Song
        </Link>
      </p>

      <header className="rise mt-10 sm:mt-14 border-b border-rule-strong pb-10 sm:pb-12 text-center">
        <p className="smallcaps text-accent mb-5">A close reading</p>
        <h1
          translate="no"
          className="display text-ink mx-auto break-words"
          style={{ fontSize: "clamp(3rem, 10vw, 7.5rem)", maxWidth: "18ch" }}
        >
          {song.title}
        </h1>
        <p className="mt-5 font-serif italic text-xl sm:text-2xl text-ink-soft">
          by{" "}
          <Link
            href={artistHref}
            className="not-italic text-ink hover:text-accent underline decoration-rule-strong underline-offset-4 transition-colors"
          >
            {by}
          </Link>
          {song.album ? (
            <>
              <span className="diamond" />
              <span>{song.album}</span>
            </>
          ) : null}
          {song.year ? <span className="text-ink-mute"> ({song.year})</span> : null}
        </p>
        {r && (
          <p className="smallcaps mt-6">
            {r.wc.toLocaleString()} words · {r.uniq.toLocaleString()} distinct
            {r.line_count ? ` · ${r.line_count} lines` : ""}
            {r.duration ? ` · ${mmss(r.duration)}` : ""}
          </p>
        )}
        {deck && (
          <p className="mx-auto mt-7 max-w-2xl font-serif text-lg sm:text-xl italic text-ink-soft leading-relaxed">
            {deck}
          </p>
        )}
        {beats.length > 1 && (
          <nav aria-label="In this reading" className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2">
            {beats.map((b, i) => (
              <a key={b.id} href={`#${b.id}`} className="smallcaps text-ink hover:text-accent transition-colors">
                {ROMAN[i]}. {b.label}
              </a>
            ))}
          </nav>
        )}
      </header>

      {!full && <NoText song={song} />}

      {full && (
        <Beat id="hook" numeral={numeral("hook")} label={hook ? "The hook" : "The lines"}>
          <div className="grid gap-10 lg:grid-cols-[1fr_1.25fr] lg:gap-16 items-start">
            <div>
              {hook ? (
                <>
                  <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">
                    One line keeps <em className="not-italic text-accent">coming back.</em>
                  </h2>
                  <blockquote translate="no" className="display mt-8 text-3xl sm:text-4xl leading-tight break-words">
                    “{r.top_line}”
                  </blockquote>
                  <p className="mt-6 flex items-baseline gap-4">
                    <span className="figure text-accent" style={{ fontSize: "clamp(4rem, 9vw, 6rem)" }}>
                      <Count value={r.top_line_n!} />
                    </span>
                    <span className="font-serif italic text-xl text-ink-soft">times, word for word</span>
                  </p>
                  <p className="mt-4 max-w-md text-sm leading-relaxed text-ink-mute">
                    It lands at {lineList(r.top_line_at ?? [])}. {pct(r.rep)} of the lines repeat one already
                    sung
                    {r.hook ? `, and ${pct(r.hook)} belong to lines sung three times or more` : ""}.
                  </p>
                </>
              ) : (
                <>
                  <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">
                    {r.rep === 0 ? (
                      <>
                        No line is <em className="not-italic text-accent">sung twice.</em>
                      </>
                    ) : (
                      <>
                        Nothing comes back <em className="not-italic text-accent">a third time.</em>
                      </>
                    )}
                  </h2>
                  <p className="mt-6 flex items-baseline gap-4">
                    <span className="figure text-accent" style={{ fontSize: "clamp(4rem, 9vw, 6rem)" }}>
                      <Count value={r.line_count ?? 0} />
                    </span>
                    <span className="font-serif italic text-xl text-ink-soft">lines, start to finish</span>
                  </p>
                  <p className="mt-4 max-w-md text-sm leading-relaxed text-ink-mute">
                    {r.rep === 0
                      ? "Every line is its own. Nothing here is a chorus in the usual sense."
                      : `${pct(r.rep)} of the lines repeat one already sung, but no line is sung more than twice.`}
                  </p>
                </>
              )}
              {r.drops != null && r.drops > 0 && (
                <p className="mt-8 border-t border-rule pt-5 font-serif italic text-lg text-ink-soft">
                  The title is sung <b className="not-italic font-medium text-ink">{r.drops}</b>{" "}
                  {r.drops === 1 ? "time" : "times"}.
                </p>
              )}
            </div>
            <HookStrip lineWords={r.line_words ?? []} hookAt={hook ? (r.top_line_at ?? []) : []} />
          </div>
        </Beat>
      )}

      {clock && (
        <Beat id="clock" numeral={numeral("clock")} label="The clock">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16 items-center">
            <div>
              <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">{clockHeadline(song)}</h2>
              <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-7">
                {r.wpm != null && (
                  <Fig label="Words a minute" value={Math.round(r.wpm)} note={p.wpm != null ? phrase(RULERS[4], p.wpm) : undefined} />
                )}
                {r.first != null && (
                  <Fig label="First word" value={mmss(r.first)} note={p.first != null ? phrase(RULERS[5], p.first) : undefined} />
                )}
                {r.gap != null && <Fig label="Longest silence" value={`${Math.round(r.gap)} s`} note={r.gap_at != null ? `from ${mmss(r.gap_at)}` : undefined} />}
                {r.fast15 != null && <Fig label="Busiest 15 seconds" value={r.fast15} note="words" />}
              </dl>
            </div>
            <Clock reading={r} />
          </div>
        </Beat>
      )}

      {full && (
        <Beat id="words" numeral={numeral("words")} label="The words">
          <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
            <div>
              <WordTable title="Most-used words" rows={song.stats.top_words_no_stop} />
              <p className="mt-3 text-[0.78rem] italic text-ink-mute">
                Stopwords set aside. The bar beneath each word is its share of the most-used.
              </p>
            </div>
            <div className="space-y-8">
              <div>
                <p className="smallcaps mb-2">Variety</p>
                <p className="figure text-ink" style={{ fontSize: "clamp(3rem, 8vw, 5rem)" }}>
                  <Count value={r.ttr * 100} suffix="%" />
                </p>
                <p className="mt-2 font-serif italic text-lg text-ink-soft">
                  {r.uniq.toLocaleString()} distinct words in {r.wc.toLocaleString()}
                  {p.ttr != null ? `, ${phrase(RULERS[1], p.ttr)}` : ""}
                </p>
              </div>
              <div className="space-y-5">
                {r.once != null && <Inline label="Used only once" value={`${r.once.toLocaleString()} words`} />}
                {r.longest_word && (
                  <Inline label="Longest word" value={<span translate="no">{r.longest_word}</span>} />
                )}
                {r.awl != null && <Inline label="Average word" value={`${r.awl} letters`} />}
                {r.q != null && r.q > 0 && <Inline label="Lines that ask a question" value={pct(r.q)} />}
                {song.has_sections && <Inline label="Chorus share" value={pct(song.stats.chorus_ratio)} />}
              </div>
            </div>
          </div>
        </Beat>
      )}

      {song.catalogue && (
        <Beat id="catalogue" numeral={numeral("catalogue")} label="In the catalogue">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.5fr] lg:gap-16 items-start">
            <div>
              <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">
                {catalogueHeadline(song, by)}
              </h2>
              <p className="mt-6 max-w-md text-sm leading-relaxed text-ink-mute">
                Every mark is one of {by}’s {song.catalogue.songs.toLocaleString()} songs, placed by its
                figure. The rule is the catalogue’s median; the oxblood mark is this song.
                {!song.catalogue.in_catalogue ? " This song itself is not in the catalogue, so it stands beside it." : ""}
              </p>
              <Link href={artistHref} className="pill pill-ghost mt-8" prefetch={false}>
                Read the whole catalogue →
              </Link>
            </div>
            <CatalogueStrips catalogue={song.catalogue} />
          </div>
        </Beat>
      )}

      {archive && (
        <Beat id="archive" numeral={numeral("archive")} label="Among the archive">
          <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug max-w-3xl">
            {archiveHeadline(song)}
          </h2>
          <p className="mt-4 mb-10 max-w-2xl text-sm leading-relaxed text-ink-mute">
            Each ruler runs from the smallest song in the archive to the largest; the mark is where this
            one falls. The archive is {bigNumber(song.archive_songs)} songs, read the same way.
          </p>
          <ArchiveRulers song={song} />
        </Beat>
      )}

      {full && (
        <Beat id="text" numeral={numeral("text")} label="The text" last>
          <Lyrics lyrics={song.lyrics} hookAt={hook ? (r.top_line_at ?? []) : []} lines={r.line_count ?? 0} />
          <p className="mt-8 text-[0.78rem] italic text-ink-mute">
            Read from {SOURCE_NAMES[song.source] ?? "the stored"} text. Another transcription would change
            the count a little; the shape would hold.
          </p>
        </Beat>
      )}
    </article>
  );
}

function Beat({
  id,
  numeral,
  label,
  last = false,
  children,
}: {
  id: string;
  numeral: string;
  label: string;
  last?: boolean;
  children: ReactNode;
}) {
  return (
    <section id={id} className={`scroll-mt-8 py-12 sm:py-16 ${last ? "" : "border-b border-rule-strong"}`}>
      <Reveal>
        <p className="smallcaps mb-6">
          {numeral}. {label}
        </p>
        {children}
      </Reveal>
    </section>
  );
}

function Fig({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="border-b border-rule pb-3">
      <dt className="smallcaps mb-1">{label}</dt>
      <dd className="figure text-3xl sm:text-4xl text-ink">{value}</dd>
      {note && <dd className="mt-1 text-[0.78rem] italic text-ink-mute">{note}</dd>}
    </div>
  );
}

function Inline({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule pb-2">
      <span className="smallcaps">{label}</span>
      <span className="figure text-2xl text-ink text-right">{value}</span>
    </div>
  );
}

function clockHeadline(song: SongPayload): ReactNode {
  const r = song.reading!;
  const p = song.percentiles;
  if (r.first != null && r.first >= 30) {
    return (
      <>
        The first word waits <em className="not-italic text-accent">{mmss(r.first)}.</em>
      </>
    );
  }
  if (r.wpm != null && p.wpm != null && p.wpm >= 80) {
    return (
      <>
        <em className="not-italic text-accent">{Math.round(r.wpm)} words a minute,</em> faster than {p.wpm}% of songs.
      </>
    );
  }
  if (r.gap != null && r.gap >= 30) {
    return (
      <>
        It falls silent for <em className="not-italic text-accent">{Math.round(r.gap)} seconds.</em>
      </>
    );
  }
  return (
    <>
      {mmss(r.duration)} of song, <em className="not-italic text-accent">{r.wc.toLocaleString()} words.</em>
    </>
  );
}

function catalogueHeadline(song: SongPayload, by: string): ReactNode {
  const c = song.catalogue!;
  const m = c.words ?? c.variety ?? c.repetition;
  if (!m) return <>One of {by}’s {c.songs} songs.</>;
  const row = c.words ? 0 : c.variety ? 1 : 2;
  const text = standing(
    m,
    c.songs,
    [
      { key: "words", label: "Words", fmt: String, most: "longest", least: "shortest" },
      { key: "variety", label: "Variety", fmt: String, most: "most varied", least: "least varied" },
      { key: "repetition", label: "Repetition", fmt: String, most: "most repetitive", least: "least repetitive" },
    ][row] as Parameters<typeof standing>[2],
  );
  const [rank, ...rest] = text.split(" ");
  return (
    <>
      The <em className="not-italic text-accent">{rank}</em> {rest.join(" ")} songs {by} has recorded.
    </>
  );
}

function archiveHeadline(song: SongPayload): ReactNode {
  const p = song.percentiles;
  const r = song.reading!;
  // The most striking standing, from what the reading has.
  const candidates = RULERS.filter((row) => p[row.key] != null && typeof r[row.key] === "number");
  if (!candidates.length) return null;
  const best = candidates.reduce((a, b) => (Math.abs(p[b.key]! - 50) > Math.abs(p[a.key]! - 50) ? b : a));
  const pb = p[best.key]!;
  const [above, below] = ARCHIVE_LEADS[best.key as string] ?? ["Above {p}% of the songs", "Below {p}% of the songs"];
  const lead = pb >= 50 ? above.replace("{p}", String(pb)) : below.replace("{p}", String(100 - pb));
  return (
    <>
      <em className="not-italic text-accent">{lead}</em> we have read.
    </>
  );
}

function NoText({ song }: { song: SongPayload }) {
  const r = song.reading;
  return (
    <section className="border-b border-rule-strong py-12 sm:py-16">
      <Reveal>
        <p className="smallcaps mb-6">The text</p>
        <h2 className="font-serif italic text-3xl sm:text-4xl leading-snug max-w-3xl">
          We know this song from the catalogue, <em className="not-italic text-accent">not from its words.</em>
        </h2>
        <p className="mt-5 max-w-2xl font-serif text-lg text-ink-soft">
          None of our sources has the text under this artist and title, so the reading below is what
          the catalogue remembers: the counts, without the lines.
        </p>
        {r && (
          <dl className="mt-10 grid grid-cols-2 gap-x-6 gap-y-7 sm:grid-cols-4">
            <Fig label="Words" value={r.wc.toLocaleString()} />
            <Fig label="Distinct" value={r.uniq.toLocaleString()} />
            <Fig label="Variety" value={pct(r.ttr)} />
            <Fig label="Lines repeated" value={pct(r.rep)} />
          </dl>
        )}
      </Reveal>
    </section>
  );
}
