#!/usr/bin/env node
/**
 * Development-only, loopback-only synthetic printer-card preview.
 *
 * This does not import the Goo Buddy backend, read its data, proxy requests,
 * or accept printer configuration.  It serves the normal frontend with a
 * fixed local response map solely for visual review.  It is deliberately not
 * referenced by production startup, Docker, or Compose configuration.
 */
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1']);
const DEFAULT_HOST = '127.0.0.1';
const DEFAULT_PORT = 8017;

function timestamp() {
  return '2030-01-02T03:04:05Z';
}

function source(id, name, platform, isActive, extras = {}) {
  return {
    id,
    name,
    platform,
    is_active: isActive,
    enabled: isActive,
    model: null,
    firmware: null,
    serial_number: 'SYNTHETIC-READ-ONLY',
    ip_address: 'Synthetic preview only',
    location: null,
    nozzle_count: 1,
    auto_archive: false,
    external_camera_enabled: false,
    created_at: timestamp(),
    updated_at: timestamp(),
    ...extras,
  };
}

const ELEGGO_ID = 101;
const MOONRAKER_ID = 201;
const MOONRAKER_PUBLIC_OFFSET = 1_000_000;

const READY_ELEGOO = {
  phase: 'ready', freshness: 'current', retained: false, last_observation_at: timestamp(), error: null,
  state: 'printing', model: 'Synthetic Centauri', firmware: 'synthetic-v3',
  temperatures: {
    nozzle: { current_c: 208, target_c: 210 }, bed: { current_c: 59, target_c: 60 }, chamber: { current_c: 33, target_c: 35 },
  },
  job: { name: null, state: 'printing', progress_percent: 42, current_layer: 84, total_layers: 200 },
  capabilities: ['status', 'temperatures', 'job'],
};

const READY_MOONRAKER = {
  phase: 'ready', freshness: 'current', retained: false, last_observation_at: timestamp(), error: null,
  state: 'printing', model: 'Synthetic Klipper', firmware: 'synthetic-moonraker',
  temperatures: {
    nozzle: { current_c: 214, target_c: 215 }, bed: { current_c: 64, target_c: 65 }, chamber: { current_c: 31, target_c: null },
  },
  job: { name: 'Synthetic print', state: 'printing', progress_percent: 57, current_layer: 114, total_layers: 200, elapsed_seconds: 5400, estimated_remaining_seconds: 4200 },
  capabilities: ['status', 'temperatures', 'job'],
};

function retainedStatus(phase, base) {
  return { ...base, phase, freshness: 'retained', retained: true, error: phase === 'stale' ? 'no_validated_inbound' : 'connection_closed' };
}

