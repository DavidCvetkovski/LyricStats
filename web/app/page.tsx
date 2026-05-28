import Link from "next/link";

export default function Home() {
  return (
    <article className="mx-auto max-w-6xl px-6 pt-10 pb-20">
      {/* Front-page lede */}
      <section className="grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:gap-16 border-b border-rule-strong pb-12">
        <div className="rise rise-1">
          <p className="smallcaps mb-3">The Feature</p>
          <h2
            className="display text-ink"
            style={{ fontSize: "clamp(2.5rem, 6vw, 4.5rem)" }}
          >
            What can a&nbsp;number tell you about a&nbsp;song?
          </h2>
          <p className="mt-6 dropcap text-lg leading-[1.7] text-ink-soft max-w-prose">
            Every song is a small library of vocabulary, rhythm and repetition. We
            count the words, the rhymes and the choruses; we measure the
            silence between them. What emerges is a quiet portrait of a writer at
            work — their tics, their grammar, their favourite verbs. This is a
            modest publication for that kind of looking. Begin with a single
            song, or read an entire artist from cover to cover.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/song" className="pill">
              Read One Song →
            </Link>
            <Link href="/artist" className="pill pill-ghost">
              Read an Artist →
            </Link>
          </div>
        </div>

        {/* Sidebar — "in this issue" */}
        <aside className="rise rise-2 border-l border-rule-strong pl-8 hidden lg:block">
          <p className="smallcaps mb-5">In this issue</p>
          <ul className="space-y-5 text-ink-soft">
            <li>
              <span className="smallcaps block mb-1 text-accent">I.</span>
              <span className="font-serif text-xl text-ink leading-snug">
                The dictionary, by the numbers — vocabulary as portrait.
              </span>
            </li>
            <li>
              <span className="smallcaps block mb-1 text-accent">II.</span>
              <span className="font-serif text-xl text-ink leading-snug">
                On the chorus, and the geometry of repetition.
              </span>
            </li>
            <li>
              <span className="smallcaps block mb-1 text-accent">III.</span>
              <span className="font-serif text-xl text-ink leading-snug">
                A field guide to the Balkan rap line.
              </span>
            </li>
          </ul>
        </aside>
      </section>

      {/* Three-column "what's inside" */}
      <section className="mt-14 grid gap-12 md:grid-cols-3">
        <Column
          numeral="I."
          title="Lexicon"
          body="How wide is a writer's vocabulary, and how often do they repeat themselves? We measure the ratio of unique words to total, and chart the words that appear only once."
        />
        <Column
          numeral="II."
          title="Structure"
          body="Verses, choruses, intros and outros: the architecture of a song. We tally each, weigh the share of the chorus, and watch what stays."
        />
        <Column
          numeral="III."
          title="Voice"
          body="The shape of a line — its average length, its longest words, its most beloved phrases. The dictionary that a single artist carries with them."
        />
      </section>

      {/* Method */}
      <section className="mt-20 border-t border-rule-strong pt-10">
        <p className="smallcaps mb-3">On Method</p>
        <p className="font-serif text-2xl sm:text-3xl text-ink leading-snug max-w-3xl">
          Lyrics are retrieved from Genius (with a quiet fallback), filed away
          in a small database, and counted with care. Statistics are computed in
          Python; the page you are reading is rendered in&nbsp;React.
          <span className="diamond" />
          Cached results return instantly; first reads take a moment.
        </p>
      </section>
    </article>
  );
}

function Column({
  numeral,
  title,
  body,
}: {
  numeral: string;
  title: string;
  body: string;
}) {
  return (
    <div>
      <p className="smallcaps text-accent mb-2">{numeral}</p>
      <h3 className="display text-3xl mb-3">{title}</h3>
      <p className="text-ink-soft leading-[1.7] text-[0.95rem]">{body}</p>
    </div>
  );
}
