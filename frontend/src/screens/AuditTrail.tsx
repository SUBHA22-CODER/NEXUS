import { useProject, useSession } from "../App";
import { get, type AuditEntry } from "../api";
import { Chip, ErrorNote, Loading, PageHead, fmtDate, useData } from "../ui";

interface AuditResponse { chain: { valid: boolean; entries: number; broken_at_sequence: number | null }; entries: AuditEntry[] }

export default function AuditTrail() {
  const { project } = useProject();
  const { me } = useSession();
  const allowed = me.user.role === "admin" || me.user.role === "approver";
  const audit = useData<AuditResponse | null>(() => (allowed ? get<AuditResponse>("/audit") : Promise.resolve(null)), [allowed]);
  return (
    <>
      <PageHead eyebrow={project.name} title="Audit trail">
        {audit.data && (audit.data.chain.valid
          ? <Chip value="verified" label={`Chain intact · ${audit.data.chain.entries} entries`} />
          : <Chip value="failed" label={`Chain broken at entry ${audit.data.chain.broken_at_sequence}`} />)}
      </PageHead>
      {!allowed && <p className="text-muted">The audit trail is available to approvers and admins.</p>}
      <ErrorNote message={audit.error} />
      {allowed && !audit.data && !audit.error && <Loading />}
      {audit.data && (
        <ol className="card rise divide-y divide-rule">
          {audit.data.entries.map((e) => (
            <li key={e.sequence} className="grid gap-x-4 gap-y-0.5 p-3 text-sm md:grid-cols-[3rem_8.5rem_1fr_auto] md:items-baseline">
              <span className="font-mono text-xs text-muted">#{e.sequence}</span>
              <span className="font-mono text-xs text-muted">{fmtDate(e.created_at)}</span>
              <span className="min-w-0 [overflow-wrap:anywhere]">
                <strong className="font-semibold">{e.action}</strong> <span className="text-muted">by {e.actor}</span>
                {typeof e.detail.title === "string" && <span className="block text-xs text-muted">{e.detail.title}</span>}
              </span>
              <span className="font-mono text-[0.68rem] text-muted" title={e.hash}>{e.hash.slice(0, 10)}</span>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
