import { useQuery } from '@tanstack/react-query';
import { useEffect, useState, type DragEvent } from 'react';
import { Crosshair, Camera, ChevronLeft, FileText, GripVertical, RotateCcw, Terminal, Thermometer } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { api, type MoonrakerDashboardStatus } from '../api/client';
import { Card, CardContent } from '../components/Card';
import { WorkshopCameraPreview, WorkshopReadOnlyPresentation } from '../components/WorkshopPrinterPresentation';

type WorkspacePanelDragProps = {
  draggable?: boolean;
  onDragStart?: (event: DragEvent<HTMLElement>) => void;
  onDragOver?: (event: DragEvent<HTMLElement>) => void;
  onDrop?: (event: DragEvent<HTMLElement>) => void;
};

const MOONRAKER_PANEL_ORDER = ['files', 'thermals', 'toolhead', 'camera', 'console'] as const;
const ELEGOO_PANEL_ORDER = ['thermals', 'job'] as const;
type PanelId = typeof MOONRAKER_PANEL_ORDER[number] | typeof ELEGOO_PANEL_ORDER[number];
type WorkspacePlatform = 'moonraker' | 'elegoo';

function defaultPanelOrder(platform: WorkspacePlatform | null): readonly PanelId[] {
  return platform === 'elegoo' ? ELEGOO_PANEL_ORDER : MOONRAKER_PANEL_ORDER;
}

function isPanelOrder(value: unknown, allowedPanels: readonly PanelId[]): value is PanelId[] {
  return Array.isArray(value)
    && value.length === allowedPanels.length
    && value.every((item): item is PanelId => typeof item === 'string' && allowedPanels.includes(item as PanelId))
    && new Set(value).size === allowedPanels.length;
}

function readPanelOrder(layoutKey: string, allowedPanels: readonly PanelId[]): PanelId[] {
  try {
    const saved: unknown = JSON.parse(window.localStorage.getItem(layoutKey) ?? 'null');
    return isPanelOrder(saved, allowedPanels) ? saved : [...allowedPanels];
  } catch {
    return [...allowedPanels];
  }
}

function WorkspacePanel({ title, icon: Icon, children, className, dragProps }: { title: string; icon: typeof Camera; children: React.ReactNode; className?: string; dragProps?: WorkspacePanelDragProps }) {
  return <section className={`moonraker-workspace-panel ${className ?? ''}`} draggable={dragProps?.draggable} onDragStart={dragProps?.onDragStart} onDragOver={dragProps?.onDragOver} onDrop={dragProps?.onDrop}><header><h2><Icon className="h-4 w-4" aria-hidden="true" /> {title}{dragProps?.draggable && <GripVertical className="moonraker-workspace-panel__drag-handle" aria-label={`Drag ${title} to rearrange`} />}</h2><span>Read-only</span></header><div className="moonraker-workspace-panel__body">{children}</div></section>;
}

function FileInventoryPanel({ sourceId, status, dragProps }: { sourceId: number; status?: MoonrakerDashboardStatus; dragProps?: WorkspacePanelDragProps }) {
  const files = status?.capabilities?.includes('files') ? status.files : undefined;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [unavailableThumbnailPath, setUnavailableThumbnailPath] = useState<string | null>(null);
  const { data: metadata, isLoading: isMetadataLoading } = useQuery({
    queryKey: ['moonraker-gcode-metadata', sourceId, selectedPath],
    queryFn: () => api.getMoonrakerGcodeMetadata(sourceId, selectedPath!),
    enabled: selectedPath !== null && Boolean(files?.some((file) => file.path === selectedPath)),
  });
  return <WorkspacePanel title="G-code inventory" icon={FileText} className="moonraker-workspace-panel--inventory" dragProps={dragProps}>
    {files?.length ? <div className="moonraker-file-inventory">
      {selectedPath && <div className="moonraker-file-metadata" aria-live="polite">
        <strong>{selectedPath}</strong>
        {isMetadataLoading ? <span>Loading metadata…</span> : metadata ? <span>{[metadata.slicer, metadata.layer_height != null ? `${metadata.layer_height} mm layers` : null, metadata.estimated_time != null ? `${Math.round(metadata.estimated_time / 60)} min` : null].filter(Boolean).join(' · ') || 'No metadata available'}</span> : <span>Metadata unavailable</span>}
        {metadata?.thumbnail_available && unavailableThumbnailPath !== selectedPath && <figure className="moonraker-gcode-thumbnail">
          <img src={api.getMoonrakerGcodeThumbnailUrl(sourceId, selectedPath)} alt={`Read-only thumbnail for ${selectedPath}`} onError={() => setUnavailableThumbnailPath(selectedPath)} />
          <figcaption>Trusted preview · read-only</figcaption>
        </figure>}
      </div>}
      <ul className="moonraker-file-list">{files.map((file) => <li key={file.path}><button type="button" className={selectedPath === file.path ? 'is-selected' : ''} onClick={() => { setSelectedPath(file.path); setUnavailableThumbnailPath(null); }} title={`Show metadata for ${file.path}`}><span>{file.path}</span></button><small>{Math.round(file.size / 1024)} KB</small></li>)}</ul>
    </div> : <p className="moonraker-workspace-panel__empty">No read-only G-code inventory available.</p>}
  </WorkspacePanel>;
}

