import { useEffect, useMemo, useState } from 'react';
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
  capabilities?: string[];
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

const TEMPERATURE_HISTORY_POINTS = 36;

function displayTemperature(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1) : '—';
}

function TemperatureTrend({ label, current }: { label: string; current?: number | null }) {
  const [history, setHistory] = useState<number[]>([]);

  useEffect(() => {
    if (typeof current !== 'number' || !Number.isFinite(current)) return;
    setHistory((previous) => [...previous, current].slice(-TEMPERATURE_HISTORY_POINTS));
  }, [current]);

  const path = useMemo(() => {
    if (history.length < 2) return '';
    const minimum = Math.min(...history);
    const maximum = Math.max(...history);
    const range = Math.max(maximum - minimum, 2);
    return history.map((temperature, index) => {
      const x = (index / (history.length - 1)) * 100;
      const y = 30 - ((temperature - minimum) / range) * 24;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(' ');
  }, [history]);

  return (
    <div className="workshop-temperature__trend" aria-label={`${label} temperature trend from ${history.length} fresh observations`}>
      <svg viewBox="0 0 100 32" preserveAspectRatio="none" role="img" aria-hidden="true">
        <path className="workshop-temperature__trend-grid" d="M 0 30 H 100" />
        {path && <path className="workshop-temperature__trend-line" d={path} />}
      </svg>
      <span>{history.length > 1 ? 'Live trend' : 'Collecting trend'}</span>
    </div>
  );
}

function TemperatureTile({ label, value }: { label: string; value?: WorkshopTemperature | null }) {
  if (!value || (value.current_c == null && value.target_c == null)) return null;
  return (
    <div className="workshop-temperature" aria-label={`${label} temperature`}>
      <div className="workshop-temperature__topline">
        <span className="workshop-temperature__label"><Thermometer className="h-3.5 w-3.5" aria-hidden="true" />{label}</span>
        <span className="workshop-temperature__target">Target {displayTemperature(value.target_c)}°</span>
      </div>
      <div className="workshop-temperature__reading"><strong>{displayTemperature(value.current_c)}°</strong><span>C</span></div>
      <TemperatureTrend label={label} current={value.current_c} />
      <span className="sr-only">{label} {displayTemperature(value.current_c)}°C</span>
    </div>
  );
}

type TemperatureSeries = { label: string; values: Array<number | null>; dash: string };

/** A compact multi-line trace built only from the fresh UI observations this
 * component has received. It deliberately has no synthetic baseline. */
function LiveTemperatureChart({ temperatures }: { temperatures?: WorkshopSnapshot['temperatures'] }) {
  const [history, setHistory] = useState<Array<{ nozzle: number | null; bed: number | null; chamber: number | null }>>([]);
  const nozzle = typeof temperatures?.nozzle?.current_c === 'number' ? temperatures.nozzle.current_c : null;
  const bed = typeof temperatures?.bed?.current_c === 'number' ? temperatures.bed.current_c : null;
  const chamber = typeof temperatures?.chamber?.current_c === 'number' ? temperatures.chamber.current_c : null;

  useEffect(() => {
    if (nozzle == null && bed == null && chamber == null) return;
    setHistory((previous) => [...previous, { nozzle, bed, chamber }].slice(-TEMPERATURE_HISTORY_POINTS));
  }, [nozzle, bed, chamber]);

  const series: TemperatureSeries[] = [
    { label: 'Nozzle', values: history.map((point) => point.nozzle), dash: '' },
    { label: 'Bed', values: history.map((point) => point.bed), dash: '5 3' },
    { label: 'Chamber', values: history.map((point) => point.chamber), dash: '1.5 3' },
  ];
  const observations = series.flatMap((item) => item.values.filter((value): value is number => value != null));
  const minimum = observations.length ? Math.min(...observations) : 0;
  const range = Math.max((observations.length ? Math.max(...observations) : 2) - minimum, 2);
  const toPath = (values: Array<number | null>) => {
    if (values.filter((value) => value != null).length < 2) return '';
    let started = false;
    return values.map((value, index) => {
      if (value == null) return '';
      const x = values.length === 1 ? 0 : (index / (values.length - 1)) * 100;
      const y = 34 - ((value - minimum) / range) * 28;
      const command = started ? 'L' : 'M';
      started = true;
      return `${command} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).filter(Boolean).join(' ');
  };

  if (!observations.length) return null;
  return (
    <section className="workshop-temperature-chart" aria-label="Live temperature chart">
      <div className="workshop-temperature-chart__heading"><span>Live temperatures</span><small>{history.length > 1 ? `${history.length} observations` : 'Collecting observations'}</small></div>
      <svg viewBox="0 0 100 38" preserveAspectRatio="none" role="img" aria-label="Nozzle, bed, and chamber temperature trends">
        <path className="workshop-temperature-chart__grid" d="M 0 34 H 100 M 0 20 H 100 M 0 6 H 100" />
        {series.map((item) => {
          const path = toPath(item.values);
          return path && <path key={item.label} className="workshop-temperature-chart__line" strokeDasharray={item.dash || undefined} d={path} />;
        })}
      </svg>
      <div className="workshop-temperature-chart__legend">{series.filter((item) => item.values.some((value) => value != null)).map((item) => <span key={item.label}><i style={{ borderTopStyle: item.dash ? 'dashed' : 'solid' }} />{item.label}</span>)}</div>
    </section>
  );
}

export function WorkshopReadOnlyPresentation({ platform, snapshot, cameraSnapshotUrl }: { platform: Exclude<WorkshopPlatform, 'bambu'>; snapshot?: WorkshopSnapshot | null; cameraSnapshotUrl?: string }) {
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
        <>
          <div className="workshop-temperature-grid">
            <TemperatureTile label="Nozzle" value={snapshot.temperatures.nozzle} />
            <TemperatureTile label="Bed" value={snapshot.temperatures.bed} />
            <TemperatureTile label="Chamber" value={snapshot.temperatures.chamber} />
          </div>
          <LiveTemperatureChart temperatures={snapshot.temperatures} />
        </>
      )}

      {typeof progress === 'number' && (
        <div className="workshop-progress" aria-label={`Print progress ${Math.round(progress)} percent`}>
          <div className="workshop-progress__topline"><span>Print progress</span><strong>{Math.round(progress)}%</strong></div>
          <div className="workshop-progress__track"><span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
          {snapshot?.job?.current_layer != null && <p>Layer {snapshot.job.current_layer}{snapshot.job.total_layers != null ? ` / ${snapshot.job.total_layers}` : ''}</p>}
        </div>
      )}

      {snapshot?.capabilities?.includes('camera') && cameraSnapshotUrl ? (
        <figure className="workshop-camera-preview"><img src={cameraSnapshotUrl} alt={`Latest camera preview for ${meta.label}`} /><figcaption>Read-only camera preview · refreshed on open</figcaption></figure>
      ) : <div className="workshop-unavailable" role="note"><CameraOff className="h-4 w-4" aria-hidden="true" /><span>Camera, files, console, maintenance, uploads, and CANVAS are unavailable for this source. Any supported job controls are shown separately.</span></div>}
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
