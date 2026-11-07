import { useRef, useState, type DragEvent } from "react";
import { useProject, useSession } from "../App";
import {
  deleteFile,
  get,
  listFiles,
  post,
  upload,
  type Domain,
  type UploadedFileRecord,
  type UploadResult,
} from "../api";
import { Button, Chip, DOMAIN, ErrorNote, PageHead, Station, fmtDate, useData } from "../ui";

interface EventRow {
  id: string;
  domain: Domain;
  event_type: string;
  severity: string;
  occurred_at: string;
  entity: string;
  summary: string;
  source_file: string;
  source_locator: string;
}

const SUPPORTED_EXTS = [".csv", ".tsv", ".txt", ".log", ".json", ".jsonl", ".md"];

const FORMATS = [
  ["Logs & Telemetry", ".log, .jsonl", "Timestamp, level, service, message. Key-value pairs like status=500 are automatically extracted."],
  ["JSON Data", ".json", "Array of JSON objects or structured events payload with telemetry, records, or dependencies."],
  ["Tabular Datasets", ".csv, .tsv", "Standard or comma/tab separated operational data, inventory, suppliers, tasks, or system records."],
  ["Inventory Snapshots", ".csv", "sku, on_hand, daily_demand. Optional: safety_stock, supplier_id, inbound_eta_days, unit_price."],
  ["Suppliers & Catalog", ".csv", "supplier_id, sku, lead_time_days, unit_cost. Optional: name, min_order, capacity, reliability."],
  ["Tasks & Ownership", ".csv", "title, owner. Optional: task_id, status, deadline, service."],
  ["Architecture Graph", ".csv", "source, target. Optional: relation, source_domain, target_domain."],
  ["Transcripts & Notes", ".txt, .md", "Meeting bridge dialogue ('Speaker: text'), incident summaries, runbooks, or free-form notes."],
];

