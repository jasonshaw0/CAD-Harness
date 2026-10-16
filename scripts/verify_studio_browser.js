// Run only through a stateful Playwriter session after reading its skill.
// Set state.studioUrl if needed. Repeated invocations perform one action each.
// This builds a fresh repository-owned example, rebuilds, and explicitly exports
// STEP in the selected test workspace. Never point it at a user's active session.
const fs = require('node:fs');
const path = require('node:path');
const steps = ['open', 'authorize', 'new', 'example', 'ready', 'select', 'isolate', 'restore',
  'review', 'expand', 'filter', 'history', 'rebuild', 'rebuilt', 'historical', 'current',
  'compare', 'overlay', 'palette', 'find-source', 'source', 'source-ready', 'export-menu',
  'export-step', 'export-finished', 'export-stl', 'export-stl-finished', 'download-menu', 'download', 'dismiss-menu',
  'theme', 'desktop-dark', 'mobile', 'close-panel', 'collapse-explorer', 'mobile-fit', 'mobile-view', 'mobile-top', 'done'];
const step = state.studioCheckStep || 'open';
state.studioArtifacts ||= path.resolve('runs', 'studio-browser-' + Date.now());
fs.mkdirSync(state.studioArtifacts, { recursive: true });
const shot = name => state.page.screenshot({ path: path.join(state.studioArtifacts, name + '.png'), scale: 'css' });
const button = name => state.page.getByRole('button', { name, exact: typeof name === 'string' });

if (step === 'open') {
  state.page = await context.newPage();
  await state.page.setViewportSize({ width: 1440, height: 960 });
  await state.page.goto(state.studioUrl || 'http://127.0.0.1:8743', { waitUntil: 'domcontentloaded' });
} else if (step === 'authorize') {
  if (await button('Enable session').count()) await button('Enable session').click();
} else if (step === 'new') await button('New design').click();
else if (step === 'example') await button('Mounting plate Four mounting holes and reference envelopes').click();
else if (step === 'ready') {
  await button('Open engineering checks').filter({ hasText: '37 / 37' }).waitFor({ timeout: 30000 });
  await shot('desktop-light');
} else if (step === 'select') await button('plate').click();
else if (step === 'isolate') await button('Isolate part').click();
else if (step === 'restore') await button('Show all parts').click();
else if (step === 'review') await button('Open engineering checks').click();
else if (step === 'expand') await state.page.getByText('plate z', { exact: true }).click();
else if (step === 'filter') await button('Needs attention · 0').click();
else if (step === 'history') await button('r001 Current revision').click();
else if (step === 'rebuild') await button('Rebuild current source').click();
else if (step === 'rebuilt') {
  await button('r002 Current revision').waitFor({ timeout: 30000 });
  await state.page.getByRole('status').waitFor({ state: 'hidden', timeout: 30000 });
} else if (step === 'historical') await button(/^r001/).click();
else if (step === 'current') await button('Return to current revision').click();
else if (step === 'compare') await button('Compare').click();
else if (step === 'overlay') await state.page.getByRole('switch', { name: /^Previous geometry overlay/ }).click();
else if (step === 'palette') await button('Command palette').click();
else if (step === 'find-source') {
  await state.page.getByRole('textbox', { name: 'Search commands' }).click();
  await state.page.getByRole('textbox', { name: 'Search commands' }).fill('source');
} else if (step === 'source') await button('Source files').click();
else if (step === 'source-ready') {
  await state.page.getByLabel('Source code').filter({ hasText: /from |\[project\]/ }).waitFor({ timeout: 10000 });
  await shot('source-light');
} else if (step === 'export-menu') await button('Export design').click();
else if (step === 'export-step') {
  const [download] = await Promise.all([state.page.waitForEvent('download'), button('STEP geometry .step').click()]);
  const failure = await download.failure();
  if (failure) throw new Error('Automatic STEP download failed: ' + failure);
  const artifact = await state.page.evaluate(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Automatic export download returned ' + response.status);
    return response.text();
  }, download.url());
  if (!artifact.startsWith('ISO-10303-21;')) throw new Error('Automatic export is not a STEP file');
  fs.writeFileSync(path.join(state.studioArtifacts, 'automatic-' + download.suggestedFilename()), artifact);
}
else if (step === 'export-finished') await state.page.getByRole('link', { name: /plate-standard\.step/ }).waitFor({ timeout: 30000 });
else if (step === 'export-stl') {
  const [download] = await Promise.all([state.page.waitForEvent('download'), button('STL mesh .stl').click()]);
  const failure = await download.failure();
  if (failure) throw new Error('Automatic STL download failed: ' + failure);
  const bytes = await state.page.evaluate(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Automatic STL download returned ' + response.status);
    return Array.from(new Uint8Array(await response.arrayBuffer()));
  }, download.url());
  const artifact = Buffer.from(bytes);
  if (artifact.length < 84 || artifact.length !== 84 + 50 * artifact.readUInt32LE(80)) throw new Error('Automatic export is not a binary STL file');
  fs.writeFileSync(path.join(state.studioArtifacts, 'automatic-' + download.suggestedFilename()), artifact);
}
else if (step === 'export-stl-finished') await state.page.getByRole('link', { name: /plate-standard\.stl/ }).waitFor({ timeout: 30000 });
else if (step === 'download-menu') await state.page.getByRole('link', { name: /plate-standard\.step/ }).waitFor();
else if (step === 'download') {
  const [download] = await Promise.all([state.page.waitForEvent('download'), state.page.getByRole('link', { name: /plate-standard\.step/ }).click()]);
  const failure = await download.failure();
  if (failure) throw new Error('Chrome download failed: ' + failure);
  // Extension-connected Chrome can complete the download without retaining the
  // relay's temporary file for saveAs. Verify the actual download above, then
  // preserve an evidence copy through this same browser session.
  const artifact = await state.page.evaluate(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Export endpoint returned ' + response.status);
    return await response.text();
  }, download.url());
  if (!artifact.startsWith('ISO-10303-21;')) throw new Error('Export is not a STEP exchange file');
  fs.writeFileSync(path.join(state.studioArtifacts, download.suggestedFilename()), artifact);
} else if (step === 'dismiss-menu') await button('Dismiss menu').click();
else if (step === 'theme') await button('Toggle light and dark theme').click();
else if (step === 'desktop-dark') await shot('desktop-dark');
else if (step === 'mobile') {
  await state.page.setViewportSize({ width: 390, height: 844 });
  await shot('mobile-panel');
} else if (step === 'close-panel') await button('Close panel').click();
else if (step === 'collapse-explorer') await button('Collapse explorer').click();
else if (step === 'mobile-fit') { await button('Fit model').click(); await shot('mobile-model'); }
else if (step === 'mobile-view') await button('View').click();
else if (step === 'mobile-top') { await button('Top').click(); await shot('mobile-top'); }
else if (step !== 'done') throw new Error('Unknown Studio check step: ' + step);

console.log('Studio check:', step, '\n' + await snapshot({ page: state.page }));
console.log('Browser logs:', await getLatestLogs({ page: state.page, sinceLastCall: true }));
state.studioCheckStep = steps[Math.min(steps.indexOf(step) + 1, steps.length - 1)];
console.log('Next:', state.studioCheckStep, 'Artifacts:', state.studioArtifacts);
