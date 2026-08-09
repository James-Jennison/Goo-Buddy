import { useMemo } from 'react';
import { Link } from 'react-router';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Activity, ArrowRight, LayoutDashboard, Printer } from 'lucide-react';
import { api, type Printer as PrinterRecord } from '../api/client';

type FleetPrinterStatus = {
  online: boolean;
  label: string;
  progress: number | null;
};

async function getFleetPrinterStatus(printer: PrinterRecord): Promise<FleetPrinterStatus> {
  if (printer.platform === 'elegoo') {
    const status = await api.getElegooStatus(-printer.id);
    return {
      online: status.phase === 'ready' && status.freshness === 'current',
      label: status.job?.state ?? status.state ?? status.phase,
      progress: status.job?.progress_percent ?? null,
    };
  }
  if (printer.platform === 'moonraker') {
    const status = await api.getMoonrakerStatus(-1_000_000 - printer.id);
    return {
      online: status.phase === 'ready' && status.freshness === 'current',
      label: status.job?.state ?? status.state ?? status.phase,
      progress: status.job?.progress_percent ?? null,
    };
  }

  const status = await api.getPrinterStatus(printer.id);
  return {
    online: status.connected,
    label: status.state ?? (status.connected ? 'ready' : 'offline'),
    progress: status.progress,
  };
}

function displayState(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function FleetDashboardPage() {
  const { data: printers = [], isLoading } = useQuery({
    queryKey: ['printers'],
    queryFn: api.getPrinters,
  });
  const statuses = useQueries({
    queries: printers.map((printer) => ({
      queryKey: ['fleet-dashboard-status', printer.id, printer.platform ?? 'bambu'],
      queryFn: () => getFleetPrinterStatus(printer),
      enabled: printer.is_active,
      refetchInterval: 3_000,
    })),
  });
  const today = new Date().toISOString().slice(0, 10);
  const sevenDaysAgo = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const { data: todayStats } = useQuery({
    queryKey: ['archiveStats', 'fleet-dashboard-today', today],
    queryFn: () => api.getArchiveStats({ dateFrom: today, dateTo: today }),
    staleTime: 60_000,
  });
  const { data: weekStats } = useQuery({
    queryKey: ['archiveStats', 'fleet-dashboard-week', sevenDaysAgo, today],
    queryFn: () => api.getArchiveStats({ dateFrom: sevenDaysAgo, dateTo: today }),
    staleTime: 60_000,
  });

  const printerStates = useMemo(() => printers.map((printer, index) => ({
    printer,
    status: statuses[index]?.data,
  })), [printers, statuses]);
  const online = printerStates.filter(({ printer, status }) => printer.is_active && status?.online).length;
  const active = printerStates.filter(({ status }) => {
    const state = status?.label.toLowerCase();
    return state === 'running' || state === 'printing' || state === 'paused' || state === 'pause';
  }).length;
  const uptime = printers.length ? Math.round((online / printers.length) * 100) : 0;
  const statItems = [
    { label: 'Printers online', value: `${online} / ${printers.length}`, detail: `${active} active` },
    { label: 'Jobs today', value: todayStats ? String(todayStats.total_prints) : '—', detail: todayStats ? 'archived prints' : 'Loading archive data' },
    { label: 'Filament used · 7d', value: weekStats ? `${Math.round(weekStats.total_filament_grams)} g` : '—', detail: weekStats ? 'recorded usage' : 'Loading archive data' },
    { label: 'Fleet uptime', value: `${uptime}%`, detail: `${Math.max(0, printers.length - online)} unavailable` },
  ];

  return (
    <main className="workshop-page nocturne-fleet-dashboard">
      <header className="workshop-page-header">
        <div className="flex items-start gap-3">
          <span className="nocturne-icon-chip"><LayoutDashboard className="h-5 w-5" aria-hidden="true" /></span>
          <div>
            <h1 className="workshop-page-title">Fleet dashboard</h1>
            <p className="workshop-page-subtitle">A live overview of the printers Goo Buddy can currently observe.</p>
          </div>
        </div>
        <Link className="nocturne-button" to="/printers">Open printers <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
      </header>

      <section className="nocturne-fleet-band" aria-label="Fleet statistics">
        <div className="nocturne-fleet-band__stats">
          {statItems.map((item) => <div className="nocturne-fleet-stat" key={item.label}><span>{item.label}</span><strong>{item.value}</strong><small>{item.detail}</small></div>)}
        </div>
        <div className="nocturne-fleet-band__live" aria-live="polite"><span className="nocturne-live-dot" aria-hidden="true" />{active ? `${active} print${active === 1 ? '' : 's'} live` : 'Fleet available'}</div>
      </section>

      <section className="nocturne-dashboard-panel" aria-labelledby="fleet-printers-heading">
        <div className="nocturne-dashboard-panel__heading">
          <div><p className="workshop-eyebrow">Fleet status</p><h2 id="fleet-printers-heading">Your printers</h2></div>
          <Link to="/printers" className="nocturne-text-link">Manage printers <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" /></Link>
        </div>
        {isLoading ? <p className="nocturne-dashboard-empty">Loading printer observations…</p> : printers.length === 0 ? (
          <div className="nocturne-dashboard-empty"><Printer className="h-5 w-5" aria-hidden="true" /><span>No printers are configured yet.</span><Link className="nocturne-text-link" to="/printers">Add a printer</Link></div>
        ) : (
          <div className="nocturne-dashboard-printer-grid">
            {printerStates.map(({ printer, status }) => {
              const isLive = Boolean(status?.online);
              return <Link className="nocturne-dashboard-printer" to="/printers" key={printer.id}>
                <span className={`nocturne-dashboard-printer__dot ${isLive ? 'is-live' : ''}`} aria-hidden="true" />
                <span className="nocturne-dashboard-printer__identity"><strong>{printer.name}</strong><small>{printer.platform === 'moonraker' ? 'Klipper via Moonraker' : printer.platform === 'elegoo' ? 'Elegoo SDCP v3' : printer.model ?? 'Bambu Lab'}</small></span>
                <span className="nocturne-dashboard-printer__state"><Activity className="h-3.5 w-3.5" aria-hidden="true" />{status ? displayState(status.label) : 'Connecting'}</span>
                {typeof status?.progress === 'number' && <span className="nocturne-dashboard-printer__progress">{Math.round(status.progress)}%</span>}
              </Link>;
            })}
          </div>
        )}
      </section>
    </main>
  );
}
