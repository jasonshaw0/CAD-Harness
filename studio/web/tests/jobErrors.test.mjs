import assert from 'node:assert/strict';
import { test } from 'node:test';
import { jobErrorMessage } from '../src/jobErrors.ts';

test('explains how to recover from evaluator changes returned by the worker', () => {
  const error = JSON.stringify({ error: 'ValueError', message: 'workflow evaluator changed; evaluate a new revision' });
  assert.equal(jobErrorMessage(error), 'workflow evaluator changed; evaluate a new revision. Rebuild current source to create fresh evidence, then export again.');
});

test('offers the same recovery for stale source evidence', () => {
  assert.match(jobErrorMessage('source or brief changed; saved evidence is stale'), /Rebuild current source/);
});

test('retains plain-text diagnostics and unwraps other structured worker failures', () => {
  assert.equal(jobErrorMessage('  export worker failed: kernel error\n'), 'export worker failed: kernel error');
  assert.equal(jobErrorMessage('{"error":"RuntimeError","message":"disk full"}'), 'disk full');
});
