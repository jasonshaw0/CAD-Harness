const path = require("node:path");
const { pathToFileURL } = require("node:url");
const inspectorUrl = pathToFileURL(
  path.join(
    process.cwd(),
    "examples",
    "project-box",
    "artifacts",
    "inspector",
    "index.html",
  ),
).href;

state.page = await context.newPage();
await state.page.setViewportSize({ width: 1440, height: 1000 });
await state.page.goto(inspectorUrl, { waitUntil: "domcontentloaded" });
console.log("URL:", state.page.url());
console.log(
  "Logs:",
  await getLatestLogs({ page: state.page, sinceLastCall: true }),
);
console.log(await snapshot({ page: state.page, showDiffSinceLastCall: false }));
