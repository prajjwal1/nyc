import type { MetadataRoute } from "next";
import { getCommunitiesData, getEventsData } from "./lib/server-data";
import { absoluteUrl, categoryPath, eventPath } from "./lib/seo";
import { CATEGORY_CONFIG } from "./lib/types";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const data = getEventsData();
  const lastModified = new Date(data.lastUpdated);
  const categories = new Set(data.events.flatMap((event) => event.categories));

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: absoluteUrl("/"), lastModified, changeFrequency: "hourly", priority: 1 },
    { url: absoluteUrl("/events/"), lastModified, changeFrequency: "hourly", priority: 0.9 },
    { url: absoluteUrl("/communities/"), lastModified, changeFrequency: "daily", priority: 0.8 },
  ];

  const categoryRoutes: MetadataRoute.Sitemap = [...categories]
    .filter((category) => category !== "other" && CATEGORY_CONFIG[category])
    .map((category) => ({
      url: absoluteUrl(categoryPath(category)),
      lastModified,
      changeFrequency: "daily" as const,
      priority: 0.75,
    }));

  const eventRoutes: MetadataRoute.Sitemap = data.events.map((event) => ({
    url: absoluteUrl(eventPath(event.id)),
    lastModified: new Date(event.scrapedAt || data.lastUpdated),
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  const communityRoutes: MetadataRoute.Sitemap = getCommunitiesData().communities
    .filter((community) => community.profileStatus !== "directory_reference")
    .map((community) => ({
      url: absoluteUrl(`/communities/${encodeURIComponent(community.slug)}/`),
      lastModified: community.lastVerifiedAt ? new Date(community.lastVerifiedAt) : lastModified,
      changeFrequency: "weekly" as const,
      priority: 0.65,
    }));

  return [...staticRoutes, ...categoryRoutes, ...communityRoutes, ...eventRoutes];
}
