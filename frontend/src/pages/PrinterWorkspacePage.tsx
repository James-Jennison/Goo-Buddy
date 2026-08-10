import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Camera, ChevronLeft, FileText, Terminal, Thermometer } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { api, type MoonrakerDashboardStatus } from '../api/client';
import { Card, CardContent } from '../components/Card';
import { WorkshopCameraPreview, WorkshopReadOnlyPresentation } from '../components/WorkshopPrinterPresentation';

function WorkspacePanel({ title, icon: Icon, children }: { title: string; icon: typeof Camera; children: React.ReactNode }) {
  return <section className="moonraker-workspace-panel"><header><h2><Icon className="h-4 w-4" aria-hidden="true" /> {title}</h2><span>Read-only</span></header><div className="moonraker-workspace-panel__body">{children}</div></section>;
}

function FileInventoryPanel({ sourceId, status }: { sourceId: number; status?: MoonrakerDashboardStatus }) {
  const files = status?.capabilities?.includes('files') ? status.files : undefined;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [unavailableThumbnailPath, setUnavailableThumbnailPath] = useState<string | null>(null);
  const { data: metadata, isLoading: isMetadataLoading } = useQuery({
    queryKey: ['moonraker-gcode-metadata', sourceId, selectedPath],
    queryFn: () => api.getMoonrakerGcodeMetadata(sourceId, selectedPath!),
    enabled: selectedPath !== null && Boolean(files?.some((file) => file.path === selectedPath)),
  });
  return <WorkspacePanel title="G-code inventory" icon={FileText}>
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

function CameraPanel({ cameraSnapshotUrl }: { cameraSnapshotUrl?: string }) {
  return <WorkspacePanel title="Camera" icon={Camera}>
    {cameraSnapshotUrl ? <WorkshopCameraPreview label="Klipper via Moonraker" cameraSnapshotUrl={cameraSnapshotUrl} /> : <p className="moonraker-workspace-panel__empty">No read-only camera snapshot available.</p>}
  </WorkspacePanel>;
}

function ConsolePanel({ status }: { status?: MoonrakerDashboardStatus }) {
  const history = status?.capabilities?.includes('console-history') ? status.console_history : undefined;
  return <WorkspacePanel title="Console history" icon={Terminal}>
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
  const sourceId = printer?.platform === 'moonraker' ? -1_000_000 - printer.id : null;
  const { data: status } = useQuery({
    queryKey: ['moonraker-status', sourceId],
    queryFn: () => api.getMoonrakerStatus(sourceId!),
    enabled: sourceId !== null,
    refetchInterval: 3000,
  });

  if (isLoading) return <main className="page-container"><p className="text-bambu-gray">Loading printer workspace…</p></main>;
  if (!printer) return <main className="page-container space-y-4"><Link to="/printers" className="nocturne-text-link"><ChevronLeft className="h-4 w-4" /> Back to printers</Link><h1 className="page-title">Printer not found</h1></main>;

  return (
    <main className="page-container moonraker-workspace-page">
      <Link to="/printers" className="nocturne-text-link"><ChevronLeft className="h-4 w-4" /> Back to printers</Link>
      <header className="page-header"><div><p className="workshop-eyebrow">Printer workspace</p><h1 className="page-title">{printer.name}</h1><p className="page-subtitle">Source-specific monitoring and capability-gated tools.</p></div></header>

      {printer.platform !== 'moonraker' ? (
        <Card><CardContent><p className="text-bambu-gray">This printer workspace is ready for its platform-specific tools. Moonraker is the first source using this layout.</p></CardContent></Card>
      ) : <div className="moonraker-workspace-dashboard">
        <FileInventoryPanel sourceId={sourceId!} status={status} />
        <WorkspacePanel title="Thermals" icon={Thermometer}><WorkshopReadOnlyPresentation platform="moonraker" snapshot={status} showCamera={false} /></WorkspacePanel>
        <CameraPanel cameraSnapshotUrl={status?.capabilities?.includes('camera') ? api.getMoonrakerCameraSnapshotUrl(printer.id) : undefined} />
        <ConsolePanel status={status} />
      </div>}
    </main>
  );
}
