"use client";

import { useSyncExternalStore } from "react";
import { Event } from "../lib/types";
import {
  PROFILE_CHANGE_EVENT,
  eventToSavedStub,
  hideEvent,
  isSavedLocal,
  toggleSavedLocal,
} from "../lib/interests";
import { downloadIcs } from "../lib/ics";

function subscribeToSavedState(callback: () => void) {
  window.addEventListener(PROFILE_CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(PROFILE_CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

export default function EventDetailActions({ event }: { event: Event }) {
  const saved = useSyncExternalStore(
    subscribeToSavedState,
    () => isSavedLocal(event.id),
    () => false,
  );

  const hint = {
    account: event.account || event.organizer || event.instagramAccount,
    categories: event.categories,
    sourceUrl: event.organizerUrl || event.sourceUrl,
    stub: eventToSavedStub(event),
  };

  return (
    <div className="mt-6 flex flex-wrap gap-3" aria-label="Event actions">
      <button
        type="button"
        onClick={() => toggleSavedLocal(event.id, hint)}
        className="rounded-full border border-[#9bb7ae] px-4 py-2 text-sm font-semibold text-[#173c35] hover:bg-[#edf5f1]"
      >
        {saved ? "★ Saved" : "☆ Save"}
      </button>
      <button
        type="button"
        onClick={() => downloadIcs(event)}
        className="rounded-full border border-[#9bb7ae] px-4 py-2 text-sm font-semibold text-[#173c35] hover:bg-[#edf5f1]"
      >
        Add to calendar
      </button>
      <button
        type="button"
        onClick={() => {
          hideEvent(event.id, hint);
          const base = process.env.NODE_ENV === "production" ? "/nyc" : "";
          window.location.assign(`${base}/events/`);
        }}
        className="rounded-full px-4 py-2 text-sm font-semibold text-[#66716c] hover:bg-[#f1ece1] hover:text-[#9f4f36]"
      >
        × Hide
      </button>
    </div>
  );
}
