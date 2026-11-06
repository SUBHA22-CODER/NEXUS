import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useProject, useSession } from "../App";
import { get, patch, post, type Incident, type Recommendation, type Role, type Task } from "../api";
import { Button, Chip, Confidence, ErrorNote, Loading, PageHead, Station, fmtMoney, useData } from "../ui";

const RANK: Record<Role, number> = { viewer: 0, analyst: 1, approver: 2, admin: 3 };
const field = "mt-1 w-full rounded border border-ink/35 bg-card px-3 py-2 text-sm";
const ACTION_LABEL: Record<string, string> = {
  service_rollback: "Production change",
  expedite_supplier: "Purchase",
  assign_owner: "Assign owner",
  create_task: "Task",
  notify_stakeholders: "Notification",
};

function DecisionForm({ rec, onDone, onClose }: { rec: Recommendation; onDone: () => void; onClose: () => void }) {
  const needsOwner = !!rec.params.needs_owner;
  const [comment, setComment] = useState("");
  const [owner, setOwner] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function decide(decision: "approved" | "rejected") {
    setBusy(true);
    setError("");
    try {
      await post(`/recommendations/${rec.id}/decision`, { decision, comment, owner });
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <div className="mt-3 space-y-3 border-t border-rule pt-3">
      {needsOwner && (
        <label className="block text-sm font-medium">
          Owner <span className="font-normal text-muted">(required to approve)</span>
          <input value={owner} onChange={(e) => setOwner(e.target.value)} className={field} placeholder="Who is responsible?" autoFocus />
        </label>
      )}
      <label className="block text-sm font-medium">
        Comment <span className="font-normal text-muted">(kept in the audit trail)</span>
        <input value={comment} onChange={(e) => setComment(e.target.value)} className={field} />
      </label>
      <ErrorNote message={error} />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={busy || (needsOwner && !owner.trim())} onClick={() => decide("approved")}>Confirm approval</Button>
        <Button variant="danger" disabled={busy} onClick={() => decide("rejected")}>Reject</Button>
        <Button variant="ghost" disabled={busy} onClick={onClose}>Cancel</Button>
      </div>
      <p className="text-xs text-muted">A decision is final and recorded.</p>
    </div>
  );
}

function RecCard({ rec, onChange, evidenceBase }: { rec: Recommendation; onChange: () => void; evidenceBase: string }) {
  const { me } = useSession();
  const [open, setOpen] = useState(false);
  const allowed = RANK[me.user.role] >= RANK[rec.required_role];
  const cost = typeof rec.params.estimated_cost === "number" ? rec.params.estimated_cost : null;
  const stripe = rec.risk_level === "high" ? "border-l-infra" : "border-l-rule";

  return (
    <li className={`card rise border-l-4 p-4 ${stripe}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2">
            <Station domain={rec.domain} size={10} />
            <span className="eyebrow">{rec.priority}. {ACTION_LABEL[rec.action_type] ?? rec.action_type}</span>
            <Chip value={rec.risk_level} label={`${rec.risk_level} risk`} />
            <Confidence value={rec.confidence} />
          </p>
          <h3 className="mt-1 font-display text-lg font-bold leading-snug [overflow-wrap:anywhere]">{rec.title}</h3>
          <p className="mt-1 text-sm text-muted">{rec.rationale}</p>
          {cost !== null && <p className="mt-2 font-mono text-sm font-semibold">Estimated cost {fmtMoney(cost)}</p>}
          <Link to={`${evidenceBase}?ids=${rec.evidence_ids.join(",")}`} className="mt-2 inline-block text-xs font-semibold underline">
            {rec.evidence_ids.length} source{rec.evidence_ids.length === 1 ? "" : "s"}
          </Link>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Chip value={rec.status} />
          {rec.status === "proposed" && !open && (
            allowed
              ? <Button variant="primary" onClick={() => setOpen(true)}>Review</Button>
              : <span className="max-w-40 text-right text-xs text-muted">Needs {rec.required_role} approval. Your role: {me.user.role}.</span>
          )}
        </div>
      </div>
      {rec.status === "blocked" && <ErrorNote message={rec.policy_result.reasons.join(" ")} />}
      {rec.status === "proposed" && open && <DecisionForm rec={rec} onClose={() => setOpen(false)} onDone={onChange} />}
      {(rec.approval || rec.executed_at) && (
        <dl className="mt-3 grid gap-x-4 gap-y-1 border-t border-rule pt-3 text-sm sm:grid-cols-[6rem_1fr]">
          {rec.approval && (
            <>
              <dt className="text-muted">Decision</dt>
              <dd>{rec.approval.decision} by {rec.approval.by}{rec.approval.comment ? `: "${rec.approval.comment}"` : ""}</dd>
            </>
          )}
          {rec.execution.note && (
            <>
              <dt className="text-muted">Execution</dt>
              <dd className="flex flex-wrap items-center gap-2">
                {rec.execution.connector === "simulated" && <Chip value="pending" label="Simulated" />} {rec.execution.note}
              </dd>
            </>
          )}
          {rec.verification.status && (
            <>
              <dt className="text-muted">Outcome</dt>
              <dd className="flex flex-wrap items-center gap-2"><Chip value={rec.verification.status} /> <span className="[overflow-wrap:anywhere]">{rec.verification.reason}</span></dd>
            </>
          )}
        </dl>
      )}
    </li>
  );
}

function TaskRow({ task, onChange, canEdit }: { task: Task; onChange: () => void; canEdit: boolean }) {
  const [error, setError] = useState("");
  async function setStatus(status: string) {
    setError("");
    try {
      await patch(`/tasks/${task.id}`, { status });
      onChange();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <li className="grid items-center gap-x-4 gap-y-1 py-2.5 text-sm md:grid-cols-[1fr_9rem_7rem_8.5rem]">
      <span className={`[overflow-wrap:anywhere] ${task.status === "done" ? "text-muted line-through" : "font-medium"}`}>{task.title}</span>
      <span className={task.owner ? "" : "font-semibold text-infra"}>{task.owner || "No owner"}</span>
      <span className="font-mono text-xs text-muted">{task.deadline || "No deadline"}</span>
      <select aria-label={`Status of ${task.title}`} disabled={!canEdit} value={task.status} onChange={(e) => setStatus(e.target.value)} className="rounded border border-ink/35 bg-card px-2 py-1 text-sm">
        <option value="open">Open</option>
        <option value="in_progress">In progress</option>
        <option value="done">Done</option>
      </select>
      {error && <span className="text-infra md:col-span-4">{error}</span>}
    </li>
  );
}

export default function ResponseCenter() {
  const { iid = "" } = useParams();
  const { project, refreshOverview } = useProject();
  const { me } = useSession();
  const recs = useData(() => get<Recommendation[]>(`/incidents/${iid}/recommendations`), [iid]);
  const tasks = useData(() => get<Task[]>(`/incidents/${iid}/tasks`), [iid]);
  const incident = useData(() => get<Incident>(`/incidents/${iid}`), [iid]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canAnalyze = me.user.role !== "viewer";
  const refresh = () => { recs.reload(); tasks.reload(); incident.reload(); refreshOverview(); };

  async function verify() {
    setError("");
    setMessage("");
    try {
      const res = await post<{ status: string; results: { status: string }[] }>(`/incidents/${iid}/verify`);
      const verified = res.results.filter((r) => r.status === "verified").length;
      const failed = res.results.filter((r) => r.status === "failed").length;
      const waiting = res.results.filter((r) => r.status === "pending").length;
      setMessage(`Checked ${res.results.length} actions: ${verified} verified, ${failed} failed, ${waiting} waiting for data.`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const list = recs.data ?? [];
  const pending = list.filter((r) => r.status === "proposed");
  const done = list.filter((r) => r.status !== "proposed");
  const anyExecuted = list.some((r) => r.executed_at);

  return (
    <>
      <PageHead eyebrow={incident.data?.title ?? "Response"} title="Response Center">
        {incident.data && <Chip value={incident.data.status} />}
        {canAnalyze && anyExecuted && <Button onClick={verify}>Check outcomes</Button>}
      </PageHead>
      <div className="space-y-7">
        <ErrorNote message={error || recs.error} />
        {message && <p role="status" className="rounded border border-ink/30 bg-card px-3 py-2 text-sm">{message}</p>}
        {!recs.data && !recs.error && <Loading />}
        {recs.data?.length === 0 && <p className="text-muted">This investigation didn't recommend any actions.</p>}
        {pending.length > 0 && (
          <section>
            <h2 className="font-display text-xl font-bold">Waiting for your decision <span className="font-mono text-base font-medium text-muted">{pending.length}</span></h2>
            <p className="mt-1 text-sm text-muted">Nothing happens until a person with the right role approves it.</p>
            <ol className="mt-3 space-y-3">{pending.map((r) => <RecCard key={r.id} rec={r} onChange={refresh} evidenceBase={`/p/${project.id}/i/${iid}/evidence`} />)}</ol>
          </section>
        )}
        {done.length > 0 && (
          <section>
            <h2 className="font-display text-xl font-bold">Decided</h2>
            {anyExecuted && <p className="mt-1 text-sm text-muted">Outcomes are checked only against data received after the action. Upload newer logs or stock files, then check outcomes.</p>}
            <ol className="mt-3 space-y-3">{done.map((r) => <RecCard key={r.id} rec={r} onChange={refresh} evidenceBase={`/p/${project.id}/i/${iid}/evidence`} />)}</ol>
          </section>
        )}
        {!!tasks.data?.length && (
          <section>
            <h2 className="font-display text-xl font-bold">Action tracking</h2>
            <ul className="card mt-3 divide-y divide-rule px-4">
              {tasks.data.map((t) => <TaskRow key={t.id} task={t} onChange={refresh} canEdit={canAnalyze} />)}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}
