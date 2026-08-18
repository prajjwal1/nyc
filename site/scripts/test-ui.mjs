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
        if (!(await page.getByRole("heading", { name: "Choose a date" }).count())) {
          throw new Error("homepage did not render the calendar-first heading");
        }
        if ((await page.getByRole("tab").count()) !== 0) throw new Error("homepage still renders Feed/Calendar tabs");
        if ((await page.getByRole("link", { name: "Feed", exact: true }).count()) !== 0) {
          throw new Error("primary navigation still exposes Feed");
        }
        if ((await page.locator('button[aria-label^="Previous month"], button[aria-label^="Next month"]').count()) < 2) {
          throw new Error("homepage calendar controls are missing");
        }
      }
    }
    await page.goto(`http://127.0.0.1:${port}/nyc/?account=${encodeURIComponent(accountCandidate)}`, { waitUntil: "networkidle" });
    if (!(await page.getByText(new RegExp(`^@${escapedAccount} · \\d+$`)).count())) {
      throw new Error("shareable account view did not render its account filter");
    }
    await page.goto(`http://127.0.0.1:${port}/nyc/?view=for-you`, { waitUntil: "networkidle" });
    if (new URL(page.url()).searchParams.has("view")) throw new Error("legacy Feed URL state was not removed");
    if (!(await page.getByRole("heading", { name: "Choose a date" }).count())) throw new Error("legacy Feed URL did not resolve to Calendar");
    await page.close();
  }
  console.log("UI checks passed: Calendar is the homepage, Feed/search are absent, navigation fits, and account views are shareable.");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
