import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { render, screen, waitFor } from '@testing-library/react';
import type { Printer } from '../../api/client';
import { ElegooPrinterCard, MoonrakerPrinterCard } from '../../pages/PrintersPage';
import { AuthProvider } from '../../contexts/AuthContext';
import { server } from '../mocks/server';

function readOnlyPrinter(overrides: Partial<Printer>): Printer {
  return {
    id: -101,
    name: 'Synthetic printer',
    serial_number: 'SYNTHETIC-READ-ONLY',
    ip_address: 'Synthetic preview only',
    model: null,
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
    created_at: '2030-01-02T03:04:05Z',
    updated_at: '2030-01-02T03:04:05Z',
    ...overrides,
  };
}

function renderCard(card: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<AuthProvider><QueryClientProvider client={queryClient}>{card}</QueryClientProvider></AuthProvider>);
}

describe('read-only printer cards', () => {
  it('renders a retained Elegoo snapshot distinctly and includes a supported chamber reading', async () => {
    server.use(http.get('/api/v1/printers/elegoo/101/status', () => HttpResponse.json({
      phase: 'stale', freshness: 'retained', retained: true, last_observation_at: '2030-01-02T03:04:05Z', error: 'no_validated_inbound',
      state: 'printing', model: 'Synthetic Centauri', firmware: 'synthetic-v3',
      temperatures: { nozzle: { current_c: 208, target_c: 210 }, bed: { current_c: 59, target_c: 60 }, chamber: { current_c: 33, target_c: 35 } },
      job: { state: 'printing', progress_percent: 42, current_layer: 84, total_layers: 200 }, capabilities: [],
    })));

    renderCard(<ElegooPrinterCard printer={readOnlyPrinter({ platform: 'elegoo' })} />);
    await waitFor(() => expect(screen.getByText(/retained data — not current/i)).toBeInTheDocument());
    expect(screen.getByText(/Chamber 33°C/i)).toBeInTheDocument();
    expect(screen.getByText(/camera, files, console, and maintenance remain unavailable/i)).toBeInTheDocument();
  });

  it('explains Moonraker authorization without exposing configuration and disables controls', async () => {
    const publicId = -1_000_201;
    server.use(http.get('/api/v1/printers/moonraker/201/status', () => HttpResponse.json({
      phase: 'unauthorized', freshness: 'unavailable', retained: false, last_observation_at: null, error: 'unauthorized',
      state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [],
    })));

    renderCard(<MoonrakerPrinterCard printer={readOnlyPrinter({ id: publicId, platform: 'moonraker', api_key_configured: true })} />);
    await waitFor(() => expect(screen.getByText(/Moonraker authentication needs attention/i)).toBeInTheDocument());
    expect(screen.getByText(/never displays the key/i)).toBeInTheDocument();
    expect(screen.getByText(/camera, files, console, maintenance, and upload remain unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/Wait for a fresh, ready printer observation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Synthetic preview only/i)).not.toBeInTheDocument();
  });

  it('does not present an invalid source as waiting for an observation', async () => {
    server.use(http.get('/api/v1/printers/elegoo/101/status', () => HttpResponse.json({
      phase: 'invalid', freshness: 'unavailable', retained: false, last_observation_at: null, error: 'invalid_configuration',
      state: null, model: null, firmware: null, temperatures: null, job: null, capabilities: [],
    })));

    renderCard(<ElegooPrinterCard printer={readOnlyPrinter({ platform: 'elegoo' })} />);
    await waitFor(() => expect(screen.getByText(/invalid configuration/i)).toBeInTheDocument());
    expect(screen.queryByText(/Waiting for a printer-pushed/i)).not.toBeInTheDocument();
  });
});
