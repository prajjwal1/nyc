// Generate a minimal RFC-5545 .ics file for a single event so the user
// can click "Add to calendar" and have it land in Apple Calendar / Google
// Calendar / Outlook without leaving the page.

import { Event } from "./types";

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

// "YYYYMMDDTHHMMSS" for floating local time. We deliberately don't tag it
// as UTC because event times in the source data are typically NYC-local.
function fmt(date: Date): string {
  return (
    date.getFullYear().toString() +
    pad(date.getMonth() + 1) +
    pad(date.getDate()) +
    "T" +
    pad(date.getHours()) +
    pad(date.getMinutes()) +
    pad(date.getSeconds())
  );
}

function escapeIcs(s: string): string {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

export function buildIcs(event: Event): string {
  // Parse date + time. If no startTime, default to whole-day.
  const [y, m, d] = event.date.split("-").map(Number);
  let start: Date;
  let end: Date;
  if (event.startTime) {
    const [sh, sm] = event.startTime.split(":").map(Number);
    start = new Date(y, m - 1, d, sh, sm, 0);
    if (event.endTime) {
      const [eh, em] = event.endTime.split(":").map(Number);
      end = new Date(y, m - 1, d, eh, em, 0);
      // Handle end-time-before-start (overnight events — assume +1 day)
      if (end <= start) end = new Date(end.getTime() + 24 * 3600 * 1000);
    } else {
      // Default 2-hour duration
      end = new Date(start.getTime() + 2 * 3600 * 1000);
    }
  } else {
    // All-day event
    start = new Date(y, m - 1, d, 0, 0, 0);
    end = new Date(y, m - 1, d + 1, 0, 0, 0);
  }

  const summary = escapeIcs(event.title || "Event");
  const desc = escapeIcs(
    [
      event.description || "",
      event.sourceUrl ? `\nMore: ${event.sourceUrl}` : "",
    ].join("").trim(),
  );
  const location = escapeIcs(
    [event.location?.name, event.location?.address, event.location?.neighborhood]
      .filter(Boolean)
      .join(", "),
  );

  const uid = `${event.id || event.sourceUrl}@nyc-events`;

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//nyc-events//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${fmt(new Date())}`,
    `DTSTART:${fmt(start)}`,
    `DTEND:${fmt(end)}`,
    `SUMMARY:${summary}`,
    desc ? `DESCRIPTION:${desc}` : "",
    location ? `LOCATION:${location}` : "",
    event.sourceUrl ? `URL:${event.sourceUrl}` : "",
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean);

  return lines.join("\r\n");
}

export function downloadIcs(event: Event): void {
  if (typeof window === "undefined") return;
  const ics = buildIcs(event);
  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const a = window.document.createElement("a");
  const safeTitle = (event.title || "event")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
  a.href = url;
  a.download = `${event.date}-${safeTitle}.ics`;
  window.document.body.appendChild(a);
  a.click();
  window.document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// Bundle multiple events into a single .ics file for bulk import (e.g.,
// "download all my saved events" → one click → import into Google /
// Apple / Outlook calendar in one shot).
export function buildIcsBundle(events: Event[]): string {
  if (events.length === 0) return "";
  const inner: string[] = [];
  for (const ev of events) {
    const single = buildIcs(ev);
    // Strip the calendar wrapper from each single .ics; we'll wrap once
    const m = single.match(/BEGIN:VEVENT[\s\S]+?END:VEVENT/);
    if (m) inner.push(m[0]);
  }
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//nyc-events//EN",
    "CALSCALE:GREGORIAN",
    ...inner,
    "END:VCALENDAR",
  ].join("\r\n");
}

export function downloadIcsBundle(events: Event[], filename: string = "saved-events"): void {
  if (typeof window === "undefined" || events.length === 0) return;
  const ics = buildIcsBundle(events);
  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const a = window.document.createElement("a");
  const today = new Date().toISOString().split("T")[0];
  a.href = url;
  a.download = `${filename}-${today}.ics`;
  window.document.body.appendChild(a);
  a.click();
  window.document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