function fmtBytes(bytes: number): string {
  if (!bytes || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getExt(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? `.${parts.pop()?.toLowerCase()}` : "";
}

function ResultItem({ r }: { r: UploadResult }) {
  if (r.error) {
    return (
      <li className="py-2.5 text-sm text-infra border-b border-rule last:border-b-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">{r.file}</span>
          <Chip value="critical" />
        </div>
        <p className="mt-1 text-xs text-infra/90">
          <strong className="font-semibold">Upload failed:</strong> {r.error}
        </p>
      </li>
    );
  }
  const added = (r.events_added ?? 0) + (r.dependencies_added ?? 0);
  return (
    <li className="py-2.5 text-sm border-b border-rule last:border-b-0">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-ink">{r.file}</span>
        <span className="font-mono text-xs uppercase px-1.5 py-0.5 rounded bg-ink/5 text-muted">{r.kind}</span>
      </div>
      <p className="mt-1 text-xs text-muted">
        <strong className="text-emerald-700 dark:text-emerald-400 font-semibold">{added} records ingested</strong>
        {r.duplicates_skipped ? ` (${r.duplicates_skipped} duplicates skipped)` : ""}
        {r.rejected_count ? ` · ${r.rejected_count} unparseable lines` : ""}
      </p>
      {!!r.rejected?.length && (
        <ul className="mt-1.5 font-mono text-[0.7rem] text-infra/80 space-y-0.5 pl-2 border-l border-infra/30">
          {r.rejected.slice(0, 3).map((x, idx) => (
            <li key={idx}>
              {x.locator}: {x.reason}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function DataIngestion() {
  const { project, refreshOverview } = useProject();
  const { me } = useSession();
  const maxMb = me.max_upload_size_mb || 25;
  const maxBytes = me.max_upload_bytes || maxMb * 1024 * 1024;

  const events = useData(() => get<EventRow[]>(`/projects/${project.id}/events?limit=60`), [project.id]);
  const filesList = useData(() => listFiles(project.id), [project.id]);

  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const canWrite = me.user.role !== "viewer";

  function stageFiles(newFiles: FileList | File[] | null) {
    if (!newFiles || !newFiles.length) return;
    const incoming = Array.from(newFiles);
    setError("");
    setStagedFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const added = incoming.filter((f) => !existingNames.has(f.name));
      return [...prev, ...added];
    });
  }

  function removeStaged(index: number) {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUploadStaged() {
    if (!stagedFiles.length) return;
    setBusy(true);
    setError("");
    try {
      const res = await upload(project.id, stagedFiles);
      setResults(res.results);
      setStagedFiles([]);
      events.reload();
      filesList.reload();
      refreshOverview();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteFile(file: UploadedFileRecord) {
    if (!window.confirm(`Delete "${file.filename}" and remove its ingested events from this project?`)) return;
    setDeletingId(file.id);
    try {
      await deleteFile(project.id, file.id);
      filesList.reload();
      events.reload();
      refreshOverview();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeletingId(null);
    }
  }

  async function runDemo(action: () => Promise<{ results: UploadResult[] }>) {
    setBusy(true);
    setError("");
    try {
      const res = await action();
      setResults(res.results);
      events.reload();
      filesList.reload();
      refreshOverview();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (canWrite) stageFiles(e.dataTransfer.files);
  };

  return (
    <>
      <PageHead eyebrow={project.name} title="Data Ingestion & Documents" />
      <div className="grid gap-6 lg:grid-cols-[1.15fr_1fr] lg:items-start">
        <div className="space-y-4">
          {canWrite ? (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={`rise rounded-lg border-2 border-dashed p-7 text-center transition-all ${
                dragging ? "border-ink bg-ink/10 scale-[1.01]" : "border-ink/25 hover:border-ink/40 bg-surface"
              }`}
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-ink/5 text-ink mb-3">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </div>
              <p className="font-display text-lg font-bold">Drag operational datasets here</p>
              <p className="mt-1 text-xs text-muted">
                Accepts <span className="font-mono text-ink">.csv, .tsv, .txt, .log, .json, .jsonl, .md</span> (Up to {maxMb} MB each)
              </p>

              {/* Robust file input with full MIME & extension coverage */}
              <input
                ref={inputRef}
                type="file"
                multiple
                style={{ display: "none" }}
                accept=".csv,.tsv,.txt,.log,.json,.jsonl,.md,text/csv,text/tab-separated-values,text/plain,application/json,text/markdown,*/*"
                onChange={(e) => {
                  stageFiles(e.target.files);
                  e.target.value = "";
                }}
              />

              <div className="mt-5 flex flex-wrap justify-center gap-2">
                <Button
                  type="button"
                  variant="primary"
                  disabled={busy}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    inputRef.current?.click();
                  }}
                >
                  Browse Files
                </Button>
                {me.demo_enabled && (
                  <Button type="button" disabled={busy} onClick={() => runDemo(() => post(`/projects/${project.id}/demo`))}>
                    Load Demo Scenario
                  </Button>
                )}
                {me.demo_enabled && (
                  <Button
                    type="button"
                    disabled={busy}
                    variant="ghost"
                    onClick={() => runDemo(() => post(`/projects/${project.id}/demo?stage=recovery`))}
                    title="Logs and stock data from after recovery actions"
                  >
                    Load Post-Recovery Data
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <p className="card p-4 text-sm text-muted">Your viewer role can inspect data but cannot upload files.</p>
          )}

          {/* Staged files review queue */}
          {stagedFiles.length > 0 && (
            <section className="card p-4 space-y-3 border-ink/20 shadow-sm" aria-live="polite">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="eyebrow">Ready to Upload ({stagedFiles.length})</h2>
                  <p className="text-xs text-muted">Review your selected files before dispatching to the normalizer.</p>
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setStagedFiles([])}
                  className="text-xs text-muted hover:text-ink underline transition-colors"
                >
                  Clear all
                </button>
              </div>

              <ul className="divide-y divide-rule max-h-56 overflow-y-auto">
                {stagedFiles.map((file, idx) => {
                  const ext = getExt(file.name);
                  const isSupported = SUPPORTED_EXTS.includes(ext);
                  const isOversized = file.size > maxBytes;
                  return (
                    <li key={`${file.name}-${idx}`} className="py-2 flex items-center justify-between gap-3 text-sm">
                      <div className="min-w-0 flex-1 flex items-center gap-2">
                        <span className="font-mono text-[0.7rem] uppercase px-1.5 py-0.5 rounded bg-ink/5 text-ink">
                          {ext || "FILE"}
                        </span>
                        <span className="truncate font-medium text-ink" title={file.name}>
                          {file.name}
                        </span>
                        <span className="text-xs text-muted font-mono">{fmtBytes(file.size)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {!isSupported ? (
                          <span className="text-[0.7rem] text-infra font-semibold">Unsupported format</span>
                        ) : isOversized ? (
                          <span className="text-[0.7rem] text-infra font-semibold">Exceeds {maxMb}MB</span>
                        ) : (
                          <span className="text-[0.7rem] text-emerald-600 font-semibold">Ready</span>
                        )}
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => removeStaged(idx)}
                          className="h-6 w-6 flex items-center justify-center rounded text-muted hover:bg-ink/5 hover:text-ink transition-colors"
                          title="Remove file"
                        >
                          ✕
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>

              <div className="pt-2 flex justify-end gap-2 border-t border-rule">
                <Button
                  type="button"
                  variant="primary"
                  disabled={busy || stagedFiles.some((f) => f.size > maxBytes)}
                  onClick={handleUploadStaged}
                >
                  {busy ? "Ingesting & Normalizing…" : `Confirm & Upload ${stagedFiles.length} File${stagedFiles.length === 1 ? "" : "s"}`}
                </Button>
              </div>
            </section>
          )}

          <ErrorNote message={error} />

          {/* Upload results */}
          {results.length > 0 && (
            <section className="card p-4" aria-live="polite">
              <div className="flex items-center justify-between mb-2">
                <h2 className="eyebrow">Upload Report</h2>
                <button type="button" onClick={() => setResults([])} className="text-xs text-muted hover:text-ink">
                  Dismiss
                </button>
              </div>
              <ul className="divide-y divide-rule">
                {results.map((r, i) => (
                  <ResultItem key={`${r.file}-${i}`} r={r} />
                ))}
              </ul>
            </section>
          )}

          {/* Uploaded Files Management List */}
          <section className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="eyebrow">
                Project Datasets {filesList.data && `(${filesList.data.length})`}
              </h2>
              <button
                type="button"
                onClick={() => filesList.reload()}
                className="text-xs text-muted hover:text-ink transition-colors"
                title="Refresh list"
              >
                Refresh
              </button>
            </div>
            <ErrorNote message={filesList.error} />
            {filesList.data?.length === 0 && (
              <p className="mt-2 text-sm text-muted">No files uploaded yet for this project. Choose or drop files above.</p>
            )}
            {filesList.data && filesList.data.length > 0 && (
              <div className="mt-2 max-h-72 overflow-y-auto divide-y divide-rule">
                {filesList.data.map((f) => (
                  <div key={f.id} className="py-2.5 flex items-center justify-between gap-3 text-sm">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink truncate" title={f.filename}>
                          {f.filename}
                        </span>
                        <span className="font-mono text-[0.68rem] uppercase px-1.5 py-0.5 rounded bg-ink/5 text-muted">
                          {f.file_type}
                        </span>
                        {f.status === "failed" ? (
                          <Chip value="critical" />
                        ) : f.status === "partial" ? (
                          <Chip value="warning" />
                        ) : (
                          <span className="text-[0.68rem] text-emerald-600 font-medium">processed</span>
                        )}
                      </div>
                      <p className="text-xs text-muted mt-0.5 font-mono">
                        {fmtBytes(f.file_size)} · {f.events_count} event{f.events_count === 1 ? "" : "s"}
                        {f.dependencies_count > 0 ? `, ${f.dependencies_count} deps` : ""} · {fmtDate(f.created_at)}
                      </p>
                      {f.error_message && <p className="text-xs text-infra mt-0.5 truncate">{f.error_message}</p>}
                    </div>
                    {canWrite && (
                      <button
                        type="button"
                        disabled={deletingId === f.id}
                        onClick={() => handleDeleteFile(f)}
                        className="text-xs text-muted hover:text-infra transition-colors px-2 py-1 rounded hover:bg-infra/10"
                        title="Delete file and its events"
                      >
                        {deletingId === f.id ? "…" : "Delete"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Formats specification */}
          <section className="card p-4">
            <h2 className="eyebrow">Accepted Formats & Schema Contracts (Up to {maxMb} MB)</h2>
            <dl className="mt-2 space-y-2.5 text-sm">
              {FORMATS.map(([name, ext, help]) => (
                <div key={name}>
                  <dt className="font-semibold text-ink">
                    {name} <span className="font-mono text-xs font-normal text-muted">{ext}</span>
                  </dt>
                  <dd className="text-muted text-xs leading-relaxed">{help}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>

        {/* Normalized events preview stream */}
        <section className="card rise min-w-0 p-4" style={{ animationDelay: ".08s" }}>
          <div className="flex items-center justify-between mb-2">
            <h2 className="eyebrow">
              Normalized Events Stream {events.data && `(${events.data.length})`}
            </h2>
            <button
              type="button"
              onClick={() => events.reload()}
              className="text-xs text-muted hover:text-ink transition-colors"
            >
              Refresh
            </button>
          </div>
          <ErrorNote message={events.error} />
          {events.data?.length === 0 && (
            <p className="mt-2 text-sm text-muted">Uploaded telemetry and documents appear here in the unified event schema.</p>
          )}
          <ul className="mt-2 max-h-[46rem] divide-y divide-rule overflow-y-auto">
            {events.data?.map((e) => (
              <li key={e.id} className="py-2.5">
                <p className="flex flex-wrap items-center gap-1.5 text-xs">
                  <Station domain={e.domain} size={9} />
                  <span className={`font-semibold ${(DOMAIN[e.domain] || DOMAIN.infrastructure).text}`}>{e.event_type.replaceAll("_", " ")}</span>
                  {e.severity !== "info" && <Chip value={e.severity} />}
                  <span className="font-mono text-muted">{fmtDate(e.occurred_at)}</span>
                </p>
                <p className="mt-0.5 text-sm [overflow-wrap:anywhere]">{e.summary}</p>
                <p className="font-mono text-[0.68rem] text-muted">
                  {e.source_file}, {e.source_locator}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
