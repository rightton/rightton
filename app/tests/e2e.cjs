// End-to-end check of the built app in headless Chromium:
//   npm run build && npx vite preview --port 4173 &   then   node tests/e2e.cjs http://localhost:4173/
// Uses the Playwright that is installed on the machine (not a project dependency).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const url = process.argv[2] || "http://localhost:4173/";
const out = process.argv[3] || "/tmp";
const heating = async (p) => Number((await p.locator(".stat.heat .stat-value").textContent()).replace(/,/g, ""));
const settled = (p) => p.waitForSelector(".status.ok, .status.bad", { timeout: 120000 });
const check = (cond, what) => { console.log(`${cond ? "ok  " : "FAIL"} ${what}`); if (!cond) process.exitCode = 1; };

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  const problems = [];
  page.on("pageerror", (e) => problems.push(e.message));
  const offsite = [];
  page.on("request", (r) => { if (!r.url().startsWith(url) && !r.url().startsWith("data:") && !r.url().startsWith("blob:")) offsite.push(r.url()); });

  await page.goto(url);
  await page.waitForSelector(".stat-value", { timeout: 120000 });
  await settled(page);
  check((await heating(page)) === 41543, "opens with the NREL base house: heating 41,543 Btu/h (the reference engine's value)");

  // Edit the blower-door number and see the load move
  await page.click('nav >> text="Air & ducts"');
  const ach = page.locator('.field:has(label:text-is("ACH50 (air changes per hour at 50 Pa)")) input[type="text"]').first();
  await ach.fill("6");
  await page.waitForFunction(() => document.querySelector(".strip-loads")?.textContent?.includes("Heating") && !document.querySelector(".status.busy"));
  await page.click('nav >> text="Results"');
  await settled(page);
  const leaky = await heating(page);
  check(leaky > 41543, `doubling ACH50 raises the heating load (${leaky})`);
  await page.click('button[aria-label="Undo"]');
  await page.waitForFunction(() => document.querySelector(".stat.heat .stat-value")?.textContent === "41,543");
  check(true, "undo restores the previous result");

  // Add a room; the checker notes it has no surfaces
  await page.click('nav >> text="Rooms"');
  await page.click("text=+ Add room");
  await page.waitForSelector(".detail");
  await page.click('nav >> text="Check"');
  await page.waitForSelector("text=no surface names this room");
  check(true, "a new room with no surfaces is flagged in plain English");

  // Save, and validate the saved file with the Python validator
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("button.primary")]);
  const saved = path.join(out, "e2e-saved.rtn.json");
  await download.saveAs(saved);
  const house = JSON.parse(fs.readFileSync(saved, "utf8"));
  check(download.suggestedFilename().endsWith(".rtn.json") && house.rooms.some((r) => r.name === "New room"), `saved ${download.suggestedFilename()} contains the new room`);

  // Open a YAML house file
  const example = path.join(__dirname, "..", "..", "examples", "old-house.rtn.yaml");
  await page.setInputFiles('input[type="file"][accept=".json,.yaml,.yml"]', example);
  await page.waitForFunction(() => document.querySelector(".project-name").value.includes("1920s"));
  await settled(page);
  check((await page.locator("table.data tbody tr").count()) > 6, "opening a YAML file shows its scenarios and rooms");

  // Layer builder: R-value comes from the Python core
  await page.click('nav >> text="Assemblies"');
  await page.locator(".row").first().click();
  await page.waitForSelector(".rbig");
  check((await page.locator(".rbig").textContent()) === "R-4.7", "layer builder shows R-4.7 for the balloon-frame wall");

  // Scenario view
  await page.click('nav >> text="Results"');
  await page.selectOption("#scn", "everything");
  await page.waitForSelector(".stat .delta.good");
  check(true, "selecting a scenario shows the change against the baseline");

  // Phone layout: no sideways scrolling
  const phone = await browser.newPage({ viewport: { width: 390, height: 800 }, isMobile: true });
  await phone.goto(url);
  await phone.waitForSelector(".stat-value", { timeout: 120000 });
  for (const tab of ["Results", "Surfaces", "Openings", "Scenarios"]) {
    await phone.click(`nav >> text="${tab}"`);
    await phone.waitForTimeout(300);
    const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(overflow <= 1, `phone: ${tab} fits the screen width (overflow ${overflow}px)`);
  }

  check(problems.length === 0, `no page errors ${problems.join("; ")}`);
  check(offsite.length === 0, `no requests to other sites ${offsite.slice(0, 3).join(", ")}`);
  await browser.close();
})().catch((e) => { console.log("FAIL", e.message); process.exit(1); });
