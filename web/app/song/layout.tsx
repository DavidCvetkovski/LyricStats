import type { Metadata } from "next";

// The song page is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: "A Close Reading",
  description:
    "Explore a song’s returning lines, written shape and unfolding vocabulary. Search for a song or read your own text privately in your browser.",
  alternates: {
    canonical: "/song",
  },
  openGraph: {
    siteName: "LyricStats",
    type: "website",
    url: "/song",
    title: "A Close Reading · LyricStats",
    description:
      "Explore a song’s returning lines, written shape and unfolding vocabulary. Search for a song or read your own text privately in your browser.",
  },
};

export default function SongLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
