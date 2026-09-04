import { Event, SOURCE_LABELS } from "./types";

export interface EventOrganizerDetails {
  account?: string;
  isOrganizer: boolean;
  label: string;
  url: string;
}

function externalUrl(value?: string): string | null {
  const trimmed = value?.trim();
  return trimmed && /^https?:\/\//i.test(trimmed) ? trimmed : null;
}

export function eventOrganizerDetails(event: Event): EventOrganizerDetails {
  const account = (event.instagramAccount || event.account)?.replace(/^@/, "").trim() || undefined;
  const namedOrganizer = event.organizer?.trim();
  const organizerUrl = externalUrl(event.organizerUrl);
  const instagramUrl = account && (event.instagramAccount || event.source === "instagram")
    ? `https://www.instagram.com/${encodeURIComponent(account)}/`
    : null;

  return {
    account,
    isOrganizer: Boolean(namedOrganizer || account),
    label: namedOrganizer || (account ? `@${account}` : SOURCE_LABELS[event.source] || event.source),
    url: organizerUrl || instagramUrl || externalUrl(event.sourceUrl) || event.sourceUrl,
  };
}
