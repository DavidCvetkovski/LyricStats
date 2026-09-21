import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { SongReading } from "@/components/song/SongReading";
import { artistName, mmss } from "@/lib/format";
import { fetchSong } from "@/lib/server";

type Params = Promise<{ artist: string; title: string }>;

function decode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { artist, title } = await params;
  const song = await fetchSong(decode(artist), decode(title));
  if (!song) return { title: "Not in the archive" };
  const by = artistName(song.artist);
  const r = song.reading;
  const bits = r
    ? [
        `${r.wc.toLocaleString()} words`,
        `${r.uniq.toLocaleString()} distinct`,
        r.top_line_n && r.top_line_n >= 3 ? `one line sung ${r.top_line_n} times` : null,
        r.first != null && r.first >= 20 ? `first word at ${mmss(r.first)}` : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : "";
  const description = `${song.title} by ${by}, read closely${bits ? `: ${bits}` : ""}.`;
  const canonical = `/song/${song.slug.artist}/${song.slug.title}`;
  return {
    title: `${song.title} by ${by}`,
    description,
    alternates: { canonical },
    openGraph: {
      siteName: "LyricStats",
      type: "article",
      url: canonical,
      title: `${song.title} by ${by} · LyricStats`,
      description,
    },
  };
}

export default async function SongPage({ params }: { params: Params }) {
  const { artist, title } = await params;
  const song = await fetchSong(decode(artist), decode(title));
  if (!song) notFound();
  // One address per song: anything that resolved to it lands on its slug.
  const { artist: a, title: t } = song.slug;
  if (a && t && (a !== artist || t !== title)) permanentRedirect(`/song/${a}/${t}`);
  return <SongReading song={song} />;
}
