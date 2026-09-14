import Link from "next/link";

/** Ordinary outbound links: no credentials, embeds, or background requests. */
export function MusicLinks({ artist, title, showArtist = false }: {
  artist: string; title?: string; showArtist?: boolean;
}) {
  const query = [artist.trim(), title?.trim()].filter(Boolean).join(" ");
  return (
    <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-[0.7rem] uppercase tracking-[0.12em]">
      {showArtist && (
        <Link href={`/artist?${new URLSearchParams({ name: artist })}`} prefetch={false}
          className="text-ink hover:text-accent underline decoration-rule-strong underline-offset-4">
          Explore the artist →
        </Link>
      )}
      <a href={`https://open.spotify.com/search/${encodeURIComponent(query)}`} target="_blank" rel="noopener noreferrer"
        className="text-ink hover:text-accent underline decoration-rule-strong underline-offset-4">
        Find on Spotify ↗
      </a>
    </div>
  );
}
