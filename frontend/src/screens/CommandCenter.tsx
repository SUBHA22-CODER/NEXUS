import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useProject, useSession } from "../App";
import { post, type Assessment, type Incident, type Risk } from "../api";
import { Button, Chip, DOMAIN, DOMAINS, Empty, LinkButton, Loading, Method, PageHead, Station, fmtDate, fmtMoney } from "../ui";

/** One row of the coverage comparison: how long stock lasts against when replenishment arrives. */
function CoverRow({ label, note, risk, scale }: { label: string; note: string; risk: Risk; scale: number }) {
  const cover = Math.min(risk.days_of_cover ?? scale, scale);
  const gap = risk.coverage_gap_days;
  return (
    <div className="grid gap-x-4 gap-y-1 py-3 md:grid-cols-[12rem_1fr_6.5rem] md:items-center">
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-xs text-muted">{note}</p>
      </div>
      <div className="relative h-5 overflow-hidden rounded-sm bg-ink/5" role="img" aria-label={`${risk.days_of_cover ?? "unlimited"} days of cover, ${gap} day gap`}>
        <div className="absolute inset-y-0 left-0 bg-ink" style={{ width: `${(cover / scale) * 100}%` }} />
        {gap > 0 && (
          <div
            className="absolute inset-y-0"
            style={{
              left: `${(cover / scale) * 100}%`,
              width: `${(gap / scale) * 100}%`,
              background: "repeating-linear-gradient(135deg, var(--color-infra) 0 5px, color-mix(in srgb, var(--color-infra) 55%, transparent) 5px 10px)",
            }}
          />
        )}
      </div>
      <p className="font-mono text-sm md:text-right">
        {gap > 0 ? <strong className="font-semibold text-infra">{gap} d gap</strong> : <span className="text-good">no gap</span>}
      </p>
    </div>
  );
}

