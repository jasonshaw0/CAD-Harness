import assert from 'node:assert/strict';
import { test } from 'node:test';
import { unzipSync } from 'fflate';
import { prepareExportDownload } from '../src/exportDownload.ts';

for (const format of ['step', 'stl']) {
  test(`${format}: one part keeps its filename and exact binary bytes`, async t => {
    const bytes = new Uint8Array([0, 255, 13, 10, 128, 42]);
    const path = `project/exports/${format}/part.${format}`;
    t.mock.method(globalThis, 'fetch', async url => {
      assert.equal(url, `/files/${path}`);
      return new Response(bytes);
    });
    const output = await prepareExportDownload([path], format, 'unused.zip', file => `/files/${file}`);
    assert.equal(output.filename, `part.${format}`);
    assert.deepEqual(new Uint8Array(await output.blob.arrayBuffer()), bytes);
  });

  test(`${format}: multiple parts form one ZIP with only the requested format`, async t => {
    const parts = { [`base.${format}`]: new Uint8Array([0, 255, 6]), [`lid.${format}`]: new Uint8Array([128, 1, 0, 10]) };
    const files = Object.keys(parts).map(name => `project/exports/${format}/${name}`);
    files.push('project/exports/step.json', 'project/evidence/scene.json',
      format === 'step' ? 'project/exports/stl/other.stl' : 'project/exports/step/other.step');
    t.mock.method(globalThis, 'fetch', async url => {
      const filename = url.split('/').pop();
      assert.ok(parts[filename], `unexpected export download: ${url}`);
      return new Response(parts[filename]);
    });
    const output = await prepareExportDownload(files, format, 'assembly.zip', file => `/files/${file}`);
    assert.equal(output.filename, 'assembly.zip');
    assert.equal(output.blob.type, 'application/zip');
    const archive = unzipSync(new Uint8Array(await output.blob.arrayBuffer()));
    assert.deepEqual(Object.keys(archive).sort(), Object.keys(parts).sort());
    for (const [name, bytes] of Object.entries(parts)) assert.deepEqual(archive[name], bytes);
  });
}

test('failed file transfers reject instead of delivering a partial archive', async t => {
  t.mock.method(globalThis, 'fetch', async url => new Response('unavailable', { status: url.endsWith('bad.stl') ? 503 : 200 }));
  await assert.rejects(prepareExportDownload(['project/exports/stl/good.stl', 'project/exports/stl/bad.stl'],
    'stl', 'assembly.zip', file => file), /Could not download bad.stl \(HTTP 503\)/);
});

test('missing or empty export files fail visibly', async t => {
  await assert.rejects(prepareExportDownload([], 'step', 'assembly.zip', file => file), /without any STEP files/);
  t.mock.method(globalThis, 'fetch', async () => new Response(new Uint8Array()));
  await assert.rejects(prepareExportDownload(['project/exports/stl/part.stl'], 'stl', 'assembly.zip', file => file), /is empty/);
});
