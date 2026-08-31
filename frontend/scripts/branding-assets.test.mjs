import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repositoryDir = path.resolve(frontendDir, '..');
const publicDir = path.join(frontendDir, 'public');
const staticDir = path.resolve(frontendDir, '..', 'static');

test('PWA metadata and cache names carry Goo Buddy branding', async () => {
  const manifest = JSON.parse(await readFile(path.join(publicDir, 'manifest.json'), 'utf8'));
  const serviceWorker = await readFile(path.join(publicDir, 'sw.js'), 'utf8');

  assert.equal(manifest.name, 'Goo Buddy');
  assert.equal(manifest.short_name, 'Goo Buddy');
  assert.match(manifest.description, /Self-hosted, local-first 3D printer management/);
  assert.doesNotMatch(JSON.stringify(manifest), /bambuddy/i);
  assert.match(serviceWorker, /goo-buddy-v2/);
  assert.match(serviceWorker, /goo-buddy-static-v2/);
  assert.doesNotMatch(serviceWorker, /bambuddy\.cool/i);
});

test('PWA icons use the repository-owned Goo Buddy mark', async () => {
  for (const icon of [
    'android-chrome-192x192.png',
    'android-chrome-512x512.png',
    'apple-touch-icon.png',
    'favicon.png',
    'favicon-16x16.png',
    'favicon-32x32.png',
    'goo_buddy_logo.png',
  ]) {
    await access(path.join(publicDir, 'img', icon));
  }

  for (const retiredAsset of [
    'bambuddy_logo_dark.png',
    'bambuddy_logo_dark_transparent.png',
    'bambuddy_logo_light.png',
  ]) {
    await assert.rejects(access(path.join(publicDir, 'img', retiredAsset)));
  }
});

test('authoritative production output preserves the branded PWA boundary', async () => {
  const manifest = JSON.parse(await readFile(path.join(staticDir, 'manifest.json'), 'utf8'));
  const serviceWorker = await readFile(path.join(staticDir, 'sw.js'), 'utf8');

  assert.equal(manifest.name, 'Goo Buddy');
  assert.match(serviceWorker, /goo-buddy-v2/);
  assert.doesNotMatch(serviceWorker, /bambuddy\.cool/i);
  await assert.rejects(access(path.join(staticDir, 'img', 'bambuddy_logo_dark.png')));
  await assert.rejects(access(path.join(staticDir, 'img', 'screenshot-desktop.png')));
});

test('roadmap and operator update guidance match the published Goo Buddy state', async () => {
  const [roadmap, updating] = await Promise.all([
    readFile(path.join(repositoryDir, 'docs', 'GOO_BUDDY_ROADMAP.md'), 'utf8'),
    readFile(path.join(repositoryDir, 'UPDATING.md'), 'utf8'),
  ]);

  assert.match(roadmap, /Goo Buddy branding migration and Goo Buddy Workshop UX[\s\S]{0,80}\*\*complete\*\*/);
  assert.match(roadmap, /first independently published alpha distribution \*\*complete\*\* at\s+`0\.3\.0-alpha\.5`/);
  assert.match(updating, /Goo Buddy publishes the `0\.3\.0-alpha\.6` multi-architecture OCI image/);
  assert.match(updating, /docker-compose\.release\.yml/);
  assert.doesNotMatch(updating, /does not yet publish a container image/i);
  assert.doesNotMatch(updating, /distribution is planned, not available now/i);
});
