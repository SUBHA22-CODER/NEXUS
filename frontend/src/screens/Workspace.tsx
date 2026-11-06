import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../App";
import { get, post, type Project, type Role, type User } from "../api";
import { Button, Chip, ErrorNote, Loading, PageHead, useData } from "../ui";

const field = "mt-1 w-full rounded border border-ink/35 bg-card px-3 py-2 text-sm";
const ROLE_HELP: Record<Role, string> = {
  admin: "Everything, including production changes",
  approver: "Approves tasks and purchases within the limit",
  analyst: "Uploads data and runs investigations",
  viewer: "Read only",
};

function Members() {
  const users = useData(() => get<User[]>("/users"), []);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "approver" as Role });
  const [error, setError] = useState("");
  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await post("/users", form);
      setForm({ name: "", email: "", password: "", role: "approver" });
      users.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <section className="card rise p-5" style={{ animationDelay: ".08s" }}>
      <h2 className="font-display text-xl font-bold">Members</h2>
      <ul className="mt-3 divide-y divide-rule">
        {users.data?.map((u) => (
          <li key={u.id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <span className="min-w-0 truncate"><strong className="font-semibold">{u.name}</strong> <span className="text-muted">{u.email}</span></span>
            <Chip value={u.role} />
          </li>
        ))}
      </ul>
      <form onSubmit={add} className="mt-5 grid gap-3 border-t border-rule pt-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={field} /></label>
        <label className="text-sm font-medium">Email<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={field} autoComplete="off" /></label>
        <label className="text-sm font-medium">Temporary password<input required type="password" minLength={10} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={field} autoComplete="new-password" /></label>
        <label className="text-sm font-medium">
          Role
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} className={field}>
            {(Object.keys(ROLE_HELP) as Role[]).map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="mt-1 block text-xs font-normal text-muted">{ROLE_HELP[form.role]}</span>
        </label>
        <div className="sm:col-span-2"><ErrorNote message={error} /></div>
        <div className="sm:col-span-2"><Button type="submit">Add member</Button></div>
      </form>
    </section>
  );
}

export default function Workspace() {
  const { me, signOut } = useSession();
  const projects = useData(() => get<Project[]>("/projects"), []);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const canCreate = me.user.role !== "viewer";

  async function create(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const project = await post<Project>("/projects", { name });
      navigate(`/p/${project.id}/command`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 md:py-12">
      <PageHead eyebrow={me.organization} title="Operational workspaces">
        <span className="text-sm text-muted">{me.user.name}</span>
        <Button variant="ghost" onClick={signOut}>Sign out</Button>
      </PageHead>
      <div className="grid gap-6 md:grid-cols-2 md:items-start">
        <section className="card rise p-5">
          <h2 className="font-display text-xl font-bold">Projects</h2>
          {projects.loading && <Loading />}
          <ErrorNote message={projects.error} />
          {projects.data?.length === 0 && <p className="mt-2 text-sm text-muted">No projects yet. A project holds the data and investigations for one operation.</p>}
          <ul className="mt-3 divide-y divide-rule">
            {projects.data?.map((p) => (
              <li key={p.id}>
                <Link to={`/p/${p.id}/command`} className="flex items-center justify-between py-2.5 font-semibold hover:underline">{p.name} <span aria-hidden>→</span></Link>
              </li>
            ))}
          </ul>
          {canCreate && (
            <form onSubmit={create} className="mt-4 flex items-end gap-2 border-t border-rule pt-4">
              <label className="min-w-0 flex-1 text-sm font-medium">New project<input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Checkout platform" className={field} /></label>
              <Button type="submit" variant="primary">Create</Button>
            </form>
          )}
          <div className="mt-2"><ErrorNote message={error} /></div>
        </section>
        {me.user.role === "admin" && <Members />}
      </div>
    </main>
  );
}
