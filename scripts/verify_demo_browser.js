// Execute only through Playwriter, one action and observation per invocation.
const fs = require('node:fs');
const path = require('node:path');
const config = JSON.parse(fs.readFileSync('browser-config.json', 'utf8'));
const steps = ['open', 'ready', 'checks', 'count', 'failed-export', 'failed-export-disabled',
  'dismiss', 'guide', 'repair', 'repaired', 'compare', 'overlay', 'overlay-off', 'guide-source', 'source',
  'source-ready', 'python', 'python-ready', 'close', 'plate', 'isolate', 'close-isolated',
  'view', 'top', 'authorize', 'guide-export', 'export', 'step', 'stl', 'dismiss-downloads', 'close-export-guide',
  'mobile', 'mobile-guide', 'mobile-guide-ready', 'mobile-close', 'mobile-collapse',
  'mobile-model', 'done'];
const step = state.demoStep || 'open';
const button = name => state.page.getByRole('button', { name, exact: typeof name === 'string' });
const shot = async name => {
  console.log(await snapshot({ page: state.page }));
  await state.page.screenshot({ path: path.join(config.artifacts, name + '.png'), scale: 'css', animations: 'disabled' });
};

if (step === 'open') {
  state.page = await context.newPage();
  await state.page.setViewportSize({ width: 1440, height: 960 });
  await state.page.goto(config.url, { waitUntil: 'domcontentloaded' });
} else if (step === 'ready') {
  await state.page.getByRole('heading', { name: 'Inspect a failure and its repair' }).waitFor();
  await button('Open engineering checks').filter({ hasText: '29 / 37' }).waitFor();
  await shot('desktop-failure');
} else if (step === 'checks') await button('Open measured checks').click();
else if (step === 'count') {
  await state.page.getByText('holes count', { exact: true }).click();
  await state.page.getByText('holes.count · Required', { exact: true }).waitFor();
  await shot('failed-hole-count');
} else if (step === 'failed-export') await button('Export design').click();
else if (step === 'failed-export-disabled') {
  if (!await button('STEP geometry .step').isDisabled() || !await button('STL mesh .stl').isDisabled()) throw new Error('Historical failed revision offered geometry export');
} else if (step === 'dismiss') await button('Dismiss menu').click();
else if (['guide', 'guide-source', 'guide-export', 'mobile-guide'].includes(step)) {
  await button('Demo walkthrough').click();
  if (step === 'mobile-guide') await shot('mobile-walkthrough-top');
}
else if (step === 'repair') await button(/2 Inspect the repaired plate/).click();
else if (step === 'repaired') {
  await button('Open engineering checks').filter({ hasText: '37 / 37' }).waitFor();
  await shot('desktop-repaired');
} else if (step === 'compare') await button('Compare the revisions').click();
else if (step === 'overlay') {
  await state.page.getByRole('switch', { name: /^Previous geometry overlay/ }).click();
  await shot('comparison-overlay');
} else if (step === 'overlay-off') {
  await state.page.getByRole('switch', { name: /^Previous geometry overlay/ }).click();
} else if (step === 'source') await button('Inspect editable source').click();
else if (step === 'source-ready') {
  await state.page.getByLabel('Source code').filter({ hasText: 'default_variant = "standard"' }).waitFor();
  await shot('source-manifest');
} else if (step === 'python') await state.page.getByLabel('Source file', { exact: true }).selectOption('project/project.py');
else if (step === 'python-ready') {
  await state.page.getByLabel('Source code').filter({ hasText: 'class PlateParameters' }).waitFor();
  await shot('editable-python');
} else if (['close', 'close-isolated', 'close-export-guide', 'mobile-close'].includes(step)) await button('Close panel').click();
else if (step === 'plate') await button('plate').click();
else if (step === 'isolate') await button('Isolate part').click();
else if (step === 'view') await button('View').click();
else if (step === 'top') { await button('Top').click(); await shot('four-holes-top'); }
else if (step === 'authorize') await button('Enable session').click();
else if (step === 'export') await button('Export repaired part…').click();
else if (step === 'step' || step === 'stl') {
  const format = step;
  const [download] = await Promise.all([state.page.waitForEvent('download', { timeout: 30000 }),
    button(format === 'step' ? 'STEP geometry .step' : 'STL mesh .stl').click()]);
  if (await download.failure()) throw new Error('Geometry download failed');
  const bytes = await state.page.evaluate(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Export download returned ' + response.status);
    return Array.from(new Uint8Array(await response.arrayBuffer()));
  }, download.url());
  const buffer = Buffer.from(bytes);
  if (format === 'step' ? !buffer.toString('utf8').startsWith('ISO-10303-21;')
    : buffer.length < 84 || buffer.length !== 84 + 50 * buffer.readUInt32LE(80)) throw new Error('Invalid ' + format + ' artifact');
  fs.writeFileSync(path.join(config.artifacts, download.suggestedFilename()), buffer);
} else if (step === 'dismiss-downloads') await button('Dismiss menu').click();
else if (step === 'mobile') await state.page.setViewportSize({ width: 390, height: 844 });
else if (step === 'mobile-guide-ready') {
  await button('Export repaired part…').scrollIntoViewIfNeeded();
  await shot('mobile-walkthrough');
} else if (step === 'mobile-collapse') await button('Collapse explorer').click();
else if (step === 'mobile-model') { await button('Fit model').click(); await shot('mobile-model'); }
else if (step !== 'done') throw new Error('Unknown demo step: ' + step);

const observed = await snapshot({ page: state.page });
const logs = await getLatestLogs({ page: state.page, sinceLastCall: true });
console.log('Step:', step, 'URL:', state.page.url(), '\n' + observed);
console.log('Browser logs:', logs);
fs.writeFileSync(path.join(config.artifacts, 'browser-' + step + '.txt'), observed + '\n' + JSON.stringify(logs));
if (logs.some(log => /\[error\]|pageerror|uncaught/i.test(typeof log === 'string' ? log : JSON.stringify(log)))) throw new Error('Browser error: ' + JSON.stringify(logs));
state.demoStep = steps[Math.min(steps.indexOf(step) + 1, steps.length - 1)];
console.log('Next:', state.demoStep);
