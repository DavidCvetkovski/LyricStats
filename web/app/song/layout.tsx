import type { Metadata } from "next";

// The search page is a client component, so its metadata lives here. Song
// pages under /song/<artist>/<title> set their own.
export const metadata: Metadata = {
  title: "On a Song",
  description:
    "One song, read closely: its returning line, the clock of its lyrics, its words, and where it stands in the artist’s catalogue and among millions of songs.",
  alternates: {
    canonical: "/song",
  },
  openGraph: {
    siteName: "LyricStats",
    type: "website",
    url: "/song",
    title: "On a Song · LyricStats",
    description:
      "One song, read closely: its returning line, the clock of its lyrics, its words, and where it stands among millions of songs.",
  },
};

export default function SongLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
