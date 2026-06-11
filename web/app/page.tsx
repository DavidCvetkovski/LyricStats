import Link from "next/link";
import { SITE_URL } from "@/lib/site";

/**
 * Front page = Issue 01, cover to cover. No mission-statement hero; the
 * feature essay IS the front page. All figures below come from the LyricStats
 * database: the duo's full catalogues (492 deduplicated songs, 180,713 words)
 * plus per-track analysis of GODZILLA (2026).
 */

// Article rich-result data for the Issue 01 feature.
const articleData = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "The Monsters of Sarajevo",
  description:
    "A data-driven feature on Jala Brat & Buba Corelli's album GODZILLA, read against every word of their 492-song catalogue.",
  image: [`${SITE_URL}/opengraph-image`],
  datePublished: "2026-06-09",
  dateModified: "2026-06-11",
  author: { "@id": `${SITE_URL}/#organization` },
  publisher: { "@id": `${SITE_URL}/#organization` },
  mainEntityOfPage: SITE_URL,
};

export default function Home() {
  return (
    <article className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-12 pb-16 sm:pb-20">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleData) }}
      />
      {/* ===== Issue 01 opener ===== */}
      <header className="rise rise-1 border-b-4 border-double border-rule-strong pb-8 sm:pb-10">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <p className="smallcaps">
            <span className="text-accent">Issue 01</span> · The Feature
          </p>
          <p className="smallcaps">Sarajevo · 23 May 2026</p>
        </div>

        <h1
          className="display text-ink mt-4 sm:mt-6 leading-[1.02]"
          style={{ fontSize: "clamp(2.6rem, 9.5vw, 6rem)" }}
        >
          The Monsters of&nbsp;Sarajevo
        </h1>

        <p className="font-serif italic text-lg sm:text-2xl text-ink-soft mt-4 sm:mt-6 max-w-4xl leading-relaxed">
          Jala Brat and Buba Corelli spent two decades climbing out of a Sarajevo
          home studio and onto the biggest stages in Europe. On their new album,
          <em> GODZILLA</em>, they finally turned into monsters. So we counted
          every word they have ever released to find out what the monster is
          made of.
        </p>

        {/* Cover stats: the numbers are the artwork */}
        <div className="mt-8 sm:mt-10 grid grid-cols-2 sm:grid-cols-4 gap-y-6 sm:divide-x sm:divide-[var(--rule-strong)]">
          {[
            ["180,713", "words counted"],
            ["19,804", "distinct words"],
            ["279", "words they had never used before GODZILLA"],
            ["607", "times they have said “mala”"],
          ].map(([n, label]) => (
            <div key={label} className="sm:px-6 first:pl-0 last:pr-0">
              <p className="figure display text-3xl sm:text-4xl text-accent">{n}</p>
              <p className="smallcaps mt-1 leading-snug">{label}</p>
            </div>
          ))}
        </div>
      </header>

      {/* ===== The essay ===== */}
      <section className="mt-10 sm:mt-14 grid gap-12 lg:grid-cols-[2fr_1fr] lg:gap-16">
        <div className="rise rise-2 space-y-7 font-serif text-[1.05rem] sm:text-lg text-ink-soft leading-[1.8] max-w-prose">
          <p className="dropcap">
            On the 23rd of May, 2026, two of the most-streamed artists in the
            Balkans released a zoo. Ten tracks, twenty-three minutes, and a
            tracklist that reads like a field guide to things that bite: a shark
            (&ldquo;Ajkula&rdquo;), a pack of vampires (&ldquo;Vampiri&rdquo;), a
            pair of cat&apos;s eyes (&ldquo;Mačje oči&rdquo;), a lion
            (&ldquo;Mufasa&rdquo;), a wolf (&ldquo;Chimaev,&rdquo; after the
            Chechen UFC fighter whose nickname, Borz, means exactly that). And
            looming over all of it, <em>GODZILLA</em>. Six of the ten songs are
            named for creatures. Inside the lyrics the menagerie grows: Dracula
            appears six times, Attila twice, and <em>zvijer</em>, the Bosnian
            word for beast, twice more.
          </p>

          <p>
            A bestiary is a strange shape for an album. But Jala Brat and Buba
            Corelli have never released anything by accident, and the data (at
            this publication we read with a calculator) says <em>GODZILLA</em>{" "}
            is the most deliberate record they have ever made. So we fed all ten
            songs, and the 482 they wrote before them, through the counting
            machine. What came out is the story of two writers who built an
            empire by shrinking their songs, and who have now, quietly, started
            growing them back.
          </p>

          <h3 className="display text-3xl text-ink pt-4">From the Underground</h3>

          <p>
            The story starts unglamorously. Jasmin Fazlić, the future Jala Brat,
            was a kid from Sarajevo recording rap in an improvised home studio in
            the early 2000s, releasing mixtapes onto YouTube with an underground
            crew called BluntBylon. Amar Hodžić, who would become Buba Corelli,
            cut his first track in 2004, at fifteen. They found each other in
            2013, on an EP called <em>Sin City</em>, and sealed it in 2014 with a
            debut album whose title now reads like a mission statement:{" "}
            <em>Pakt s Đavolom</em>. A deal with the devil.
          </p>

          <p>
            The devil collected early. In June 2015 Corelli was arrested and
            spent nearly a year in prison. While he sat inside, his single
            &ldquo;Habibi&rdquo; went supernova and racked up forty million
            views; the Balkans had its first trap superstar, and he was watching
            it happen from a cell. The year he got out, Jala stood on the
            Eurovision stage with Bosnia&apos;s 2016 entry, &ldquo;Ljubav
            je.&rdquo; It remains, to this day, the last song the country ever
            sent to the contest. Then they stopped asking for permission
            entirely: they founded their own label, Imperia, and dropped two
            albums in fifteen days.
          </p>

          <p>
            What followed is the part you may already know: the features with RAF
            Camora and Rick Ross, the GOAT Tour selling out halls across Europe,
            &ldquo;TEC-9&rdquo; parked at No.&nbsp;1 on the Croatian Billboard
            chart for eighteen straight weeks. What you may not know is what was
            happening to the words.
          </p>

          <h3 className="display text-3xl text-ink pt-4">
            The Year the Hook Ate the Verse
          </h3>

          <p>
            In the mixtape years, a Jala or Buba song was a long walk. In 2011
            the average track ran 515 words. By 2013 more than half the words in
            a typical song appeared in that song for the first time (a lexical
            variety of .55, the highest of their careers), and only a fifth of
            its lines ever repeated. This was rap as endurance sport: dense,
            show-offy, built for headphones.
          </p>

          <p>
            Then streaming arrived, Imperia needed hits, and the hook ate the
            verse. By 2017 the average song had collapsed to barely 300 words.
            Lexical variety sank from .55 to .39. Line-for-line repetition more
            than doubled. The songs got shorter, rounder, more hypnotic, and
            enormously more popular. It is the most legible career pivot in our
            entire database: you can put your finger on the exact year the two
            rappers became a pop factory.
          </p>

          <blockquote className="border-l-2 border-accent pl-6 py-1 font-serif italic text-xl text-ink leading-relaxed">
            On paper they are a contradiction: a rapper who refuses to repeat
            himself, and a singer whose entire job is repetition. The factory
            works because the two halves never tried to do the same job.
          </blockquote>

          <p>
            The division of labour shows up in the numbers like a fingerprint.
            Across 407 songs, just under 30% of Jala Brat&apos;s lines live inside
            a chorus. Across Buba Corelli&apos;s 304, it is 44%: nearly half of
            every song he touches is hook. Jala builds the walls; Buba installs
            the echo. And here is the strangest part. Their per-song vocabularies
            are almost identical (a lexical variety of .460 versus .462, a
            rounding error apart). They write with the same richness, just aimed
            at different organs. One at the head, one at the bloodstream.
          </p>

          <h3 className="display text-3xl text-ink pt-4">
            The Monster Learns New Words
          </h3>

          <p>
            Which brings us back to the zoo. <em>GODZILLA</em> is, at first
            glance, peak factory: ten tracks averaging 319 words, none longer
            than 2 minutes 48. The title track runs 264 words, shorter than 86%
            of everything they have ever released. But run the vocabulary and
            the album turns inside out. Its per-song lexical variety is .52,{" "}
            <strong>the richest writing they have put on a record in a decade</strong>,
            back at the level of the mixtape years but in songs a third shorter.
            Repetition, meanwhile, stayed flat at their career average. They
            didn&apos;t loosen the structure. They packed it tighter.
          </p>

          <p>
            Of the album&apos;s 1,169 distinct words, 279 had never appeared in a
            Jala Brat or Buba Corelli song before.{" "}
            <strong>
              Almost one word in four on <em>GODZILLA</em> is brand new
            </strong>
            , after 482 songs and 177,000 words of back catalogue. You can hear
            the new dictionary arriving in real time on &ldquo;Ajkula,&rdquo;
            whose hook is welded out of a single rhyme family the catalogue had
            never seen: <em>ajkula, drakula, datula, arabija, natural</em>. Each
            appears exactly six times, a shark circling the same sound.
          </p>

          <p>
            And the sharpest twist is who got hungriest. The album&apos;s densest
            track, &ldquo;Bass &amp; Rave,&rdquo; carries a lexical variety of
            .64. The second-densest, &ldquo;Topovska&rdquo; at .59, is Buba
            Corelli&apos;s solo: the hook-singer, the man whose career is 44%
            chorus, quietly delivering some of the most varied writing on the
            record. The melodic half of the factory is rapping again. Not that
            the factory closed. &ldquo;Zaronim&rdquo; repeats its title
            twenty-four times in 419 words, an echo chamber installed dead in
            the middle of the album, just to prove they still can.
          </p>

          <h3 className="display text-3xl text-ink pt-4">The Word That Survived</h3>

          <p>
            One word walked through all of it untouched. <em>Mala</em>, the
            &ldquo;little one&rdquo; every Balkan hook is sung to, is the
            most-used content word in their combined catalogue: 607 appearances
            and counting. It survived the underground years, the prison year,
            the Eurovision detour, the pivot to pop. On <em>GODZILLA</em> it
            appears thirty times across seven of the ten tracks, nearly{" "}
            <strong>three times its career-average density</strong> and the most
            concentrated it has ever been. They filled the album with predators,
            and the oldest word in their universe outlived every one of them.
          </p>

          <p>
            Here is the number we keep coming back to. Of the 19,804 distinct
            words Jala Brat and Buba Corelli have ever rapped, more than half
            (10,260) appear exactly once. Used one time, placed where they
            belonged, never touched again. That is not the vocabulary of a hit
            factory. That is the vocabulary of two writers, fifteen years in,
            still spending words like they&apos;re fresh out of the basement
            with everything to prove. The monster on the cover was never
            Godzilla. It&apos;s the dictionary.
          </p>

          <p className="border-t border-rule pt-6 text-base text-ink-mute font-sans">
            Every figure in this essay is drawn from the LyricStats database,
            and every one of them is a thread you can pull. Open a catalogue
            below and read it yourself.
          </p>

          <div className="flex flex-wrap gap-3">
            <Link href="/artist?name=Jala%20Brat&min=500" className="pill">
              Read Jala Brat →
            </Link>
            <Link href="/artist?name=Buba%20Corelli&min=500" className="pill">
              Read Buba Corelli →
            </Link>
            <Link href="/song" className="pill pill-ghost">
              Read Any Song →
            </Link>
          </div>
        </div>

        {/* ===== Sidebar: the numbers, at a glance ===== */}
        <aside className="rise rise-3 space-y-8 lg:mt-2">
          <div className="border-2 border-rule-strong bg-paper-soft p-6 sm:p-7 space-y-4">
            <p className="smallcaps text-accent border-b border-rule pb-2">
              GODZILLA at a Glance
            </p>
            <p className="smallcaps">Imperia · 10 tracks · 23 minutes</p>
            <div className="space-y-3 font-serif text-sm">
              {[
                ["Total words", "3,193"],
                ["Distinct words", "1,169"],
                ["Never used before", "279"],
                ["Densest track", "Bass & Rave (.64)"],
                ["Shortest track", "Godzilla (264 words)"],
                ["Loudest echo", "“zaronim” ×24"],
                ["“mala” count", "30"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-rule pb-2 last:border-b-0 last:pb-0">
                  <span className="text-ink-soft">{k}</span>
                  <span className="figure text-ink font-bold text-right">{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-rule-strong p-6 sm:p-7 space-y-5">
            <p className="smallcaps text-accent border-b border-rule pb-2">
              The Duo, Side by Side
            </p>
            <div className="grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-3 font-serif text-sm items-baseline">
              <span />
              <span className="smallcaps">Jala</span>
              <span className="smallcaps">Buba</span>
              {[
                ["Songs", "407", "304"],
                ["Vocabulary", "17,553", "13,867"],
                ["Words written", "151,245", "109,146"],
                ["Chorus share", "29.8%", "44.1%"],
                ["Lexical variety", ".460", ".462"],
                ["“mala” said", "512×", "492×"],
              ].map(([k, j, b]) => (
                <div key={k} className="contents">
                  <span className="text-ink-soft border-b border-rule pb-2">{k}</span>
                  <span className="figure text-ink font-bold border-b border-rule pb-2 text-right">{j}</span>
                  <span className="figure text-ink font-bold border-b border-rule pb-2 text-right">{b}</span>
                </div>
              ))}
            </div>
            <p className="font-serif text-sm text-ink-soft leading-relaxed">
              Same richness, different organs: Jala writes for the head, Buba for
              the bloodstream.
            </p>
          </div>

          <div className="border border-rule-strong p-6 space-y-4">
            <h4 className="display text-xl text-ink">In Issue 02</h4>
            <p className="font-serif text-sm text-ink-soft leading-relaxed">
              On the chorus, and the geometry of repetition: what 492 hooks say
              about why some lines refuse to leave your head.
            </p>
            <p className="smallcaps text-ink-mute">In preparation</p>
          </div>
        </aside>
      </section>
    </article>
  );
}