function CameraPanel({ cameraSnapshotUrl, dragProps }: { cameraSnapshotUrl?: string; dragProps?: WorkspacePanelDragProps }) {
  return <WorkspacePanel title="Camera" icon={Camera} dragProps={dragProps}>
    {cameraSnapshotUrl ? <WorkshopCameraPreview label="Klipper via Moonraker" cameraSnapshotUrl={cameraSnapshotUrl} /> : <p className="moonraker-workspace-panel__empty">No read-only camera snapshot available.</p>}
  </WorkspacePanel>;
}

function ToolheadPanel({ status, dragProps }: { status?: MoonrakerDashboardStatus; dragProps?: WorkspacePanelDragProps }) {
  const toolhead = status?.capabilities?.includes('toolhead-telemetry') ? status.toolhead : undefined;
  return <WorkspacePanel title="Toolhead" icon={Crosshair} dragProps={dragProps}>
    {toolhead ? <dl className="moonraker-toolhead-telemetry">
      <div><dt>Active tool</dt><dd>{toolhead.active_extruder ?? 'Unavailable'}</dd></div>
      <div><dt>Homed axes</dt><dd>{toolhead.homed_axes ? toolhead.homed_axes.toUpperCase() : 'None'}</dd></div>
    </dl> : <p className="moonraker-workspace-panel__empty">No read-only toolhead telemetry available.</p>}
  </WorkspacePanel>;
}

function JobStatusPanel({ status, dragProps }: { status?: MoonrakerDashboardStatus; dragProps?: WorkspacePanelDragProps }) {
  const job = status?.capabilities?.includes('job-status') ? status.job : undefined;
  const staleJob = status?.stale_job;
  return <WorkspacePanel title="Job status" icon={FileText} dragProps={dragProps}>
    {job ? <dl className="moonraker-toolhead-telemetry">
      <div><dt>State</dt><dd>{job.state ?? 'Unavailable'}</dd></div>
      <div><dt>Progress</dt><dd>{job.progress_percent != null ? `${Math.round(job.progress_percent)}%` : 'Unavailable'}</dd></div>
      <div><dt>Layer</dt><dd>{job.current_layer != null ? `${job.current_layer}${job.total_layers != null ? ` / ${job.total_layers}` : ''}` : 'Unavailable'}</dd></div>
    </dl> : staleJob ? <dl className="moonraker-toolhead-telemetry" aria-label="Stale retained job data">
      <div><dt>State</dt><dd>{staleJob.state ?? 'Unavailable'}</dd></div>
      <div><dt>Freshness</dt><dd>Stale retained data — not a live print</dd></div>
      <div><dt>Previous progress</dt><dd>{staleJob.progress_percent != null ? `${Math.round(staleJob.progress_percent)}%` : 'Unavailable'}</dd></div>
      <div><dt>Previous layer</dt><dd>{staleJob.current_layer != null ? `${staleJob.current_layer}${staleJob.total_layers != null ? ` / ${staleJob.total_layers}` : ''}` : 'Unavailable'}</dd></div>
      <div><dt>Timing</dt><dd>Unsupported</dd></div>
    </dl> : <p className="moonraker-workspace-panel__empty">No current read-only job observation available.</p>}
  </WorkspacePanel>;
}

function ConsolePanel({ status, dragProps }: { status?: MoonrakerDashboardStatus; dragProps?: WorkspacePanelDragProps }) {
  const history = status?.capabilities?.includes('console-history') ? status.console_history : undefined;
  return <WorkspacePanel title="Console history" icon={Terminal} dragProps={dragProps}>
    {history?.length ? <ol className="moonraker-console-list">{history.map((entry, index) => <li key={`${entry.timestamp}-${index}`}><span>{entry.kind}</span>{entry.message}</li>)}</ol> : <p className="moonraker-workspace-panel__empty">No read-only console history available.</p>}
  </WorkspacePanel>;
}

/** Per-printer workspace foundation. The fleet page deliberately remains a
 * compact overview; source-specific capabilities live here instead. */
