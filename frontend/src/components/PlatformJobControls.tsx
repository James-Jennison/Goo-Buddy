import { useState } from 'react';
import { Pause, Play, Square } from 'lucide-react';
import { Button } from './Button';
import { ConfirmModal } from './ConfirmModal';

export type PlatformJobOperation = 'pause' | 'resume' | 'cancel';

export interface PlatformJobControlResult {
  operation: string;
  status: string;
  error_code?: string | null;
}

interface PlatformJobControlsProps {
  platformLabel: string;
  printerName: string;
  phase?: string | null;
  freshness?: string | null;
  state?: string | null;
  capabilities?: string[];
  canControl: boolean;
  submit: (operation: PlatformJobOperation) => Promise<PlatformJobControlResult>;
}

const CONTROL_COPY = {
  pause: { label: 'Pause', effect: 'The current print will be paused.', Icon: Pause, buttonVariant: 'secondary' as const, confirmVariant: 'warning' as const },
  resume: { label: 'Resume', effect: 'The current paused print will resume.', Icon: Play, buttonVariant: 'primary' as const, confirmVariant: 'default' as const },
  cancel: { label: 'Cancel print', effect: 'The current print will be cancelled.', Icon: Square, buttonVariant: 'danger' as const, confirmVariant: 'danger' as const },
};

function availabilityReason({ phase, freshness, state, capabilities, canControl }: Omit<PlatformJobControlsProps, 'platformLabel' | 'printerName' | 'submit'>): string | null {
  if (!canControl) return 'Your role does not have permission to control printers.';
  if (phase !== 'ready' || freshness !== 'current') return 'Wait for a fresh, ready printer observation before using job controls.';
  if (!capabilities?.includes('job_control')) return 'This saved driver has not reported the job-control capability.';
  if (state !== 'printing' && state !== 'paused') return 'Job controls are unavailable because the printer is not printing or paused.';
  return null;
}

function operationIsAvailable(operation: PlatformJobOperation, state: string | null | undefined): boolean {
  if (operation === 'pause') return state === 'printing';
  if (operation === 'resume') return state === 'paused';
  return state === 'printing' || state === 'paused';
}

/**
 * Presentation-only controls for the three persisted platform operations.
 * The submit callback is intentionally an operation union rather than a URL,
 * protocol method, body, G-code value, or arbitrary command.
 */
export function PlatformJobControls(props: PlatformJobControlsProps) {
  const [confirming, setConfirming] = useState<PlatformJobOperation | null>(null);
  const [pending, setPending] = useState<PlatformJobOperation | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const reason = availabilityReason(props);
  const descriptionId = `platform-job-control-${props.printerName.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`;
  const unavailableId = `${descriptionId}-unavailable`;

  const confirm = async () => {
    if (!confirming) return;
    const operation = confirming;
    setPending(operation);
    setResult(null);
    try {
      const response = await props.submit(operation);
      setResult(response.status === 'acknowledged'
        ? `${CONTROL_COPY[operation].label} confirmed for ${props.printerName}.`
        : response.error_code === 'unconfirmed'
          ? `${CONTROL_COPY[operation].label} was sent, but ${props.printerName} did not confirm the new state. Check its status before retrying.`
          : `${CONTROL_COPY[operation].label} is unavailable for ${props.printerName}.`);
    } catch {
      setResult(`${CONTROL_COPY[operation].label} could not be sent. Check the printer status and try again.`);
    } finally {
      setPending(null);
      setConfirming(null);
    }
  };

  return (
    <section className="space-y-2 border-t border-bambu-dark-tertiary pt-3" aria-labelledby={descriptionId}>
      <div>
        <h4 id={descriptionId} className="text-sm font-medium text-white">Print controls for {props.printerName}</h4>
        <p className="text-xs text-bambu-gray">{props.platformLabel}: only pause, resume, and cancel are available when this printer reports a compatible current job.</p>
      </div>
      {reason && <p id={unavailableId} className="text-xs text-bambu-gray" role="status">Controls unavailable: {reason}</p>}
      <div className="flex flex-wrap gap-2">
        {(Object.keys(CONTROL_COPY) as PlatformJobOperation[]).map((operation) => {
          const control = CONTROL_COPY[operation];
          const disabled = Boolean(reason) || pending !== null || !operationIsAvailable(operation, props.state);
          const unavailable = reason ?? (operation === 'pause'
            ? 'Pause is available only while the current job is printing.'
            : operation === 'resume'
              ? 'Resume is available only while the current job is paused.'
              : 'Cancel is available only while the current job is printing or paused.');
          return (
            <Button
              key={operation}
              variant={control.buttonVariant}
              disabled={disabled}
              aria-describedby={reason ? unavailableId : undefined}
              title={disabled ? unavailable : `${control.label} ${props.printerName}`}
              onClick={() => setConfirming(operation)}
            >
              <control.Icon className="mr-1 h-4 w-4" aria-hidden="true" />
              {pending === operation ? 'Sending…' : control.label}
            </Button>
          );
        })}
      </div>
      {result && <p role="status" aria-live="polite" className="text-sm text-bambu-gray">{result}</p>}
      {confirming && (
        <ConfirmModal
          title={`${CONTROL_COPY[confirming].label} ${props.printerName}?`}
          message={`${CONTROL_COPY[confirming].effect}\n\nTarget: ${props.printerName} via ${props.platformLabel}.`}
          confirmText={CONTROL_COPY[confirming].label}
          variant={CONTROL_COPY[confirming].confirmVariant}
          isLoading={pending === confirming}
          loadingText="Sending control request…"
          onConfirm={confirm}
          onCancel={() => setConfirming(null)}
        />
      )}
    </section>
  );
}
