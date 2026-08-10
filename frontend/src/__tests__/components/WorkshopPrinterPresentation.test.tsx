import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { WorkshopReadOnlyPresentation } from '../../components/WorkshopPrinterPresentation';
import { workshopPlatformMeta } from '../../components/workshopPresentationMeta';

describe('Workshop printer presentation', () => {
  it('derives driver labels solely from the saved platform', () => {
    expect(workshopPlatformMeta('elegoo').label).toBe('Elegoo SDCP v3');
    expect(workshopPlatformMeta('moonraker').label).toBe('Klipper via Moonraker');
    expect(workshopPlatformMeta('bambu').label).toBe('Bambu Lab');
  });

  it('does not infer a Moonraker label from an Elegoo model name', () => {
    render(<WorkshopReadOnlyPresentation platform="elegoo" snapshot={{ phase: 'ready', freshness: 'current', model: 'Klipper' }} />);

    expect(screen.getByText('Elegoo SDCP v3')).toBeInTheDocument();
    expect(screen.queryByText('Klipper via Moonraker')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Ready')).toBeInTheDocument();
  });

  it('labels retained observations as not current and keeps unsupported capabilities unavailable', () => {
    render(<WorkshopReadOnlyPresentation platform="elegoo" snapshot={{ phase: 'stale', retained: true, model: 'Synthetic Centauri', temperatures: { nozzle: { current_c: 200, target_c: 210 } } }} />);
    expect(screen.getByText(/Retained data — not current/i)).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent(/Camera, files, console, maintenance, uploads, CANVAS are unavailable/i);
    expect(screen.getByLabelText(/Stale; retained data, not current/i)).toBeInTheDocument();
  });

  it('keeps current progress and layer data distinct from a disabled unavailable source', () => {
    const { rerender } = render(<WorkshopReadOnlyPresentation platform="moonraker" snapshot={{
      phase: 'ready',
      freshness: 'current',
      job: { progress_percent: 37.4, current_layer: 12, total_layers: 40 },
    }} />);

    expect(screen.getByLabelText('Print progress 37 percent')).toBeInTheDocument();
    expect(screen.getByText('Layer 12 / 40')).toBeInTheDocument();
    expect(screen.queryByText(/Retained data — not current/i)).not.toBeInTheDocument();

    rerender(<WorkshopReadOnlyPresentation platform="moonraker" snapshot={{ phase: 'disabled', freshness: 'unavailable' }} />);
    expect(screen.getByLabelText('Disabled')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Print progress/i)).not.toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent(/Camera, files, console, maintenance, uploads, CANVAS are unavailable/i);
  });

  it('shows a proxied camera preview only when the source has the camera capability', () => {
    const { rerender } = render(<WorkshopReadOnlyPresentation platform="moonraker" snapshot={{
      phase: 'ready', freshness: 'current', capabilities: ['camera'],
    }} cameraSnapshotUrl="/api/v1/printers/moonraker/-1000001/camera/snapshot?token=opaque" />);

    expect(screen.getByRole('img', { name: 'Latest camera preview for Klipper via Moonraker' })).toHaveAttribute(
      'src',
      '/api/v1/printers/moonraker/-1000001/camera/snapshot?token=opaque',
    );
    expect(screen.getByText('Read-only camera preview · refreshed on open')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open full-size image/i })).toHaveAttribute(
      'href',
      '/api/v1/printers/moonraker/-1000001/camera/snapshot?token=opaque',
    );
    expect(screen.getByRole('link', { name: /Open full-size image/i })).toHaveAttribute('target', '_blank');

    rerender(<WorkshopReadOnlyPresentation platform="moonraker" snapshot={{ phase: 'ready', freshness: 'current' }} />);
    expect(screen.queryByRole('img', { name: /Latest camera preview/i })).not.toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent(/Camera, files, console, maintenance, uploads, CANVAS are unavailable/i);
  });

  it('builds temperature trends from fresh observations instead of rendering an invented history', () => {
    const { rerender } = render(<WorkshopReadOnlyPresentation platform="elegoo" snapshot={{
      phase: 'ready', freshness: 'current', temperatures: { nozzle: { current_c: 200, target_c: 210 } },
    }} />);

    expect(screen.getByLabelText('Nozzle temperature trend from 1 fresh observations')).toHaveTextContent('Collecting trend');

    rerender(<WorkshopReadOnlyPresentation platform="elegoo" snapshot={{
      phase: 'ready', freshness: 'current', temperatures: { nozzle: { current_c: 203, target_c: 210 } },
    }} />);

    expect(screen.getByLabelText('Nozzle temperature trend from 2 fresh observations')).toHaveTextContent('Live trend');
  });
});
