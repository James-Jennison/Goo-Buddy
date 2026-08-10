import { describe, expect, it, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { http, HttpResponse } from 'msw';
import { PrinterWorkspacePage } from '../../pages/PrinterWorkspacePage';
import { server } from '../mocks/server';

const printer = {
  id: -1000001,
  name: 'Calculon',
  serial_number: 'READ-ONLY-MOONRAKER',
  ip_address: 'read-only-source',
  model: 'Klipper via Moonraker',
  location: null,
  nozzle_count: 1,
  is_active: true,
  auto_archive: false,
  external_camera_url: null,
  external_camera_type: null,
  external_camera_enabled: false,
  external_camera_snapshot_url: null,
  camera_rotation: 0,
  plate_detection_enabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  platform: 'moonraker',
};

const status = {
  phase: 'ready',
  freshness: 'current',
  retained: false,
  last_observation_at: '2026-01-01T00:00:00Z',
  error: null,
  state: 'idle',
  model: 'Klipper',
  firmware: null,
  temperatures: {},
  job: null,
  capabilities: ['files', 'toolhead-telemetry'],
  files: [],
  toolhead: { active_extruder: 'extruder', homed_axes: 'xyz' },
};

function renderWorkspace(printerId = -1_000_001) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/printers/${printerId}`]}>
        <Routes><Route path="/printers/:printerId" element={<PrinterWorkspacePage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PrinterWorkspacePage', () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.mocked(window.localStorage.getItem).mockImplementation((key) => storage.get(key) ?? null);
    vi.mocked(window.localStorage.setItem).mockImplementation((key, value) => { storage.set(key, value); });
    vi.mocked(window.localStorage.removeItem).mockImplementation((key) => { storage.delete(key); });
    vi.mocked(window.localStorage.clear).mockImplementation(() => { storage.clear(); });
    window.localStorage.clear();
    server.use(
      http.get('/api/v1/printers/', () => HttpResponse.json([printer])),
      http.get('/api/v1/printers/moonraker/:id/status', () => HttpResponse.json(status)),
    );
  });

  it('restores a per-printer persisted panel order', async () => {
    window.localStorage.setItem(
      'goo-buddy:moonraker-workspace:-1000001:panel-order:v1',
      JSON.stringify(['camera', 'files', 'thermals', 'toolhead', 'console']),
    );
    expect(window.localStorage.getItem('goo-buddy:moonraker-workspace:-1000001:panel-order:v1')).not.toBeNull();
    renderWorkspace();

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(5));
    expect(screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)).toEqual(expect.arrayContaining([
      expect.stringContaining('Camera'), expect.stringContaining('G-code inventory'),
    ]));
    expect(screen.getAllByRole('heading', { level: 2 })[0]).toHaveTextContent('Camera');
  });

  it('reorders panels live and persists the arrangement', async () => {
    renderWorkspace();

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(5));
    let draggedPanel = '';
    const transfer = {
      effectAllowed: '',
      dropEffect: '',
      setData: (format: string, value: string) => { if (format === 'text/plain') draggedPanel = value; },
      getData: (format: string) => format === 'text/plain' ? draggedPanel : '',
    };
    const headings = screen.getAllByRole('heading', { level: 2 });
    const cameraPanel = headings.find((heading) => heading.textContent?.includes('Camera'))?.closest('section');
    const filesPanel = headings.find((heading) => heading.textContent?.includes('G-code inventory'))?.closest('section');

    fireEvent.dragStart(cameraPanel!, { dataTransfer: transfer });
    fireEvent.dragOver(filesPanel!, { dataTransfer: transfer });
    fireEvent.drop(filesPanel!, { dataTransfer: transfer });

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })[0]).toHaveTextContent('Camera'));
    expect(JSON.parse(window.localStorage.getItem('goo-buddy:moonraker-workspace:-1000001:panel-order:v1') ?? 'null')).toEqual([
      'camera', 'files', 'thermals', 'toolhead', 'console',
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Reset layout' }));

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })[0]).toHaveTextContent('G-code inventory'));
    expect(window.localStorage.getItem('goo-buddy:moonraker-workspace:-1000001:panel-order:v1')).toBeNull();
  });

  it('gives Elegoo its own read-only workspace without inferring unsupported panels', async () => {
    server.use(
      http.get('/api/v1/printers/', () => HttpResponse.json([{ ...printer, id: -1, name: 'CC1', platform: 'elegoo' }])),
      http.get('/api/v1/printers/elegoo/:id/status', () => HttpResponse.json({
        ...status,
        capabilities: ['temperatures'],
        temperatures: { nozzle: { current_c: 30, target_c: 0 }, bed: { current_c: 29, target_c: 0 } },
      })),
    );
    renderWorkspace(-1);

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(2));
    expect(screen.getAllByRole('heading', { level: 2 })[0]).toHaveTextContent('Thermals');
    expect(screen.getAllByRole('heading', { level: 2 })[1]).toHaveTextContent('Job status');
    expect(screen.getByText('No current read-only job observation available.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Camera/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /G-code inventory/i })).not.toBeInTheDocument();
  });

  it('shows a CC1 job only when the normalized job-status capability is present', async () => {
    server.use(
      http.get('/api/v1/printers/', () => HttpResponse.json([{ ...printer, id: -1, name: 'CC1', platform: 'elegoo' }])),
      http.get('/api/v1/printers/elegoo/:id/status', () => HttpResponse.json({
        ...status,
        capabilities: ['temperatures', 'job-status'],
        job: { state: 'printing', progress_percent: 32, current_layer: 8, total_layers: 25 },
      })),
    );
    renderWorkspace(-1);

    await waitFor(() => expect(screen.getAllByText('32%')).toHaveLength(2));
    expect(screen.getByText('8 / 25')).toBeInTheDocument();
    expect(screen.queryByText('No current read-only job observation available.')).not.toBeInTheDocument();
  });

  it('labels CC1 idle counters as stale and shows telemetry without controls', async () => {
    server.use(
      http.get('/api/v1/printers/', () => HttpResponse.json([{ ...printer, id: -1, name: 'CC1', platform: 'elegoo' }])),
      http.get('/api/v1/printers/elegoo/:id/status', () => HttpResponse.json({
        ...status,
        state: 'idle',
        capabilities: ['temperatures'],
        temperatures: { nozzle: { current_c: 30, target_c: 0 }, bed: { current_c: 29, target_c: 0 } },
        stale_job: { state: 'idle', progress_percent: 97.65625, current_layer: 126, total_layers: 128, elapsed_seconds: null, estimated_remaining_seconds: null },
        environment: {
          fan: { availability: 'observed', speed_percent: 42 },
          chamber_light: { availability: 'observed', is_on: true },
        },
      })),
    );
    renderWorkspace(-1);

    await waitFor(() => expect(screen.getByText('Stale retained data — not a live print')).toBeInTheDocument());
    expect(screen.getByText('Previous progress')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Print progress 98 percent/i)).not.toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText('On')).toBeInTheDocument();
    expect(screen.getByText('Unsupported')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pause|resume|cancel/i })).not.toBeInTheDocument();
  });
});