function RiskCard({ a }: { a: Assessment }) {
  const scale = Math.max(a.current.replenishment_days, a.worst_case.replenishment_days, a.current.days_of_cover ?? 0, 1);
  const hidden = a.baseline.coverage_gap_days === 0 && a.current.coverage_gap_days > 0;
  return (
    <article className="card rise p-5" style={{ animationDelay: ".1s" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{a.sku}</p>
          <h3 className="font-display text-xl font-bold">{a.name}</h3>
        </div>
        <div className="flex items-center gap-4 text-right">
          <div>
            <p className="font-mono text-xl font-semibold">{fmtMoney(a.revenue_at_risk)}</p>
            <p className="text-xs text-muted">revenue at risk{a.revenue_at_risk_worst > a.revenue_at_risk ? `, up to ${fmtMoney(a.revenue_at_risk_worst)}` : ""}</p>
          </div>
          <Chip value={a.current.risk_level} />
        </div>
      </div>
      {hidden && (
        <p className="mt-3 border-l-4 border-comms pl-3 text-sm">
          <strong>Invisible from inventory data alone.</strong> The stock system shows this shipment arriving on time. The {a.delay_days}-day delay was only mentioned in a meeting.
        </p>
      )}
      <div className="mt-2 divide-y divide-rule">
        <CoverRow label="Inventory data only" note="What the stock system shows" risk={a.baseline} scale={scale} />
        {a.delay_days > 0 && <CoverRow label="With the meeting" note={`Adds the ${a.delay_days}-day supplier delay`} risk={a.current} scale={scale} />}
        {a.held_units > 0 && <CoverRow label="With held orders" note={`Adds ${a.held_units} units stuck behind the outage`} risk={a.worst_case} scale={scale} />}
      </div>
      <p className="mt-2 font-mono text-xs text-muted">Solid: days of stock. Hatched: days with no stock. Calculated, not AI-generated; assumes constant demand.</p>
    </article>
  );
}

function Headline({ incident, pending, base }: { incident: Incident; pending: number; base: string }) {
  return (
    <section className="rise grid gap-6 border-b border-rule pb-6 lg:grid-cols-[1fr_auto]">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Chip value={incident.severity} /> <Chip value={incident.status} /> <Method value={incident.narrative_method} />
        </div>
        <h2 className="font-display text-2xl font-bold leading-tight tracking-tight md:text-3xl">{incident.title}</h2>
        <p className="mt-3 max-w-3xl leading-relaxed">{incident.summary}</p>
        <div className="no-print mt-4 flex flex-wrap gap-2">
          <LinkButton primary to={`${base}/i/${incident.id}/response`}>{pending ? `Review ${pending} pending action${pending === 1 ? "" : "s"}` : "Open Response Center"}</LinkButton>
          <LinkButton to={`${base}/i/${incident.id}/graph`}>See how it connects</LinkButton>
        </div>
      </div>
      <div className="flex items-baseline gap-2 lg:block lg:text-right">
        <p className="font-display text-7xl font-extrabold leading-none tracking-tighter">{incident.risk_score}</p>
        <p className="eyebrow mt-1">Risk score / 100</p>
      </div>
    </section>
  );
}

export default function CommandCenter() {
  const { project, overview, refreshOverview } = useProject();
  const { me } = useSession();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const base = `/p/${project.id}`;
  const canRun = me.user.role !== "viewer";

  async function investigate(force = false) {
    setBusy(true);
    setError("");
    try {
      const url = `/projects/${project.id}/investigations${force ? "?force=true" : ""}`;
      const incident = await post<Incident>(url);
      refreshOverview();
      navigate(`${base}/i/${incident.id}/agents`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!overview) return <Loading />;
  const eventTotal = Object.values(overview.event_counts).reduce((sum, n) => sum + (n ?? 0), 0);
  const running = overview.incidents.find((i) => i.status === "running");
  const failed = overview.incidents[0]?.status === "failed" ? overview.incidents[0] : null;

  return (
    <>
      <PageHead eyebrow={project.name} title="Command Center">
        {canRun && eventTotal > 0 && (
          <div className="flex items-center gap-2">
            <Button variant={overview.latest ? "secondary" : "primary"} onClick={() => investigate(false)} disabled={busy || !!running}>
              {busy ? "Starting..." : running ? "Investigation in progress" : overview.latest ? "Run a new investigation" : "Start investigation"}
            </Button>
            {running && (
              <Button variant="ghost" onClick={() => investigate(true)} disabled={busy} title="Cancel stuck run and restart">
                Force restart
              </Button>
            )}
          </div>
        )}
      </PageHead>
      <div className="space-y-6">
        {error && (
          <div className="card border-infra/40 bg-infra/5 p-4 text-sm text-infra flex flex-wrap items-center justify-between gap-3">
            <span>{error}</span>
            {error.toLowerCase().includes("running") && (
              <Button variant="secondary" onClick={() => investigate(true)} disabled={busy} className="text-xs">
                Force restart investigation
              </Button>
            )}
          </div>
        )}
        {failed && (
          <div className="card border-infra/30 p-4 text-sm flex flex-wrap items-center justify-between gap-3">
            <span>The last investigation encountered an issue: {failed.error || failed.title || "unknown error"}</span>
            {canRun && (
              <Button variant="secondary" onClick={() => investigate(true)} disabled={busy} className="text-xs">
                Retry investigation
              </Button>
            )}
          </div>
        )}
        {running && (
          <div className="card flex flex-wrap items-center justify-between gap-3 p-4 font-semibold hover:border-ink">
            <Link to={`${base}/i/${running.id}/agents`} className="flex items-center gap-3">
              <span className="pulse-dot size-2.5 rounded-full bg-exec" /> Investigation in progress. Watch the agents →
            </Link>
            <Button variant="ghost" onClick={() => investigate(true)} disabled={busy} className="text-xs text-muted hover:text-ink">
              Restart if stuck
            </Button>
          </div>
        )}
        {eventTotal === 0 && (
          <Empty title="Nothing to investigate yet">
            <p className="text-muted">Add logs, inventory, supplier files and meeting transcripts. NEXUS looks for how they affect one another.</p>
            <LinkButton primary to={`${base}/data`}>Add data</LinkButton>
          </Empty>
        )}
        {eventTotal > 0 && !overview.latest && !running && (
          <Empty title={`${eventTotal} events ready`}>
            <p className="text-muted">Start an autonomous investigation to correlate cross-domain telemetry and calculate operational risk.</p>
            {canRun && (
              <div className="mt-4">
                <Button variant="primary" onClick={() => investigate(false)} disabled={busy}>
                  {busy ? "Starting..." : "Start investigation"}
                </Button>
              </div>
            )}
          </Empty>
        )}
        {overview.latest && <Headline incident={overview.latest} pending={overview.pending_approvals} base={base} />}

        {overview.business_risks.map((a) => <RiskCard key={a.sku} a={a} />)}

        {eventTotal > 0 && (
          <section className="rise grid grid-cols-2 gap-px overflow-hidden rounded-md border border-rule bg-rule lg:grid-cols-6" style={{ animationDelay: ".16s" }} aria-label="Project totals">
            {DOMAINS.filter((d) => (overview.event_counts[d] ?? 0) > 0 || ["infrastructure", "supply", "communication", "execution"].includes(d)).map((d) => (
              <div key={d} className="bg-card p-4">
                <p className="flex items-center gap-1.5 text-xs font-medium text-muted"><Station domain={d} size={10} /> {DOMAIN[d].label}</p>
                <p className="mt-1 font-mono text-2xl font-semibold">{overview.event_counts[d] ?? 0}</p>
                <p className="text-xs text-muted">events</p>
              </div>
            ))}
            <div className="bg-card p-4">
              <p className="text-xs font-medium text-muted">Awaiting decision</p>
              <p className="mt-1 font-mono text-2xl font-semibold">{overview.pending_approvals}</p>
              <p className="text-xs text-muted">actions</p>
            </div>
            <div className="bg-card p-4">
              <p className="text-xs font-medium text-muted">Open</p>
              <p className="mt-1 font-mono text-2xl font-semibold">{overview.open_tasks}</p>
              <p className="text-xs text-muted">tasks</p>
            </div>
          </section>
        )}

        {overview.latest?.uncertainties && overview.latest.uncertainties.length > 0 && (
          <section className="rise" style={{ animationDelay: ".2s" }}>
            <h2 className="font-display text-xl font-bold">What NEXUS isn't sure about</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {overview.latest.uncertainties.map((u) => <li key={u}>{u}</li>)}
            </ul>
          </section>
        )}
        {overview.latest && <p className="text-xs text-muted">Latest investigation opened {fmtDate(overview.latest.created_at)}, from {overview.latest.event_count} events.</p>}
      </div>
    </>
  );
}
