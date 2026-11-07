import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { get, getToken, setToken, setUnauthorizedHandler, type Me, type Overview, type Project } from "./api";
import { Button, DOMAIN, DOMAINS, ErrorNote, Loading, useData } from "./ui";
import AgentWorkspace from "./screens/AgentWorkspace";
import AuditTrail from "./screens/AuditTrail";
import CommandCenter from "./screens/CommandCenter";
import DataIngestion from "./screens/DataIngestion";
import EvidenceViewer from "./screens/EvidenceViewer";
import History from "./screens/History";
import IntelligenceGraph from "./screens/IntelligenceGraph";
import Login from "./screens/Login";
import ReportView from "./screens/ReportView";
import ResponseCenter from "./screens/ResponseCenter";
import Workspace from "./screens/Workspace";

interface Session { me: Me; signOut: () => void }
const SessionContext = createContext<Session | null>(null);
export const useSession = () => useContext(SessionContext)!;

interface ProjectCtx { project: Project; overview: Overview | undefined; refreshOverview: () => void; incidentId: string | undefined }
const ProjectContext = createContext<ProjectCtx | null>(null);
export const useProject = () => useContext(ProjectContext)!;

function ProjectShell() {
  const { pid = "", iid } = useParams();
  const { me, signOut } = useSession();
  const projects = useData(() => get<Project[]>("/projects"), []);
  const overview = useData(
    () => get<Overview>(`/projects/${pid}/overview`),
    [pid],
    (d) => (d?.active_investigations ? 1500 : 10000),
  );
  const project = projects.data?.find((p) => p.id === pid);
  const incidentId = iid ?? overview.data?.incidents.find((i) => i.status !== "failed" && i.status !== "running")?.id ?? overview.data?.incidents[0]?.id;
  const base = `/p/${pid}`;
  const inc = incidentId ? `${base}/i/${incidentId}` : null;
  const pending = overview.data?.pending_approvals ?? 0;

  const nav: { to: string | null; label: string; hint?: number }[] = [
    { to: `${base}/command`, label: "Command Center" },
    { to: `${base}/data`, label: "Data ingestion" },
    { to: inc && `${inc}/agents`, label: "Agent Workspace" },
    { to: inc && `${inc}/graph`, label: "Intelligence Graph" },
    { to: inc && `${inc}/response`, label: "Response Center", hint: pending },
    { to: inc && `${inc}/evidence`, label: "Evidence" },
    { to: inc && `${inc}/report`, label: "Report" },
    { to: `${base}/history`, label: "History" },
    { to: `${base}/audit`, label: "Audit trail" },
  ];

  if (projects.error) return <main className="p-8"><ErrorNote message={projects.error} /></main>;
  if (projects.loading) return <main className="p-8"><Loading /></main>;
  if (!project) return <Navigate to="/workspace" replace />;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="no-print flex shrink-0 flex-col border-b-2 border-ink bg-ink text-paper md:sticky md:top-0 md:h-screen md:w-60 md:border-b-0">
        <div className="flex items-center justify-between gap-2 px-5 pt-5 md:block">
          <NavLink to="/workspace" className="font-display text-2xl font-extrabold tracking-tight" aria-label="NEXUS: change project">NEXUS</NavLink>
          <p className="truncate text-sm text-paper/70 md:mt-3">{project.name}</p>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 py-3 md:mt-3 md:flex-1 md:flex-col md:overflow-y-auto md:py-0">
          {nav.map((item) =>
            item.to ? (
              <NavLink
                key={item.label}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center justify-between gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-sm font-medium transition-colors ${isActive ? "bg-paper text-ink" : "text-paper/80 hover:bg-paper/10 hover:text-paper"}`
                }
              >
                {item.label}
                {!!item.hint && <span className="rounded-sm bg-infra px-1.5 font-mono text-xs font-semibold text-white" aria-label={`${item.hint} pending`}>{item.hint}</span>}
              </NavLink>
            ) : (
              <span key={item.label} className="whitespace-nowrap px-2.5 py-1.5 text-sm text-paper/35" title="Run an investigation first">{item.label}</span>
            ),
          )}
        </nav>
        <div className="hidden border-t border-paper/15 px-5 py-4 md:block">
          <ul className="mb-4 space-y-1">
            {DOMAINS.slice(0, 4).map((d) => (
              <li key={d} className="flex items-center gap-2 font-mono text-[0.68rem] text-paper/70">
                <span className="inline-block h-1 w-5 rounded" style={{ background: DOMAIN[d].color }} /> {DOMAIN[d].label}
              </li>
            ))}
          </ul>
          <p className="truncate text-sm font-medium">{me.user.name}</p>
          <p className="truncate text-xs text-paper/60">{me.organization} · {me.user.role}</p>
          <button type="button" onClick={signOut} className="mt-2 cursor-pointer text-xs text-paper/70 underline hover:text-paper">Sign out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-9 md:py-8">
        <div className="mx-auto max-w-6xl">
          <ProjectContext.Provider value={{ project, overview: overview.data, refreshOverview: overview.reload, incidentId }}>
            <Outlet />
          </ProjectContext.Provider>
        </div>
      </main>
    </div>
  );
}

function RequireAuth() {
  const [me, setMe] = useState<Me>();
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const signOut = useCallback(() => {
    setToken(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    if (!getToken()) return;
    get<Me>("/me").then(setMe).catch((e: Error) => setError(e.message));
  }, [signOut]);

  if (!getToken()) return <Navigate to="/login" replace />;
  if (error)
    return (
      <main className="mx-auto max-w-xl space-y-3 p-8">
        <ErrorNote message={error} />
        <Button onClick={() => window.location.reload()}>Try again</Button>
      </main>
    );
  if (!me) return <main className="p-8"><Loading /></main>;
  return (
    <SessionContext.Provider value={{ me, signOut }}>
      <Outlet />
    </SessionContext.Provider>
  );
}


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/p/:pid" element={<ProjectShell />}>
          <Route index element={<Navigate to="command" replace />} />
          <Route path="command" element={<CommandCenter />} />
          <Route path="data" element={<DataIngestion />} />
          <Route path="history" element={<History />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="i/:iid/agents" element={<AgentWorkspace />} />
          <Route path="i/:iid/graph" element={<IntelligenceGraph />} />
          <Route path="i/:iid/response" element={<ResponseCenter />} />
          <Route path="i/:iid/evidence" element={<EvidenceViewer />} />
          <Route path="i/:iid/report" element={<ReportView />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/workspace" replace />} />
    </Routes>
  );
}