export function PrinterWorkspacePage() {
  const { printerId } = useParams();
  const id = Number(printerId);
  const { data: printers, isLoading } = useQuery({ queryKey: ['printers'], queryFn: api.getPrinters });
  const printer = Number.isInteger(id) ? printers?.find((item) => item.id === id) : undefined;
  const platform: WorkspacePlatform | null = printer?.platform === 'moonraker' || printer?.platform === 'elegoo' ? printer.platform : null;
  const sourceId = platform === 'moonraker' && printer ? -1_000_000 - printer.id : platform === 'elegoo' && printer ? -printer.id : null;
  const { data: status } = useQuery({
    queryKey: ['printer-workspace-status', platform, sourceId],
    queryFn: () => platform === 'moonraker' ? api.getMoonrakerStatus(sourceId!) : api.getElegooStatus(sourceId!),
    enabled: sourceId !== null,
    refetchInterval: 3000,
  });
  const allowedPanels = defaultPanelOrder(platform);
  const layoutKey = `goo-buddy:${platform ?? 'unavailable'}-workspace:${id}:panel-order:v1`;
  const [panelOrder, setPanelOrder] = useState<PanelId[]>(() => readPanelOrder(layoutKey, allowedPanels));
  useEffect(() => setPanelOrder(readPanelOrder(layoutKey, allowedPanels)), [layoutKey, allowedPanels]);
  const visiblePanelOrder = isPanelOrder(panelOrder, allowedPanels) ? panelOrder : [...allowedPanels];
  const movePanel = (source: PanelId, target: PanelId) => {
    if (source === target) return;
    setPanelOrder((current) => {
      const next = current.filter((item) => item !== source);
      next.splice(next.indexOf(target), 0, source);
      try { window.localStorage.setItem(layoutKey, JSON.stringify(next)); } catch { /* Layout persistence is optional. */ }
      return next;
    });
  };
  const resetPanelOrder = () => {
    try { window.localStorage.removeItem(layoutKey); } catch { /* Layout persistence is optional. */ }
    setPanelOrder([...allowedPanels]);
  };
  const dragPropsFor = (panel: PanelId): WorkspacePanelDragProps => ({
    draggable: true,
    onDragStart: (event) => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', panel); },
    onDragOver: (event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; },
    onDrop: (event) => { event.preventDefault(); const source = event.dataTransfer.getData('text/plain'); if (allowedPanels.includes(source as PanelId)) movePanel(source as PanelId, panel); },
  });

  if (isLoading) return <main className="page-container"><p className="text-bambu-gray">Loading printer workspace…</p></main>;
  if (!printer) return <main className="page-container space-y-4"><Link to="/printers" className="nocturne-text-link"><ChevronLeft className="h-4 w-4" /> Back to printers</Link><h1 className="page-title">Printer not found</h1></main>;

  return (
    <main className="page-container moonraker-workspace-page">
      <Link to="/printers" className="nocturne-text-link"><ChevronLeft className="h-4 w-4" /> Back to printers</Link>
      <header className="page-header"><div><p className="workshop-eyebrow">Printer workspace</p><h1 className="page-title">{printer.name}</h1><p className="page-subtitle">Source-specific monitoring and capability-gated tools.</p></div>{platform !== null && <button type="button" className="moonraker-workspace-reset" onClick={resetPanelOrder}><RotateCcw className="h-4 w-4" aria-hidden="true" /> Reset layout</button>}</header>

      {platform === null ? (
        <Card><CardContent><p className="text-bambu-gray">This printer workspace is ready for its platform-specific tools. Moonraker is the first source using this layout.</p></CardContent></Card>
      ) : <div className="moonraker-workspace-dashboard" aria-label="Rearrangeable printer workspace">
        {visiblePanelOrder.map((panel) => {
          const dragProps = dragPropsFor(panel);
          if (platform === 'elegoo') {
            if (panel === 'thermals') return <WorkspacePanel key={panel} title="Thermals" icon={Thermometer} className="moonraker-workspace-panel--thermals" dragProps={dragProps}><WorkshopReadOnlyPresentation platform="elegoo" snapshot={status} showCamera={false} /></WorkspacePanel>;
            return <JobStatusPanel key={panel} status={status} dragProps={dragProps} />;
          }
          if (panel === 'files') return <FileInventoryPanel key={panel} sourceId={sourceId!} status={status} dragProps={dragProps} />;
          if (panel === 'thermals') return <WorkspacePanel key={panel} title="Thermals" icon={Thermometer} className="moonraker-workspace-panel--thermals" dragProps={dragProps}><WorkshopReadOnlyPresentation platform="moonraker" snapshot={status} showCamera={false} /></WorkspacePanel>;
          if (panel === 'toolhead') return <ToolheadPanel key={panel} status={status} dragProps={dragProps} />;
          if (panel === 'camera') return <CameraPanel key={panel} cameraSnapshotUrl={status?.capabilities?.includes('camera') ? api.getMoonrakerCameraSnapshotUrl(printer.id) : undefined} dragProps={dragProps} />;
          return <ConsolePanel key={panel} status={status} dragProps={dragProps} />;
        })}
      </div>}
    </main>
  );
}
