import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { SYNTHETIC_PRINTERS, parsePreviewOptions, syntheticResponse } from './synthetic-printer-preview.mjs';

test('synthetic preview accepts only a literal loopback listener', () => {
  assert.deepEqual(parsePreviewOptions([]), { host: '127.0.0.1', port: 8017 });
  assert.throws(() => parsePreviewOptions(['--host', '0.0.0.0']), /literal loopback/);
  assert.throws(() => parsePreviewOptions(['--host', 'localhost']), /literal loopback/);
  assert.throws(() => parsePreviewOptions(['--endpoint', 'anything']), /Unsupported/);
});

test('synthetic preview refuses production mode and arbitrary input', () => {
  assert.throws(() => parsePreviewOptions([], { NODE_ENV: 'production' }), /unavailable in production/);
  assert.throws(() => parsePreviewOptions(['--mode', 'production']), /unavailable in production/);
  assert.throws(() => parsePreviewOptions(['--api-key', 'anything']), /Unsupported/);
});

test('synthetic API is a fixed GET-only state matrix without mutation routes', () => {
  assert.equal(SYNTHETIC_PRINTERS.length, 14);
  assert.equal(SYNTHETIC_PRINTERS.filter((printer) => printer.platform === 'elegoo').length, 6);
  assert.equal(SYNTHETIC_PRINTERS.filter((printer) => printer.platform === 'moonraker').length, 8);
  assert.equal(syntheticResponse('GET', '/api/v1/printers/').status, 200);
  assert.equal(syntheticResponse('POST', '/api/v1/printers/').status, 405);
  assert.equal(syntheticResponse('GET', '/api/v1/printers/moonraker/201/status').payload.phase, 'ready');
  assert.equal(syntheticResponse('GET', '/api/v1/printers/elegoo/111/status').payload.phase, 'waiting');
  assert.equal(syntheticResponse('GET', '/api/v1/printers/moonraker/211/status').payload.phase, 'connecting');
  assert.equal(syntheticResponse('GET', '/api/v1/printers/moonraker/999/status').status, 404);
});

test('the authoritative production build does not include the synthetic harness', async () => {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const staticRoot = resolve(root, '../static');
  const output = await Promise.all([
    readFile(resolve(staticRoot, 'index.html'), 'utf8'),
    ...((await readdir(resolve(staticRoot, 'assets'))).filter((name) => name.endsWith('.js')).map((name) => readFile(resolve(staticRoot, 'assets', name), 'utf8'))),
  ]);
  assert.ok(output.every((content) => !content.includes('synthetic-printer-preview')));
  assert.ok(output.every((content) => !content.includes('Synthetic printer preview')));
});