const ELEGGO_STATUSES = new Map([
  [ELEGGO_ID, READY_ELEGOO],
  [ELEGGO_ID + 1, retainedStatus('stale', READY_ELEGOO)],
  [ELEGGO_ID + 2, retainedStatus('disconnected', READY_ELEGOO)],
  [ELEGGO_ID + 3, { phase: 'invalid', freshness: 'unavailable', retained: false, last_observation_at: null, error: 'invalid_configuration', state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
  [ELEGGO_ID + 4, { phase: 'disabled', freshness: 'unavailable', retained: false, last_observation_at: null, error: null, state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
  [ELEGGO_ID + 10, { phase: 'waiting', freshness: 'unavailable', retained: false, last_observation_at: null, error: null, state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
]);

const MOONRAKER_STATUSES = new Map([
  [MOONRAKER_ID, READY_MOONRAKER],
  [MOONRAKER_ID + 1, { ...READY_MOONRAKER, state: 'idle', job: null }],
  [MOONRAKER_ID + 2, retainedStatus('stale', READY_MOONRAKER)],
  [MOONRAKER_ID + 3, retainedStatus('disconnected', READY_MOONRAKER)],
  [MOONRAKER_ID + 4, { phase: 'unauthorized', freshness: 'unavailable', retained: false, last_observation_at: null, error: 'unauthorized', state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
  [MOONRAKER_ID + 5, { phase: 'invalid', freshness: 'unavailable', retained: false, last_observation_at: null, error: 'invalid_configuration', state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
  [MOONRAKER_ID + 6, { phase: 'disabled', freshness: 'unavailable', retained: false, last_observation_at: null, error: null, state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
  [MOONRAKER_ID + 10, { phase: 'connecting', freshness: 'unavailable', retained: false, last_observation_at: null, error: null, state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [] }],
]);

export const SYNTHETIC_PRINTERS = Object.freeze([
  source(-ELEGGO_ID, 'Synthetic Elegoo — ready', 'elegoo', true),
  source(-(ELEGGO_ID + 1), 'Synthetic Elegoo — stale', 'elegoo', true),
  source(-(ELEGGO_ID + 2), 'Synthetic Elegoo — disconnected', 'elegoo', true),
  source(-(ELEGGO_ID + 3), 'Synthetic Elegoo — invalid', 'elegoo', true),
  source(-(ELEGGO_ID + 4), 'Synthetic Elegoo — disabled', 'elegoo', false),
  source(-(ELEGGO_ID + 10), 'Synthetic Elegoo — waiting', 'elegoo', true),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID, 'Synthetic Moonraker — printing', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 1, 'Synthetic Moonraker — idle', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 2, 'Synthetic Moonraker — stale', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 3, 'Synthetic Moonraker — disconnected', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 4, 'Synthetic Moonraker — unauthorized', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: true }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 5, 'Synthetic Moonraker — invalid', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 6, 'Synthetic Moonraker — disabled', 'moonraker', false, { port: 7125, scheme: 'http', api_key_configured: false }),
  source(-MOONRAKER_PUBLIC_OFFSET - MOONRAKER_ID - 10, 'Synthetic Moonraker — connecting', 'moonraker', true, { port: 7125, scheme: 'http', api_key_configured: false }),
]);

const UI_PREFERENCES = {
  nozzle_temp_presets: null, bed_temp_presets: null, chamber_temp_presets: null, fan_speed_presets: null,
  drying_presets: null, camera_view_mode: 'window', printer_sort: 'name', printer_sort_ascending: true,
};

function response(status, payload) {
  return { status, payload };
}

/** Pure, fixed response map. It accepts only GET paths used by the normal UI. */
export function syntheticResponse(method, path) {
  if (method !== 'GET') return response(405, { detail: 'Synthetic preview is read-only' });
  if (path === '/api/v1/auth/status') return response(200, { auth_enabled: false, requires_setup: false });
  if (path === '/api/v1/printers/') return response(200, SYNTHETIC_PRINTERS);
  if (path === '/api/v1/settings/' || path === '/api/v1/settings/ui-preferences') return response(200, UI_PREFERENCES);
  if (path === '/api/v1/inventory/colors') return response(200, []);
  const elegoo = path.match(/^\/api\/v1\/printers\/elegoo\/(\d+)\/status$/);
  if (elegoo && ELEGGO_STATUSES.has(Number(elegoo[1]))) return response(200, ELEGGO_STATUSES.get(Number(elegoo[1])));
  const moonraker = path.match(/^\/api\/v1\/printers\/moonraker\/(\d+)\/status$/);
  if (moonraker && MOONRAKER_STATUSES.has(Number(moonraker[1]))) return response(200, MOONRAKER_STATUSES.get(Number(moonraker[1])));
  return response(404, { detail: 'Synthetic preview route not found' });
}

export function parsePreviewOptions(args, environment = process.env) {
  if (environment.NODE_ENV === 'production') throw new Error('Synthetic preview is unavailable in production mode');
  let host = DEFAULT_HOST;
  let port = DEFAULT_PORT;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--host') host = args[++index] ?? '';
    else if (arg === '--port') port = Number(args[++index]);
    else if (arg === '--mode' && args[++index] === 'production') throw new Error('Synthetic preview is unavailable in production mode');
    else throw new Error(`Unsupported synthetic-preview option: ${arg}`);
  }
  if (!LOOPBACK_HOSTS.has(host)) throw new Error('Synthetic preview requires a literal loopback host');
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Synthetic preview requires a local unprivileged port');
  return { host, port };
}

export async function startSyntheticPreview(options = parsePreviewOptions(process.argv.slice(2))) {
  const currentFile = fileURLToPath(import.meta.url);
  const frontendRoot = resolve(dirname(currentFile), '..');
  const server = await createServer({
    root: frontendRoot,
    configFile: false,
    appType: 'spa',
    server: { host: options.host, port: options.port, strictPort: true },
    plugins: [{
      name: 'synthetic-printer-preview-api',
      configureServer(vite) {
        vite.middlewares.use((req, res, next) => {
          const path = (req.url ?? '/').split('?', 1)[0];
          if (!path.startsWith('/api/v1/')) return next();
          const result = syntheticResponse(req.method ?? 'GET', path);
          res.writeHead(result.status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
          res.end(JSON.stringify(result.payload));
        });
      },
    }],
  });
  await server.listen();
  const url = `http://${options.host === '::1' ? '[::1]' : options.host}:${options.port}`;
  console.log(`Synthetic printer preview: ${url}`);
  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  startSyntheticPreview().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
