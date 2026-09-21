import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  // lastModified is the build date — each deploy refreshes it.
  const lastModified = new Date();
  return [
    { url: `${SITE_URL}/issues`, lastModified, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE_URL}/issues/01`, lastModified: new Date("2026-06-11"), priority: 0.6 },
    {
      url: `${SITE_URL}/issues/02`,
      lastModified: new Date("2026-09-14"),
      changeFrequency: "monthly",
      priority: 0.9,
    },
    {
      url: SITE_URL,
      lastModified,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${SITE_URL}/song`,
      lastModified,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/artist`,
      lastModified,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    // The readings the song page opens with.
    ...["michael-jackson/thriller", "queen/bohemian-rhapsody", "kendrick-lamar/humble"].map(
      (path) => ({
        url: `${SITE_URL}/song/${path}`,
        lastModified,
        changeFrequency: "monthly" as const,
        priority: 0.6,
      }),
    ),
  ];
}
