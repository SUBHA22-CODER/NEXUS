import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useProject } from "../App";
import { get, type AgentRun, type Domain, type Incident } from "../api";
import { Chip, Confidence, DOMAIN, ErrorNote, Loading, Method, PageHead, Station, useData } from "../ui";

const AGENTS: Record<string, { domain: Domain; title: string; role: string }> = {
  incident: { domain: "infrastructure", title: "Incident Agent", role: "Logs, error signatures, root cause, service impact" },
  communication: { domain: "communication", title: "Communication Agent", role: "Decisions, commitments, owners, deadlines" },
  supply: { domain: "supply", title: "Supply Agent", role: "Stockout risk and supplier comparison" },
  execution: { domain: "execution", title: "Execution Agent", role: "Missing owners and recovery work" },
  security: { domain: "security", title: "Security Agent", role: "Vulnerabilities, compliance, security incidents" },
  finance: { domain: "finance", title: "Finance Agent", role: "Transaction risk, payment reconciliation, revenue impact" },
  manufacturing: { domain: "manufacturing", title: "Manufacturing Agent", role: "Production lines, equipment telemetry, output yield" },
};

function RunCard({ run, index }: { run: AgentRun; index: number }) {
  const meta = AGENTS[run.agent] || {
    domain: "infrastructure" as Domain,
    title: `${run.agent.charAt(0).toUpperCase() + run.agent.slice(1)} Agent`,
    role: "Operational domain analysis",
  };
  const domainInfo = DOMAIN[meta.domain] || DOMAIN.infrastructure;
  const color = domainInfo.color;
  return (
    <li className="rise relative pl-9" style={{ animationDelay: `${index * 0.06}s` }}>
      {/* The run reads as a line with a station for each agent. */}
      <span aria-hidden className="absolute bottom-[-1.25rem] left-[9px] top-3 w-1 last-of-type:hidden" style={{ background: run.status === "skipped" ? "var(--color-rule)" : color }} />
      <span aria-hidden className="absolute left-0 top-1 size-[22px] rounded-full border-[5px] bg-card" style={{ borderColor: run.status === "skipped" ? "var(--color-rule)" : color }} />
      <div className={`card p-4 ${run.status === "skipped" ? "opacity-70" : ""}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-display text-lg font-bold leading-tight">{meta.title}</h2>
            <p className="text-xs text-muted">{meta.role}</p>
          </div>
          <div className="flex items-center gap-2">
            {run.status === "running" && <span className="pulse-dot size-2 rounded-full bg-exec" />}
            {run.status === "completed" && <Method value={run.method} />}
            <Chip value={run.status} />
          </div>
        </div>
        {run.note && <p className="mt-2 text-sm">{run.note}</p>}
        <ErrorNote message={run.error} />
        {run.tool_calls.length > 0 && (
          <details className="mt-3" open={run.tool_calls.length <= 2}>
            <summary className="eyebrow cursor-pointer">{run.tool_calls.length} tool call{run.tool_calls.length === 1 ? "" : "s"}</summary>
            <ul className="mt-2 space-y-1">
              {run.tool_calls.map((c, i) => (
                <li key={i} className="overflow-x-auto rounded-sm bg-ink px-3 py-2 font-mono text-xs leading-relaxed text-paper">
                  <span className="font-semibold">{c.tool}</span>
                  <span className="text-paper/60">({Object.entries(c.inputs).map(([k, v]) => `${k}=${v}`).join(", ")})</span>
                  <span className="block text-paper/85">→ {c.output} <span className="text-paper/50">{c.duration_ms} ms</span></span>
                </li>
              ))}
            </ul>
          </details>
        )}
        {run.findings.length > 0 && (
          <ul className="mt-3 divide-y divide-rule border-t border-rule">
            {run.findings.map((f, i) => (
              <li key={i} className="py-2.5">
                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                  {f.title} {f.severity !== "info" && <Chip value={f.severity} />} <Confidence value={f.confidence} />
                </p>
                <p className="mt-0.5 text-sm text-muted [overflow-wrap:anywhere]">{f.detail}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

export default function AgentWorkspace() {
  const { iid = "" } = useParams();
  const { project, refreshOverview } = useProject();
  const incident = useData(() => get<Incident>(`/incidents/${iid}`), [iid], (d) => (d?.status === "running" ? 1000 : null));
  const running = incident.data?.status === "running";
  const runs = useData(() => get<AgentRun[]>(`/incidents/${iid}/agent-runs`), [iid], () => (running || !incident.data ? 1000 : null));
  const wasRunning = useRef(false);

  useEffect(() => {
    if (wasRunning.current && !running) {
      runs.reload();
      refreshOverview();
    }
    wasRunning.current = !!running;
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps

  const steps = ["triage", ...(runs.data ?? []).filter((r) => r.status !== "skipped").map((r) => r.agent), "correlate", "plan", "policy check"];

  return (
    <>
      <PageHead eyebrow={incident.data?.title ?? "Investigation"} title="Agent Workspace">
        {incident.data && <Chip value={incident.data.status} />}
      </PageHead>
      <ErrorNote message={incident.error || runs.error} />
      {!runs.data && !runs.error && <Loading />}
      {incident.data?.status === "failed" && <ErrorNote message={incident.data.error} />}
      {runs.data && (
        <div className="grid gap-8 lg:grid-cols-[1fr_15rem] lg:items-start">
          <ol className="space-y-5">
            {runs.data.map((run, i) => <RunCard key={run.id} run={run} index={i} />)}
            {running && <li className="pl-9"><Loading label="Next step" /></li>}
          </ol>
          <aside className="space-y-4 lg:sticky lg:top-8">
            <section className="card p-4">
              <h2 className="eyebrow">Orchestrator path</h2>
              <ol className="mt-2 space-y-1 font-mono text-xs">
                {steps.map((s, i) => <li key={`${s}${i}`}>{i + 1}. {s}</li>)}
              </ol>
              <p className="mt-3 text-xs text-muted">Agents never talk to each other. They return structured findings and the state machine picks the next step. Agents with no relevant data are skipped.</p>
            </section>
            <section className="card flex flex-wrap gap-x-3 gap-y-1 p-4">
              {Object.values(AGENTS).map((a) => (
                <span key={a.title} className="flex items-center gap-1.5 text-xs"><Station domain={a.domain} size={9} /> {DOMAIN[a.domain]?.label || a.title}</span>
              ))}
            </section>
            {!running && incident.data && (
              <Link to={`/p/${project.id}/i/${iid}/response`} className="block text-sm font-semibold underline">Go to the Response Center →</Link>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
