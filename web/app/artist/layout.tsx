import type { Metadata } from "next";

// The artist page is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: "Artist Statistics",
  description:
    "Read an artist's whole catalogue as numbers: total vocabulary, lexical variety, average chorus share, repetition and their most frequent words.",
  alternates: {
    canonical: "/artist",
  },
  openGraph: {
    siteName: "LyricStats",
    type: "website",
    url: "/artist",
    title: "Artist Statistics · LyricStats",
    description:
      "Read an artist's whole catalogue as numbers: total vocabulary, lexical variety, average chorus share, repetition and their most frequent words.",
  },
};

export default function ArtistLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
