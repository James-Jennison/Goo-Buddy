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

  it('labels retained observations as not current and keeps unsupported capabilities unavailable', () => {
    render(<WorkshopReadOnlyPresentation platform="elegoo" snapshot={{ phase: 'stale', retained: true, model: 'Synthetic Centauri', temperatures: { nozzle: { current_c: 200, target_c: 210 } } }} />);
    expect(screen.getByText(/Retained data — not current/i)).toBeInTheDocument();
    expect(screen.getByText(/Camera, files, console, maintenance, uploads, CANVAS, and controls are unavailable/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Stale; retained data, not current/i)).toBeInTheDocument();
  });
});
