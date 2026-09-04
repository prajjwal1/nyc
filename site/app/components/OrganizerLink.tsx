"use client";

import { Event } from "../lib/types";
import { trackAccountClick } from "../lib/interests";
import { eventOrganizerDetails } from "../lib/organizer";

export default function OrganizerLink({ event, className = "" }: { event: Event; className?: string }) {
  const organizer = eventOrganizerDetails(event);

  return (
    <a
      href={organizer.url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(clickEvent) => {
        clickEvent.stopPropagation();
        if (organizer.account) trackAccountClick(organizer.account);
      }}
      className={className}
      aria-label={`${organizer.isOrganizer ? "Organizer" : "More information"}: ${organizer.label} (opens in a new tab)`}
    >
      <span className="text-[#8b918e]">{organizer.isOrganizer ? "By" : "More info"}</span>{" "}
      <span className="font-semibold">{organizer.label} ↗</span>
    </a>
  );
}
