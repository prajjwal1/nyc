import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("out");
const port = 4173;
const eventsPayload = JSON.parse(await readFile(path.join(root, "events.json"), "utf8"));
const accountCandidate = (eventsPayload.events || [])
  .map((event) => event.instagramAccount || event.account)
  .find(Boolean);
if (!accountCandidate) throw new Error("events.json contains no account suitable for the account-view check");
const escapedAccount = accountCandidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const mime = {
  ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2",
};

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://127.0.0.1:${port}`);
    let relative = decodeURIComponent(url.pathname).replace(/^\/nyc\/?/, "");
    let file = path.join(root, relative);
    if (!file.startsWith(root)) throw new Error("invalid path");
    try {
      if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
    } catch {
      if (!path.extname(file)) file = path.join(file, "index.html");
    }
    const body = await readFile(file);
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "text/html" });
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end("Not found");
  }
});

await new Promise((resolve) => server.listen(port, "127.0.0.1", resolve));
const browser = await chromium.launch();

try {
  for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 900 }]) {
    const page = await browser.newPage({ viewport });
    for (const route of ["", "events/", "communities/", "saved/"]) {
      const response = await page.goto(`http://127.0.0.1:${port}/nyc/${route}`, { waitUntil: "networkidle" });
      if (response?.status() !== 200) throw new Error(`${route || "home"} returned ${response?.status()}`);
      const searchInputs = await page.locator('input[type="search"], input[placeholder*="search" i]').count();
      if (searchInputs) throw new Error(`${route || "home"} still renders ${searchInputs} search inputs`);
      const clipped = await page.locator("nav a").evaluateAll((links) => links
        .filter((link) => {
          const rect = link.getBoundingClientRect();
          return rect.left < 0 || rect.right > window.innerWidth;
        })
        .map((link) => link.textContent?.trim()));
      if (clipped.length) throw new Error(`${route || "home"} clips navigation: ${clipped.join(", ")}`);
      if (!route) {
        if (!(await page.getByRole("heading", { name: "What's happening in NYC" }).count())) {
          throw new Error("homepage did not render its primary heading");
        }
        if ((await page.getByRole("tab").count()) !== 0) throw new Error("homepage still renders Feed/Calendar tabs");
        if ((await page.getByRole("link", { name: "Feed", exact: true }).count()) !== 0) {
          throw new Error("primary navigation still exposes Feed");
        }
        if ((await page.locator('button[aria-label^="Previous month"], button[aria-label^="Next month"]').count()) < 2) {
          throw new Error("homepage calendar controls are missing");
        }
        const card = page.locator("[data-event-id]").first();
        if (await card.count()) {
          const minimumTarget = viewport.width < 640 ? 44 : 36;
          for (const name of ["Save", "Add to calendar", "Hide"]) {
            const control = card.getByRole("button", { name });
            const box = await control.boundingBox();
            if (!box || box.width < minimumTarget || box.height < minimumTarget) {
              throw new Error(`${name} touch target is smaller than ${minimumTarget}px`);
            }
          }
        }
      }
    }
    await page.goto(`http://127.0.0.1:${port}/nyc/?account=${encodeURIComponent(accountCandidate)}`, { waitUntil: "networkidle" });
    if (!(await page.getByText(new RegExp(`^Showing @${escapedAccount} · \\d+ events$`)).count())) {
      throw new Error("shareable account view did not render its account filter");
    }
    await page.goto(`http://127.0.0.1:${port}/nyc/?view=for-you`, { waitUntil: "networkidle" });
    if (new URL(page.url()).searchParams.has("view")) throw new Error("legacy Feed URL state was not removed");
    if (!(await page.getByRole("heading", { name: "What's happening in NYC" }).count())) throw new Error("legacy Feed URL did not resolve to Calendar");

    const firstCard = page.locator("[data-event-id]").first();
    if (await firstCard.count()) {
      const hiddenId = await firstCard.getAttribute("data-event-id");
      await firstCard.getByRole("button", { name: "Hide" }).click();
      if (await page.locator(`[data-event-id="${hiddenId}"]`).count()) {
        throw new Error("hidden event remained visible on the homepage");
      }
      await page.reload({ waitUntil: "networkidle" });
      if (await page.locator(`[data-event-id="${hiddenId}"]`).count()) {
        throw new Error("hidden event returned after reload");
      }
    }

    if (viewport.width === 1280) {
      await page.evaluate(() => {
        const stub = (id, title) => ({
          id, title, description: `${title} description`, categories: ["books"],
          date: "2026-08-01", sourceUrl: "https://example.com/event", imageUrl: null,
          organizer: "Example Books", locationName: "Brooklyn",
        });
        localStorage.setItem("nyc-events:saved:v1", JSON.stringify(["saved-1"]));
        localStorage.setItem("nyc-events:savedCache:v1", JSON.stringify({ "saved-1": stub("saved-1", "Saved reading") }));
        localStorage.setItem("nyc-events:hidden:v1", JSON.stringify(["hidden-1"]));
        localStorage.setItem("nyc-events:hiddenCache:v1", JSON.stringify({ "hidden-1": stub("hidden-1", "Hidden party") }));
        localStorage.setItem("nyc-events:attended:v1", JSON.stringify({ "yes-1": "yes", "no-1": "no" }));
        localStorage.setItem("nyc-events:attendedCache:v1", JSON.stringify({
          "yes-1": { stub: stub("yes-1", "Attended book club") },
          "no-1": { stub: stub("no-1", "Missed workshop") },
        }));
      });
      await page.reload({ waitUntil: "networkidle" });
      const beforeAttendance = await page.evaluate(() => localStorage.getItem("nyc-events:attended:v1"));
      const downloadPromise = page.waitForEvent("download");
      await page.getByRole("button", { name: "Export taste" }).click();
      const download = await downloadPromise;
      if (download.suggestedFilename() !== "user_engagement.json") throw new Error("taste export filename changed");
      const stream = await download.createReadStream();
      let contents = "";
      for await (const chunk of stream) contents += chunk.toString();
      const snapshot = JSON.parse(contents);
      if (!snapshot.positiveTexts.some((text) => text.includes("Saved reading"))) throw new Error("saved event missing from taste positives");
      if (!snapshot.negativeTexts.some((text) => text.includes("Hidden party"))) throw new Error("hidden event missing from taste negatives");
      if (!snapshot.attendedYesTexts.some((text) => text.includes("Attended book club"))) throw new Error("attended yes missing from taste export");
      if (!snapshot.attendedNoTexts.some((text) => text.includes("Missed workshop"))) throw new Error("attended no missing from taste export");
      if (JSON.stringify(snapshot.attended) !== JSON.stringify({ "yes-1": "yes", "no-1": "no" })) throw new Error("attendance states missing from taste export");
      await page.reload({ waitUntil: "networkidle" });
      const afterAttendance = await page.evaluate(() => localStorage.getItem("nyc-events:attended:v1"));
      if (beforeAttendance !== afterAttendance) throw new Error("taste export changed attended:v1");
    }
    await page.close();
  }
  console.log("UI checks passed: compact calendar hierarchy, touch-safe actions, persistent Hide, navigation, account views, and taste export.");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
