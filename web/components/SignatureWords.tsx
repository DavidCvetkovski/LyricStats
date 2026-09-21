import type { Signature } from "@/lib/types";

const LANGUAGES: Record<string, string> = {
  en: "English",
  bs: "Bosnian, Croatian or Serbian",
  sc: "Serbian",
  es: "Spanish",
  pt: "Portuguese",
  fr: "French",
  de: "German",
  it: "Italian",
  ru: "Russian",
  uk: "Ukrainian",
  tr: "Turkish",
  pl: "Polish",
  nl: "Dutch",
  sv: "Swedish",
  id: "Indonesian",
  ro: "Romanian",
  el: "Greek",
  ar: "Arabic",
  he: "Hebrew",
  th: "Thai",
  hi: "Hindi",
};

/**
 * The words that are theirs: recurring across the catalogue, rare among other
 * artists singing in the same language. Counted in songs, not uses, so a
 * word shouted a hundred times in one song does not make the list.
 */
export function SignatureWords({ signature, by }: { signature: Signature; by: string }) {
  const rows = signature.words.slice(0, 10);
  if (!rows.length) return null;
  const language = LANGUAGES[signature.lang];
  return (
    <section>
      <header className="mb-4 flex items-baseline justify-between">
        <h3 className="display text-2xl sm:text-3xl">Theirs</h3>
        <span className="smallcaps">in songs</span>
      </header>
      <ol className="border-t border-rule-strong">
        {rows.map(([word, songs], i) => (
          <li
            key={word}
            className="grid grid-cols-[2rem_1fr_auto] items-baseline gap-4 border-b border-rule py-2"
          >
            <span className="figure text-base tabular-nums text-ink-mute">{String(i + 1).padStart(2, "0")}</span>
            <span
              translate="no"
              className={`notranslate font-serif text-xl ${i === 0 ? "text-accent italic font-medium" : "text-ink"}`}
            >
              {word}
            </span>
            <span className="figure text-ink tabular-nums text-base">{songs}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[0.78rem] italic text-ink-mute">
        Words {by} keeps returning to that most {language ? `${language}-singing` : "other"} artists do not.
        Each is counted once per song.
      </p>
    </section>
  );
}
