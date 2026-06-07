import Link from "next/link";

export default function Home() {
  return (
    <article className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      {/* Front-page lede */}
      <section className="grid gap-8 sm:gap-10 lg:grid-cols-[1.4fr_1fr] lg:gap-16 border-b border-rule-strong pb-10 sm:pb-12">
        <div className="rise rise-1">
          <p className="smallcaps mb-3">The Feature</p>
          <h2
            className="display text-ink"
            style={{ fontSize: "clamp(2rem, 8vw, 4.5rem)" }}
          >
            What can a&nbsp;number tell you about a&nbsp;song?
          </h2>
          <p className="mt-5 sm:mt-6 dropcap text-base sm:text-lg leading-[1.65] sm:leading-[1.7] text-ink-soft max-w-prose">
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
                Jala Brat & Buba Corelli: The Architects of the Balkan Rap Line.
              </span>
            </li>
            <li>
              <span className="smallcaps block mb-1 text-ink-mute">II. (Upcoming)</span>
              <span className="font-serif text-xl text-ink-mute leading-snug">
                On the chorus, and the geometry of repetition.
              </span>
            </li>
            <li>
              <span className="smallcaps block mb-1 text-ink-mute">III. (Upcoming)</span>
              <span className="font-serif text-xl text-ink-mute leading-snug">
                A field guide to the Balkan rap line.
              </span>
            </li>
          </ul>
        </aside>
      </section>

      {/* Main Article Body — Issue 01 */}
      <section className="mt-12 sm:mt-16 grid gap-12 lg:grid-cols-[2fr_1fr] lg:gap-16 border-b border-rule-strong pb-12 sm:pb-16">
        <div className="rise rise-3 space-y-8">
          <header className="border-b border-rule pb-6">
            <p className="smallcaps text-accent mb-2">Issue 01 · Feature Essay</p>
            <h1 className="display text-4xl sm:text-5xl md:text-6xl text-ink leading-tight">
              Jala Brat & Buba Corelli: The Architects of the Balkan Rap Line
            </h1>
            <p className="font-serif italic text-lg sm:text-xl text-ink-soft mt-3 leading-relaxed">
              A comparative reading of Jasmin Fazlić and Amar Hodžić through their vocabulary, repetition, and the geometry of the hook.
            </p>
          </header>

          <div className="font-serif text-[1.05rem] sm:text-lg text-ink-soft leading-[1.8] space-y-6 max-w-prose">
            <p className="dropcap">
              Over the last decade, Jasmin Fazlić (Jala Brat) and Amar Hodžić (Buba Corelli) have transformed the landscape of southeastern European pop music. From their roots in the Sarajevo underground rap scene, the duo pioneered a sonic blueprint combining trap, dancehall, and regional Balkan folk melodies—a formula that has conquered the airwaves and dominated streaming charts. But behind the heavy auto-tune and thumping bass lies a meticulous, highly structured approach to lyricism.
            </p>
            
            <p>
              By analyzing their catalogues, we can study how their writing styles diverge and complement one another. Our data reveals a highly optimized songwriting partnership—a division of labor where each artist plays a specialized role in the architecture of their hits.
            </p>

            <h3 className="display text-3xl text-ink mt-10 mb-4">The Vocabulary: Density vs. Melodic Repetition</h3>
            <p>
              When aggregating their total outputs, we find Jala Brat carries a dictionary of <strong>17,553 unique words</strong> across 407 songs (totaling 151,245 words). Buba Corelli's catalog, comprising 304 songs and 109,146 words, utilizes <strong>13,867 unique words</strong>. Interestingly, their song-by-song lexical variety (Type-Token Ratio) is nearly identical—averaging <strong>46.0%</strong> for Jala and <strong>46.2%</strong> for Buba. 
            </p>
            <p>
              This means that on any single song, both writers use roughly the same ratio of new to repeated words. However, the absolute size of Jala's vocabulary reflects his prolific nature and dense, multi-syllabic rhyme structures that pack more words into each verse.
            </p>

            <h3 className="display text-3xl text-ink mt-10 mb-4">The Hook: The Anatomy of a Hit</h3>
            <p>
              The most dramatic contrast between the two is found in the <strong>average chorus share</strong>. A typical Buba Corelli song has an average chorus ratio of <strong>44.1%</strong>, meaning nearly half of the entire song consists of repeated hooks. In contrast, Jala Brat's average chorus ratio sits at <strong>29.8%</strong>.
            </p>
            <p>
              This statistical divide mirrors their roles. Buba Corelli is the melodic core of the duo, composing the soaring, hypnotic hooks that linger in the listener's ear. Jala Brat builds the surrounding structure, filling the track with long, narrative verses that drive the song forward.
            </p>

            <blockquote className="border-l-2 border-accent pl-6 py-1 my-8 font-serif italic text-xl text-ink leading-relaxed">
              "Buba Corelli is the melodic mastermind who pens the anthemic hooks, whereas Jala is the dense, fast-rhyming lyricist."
            </blockquote>

            <h3 className="display text-3xl text-ink mt-10 mb-4">The Balkan Tropes</h3>
            <p>
              What words build this universe? Both artists share an obsession with the word <strong>"mala"</strong> (meaning "little girl" or "babe"), which appears 512 times in Jala's catalog and 492 times in Buba's. It acts as the core gravity around which their narratives rotate. Outside of this shared focal point, Jala's most frequent content words are "znam" (know) and "kada" (when), while Buba heavily relies on "znam" (know) and "nema" (there is no).
            </p>
          </div>
        </div>

        {/* Sidebar Statistics Card */}
        <div className="rise rise-4 space-y-8 lg:mt-24">
          <div className="border border-rule-strong bg-paper-soft p-6 sm:p-8 space-y-6">
            <p className="smallcaps text-accent border-b border-rule pb-2">The Stats Side-by-Side</p>
            
            <div className="space-y-6">
              <div>
                <h4 className="display text-2xl mb-4 text-ink">Jala Brat</h4>
                <div className="space-y-3 font-serif text-sm">
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Songs Aggregated</span>
                    <span className="figure text-ink font-bold">407</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Total Vocabulary</span>
                    <span className="figure text-ink font-bold">17,553 words</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Avg. Chorus Share</span>
                    <span className="figure text-ink font-bold">29.8%</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Avg. Repetition</span>
                    <span className="figure text-ink font-bold">31.8%</span>
                  </div>
                  <div className="flex justify-between pb-2">
                    <span className="text-ink-soft">Signature Word</span>
                    <span className="font-sans smallcaps text-ink">"mala" (512x)</span>
                  </div>
                </div>
              </div>

              <div className="border-t border-rule-strong pt-6">
                <h4 className="display text-2xl mb-4 text-ink">Buba Corelli</h4>
                <div className="space-y-3 font-serif text-sm">
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Songs Aggregated</span>
                    <span className="figure text-ink font-bold">304</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Total Vocabulary</span>
                    <span className="figure text-ink font-bold">13,867 words</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Avg. Chorus Share</span>
                    <span className="figure text-ink font-bold">44.1%</span>
                  </div>
                  <div className="flex justify-between border-b border-rule pb-2">
                    <span className="text-ink-soft">Avg. Repetition</span>
                    <span className="figure text-ink font-bold">30.5%</span>
                  </div>
                  <div className="flex justify-between pb-2">
                    <span className="text-ink-soft">Signature Word</span>
                    <span className="font-sans smallcaps text-ink">"mala" (492x)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="border border-rule-strong p-6 space-y-4">
            <h4 className="display text-xl text-ink">Read Their Catalogues</h4>
            <p className="font-serif text-sm text-ink-soft leading-relaxed">
              Explore the full, interactive stats of Jala Brat and Buba Corelli, drawn directly from our database.
            </p>
            <div className="flex flex-col gap-2 pt-2">
              <Link href="/artist?name=Jala%20Brat&min=500" className="pill text-center justify-center">
                Explore Jala Brat →
              </Link>
              <Link href="/artist?name=Buba%20Corelli&min=500" className="pill pill-ghost text-center justify-center">
                Explore Buba Corelli →
              </Link>
            </div>
          </div>
        </div>
      </section>
    </article>
  );
}
