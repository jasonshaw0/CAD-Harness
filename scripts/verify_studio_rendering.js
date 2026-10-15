// Driven only by Playwriter, in a fresh --browser headless session.
// The Python runner creates browser-config.json in this invocation's cwd.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('assert').strict;
const hash = value => require('node:crypto').createHash('sha256').update(value).digest('hex');
state.renderQa ||= JSON.parse(fs.readFileSync('browser-config.json', 'utf8'));
state.renderStep ||= 0;
const q = state.renderQa;
const canvas = page => page.getByTestId('cad-canvas');
const steps = ['open', 'alter', 'baseline', 'check', 'webgl', 'check', 'close'];
const step = steps[state.renderStep];
if (step === 'open') {
  state.page = await context.newPage();
  await state.page.setViewportSize({width: 1440, height: 960});
  await state.page.goto(q.url);
  await state.page.getByRole('button', {name: 'mug', exact: true}).waitFor();
  state.otherPage = await context.newPage();
  await state.otherPage.goto(q.url);
  await state.otherPage.getByRole('button', {name: 'mug', exact: true}).waitFor();
} else if (step === 'alter') {
  await state.page.getByRole('button', {name: 'mug', exact: true}).click();
  await state.page.getByRole('button', {name: 'Hide saucer', exact: true}).click();
  await state.page.getByRole('button', {name: 'Toggle light and dark theme', exact: true}).click();
  await state.page.getByRole('button', {name: 'View from Y axis', exact: true}).click();
  await state.otherPage.getByRole('button', {name: 'View from Z axis', exact: true}).click();
} else if (step === 'baseline') {
  // Remove Playwriter's ghost pointer and UI hover before comparing pixels.
  for (const page of [state.page, state.otherPage]) {
    await page.mouse.move(800, 50); await ghostCursor.hide({page});
    assert.equal(await page.evaluate(() => performance.getEntriesByType('resource').some(
      entry => /renderView-.*\.js/.test(entry.name))), false, 'Capture code loaded without a request');
    await page.evaluate(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      window.__qaCaptureContexts = [];
      HTMLCanvasElement.prototype.getContext = function(...args) {
        const result = original.apply(this, args);
        if (!this.isConnected && /^webgl/.test(args[0]) && result) window.__qaCaptureContexts.push(result);
        return result;
      };
    });
  }
  state.beforePixels = hash(await canvas(state.page).screenshot({path: path.join(q.artifacts, 'primary-before.png'), scale: 'css'}));
  state.otherPixels = hash(await canvas(state.otherPage).screenshot({path: path.join(q.artifacts, 'secondary-before.png'), scale: 'css'}));
  state.beforeText = await state.page.locator('main').innerText();
  state.beforeClass = await state.page.locator('html').getAttribute('class');
} else if (step === 'check') {
  const primary = hash(await canvas(state.page).screenshot({path: path.join(q.artifacts, 'primary-after.png'), scale: 'css'}));
  const secondary = hash(await canvas(state.otherPage).screenshot({path: path.join(q.artifacts, 'secondary-after.png'), scale: 'css'}));
  assert.equal(primary, state.beforePixels, 'Capture changed the primary viewport');
  assert.equal(secondary, state.otherPixels, 'Capture changed the second viewport');
  assert.equal(await state.page.locator('main').innerText(), state.beforeText, 'Capture changed selection or visible UI');
  assert.equal(await state.page.locator('html').getAttribute('class'), state.beforeClass, 'Capture changed theme');
  await state.page.screenshot({path: path.join(q.artifacts, 'viewport-after.png'), scale: 'css'});
  for (const page of [state.page, state.otherPage]) {
    const logs = await getLatestLogs({page, search: /pageerror|uncaught (TypeError|ReferenceError)|Failed to load resource/i, count: 20});
    assert.equal(logs.length, 0, JSON.stringify(logs));
  }
} else if (step === 'webgl') {
  for (const page of [state.page, state.otherPage]) await page.evaluate(() => {
    for (const context of window.__qaCaptureContexts) context.getExtension('WEBGL_lose_context').loseContext();
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(...args) {
      if (!this.isConnected && /^webgl/.test(args[0])) throw new Error('QA WebGL unavailable');
      return original.apply(this, args);
    };
  });
} else if (step === 'close') {
  await state.otherPage.close(); await state.page.close();
} else throw new Error('Unknown rendering QA step');
state.renderStep++;
console.log('CAPTURE_QA_STAGE ' + step);
