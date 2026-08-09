import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PlatformJobControls } from '../../components/PlatformJobControls';

const submit = vi.fn(async (operation: 'pause' | 'resume' | 'cancel') => ({
  id: 1,
  operation: `${operation}_job` as 'pause_job' | 'resume_job' | 'cancel_job',
  status: 'acknowledged' as const,
}));

function renderControls(overrides: Partial<React.ComponentProps<typeof PlatformJobControls>> = {}) {
  return render(
    <PlatformJobControls
      platformLabel="Elegoo SDCP v3"
      printerName="Synthetic printer"
      phase="ready"
      freshness="current"
      state="printing"
      capabilities={['job_control']}
      canControl
      submit={submit}
      {...overrides}
    />
  );
}

describe('PlatformJobControls', () => {
  it('confirms a capability-gated pause against its named target and reports the result', async () => {
    const user = userEvent.setup();
    renderControls();

    expect(screen.getByRole('button', { name: 'Pause' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel print' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Pause' }));
    expect(screen.getByText('Pause Synthetic printer?')).toBeInTheDocument();
    expect(screen.getByText(/Target: Synthetic printer via Elegoo SDCP v3/i)).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'Pause' }).at(-1)!);

    expect(submit).toHaveBeenCalledWith('pause');
    expect(await screen.findByText(/Pause confirmed for Synthetic printer/i)).toBeInTheDocument();
  });

  it('keeps controls disabled with an accessible explanation when permission or a fresh capability is absent', () => {
    renderControls({ canControl: false, phase: 'stale', freshness: 'retained', capabilities: [] });

    expect(screen.getByText(/Your role does not have permission to control printers/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel print' })).toBeDisabled();
  });

  it('offers only resume and cancel for a paused job', () => {
    renderControls({ state: 'paused' });

    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Cancel print' })).toBeEnabled();
  });

  it('keeps the fixed operation pending and reports a failed adapter result without adding another control', async () => {
    const user = userEvent.setup();
    let resolveSubmit!: (value: { id: number; operation: 'cancel_job'; status: 'failed' }) => void;
    const unavailableSubmit = vi.fn(
      () => new Promise<{ id: number; operation: 'cancel_job'; status: 'failed' }>((resolve) => { resolveSubmit = resolve; }),
    );
    renderControls({ submit: unavailableSubmit });

    await user.click(screen.getByRole('button', { name: 'Cancel print' }));
    await user.click(screen.getAllByRole('button', { name: 'Cancel print' }).at(-1)!);

    expect(unavailableSubmit).toHaveBeenCalledWith('cancel');
    expect(screen.getByRole('button', { name: 'Sending control request…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled();
    resolveSubmit({ id: 1, operation: 'cancel_job', status: 'failed' });
    expect(await screen.findByText(/Cancel print is unavailable for Synthetic printer/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /G-code|console|restart/i })).not.toBeInTheDocument();
  });

  it('makes an unconfirmed request explicit instead of presenting it as an acknowledgement', async () => {
    const user = userEvent.setup();
    renderControls({ submit: vi.fn(async () => ({ id: 1, operation: 'pause_job', status: 'failed', error_code: 'unconfirmed' })) });

    await user.click(screen.getByRole('button', { name: 'Pause' }));
    await user.click(screen.getAllByRole('button', { name: 'Pause' }).at(-1)!);

    expect(await screen.findByText(/was sent, but Synthetic printer did not confirm the new state/i)).toBeInTheDocument();
  });
});
