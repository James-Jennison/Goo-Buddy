import { Activity, CheckCircle2, CircleAlert, Clock3, Link2Off, LoaderCircle, PauseCircle, Radio } from 'lucide-react';

export type WorkshopPlatform = 'bambu' | 'elegoo' | 'moonraker';
export type WorkshopPhase = 'ready' | 'stale' | 'disconnected' | 'disabled' | 'invalid' | 'unauthorized' | 'connecting' | 'waiting' | 'reconnecting' | 'error' | string;

const PLATFORM_META: Record<WorkshopPlatform, { label: string; detail: string }> = {
  bambu: { label: 'Bambu Lab', detail: 'connected printer' },
  elegoo: { label: 'Elegoo SDCP v3', detail: 'evidence-backed read-only monitoring' },
  moonraker: { label: 'Klipper via Moonraker', detail: 'capability-gated monitoring and job control' },
};

const PHASE_META: Record<string, { label: string; tone: string; Icon: typeof CheckCircle2 }> = {
  ready: { label: 'Ready', tone: 'workshop-status--ready', Icon: CheckCircle2 },
  stale: { label: 'Stale', tone: 'workshop-status--stale', Icon: Clock3 },
  disconnected: { label: 'Disconnected', tone: 'workshop-status--disconnected', Icon: Link2Off },
  disabled: { label: 'Disabled', tone: 'workshop-status--disabled', Icon: PauseCircle },
  invalid: { label: 'Invalid', tone: 'workshop-status--invalid', Icon: CircleAlert },
  unauthorized: { label: 'Credentials need attention', tone: 'workshop-status--attention', Icon: CircleAlert },
  connecting: { label: 'Connecting', tone: 'workshop-status--waiting', Icon: LoaderCircle },
  waiting: { label: 'Waiting for observation', tone: 'workshop-status--waiting', Icon: Radio },
  reconnecting: { label: 'Reconnecting', tone: 'workshop-status--waiting', Icon: LoaderCircle },
  error: { label: 'Connection error', tone: 'workshop-status--invalid', Icon: CircleAlert },
};

/** Platform labels are keyed only by the saved driver contract, never by model text. */
export function workshopPlatformMeta(platform: WorkshopPlatform) {
  return PLATFORM_META[platform];
}

export function workshopPhaseMeta(phase: WorkshopPhase | null | undefined) {
  return PHASE_META[phase ?? ''] ?? { label: 'Status unavailable', tone: 'workshop-status--disabled', Icon: Activity };
}
