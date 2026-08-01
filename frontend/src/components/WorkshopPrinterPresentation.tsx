import { CameraOff, Clock3, PlugZap, Thermometer, Waves } from 'lucide-react';
import { workshopPhaseMeta, workshopPlatformMeta, type WorkshopPhase, type WorkshopPlatform } from './workshopPresentationMeta';

export type { WorkshopPhase, WorkshopPlatform } from './workshopPresentationMeta';

export interface WorkshopTemperature {
  current_c?: number | null;
  target_c?: number | null;
}

export interface WorkshopSnapshot {
  phase?: WorkshopPhase | null;
  freshness?: 'current' | 'retained' | 'unavailable' | string | null;
  retained?: boolean | null;
  state?: string | null;
  model?: string | null;
  firmware?: string | null;
  error?: string | null;
  temperatures?: {
    nozzle?: WorkshopTemperature | null;
    bed?: WorkshopTemperature | null;
    chamber?: WorkshopTemperature | null;
  } | null;
  job?: {
    state?: string | null;
    progress_percent?: number | null;
    current_layer?: number | null;
    total_layers?: number | null;
    elapsed_seconds?: number | null;
    estimated_remaining_seconds?: number | null;
  } | null;
}

export function WorkshopStatusBadge({ phase, retained = false }: { phase?: WorkshopPhase | null; retained?: boolean }) {
  const meta = workshopPhaseMeta(phase);
  const Icon = meta.Icon;
  return (
    <span className={`workshop-status ${meta.tone}`} aria-label={retained ? `${meta.label}; retained data, not current` : meta.label}>
      <Icon className={`h-3.5 w-3.5 ${phase === 'connecting' || phase === 'reconnecting' ? 'motion-safe:animate-spin' : ''}`} aria-hidden="true" />
      <span>{meta.label}</span>
      {retained && <span className="workshop-status__retained">retained</span>}
    </span>
  );
}

function TemperatureTile({ label, value }: { label: string; value?: WorkshopTemperature | null }) {
  if (!value || (value.current_c == null && value.target_c == null)) return null;
  return (
    <div className="workshop-temperature" aria-label={`${label} temperature`}>
      <Thermometer className="h-4 w-4" aria-hidden="true" />
      <span className="workshop-temperature__label">{label}</span>
      <strong>{value.current_c ?? '—'}°</strong>
      <span className="workshop-temperature__target">/ {value.target_c ?? '—'}°</span>
      <span className="sr-only">{label} {value.current_c ?? '—'}°C</span>
    </div>
  );
}

export function WorkshopReadOnlyPresentation({ platform, snapshot }: { platform: Exclude<WorkshopPlatform, 'bambu'>; snapshot?: WorkshopSnapshot | null }) {
  const meta = workshopPlatformMeta(platform);
  const retained = Boolean(snapshot?.retained || snapshot?.freshness === 'retained');
  const phase = snapshot?.phase ?? 'connecting';
  const progress = snapshot?.job?.progress_percent;
  const state = snapshot?.job?.state ?? snapshot?.state;

  return (
    <section className="workshop-printer-summary" aria-label={`${meta.label} monitoring summary`}>
      <div className="workshop-printer-summary__identity">
        <div>
          <p className="workshop-eyebrow">{meta.label}</p>
          <p className="workshop-driver-copy">{meta.detail}</p>
        </div>
        <WorkshopStatusBadge phase={phase} retained={retained} />
      </div>

      {retained && (
        <p className="workshop-retained-notice"><Clock3 className="h-4 w-4" aria-hidden="true" /> Retained data — not current. Waiting for a fresh validated observation.</p>
      )}

      {(snapshot?.model || snapshot?.firmware || state) && (
        <p className="workshop-model-line">{snapshot?.model ?? meta.label}{snapshot?.firmware ? ` · ${snapshot.firmware}` : ''}{state ? ` · ${state}` : ''}</p>
      )}

      {snapshot?.temperatures && (
        <div className="workshop-temperature-grid">
          <TemperatureTile label="Nozzle" value={snapshot.temperatures.nozzle} />
          <TemperatureTile label="Bed" value={snapshot.temperatures.bed} />
          <TemperatureTile label="Chamber" value={snapshot.temperatures.chamber} />
        </div>
      )}

      {typeof progress === 'number' && (
        <div className="workshop-progress" aria-label={`Print progress ${Math.round(progress)} percent`}>
          <div className="workshop-progress__topline"><span>Print progress</span><strong>{Math.round(progress)}%</strong></div>
          <div className="workshop-progress__track"><span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
          {snapshot?.job?.current_layer != null && <p>Layer {snapshot.job.current_layer}{snapshot.job.total_layers != null ? ` / ${snapshot.job.total_layers}` : ''}</p>}
        </div>
      )}

      <div className="workshop-unavailable" role="note"><CameraOff className="h-4 w-4" aria-hidden="true" /><span>Camera, files, console, maintenance, uploads, CANVAS, and controls are unavailable for this read-only source.</span></div>
    </section>
  );
}

export function WorkshopBambuSignal({ connected, state }: { connected?: boolean; state?: string | null }) {
  return (
    <div className="workshop-bambu-signal">
      <PlugZap className="h-4 w-4" aria-hidden="true" />
      <span>{connected ? (state ?? 'Connected') : 'Connection unavailable'}</span>
      <Waves className="h-3.5 w-3.5" aria-hidden="true" />
    </div>
  );
}
