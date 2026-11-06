import { Link } from "react-router-dom";
import { useProject } from "../App";
import { Chip, Empty, Loading, PageHead, fmtDate } from "../ui";

export default function History() {
  const { project, overview } = useProject();
  if (!overview) return <Loading />;
  return (
    <>
      <PageHead eyebrow={project.name} title="Investigation history" />
      {overview.incidents.length === 0 ? (
        <Empty title="No investigations yet"><p className="text-muted">Past investigations will be listed here.</p></Empty>
      ) : (
        <ul className="card rise divide-y divide-rule">
          {overview.incidents.map((i) => (
            <li key={i.id}>
              <Link to={`/p/${project.id}/i/${i.id}/${i.status === "running" || i.status === "failed" ? "agents" : "response"}`} className="grid gap-x-4 gap-y-1 p-4 hover:bg-ink/5 md:grid-cols-[1fr_auto_auto_7rem] md:items-center">
                <span className="font-semibold">{i.title}</span>
                <span className="flex gap-1.5"><Chip value={i.severity} /><Chip value={i.status} /></span>
                <span className="font-mono text-sm">Risk {i.risk_score}</span>
                <span className="font-mono text-xs text-muted md:text-right">{fmtDate(i.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
