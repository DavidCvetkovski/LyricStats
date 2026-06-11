import type { Metadata } from "next";

// The song page is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: "Song Statistics",
  description:
    "Pick a song and read its statistics: unique words, lexical variety, repetition, chorus share and the words it leans on most.",
  alternates: {
    canonical: "/song",
  },
  openGraph: {
    siteName: "LyricStats",
    type: "website",
    url: "/song",
    title: "Song Statistics · LyricStats",
    description:
      "Pick a song and read its statistics: unique words, lexical variety, repetition, chorus share and the words it leans on most.",
  },
};

export default function SongLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
