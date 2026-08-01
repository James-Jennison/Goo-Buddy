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
const BAMBU_ID = 1;

const SYNTHETIC_BAMBU_STATUS = Object.freeze({
  id: BAMBU_ID, name: 'Synthetic Bambu — printing', connected: true, state: 'RUNNING',
  current_print: 'Synthetic workshop job', subtask_name: null, current_archive_id: null, current_plate_id: null,
  gcode_file: null, progress: 36, remaining_time: null, layer_num: 72, total_layers: 200,
  temperatures: { nozzle: 212, nozzle_target: 215, bed: 56, bed_target: 60, chamber: 31, chamber_target: 33 },
  cover_url: null, hms_errors: [], ams: [], ams_exists: false, vt_tray: [], store_to_sdcard: false,
  timelapse: false, ipcam: false, wifi_signal: null, wired_network: true, door_open: false,
  nozzles: [], nozzle_rack: [], print_options: null, stg_cur: -1, stg_cur_name: null, stg: [],
  airduct_mode: 0, speed_level: 2, chamber_light: false, active_extruder: 0, ams_mapping: [],
  ams_extruder_map: {}, fila_switch: null, tray_now: 255, expected_tray: null, previous_tray: null,
  ams_status_main: 0, ams_status_sub: 0, mc_print_sub_stage: 0, last_ams_update: 0,
  printable_objects_count: 0, cooling_fan_speed: null, big_fan1_speed: null, big_fan2_speed: null,
  heatbreak_fan_speed: null, firmware_version: 'synthetic-bambu', developer_mode: null,
  ams_filament_backup: null, awaiting_plate_clear: false, supports_drying: false,
});

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
  source(BAMBU_ID, 'Synthetic Bambu — printing', 'bambu', true, { model: 'X1 Carbon', serial_number: 'SYNTHETIC-BAMBU', ip_address: null }),
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

/**
 * Fixed, non-secret defaults for the normal Settings page.  This is deliberately
 * separate from UI_PREFERENCES: the production endpoint returns the complete
 * application-settings schema, whereas /ui-preferences is a small user-preference
 * payload.  Keeping both fixed here prevents the preview from accepting data.
 */
const SYNTHETIC_SETTINGS = Object.freeze({
  auto_archive: true, save_thumbnails: true, capture_finish_photo: true,
  default_filament_cost: 25, currency: 'USD', energy_cost_per_kwh: 0.15, energy_tracking_mode: 'total',
  spoolman_enabled: false, spoolman_url: '', spoolman_sync_mode: 'auto', spoolman_disable_weight_sync: false,
  spoolman_report_partial_usage: true, auto_add_unknown_rfid: true, disable_filament_warnings: false,
  prefer_lowest_filament: false, check_updates: true, check_printer_firmware: true, include_beta_updates: false,
  language: 'en', notification_language: 'en', bed_cooled_threshold: 35,
  ams_humidity_good: 40, ams_humidity_fair: 60, ams_temp_good: 28, ams_temp_fair: 35,
  ams_history_retention_days: 30, printer_sensor_history_retention_days: 30,
  queue_drying_enabled: false, queue_drying_block: false, ambient_drying_enabled: false, print_drying_enabled: false,
  drying_presets: '', ams_humidity_thresholds: '', gcode_snippets: '',
  local_backup_enabled: false, local_backup_schedule: 'daily', local_backup_time: '03:00',
  local_backup_retention: 5, local_backup_path: '', per_printer_mapping_expanded: false,
  date_format: 'system', time_format: 'system', default_printer_id: null, pipeline_max_copies: 50,
  virtual_printer_enabled: false, virtual_printer_access_code: '', virtual_printer_mode: 'archive',
  virtual_printer_archive_name_source: 'metadata', dark_style: 'vibrant', dark_background: 'cool', dark_accent: 'green',
  light_style: 'classic', light_background: 'neutral', light_accent: 'green',
  ftp_retry_enabled: true, ftp_retry_count: 3, ftp_retry_delay: 2, ftp_timeout: 30,
  mqtt_enabled: false, mqtt_broker: '', mqtt_port: 1883, mqtt_username: '', mqtt_password: '',
  mqtt_topic_prefix: 'goo-buddy', mqtt_use_tls: false, external_url: '',
  ha_enabled: false, ha_url: '', ha_token: '', ha_url_from_env: false, ha_token_from_env: false, ha_env_managed: false,
  library_archive_mode: 'ask', library_disk_warning_gb: 5, camera_view_mode: 'window',
  preferred_slicer: 'bambu_studio', open_in_slicer: null, use_slicer_api: false,
  orcaslicer_api_url: '', bambu_studio_api_url: '', prometheus_enabled: false, prometheus_token: '',
  low_stock_threshold: 20, session_max_hours: 24, user_notifications_enabled: true,
  default_bed_levelling: 'auto', default_flow_cali: 'auto', default_vibration_cali: true,
  default_layer_inspect: false, default_timelapse: false, default_nozzle_offset_cali: 'auto',
  stagger_group_size: 2, stagger_interval_minutes: 5, require_plate_clear: false,
  queue_shortest_first: false, queue_max_concurrent_uploads: 4,
  preheat_enabled: false, preheat_filament_targets: '', preheat_max_wait_seconds: 900, preheat_soak_seconds: 300,
  nozzle_temp_presets: '', bed_temp_presets: '', chamber_temp_presets: '', fan_speed_presets: '',
  local_login_enabled: true, ldap_enabled: false, ldap_server_url: '', ldap_bind_dn: '', ldap_bind_password: '',
  ldap_search_base: '', ldap_user_filter: '(sAMAccountName={username})', ldap_security: 'starttls',
  ldap_group_mapping: '', ldap_auto_provision: false, ldap_default_group: '',
  obico_enabled: false, obico_ml_url: '', obico_sensitivity: 'medium', obico_action: 'notify',
  obico_poll_interval: 10, obico_enabled_printers: '', forecast_global_lead_time_days: 0, default_sidebar_order: '',
});

function response(status, payload) {
  return { status, payload };
}

/** Pure, fixed response map. It accepts only GET paths used by the normal UI. */
export function syntheticResponse(method, path) {
  if (method !== 'GET') return response(405, { detail: 'Synthetic preview is read-only' });
  if (path === '/api/v1/auth/status') return response(200, { auth_enabled: false, requires_setup: false });
  if (path === '/api/v1/printers/') return response(200, SYNTHETIC_PRINTERS);
  if (path === `/api/v1/printers/${BAMBU_ID}/status`) return response(200, SYNTHETIC_BAMBU_STATUS);
  if (path === '/api/v1/settings/') return response(200, SYNTHETIC_SETTINGS);
  if (path === '/api/v1/settings/ui-preferences') return response(200, UI_PREFERENCES);
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
