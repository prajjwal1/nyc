export const SITE_URL = "https://prajjwal1.github.io/nyc";
export const SITE_NAME = "NYC Events";

export const SITE_TITLE = "NYC Events: Things to Do Today & This Weekend";
export const SITE_DESCRIPTION =
  "Discover curated NYC events, free things to do, live music, comedy, art, food, and fitness across Brooklyn, Manhattan, Queens, and beyond.";
export const DEFAULT_OG_IMAGE = "/opengraph-image";
export const DEFAULT_TWITTER_IMAGE = "/twitter-image";

export function absoluteUrl(path = "/"): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_URL}${normalized}`;
}

export function eventPath(id: string): string {
  return `/events/${encodeURIComponent(id)}/`;
}

export function categoryPath(category: string): string {
  return `/categories/${encodeURIComponent(category)}/`;
}

export function plainText(value: string, maxLength = 180): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}
