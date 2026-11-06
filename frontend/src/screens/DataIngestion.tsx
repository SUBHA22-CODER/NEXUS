import { useRef, useState, type DragEvent } from "react";
import { useProject, useSession } from "../App";
import { get, post, upload, type Domain, type UploadResult } from "../api";
import { Button, Chip, DOMAIN, ErrorNote, PageHead, Station, fmtDate, useData } from "../ui";

interface EventRow { id: string; domain: Domain; event_type: string; severity: string; occurred_at: string; entity: string; summary: string; source_file: string; source_locator: string }

const FORMATS = [
  ["Logs", ".log, .jsonl", "Timestamp, level, service, message. Add key=value pairs such as status=500."],
  ["Inventory", ".csv", "sku, on_hand, daily_demand. Optional: safety_stock, supplier_id, inbound_eta_days, unit_price, as_of."],
  ["Suppliers", ".csv", "supplier_id, sku, lead_time_days, unit_cost. Optional: name, min_order, capacity, reliability."],
  ["Tasks", ".csv", "title, owner. Optional: task_id, status, deadline, service."],
  ["Dependencies", ".csv", "source, target. Optional: relation, source_domain, target_domain."],
  ["Transcripts", ".txt, .md", "One 'Speaker Name: text' per line, optionally with [09:40]. A 'Date: YYYY-MM-DD' header dates them."],
];

function Result({ r }: { r: UploadResult }) {
  if (r.error) return <li className="py-2 text-sm text-infra"><strong className="font-semibold">Not added.</strong> {r.error}</li>;
  const added = (r.events_added ?? 0) + (r.dependencies_added ?? 0);
  return (
    <li className="py-2 text-sm">
      <span className="font-semibold">{r.file}</span> <span className="font-mono text-xs text-muted">{r.kind}</span>
      <span className="block text-muted">
        {added} added{r.duplicates_skipped ? `, ${r.duplicates_skipped} already here` : ""}{r.rejected_count ? `, ${r.rejected_count} couldn't be read` : ""}
      </span>
      {!!r.rejected?.length && (
        <ul className="mt-1 font-mono text-xs text-infra">
          {r.rejected.slice(0, 5).map((x) => <li key={x.locator}>{x.locator}: {x.reason}</li>)}
        </ul>
      )}
    </li>
  );
}

export default function DataIngestion() {
  const { project, refreshOverview } = useProject();
  const { me } = useSession();
  const events = useData(() => get<EventRow[]>(`/projects/${project.id}/events?limit=60`), [project.id]);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const canWrite = me.user.role !== "viewer";

  async function run(action: () => Promise<{ results: UploadResult[] }>) {
    setBusy(true);
    setError("");
    try {
      setResults((await action()).results);
      events.reload();
      refreshOverview();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const send = (list: FileList | null) => {
    if (list?.length) run(() => upload(project.id, Array.from(list)));
  };
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (canWrite) send(e.dataTransfer.files);
  };

  return (
    <>
      <PageHead eyebrow={project.name} title="Data ingestion" />
      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-start">
        <div className="space-y-4">
          {canWrite ? (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={drop}
              className={`rise rounded-md border-2 border-dashed p-8 text-center transition-colors ${dragging ? "border-ink bg-ink/5" : "border-ink/30"}`}
            >
              <p className="font-display text-xl font-bold">Drop operational files here</p>
              <p className="mt-1 text-sm text-muted">Up to 5 MB each. Uploading the same file twice adds nothing.</p>
              <input ref={input} type="file" multiple hidden accept=".log,.jsonl,.csv,.txt,.md" onChange={(e) => { send(e.target.files); e.target.value = ""; }} />
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button variant="primary" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Reading…" : "Choose files"}</Button>
                {me.demo_enabled && <Button disabled={busy} onClick={() => run(() => post(`/projects/${project.id}/demo`))}>Load demo scenario</Button>}
                {me.demo_enabled && <Button disabled={busy} variant="ghost" onClick={() => run(() => post(`/projects/${project.id}/demo?stage=recovery`))} title="Logs and stock data from after the recovery actions, for testing verification">Load post-recovery data</Button>}
              </div>
            </div>
          ) : (
            <p className="card p-4 text-sm text-muted">Your viewer role can see this data but can't add to it.</p>
          )}
          <ErrorNote message={error} />
          {results.length > 0 && (
            <section className="card p-4" aria-live="polite">
              <h2 className="eyebrow">Last upload</h2>
              <ul className="mt-1 divide-y divide-rule">{results.map((r, i) => <Result key={`${r.file}${i}`} r={r} />)}</ul>
            </section>
          )}
          <section className="card p-4">
            <h2 className="eyebrow">Accepted formats</h2>
            <dl className="mt-2 space-y-2 text-sm">
              {FORMATS.map(([name, ext, help]) => (
                <div key={name}>
                  <dt className="font-semibold">{name} <span className="font-mono text-xs font-normal text-muted">{ext}</span></dt>
                  <dd className="text-muted">{help}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
        <section className="card rise min-w-0 p-4" style={{ animationDelay: ".08s" }}>
          <h2 className="eyebrow">Normalized events {events.data && `(latest ${events.data.length})`}</h2>
          <ErrorNote message={events.error} />
          {events.data?.length === 0 && <p className="mt-2 text-sm text-muted">Everything you add appears here in one common format.</p>}
          <ul className="mt-2 max-h-[46rem] divide-y divide-rule overflow-y-auto">
            {events.data?.map((e) => (
              <li key={e.id} className="py-2">
                <p className="flex flex-wrap items-center gap-1.5 text-xs">
                  <Station domain={e.domain} size={9} /> <span className={`font-semibold ${DOMAIN[e.domain].text}`}>{e.event_type.replaceAll("_", " ")}</span>
                  {e.severity !== "info" && <Chip value={e.severity} />}
                  <span className="font-mono text-muted">{fmtDate(e.occurred_at)}</span>
                </p>
                <p className="mt-0.5 text-sm [overflow-wrap:anywhere]">{e.summary}</p>
                <p className="font-mono text-[0.68rem] text-muted">{e.source_file}, {e.source_locator}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
