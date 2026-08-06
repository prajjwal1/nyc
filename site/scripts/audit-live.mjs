import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const baseUrl = (process.env.SITE_URL || "https://prajjwal1.github.io/nyc/").replace(/\/?$/, "/");
const outputDir = process.env.AUDIT_OUTPUT_DIR || "../audit-output";
const routes = ["", "events/", "communities/", "saved/"];
const viewports = [
  { name: "mobile", width: 390, height: 844 },
  { name: "desktop", width: 1440, height: 900 },
];

await fs.mkdir(outputDir, { recursive: true });
const browser = await chromium.launch();
const results = [];

for (const viewport of viewports) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    timezoneId: "America/New_York",
    colorScheme: "light",
  });
  for (const route of routes) {
    const page = await context.newPage();
    const consoleErrors = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const routeName = route ? route.replaceAll("/", "") : "home";
    let status = 0;
    try {
      const response = await page.goto(new URL(route, baseUrl).toString(), {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
      status = response?.status() || 0;
      await page.waitForTimeout(5_000);
      await page.screenshot({
        path: path.join(outputDir, `${viewport.name}-${routeName}.png`),
        fullPage: true,
      });
      await page.screenshot({
        path: path.join(outputDir, `${viewport.name}-${routeName}-critic.jpg`),
        type: "jpeg",
        quality: 68,
        fullPage: false,
      });
      const facts = await page.evaluate(() => {
        const images = [...document.images];
        const showcased = [...document.querySelectorAll("[data-event-id]")].map((node) => ({
          id: node.getAttribute("data-event-id"),
          section: node.getAttribute("data-feed-section"),
          rank: Number(node.getAttribute("data-rank") || 0),
        }));
        return {
          title: document.title,
          bodyTextLength: document.body.innerText.length,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
          brokenImages: images.filter((image) => image.complete && image.naturalWidth === 0).map((image) => image.currentSrc || image.src).slice(0, 20),
          showcased,
          navLabels: [...document.querySelectorAll("nav a")].map((node) => node.textContent?.trim()),
          h1: document.querySelector("h1")?.textContent?.trim() || null,
        };
      });
      results.push({ viewport: viewport.name, route: routeName, status, consoleErrors, pageErrors, ...facts });
    } catch (error) {
      results.push({ viewport: viewport.name, route: routeName, status, error: String(error), consoleErrors, pageErrors });
    } finally {
      await page.close();
    }
  }
  await context.close();
}

await browser.close();
await fs.writeFile(path.join(outputDir, "browser-audit.json"), JSON.stringify({ baseUrl, auditedAt: new Date().toISOString(), results }, null, 2) + "\n");
const home = results.filter((result) => result.route === "home");
const uniqueShowcased = new Set(home.flatMap((result) => (result.showcased || []).map((event) => event.id)));
console.log(JSON.stringify({ routes: results.length, failures: results.filter((result) => result.status !== 200 || result.error).length, showcased: uniqueShowcased.size }, null, 2));
