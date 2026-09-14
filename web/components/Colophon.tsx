import Link from "next/link";
import { issues } from "@/lib/issues";

export function Colophon() {
  return (
    <footer className="publication-footer">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="colophon-rule"><span>The colophon</span><span aria-hidden="true">❦</span></div>
        <div className="colophon-grid">
          <div className="colophon-imprint">
            <Link href="/" className="display text-[2.65rem]">LyricStats</Link>
            <p className="colophon-byline">An independent project by<br/><span translate="no">David Cvetkovski</span></p>
            <p className="colophon-description">A closer look at the words <br/>behind the music.</p>
          </div>
          <nav aria-label="Journal archive" className="colophon-issues">
            <Link href="/issues" className="colophon-label">The journal <span aria-hidden="true">↗</span></Link>
            {issues.map(issue => <Link key={issue.id} prefetch={false} href={issue.href} className="colophon-issue"><span className="figure">{issue.id}</span><span>{issue.title}</span></Link>)}
            <Link href="/issues" className="colophon-archive">All issues →</Link>
          </nav>
          <nav aria-label="Explore LyricStats" className="colophon-explore">
            <p className="colophon-label">Explore</p>
            <Link href="/song" prefetch={false}>Read a song <span aria-hidden="true">↗</span></Link>
            <Link href="/artist" prefetch={false}>Explore an artist <span aria-hidden="true">↗</span></Link>
          </nav>
        </div>
        <div className="colophon-bottom"><p>Words, lines, repetitions. Always room for another listen.</p><p>Set in Fraunces &amp; Inter.</p></div>
      </div>
    </footer>
  );
}
