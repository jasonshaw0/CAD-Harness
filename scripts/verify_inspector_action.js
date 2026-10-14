const actions = {
  1: "review-filter",
  2: "pass-filter",
  3: "component-link",
  4: "mobile",
};
const action = actions[state.action];
if (!state.page || state.page.isClosed()) {
  throw new Error("inspector page is not available in this Playwriter session");
}

if (action === "review-filter") {
  await state.page.getByRole("button", { name: "Needs review" }).click();
} else if (action === "pass-filter") {
  await state.page.getByRole("button", { name: "Passing" }).click();
} else if (action === "component-link") {
  await state.page.getByRole("link", { name: "base" }).first().click();
} else if (action === "mobile") {
  await state.page.setViewportSize({ width: 390, height: 844 });
} else {
  throw new Error(`unknown INSPECTOR_ACTION: ${action}`);
}

const visibleChecks = await state.page.locator("[data-status]:visible").count();
const loadedImages = await state.page.locator("figure img").evaluateAll((images) =>
  images.map((image) => ({
    alt: image.alt,
    complete: image.complete,
    width: image.naturalWidth,
    height: image.naturalHeight,
  })),
);
console.log("Action:", action);
console.log("URL:", state.page.url());
console.log("Visible checks:", visibleChecks);
console.log("Preview images:", loadedImages);
console.log(
  "Logs:",
  await getLatestLogs({ page: state.page, sinceLastCall: true }),
);
console.log(await snapshot({ page: state.page, showDiffSinceLastCall: true }));
if (action === "mobile") {
  const path = require("node:path");
  const screenshotPath = path.join(
    process.cwd(),
    "examples",
    "project-box",
    "artifacts",
    "inspector",
    "mobile-verification.png",
  );
  await state.page.screenshot({ path: screenshotPath, scale: "css", fullPage: true });
  await resizeImageForAgent({ input: screenshotPath, maxDimension: 1000 });
}
