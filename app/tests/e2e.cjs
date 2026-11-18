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

  // Input confidence: a load range appears after the main result
  await page.waitForSelector(".stat-range", { timeout: 120000 });
  const range = await page.locator(".stat.heat .stat-range").textContent();
  const [lo, hi] = range.replace(/,/g, "").match(/[\d.]+/g).map(Number);
  check(lo < 41543 && hi > 41543, `heating load range is shown around the result (${range})`);
  check((await page.locator("table.ranges tbody tr").count()) === 10, "the ten most influential unmeasured inputs are listed");

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
  check((await page.locator(".rbig").textContent()) === "R-4.8", "layer builder shows R-4.8 for the balloon-frame wall");
  const groups = await page.locator('.layer select[aria-label="Material"]').first().locator("optgroup").evaluateAll((gs) => gs.map((g) => g.label));
  check(["Spray foam", "Batts and blankets", "Rigid boards", "Loose fill and blown-in"].every((g) => groups.includes(g)) && !groups.some((g) => /insulation/.test(g)),
    `material picker is grouped by material type (${groups.join(", ")})`);

  // Split cavity: 2 in closed-cell foam + 2 in mineral wool batt in a 5.5 in (2x6) cavity
  await page.click("text=+ Fill this cavity");
  const mats = page.locator('.layer select[aria-label="Material"]');
  await mats.nth(1).selectOption("spray_foam_closed_cell");
  await page.locator(".layer").nth(1).locator('label:has-text("Thickness") input').fill("2");
  await page.waitForSelector("text=1.75 in left over");  // 3.75 in balloon-frame cavity minus 2 in of foam
  await page.click("text=Split cavity: add a fill");
  await mats.nth(2).selectOption("mineral_wool_batt");
  await page.locator(".layer").nth(2).locator('label:has-text("Thickness") input').fill("2");
  const depth = page.locator('input[aria-label="Cavity depth (in)"]').first();
  await depth.fill("5.5");
  await depth.blur();
  await page.waitForSelector("text=1.5 in left over is counted as a closed air space");
  check(true, "split cavity: 2 in foam + 2 in batt in a 5.5 in cavity leaves 1.5 in of air space");
  check((await page.locator(".layer.in-cavity").count()) === 3, "the cavity shows its two fills and the air space");
  await depth.fill("3");
  await page.waitForSelector("text=do not fit in a 3 in cavity");
  check(true, "fills deeper than the cavity are refused with a message");
  await depth.blur();
  await page.waitForSelector('.rbox[aria-busy="false"]');
  check((await page.locator(".layer-r").allTextContents()).slice(1, 4).join(" ") === "R-10.00 R-8.40 R-1.00", "each fill shows its own R-value: foam R-10, batt R-8.4, air space R-1.0");
  await page.locator(".cavity-head").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(out, "split-cavity-desktop.png"), fullPage: false });
  await page.setInputFiles('input[type="file"][accept=".json,.yaml,.yml"]', example);  // back to the unedited example
  await settled(page);
  await page.click('nav >> text="Assemblies"');

  // Framing share from lumber and spacing (sunroom wall: 2x4 studs with an R-11 batt, typed share 30 %)
  await page.locator(".row").nth(1).click();
  await page.waitForSelector(".framing-panel");
  const sumRows = async () => { await page.waitForSelector(".framing-sum"); await page.waitForSelector('.rbox[aria-busy="false"]'); return (await page.locator(".framing-sum td").allTextContents()).map((t) => t.trim()); };
  await page.fill('input[aria-label="Framing share override (%)"]', "");
  await page.selectOption('select[aria-label="Lumber"]', "2x4");
  await page.selectOption('select[aria-label="Spacing"]', "16");
  let rows = await sumRows();
  check(rows[0] === "9.4%" && rows[2] === "23.0%", `2x4 at 16 in: studs 9.4 % + allowance = framing share 23.0 % (${rows.join(" | ")})`);
  await page.selectOption('select[aria-label="Lumber"]', "2x6");
  await page.selectOption('select[aria-label="Spacing"]', "24");
  rows = await sumRows();
  check(rows[0] === "6.3%" && rows[2] === "20.0%", `2x6 at 24 in: studs 6.3 % + allowance = framing share 20.0 % (${rows.join(" | ")})`);
  check((await page.locator('input[aria-label="Cavity depth (in)"]').inputValue()) === "5.5", "2x6 lumber sets the cavity depth to 5.5 in (the rest of the batt's cavity is air space)");
  await page.locator(".framing-panel").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(out, "framing-desktop.png") });
  await page.setInputFiles('input[type="file"][accept=".json,.yaml,.yml"]', example);
  await settled(page);

  // Scenario view
  await page.click('nav >> text="Results"');
  await page.selectOption("#scn", "everything");
  await page.waitForSelector(".stat .delta.good");
  check(true, "selecting a scenario shows the change against the baseline");

  // Custom glazing from an NFRC label: U 0.27 / SHGC 0.22, saved to the glazings library, saved, reopened, calculated
  await page.click('nav >> text="Openings"');
  await page.locator(".row", { hasText: "Window" }).first().click();
  await page.selectOption('select[aria-label="Glazing"]', "__custom__");
  await page.fill('input[aria-label="U-factor"]', "0.27");
  await page.fill('input[aria-label="SHGC"]', "0.22");
  await page.fill('input[aria-label="Glazing name"]', "Label test window");
  await page.screenshot({ path: path.join(out, "glazing-desktop.png") });
  await page.click("text=Save for other windows");
  await page.waitForFunction(() => document.querySelector('select[aria-label="Glazing"]')?.value === "label-test-window");
  check(true, "custom glazing saved to the library and the window now uses it");
  await settled(page);
  const [dl2] = await Promise.all([page.waitForEvent("download"), page.click("button.primary")]);
  const saved2 = path.join(out, "e2e-glazing.rtn.json");
  await dl2.saveAs(saved2);
  const h2 = JSON.parse(fs.readFileSync(saved2, "utf8"));
  const g2 = (h2.glazings || []).find((g) => g.id === "label-test-window");
  check(h2.format_version === "1.1.0" && g2 && g2.u_factor_btu_hr_ft2_f === 0.27 && g2.shgc === 0.22 && h2.openings.some((o) => o.glazing === "label-test-window"),
    "saved file (format 1.1.0) holds the glazing and the window's reference to it");
  await page.setInputFiles('input[type="file"][accept=".json,.yaml,.yml"]', saved2);
  await settled(page);
  check((await page.locator(".status.bad").count()) === 0 && (await heating(page)) > 0, `reopened file calculates (heating ${await heating(page)} Btu/h)`);
  await page.click('nav >> text="Openings"');
  await page.click("text=My glazings (1)");
  check((await page.locator(".row", { hasText: "Label test window" }).count()) === 1, "the glazing is listed under My glazings after reopening");

  // Phone layout: no sideways scrolling
  const phone = await browser.newPage({ viewport: { width: 390, height: 800 }, isMobile: true });
  await phone.goto(url);
  await phone.waitForSelector(".stat-value", { timeout: 120000 });
  for (const tab of ["Results", "Rooms", "Assemblies", "Surfaces", "Openings", "Scenarios"]) {
    await phone.click(`nav >> text="${tab}"`);
    await phone.waitForTimeout(300);
    const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(overflow <= 1, `phone: ${tab} fits the screen width (overflow ${overflow}px)`);
  }

  // Phone: the layer builder with a framed cavity fits too
  await phone.setInputFiles('input[type="file"][accept=".json,.yaml,.yml"]', example);
  await phone.waitForFunction(() => document.querySelector(".project-name").value.includes("1920s"));
  await phone.click('nav >> text="Assemblies"');
  await phone.locator(".row").first().click();
  await phone.waitForSelector(".cavity-head");
  await phone.waitForTimeout(500);
  const phoneOverflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(phoneOverflow <= 1, `phone: layer builder with a framed cavity fits the screen width (overflow ${phoneOverflow}px)`);
  await phone.locator(".cavity-head").scrollIntoViewIfNeeded();
  await phone.screenshot({ path: path.join(out, "layers-phone.png") });
  await phone.click('nav >> text="Openings"');
  await phone.locator(".row", { hasText: "Window" }).first().click();
  await phone.selectOption('select[aria-label="Glazing"]', "__custom__");
  await phone.waitForSelector(".glazing-custom");
  const glzOverflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(glzOverflow <= 1, `phone: custom glazing entry fits the screen width (overflow ${glzOverflow}px)`);
  await phone.locator(".glazing-custom").scrollIntoViewIfNeeded();
  await phone.screenshot({ path: path.join(out, "glazing-phone.png") });

  check(problems.length === 0, `no page errors ${problems.join("; ")}`);
  check(offsite.length === 0, `no requests to other sites ${offsite.slice(0, 3).join(", ")}`);
  await browser.close();
})().catch((e) => { console.log("FAIL", e.message); process.exit(1); });
