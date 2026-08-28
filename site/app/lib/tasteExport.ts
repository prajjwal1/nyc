import {
  loadAttendedExamples,
  loadAttendedStates,
  loadHiddenStubs,
  loadProfile,
  loadSavedStubs,
  SavedEventStub,
} from "./interests";

export interface TasteSnapshot {
  updatedAt: string;
  accounts: Record<string, number>;
  categories: Record<string, number>;
  hosts: Record<string, number>;
  negAccounts: Record<string, number>;
  negHosts: Record<string, number>;
  negCategories: Record<string, number>;
  timeBuckets: Record<string, number>;
  dayOfWeek: Record<string, number>;
  attended: Record<string, "yes" | "no">;
  positiveTexts: string[];
  negativeTexts: string[];
  attendedYesTexts: string[];
  attendedNoTexts: string[];
}

function eventText(stub: SavedEventStub): string {
  return [
    stub.title,
    stub.description,
    ...(stub.categories || []),
    stub.locationName,
    stub.organizer,
    stub.account,
    stub.instagramAccount,
  ].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

function uniqueTexts(stubs: SavedEventStub[]): string[] {
  return [...new Set(stubs.map(eventText).filter(Boolean))];
}

export function buildTasteSnapshot(): TasteSnapshot {
  const profile = loadProfile();
  const attendance = loadAttendedExamples();
  const yesStubs = attendance
    .filter((item) => item.state === "yes" && item.stub)
    .map((item) => item.stub as SavedEventStub);
  const noStubs = attendance
    .filter((item) => item.state === "no" && item.stub)
    .map((item) => item.stub as SavedEventStub);

  return {
    updatedAt: new Date().toISOString(),
    accounts: profile.accounts || {},
    categories: profile.categories || {},
    hosts: profile.hosts || {},
    negAccounts: profile.negAccounts || {},
    negHosts: profile.negHosts || {},
    negCategories: profile.negCategories || {},
    timeBuckets: profile.timeBuckets || {},
    dayOfWeek: profile.dayOfWeek || {},
    attended: loadAttendedStates(),
    positiveTexts: uniqueTexts([...loadSavedStubs(), ...yesStubs]),
    negativeTexts: uniqueTexts(loadHiddenStubs()),
    attendedYesTexts: uniqueTexts(yesStubs),
    attendedNoTexts: uniqueTexts(noStubs),
  };
}

export function hasTasteSignal(): boolean {
  const snapshot = buildTasteSnapshot();
  const mapSize = (value: Record<string, unknown>) => Object.keys(value).length;
  return mapSize(snapshot.accounts) + mapSize(snapshot.categories) + mapSize(snapshot.hosts)
    + mapSize(snapshot.negAccounts) + mapSize(snapshot.negCategories) + mapSize(snapshot.negHosts)
    + mapSize(snapshot.attended) + snapshot.positiveTexts.length + snapshot.negativeTexts.length > 0;
}

export function downloadTasteSnapshot(): TasteSnapshot {
  const snapshot = buildTasteSnapshot();
  const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "user_engagement.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return snapshot;
}

