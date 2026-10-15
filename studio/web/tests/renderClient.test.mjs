import assert from 'node:assert/strict';
import { test } from 'node:test';
import { connectRenderClient, RENDER_PROTOCOL } from '../src/renderClient.ts';

// No browser substitute: exercise polling decisions and HTTP recovery only.
// Real WebGL/MCP image transport is checked separately in Studio acceptance.
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness(t, response) {
  const requests = [], timers = [], warnings = [];
  t.mock.method(globalThis, 'fetch', async (...args) => {
    requests.push(args);
    if (response instanceof Error) throw response;
    return { ok: response === 200, status: response, json: async () => ({ request: null }) };
  });
  t.mock.method(globalThis, 'setTimeout', (callback, delay) => {
    const timer = { callback, delay }; timers.push(timer); return timer;
  });
  t.mock.method(globalThis, 'clearTimeout', () => {});
  t.mock.method(console, 'warn', message => warnings.push(message));
  return { requests, timers, warnings };
}

test('does not poll an old server without the advertised capture protocol', async t => {
  const h = harness(t, 405);
  for (const protocol of [undefined, 'unknown']) connectRenderClient('test-token', protocol)();
  await flush();
  assert.equal(h.requests.length, 0);
  assert.equal(h.timers.length, 0);
});

test('registers a compatible renderer and aborts cleanly', async t => {
  const h = harness(t, 200);
  const close = connectRenderClient('test-token', RENDER_PROTOCOL);
  await flush();
  assert.equal(h.requests[0][0], '/api/renderers/poll');
  assert.equal(h.requests[0][1].headers['X-Studio-Token'], 'test-token');
  assert.equal(h.timers[0].delay, 1000);
  close();
  assert.equal(h.requests[0][1].signal.aborted, true);
});

for (const status of [401, 403, 404, 405, 410, 426]) {
  test(`stops instead of flooding an incompatible/expired endpoint (${status})`, async t => {
    const h = harness(t, status);
    const close = connectRenderClient('test-token', RENDER_PROTOCOL);
    await flush();
    assert.equal(h.requests.length, 1);
    assert.equal(h.timers.length, 0);
    assert.equal(h.warnings.length, 1);
    assert.match(h.warnings[0], /Restart the Studio owner/);
    close();
  });
}

for (const response of [503, new TypeError('network disconnected')]) {
  test(`backs off temporary failures and recovers (${response})`, async t => {
    const h = harness(t, response);
    const close = connectRenderClient('test-token', RENDER_PROTOCOL);
    await flush();
    assert.equal(h.timers[0].delay, 2000);
    await h.timers[0].callback();
    assert.equal(h.timers[1].delay, 4000);
    t.mock.method(globalThis, 'fetch', async () => ({ok: true, json: async () => ({request:null})}));
    await h.timers[1].callback();
    assert.equal(h.timers[2].delay, 1000);
    assert.equal(h.warnings.length, 0);
    close();
  });
}
