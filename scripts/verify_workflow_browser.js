// Execute only through a stateful Playwriter session, after reading its skill.
// Set state.reviewRevision to an absolute saved revision path before first run.
// Each invocation performs one action, observes, and advances to the next phase.
const path = require("node:path");
const { pathToFileURL } = require("node:url");
if (!state.reviewRevision || !path.isAbsolute(state.reviewRevision)) {
  throw new Error("Set state.reviewRevision to an absolute revision path first.");
}
const revision = state.reviewRevision;
const phase = state.reviewAction || "review";
const phases = ["review", "mobile-review", "inspector", "needs-review", "passing", "component", "mobile-inspector", "done"];

if (phase === "review") {
  state.page = await context.newPage();
  await state.page.setViewportSize({ width: 1440, height: 1000 });
  await state.page.goto(pathToFileURL(path.join(revision, "review.html")).href, { waitUntil: "domcontentloaded" });
} else {
  if (!state.page || state.page.isClosed()) throw new Error("Review tab closed; reset state.reviewAction to review.");
  if (phase === "mobile-review") {
    await state.page.setViewportSize({ width: 390, height: 844 });
  } else if (phase === "inspector") {
    await state.page.setViewportSize({ width: 1440, height: 1000 });
    await state.page.getByRole("link", { name: "CAD inspector", exact: true }).click();
  } else if (phase === "needs-review") {
    await state.page.getByRole("button", { name: "Needs review", exact: true }).click();
  } else if (phase === "passing") {
    await state.page.getByRole("button", { name: "Passing", exact: true }).click();
  } else if (phase === "component") {
    await state.page.getByRole("link", { name: "plate", exact: true }).first().click();
  } else if (phase === "mobile-inspector") {
    await state.page.setViewportSize({ width: 390, height: 844 });
  } else if (phase === "done") {
    console.log("Browser checks complete. Inspect saved desktop/mobile screenshots.");
  } else throw new Error("Unknown review phase: " + phase);
}

console.log("Phase:", phase, "URL:", state.page.url());
const observed = await snapshot({ page: state.page, showDiffSinceLastCall: false });
console.log(observed.split("\n").filter(line => /URL:|heading |Variant |role=button|role=link|image |strong:|ready-for-review|needs-revision/.test(line)).slice(0, 50).join("\n"));
const logs = await getLatestLogs({ page: state.page, sinceLastCall: true });
console.log("Browser logs:", logs);
const images = await state.page.locator("figure img").evaluateAll(images => images.map(img => ({
  alt: img.alt, loaded: img.complete && img.naturalWidth > 0,
})));
console.log("Previews:", images);
if (images.some(image => !image.loaded)) throw new Error("A review preview failed to load");
if (phase === "needs-review" && await state.page.locator('[data-status="pass"]:visible').count()) {
  throw new Error("Needs review filter left passing checks visible");
}
if (phase === "passing" && await state.page.locator('[data-status]:visible:not([data-status="pass"])').count()) {
  throw new Error("Passing filter left non-passing checks visible");
}
if (phase === "component" && !state.page.url().includes("#component-plate")) throw new Error("Component anchor failed");
if (["review", "mobile-review", "inspector", "mobile-inspector"].includes(phase)) {
  const screenshot = path.join(revision, "browser-" + phase + ".png");
  await state.page.screenshot({ path: screenshot, scale: "css", fullPage: false });
  console.log("Screenshot:", screenshot);
}
state.reviewAction = phases[Math.min(phases.indexOf(phase) + 1, phases.length - 1)];
console.log("Next phase:", state.reviewAction, "— run this script again.");
