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
      for (const removedTab of ["Events", "Communities", "Saved"]) {
        const count = await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: removedTab, exact: true }).count();
        if (count) throw new Error(`primary navigation still exposes ${removedTab}`);
      }
      if (await page.getByRole("button", { name: "Export taste" }).count()) {
        throw new Error("header still exposes Export taste");
      }
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
          const organizerLink = card.locator('a[aria-label^="Organizer:"], a[aria-label^="More information:"]').first();
          if (!(await organizerLink.count()) || await organizerLink.getAttribute("target") !== "_blank") {
            throw new Error("event card is missing its external organizer link");
          }
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

    await page.close();
  }
  console.log("UI checks passed: calendar-first navigation, organizer links, touch-safe actions, persistent Hide, and account views.");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
