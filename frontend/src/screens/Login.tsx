import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { post, setToken } from "../api";
import { Button, DOMAIN, DOMAINS, ErrorNote } from "../ui";

const field = "mt-1 w-full rounded border border-ink/35 bg-card px-3 py-2 text-sm focus:border-ink";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ organization: "", name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = mode === "login" ? { email: form.email, password: form.password } : form;
      const res = await post<{ token: string }>(`/auth/${mode}`, body);
      setToken(res.token);
      navigate("/workspace", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen md:grid-cols-[1.2fr_1fr]">
      <section className="relative flex flex-col justify-between overflow-hidden bg-ink p-8 text-paper md:p-14">
        <p className="font-display text-2xl font-extrabold">NEXUS</p>
        {/* Four lines converging on one interchange: the product in a single picture. */}
        <svg viewBox="0 0 600 300" className="my-8 w-full max-w-xl" aria-hidden fill="none" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round">
          <path className="route-draw" d="M10 40 H210 L300 150 H590" stroke={DOMAIN.infrastructure.color} />
          <path className="route-draw" d="M10 110 H190 L300 150" stroke={DOMAIN.supply.color} style={{ animationDelay: ".12s" }} />
          <path className="route-draw" d="M10 190 H190 L300 150" stroke={DOMAIN.communication.color} style={{ animationDelay: ".24s" }} />
          <path className="route-draw" d="M10 260 H210 L300 150" stroke={DOMAIN.execution.color} style={{ animationDelay: ".36s" }} />
          <circle cx="300" cy="150" r="20" fill="#16181d" stroke="#f3efe6" strokeWidth="8" />
        </svg>
        <div>
          <h1 className="max-w-lg font-display text-4xl font-bold leading-[1.05] tracking-tight md:text-5xl">One intelligence layer. Multiple operational domains. Coordinated decisions.</h1>
          <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-1 font-mono text-xs text-paper/70">
            {DOMAINS.map((d) => <li key={d}>{DOMAIN[d].label}</li>)}
          </ul>
        </div>
      </section>
      <section className="flex items-center justify-center p-6 md:p-12">
        <form onSubmit={submit} className="rise w-full max-w-sm space-y-4">
          <h2 className="font-display text-3xl font-bold tracking-tight">{mode === "login" ? "Sign in" : "Create your organization"}</h2>
          {mode === "register" && (
            <>
              <label className="block text-sm font-medium">Organization<input required minLength={2} value={form.organization} onChange={set("organization")} className={field} autoComplete="organization" /></label>
              <label className="block text-sm font-medium">Your name<input required value={form.name} onChange={set("name")} className={field} autoComplete="name" /></label>
            </>
          )}
          <label className="block text-sm font-medium">Email<input required type="email" value={form.email} onChange={set("email")} className={field} autoComplete="email" /></label>
          <label className="block text-sm font-medium">
            Password
            <input required type="password" minLength={mode === "register" ? 10 : 1} value={form.password} onChange={set("password")} className={field} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            {mode === "register" && <span className="mt-1 block text-xs font-normal text-muted">At least 10 characters.</span>}
          </label>
          <ErrorNote message={error} />
          <Button type="submit" variant="primary" disabled={busy} className="w-full">{busy ? "One moment…" : mode === "login" ? "Sign in" : "Create organization"}</Button>
          <button type="button" className="cursor-pointer text-sm text-muted underline hover:text-ink" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "New here? Create an organization" : "Already have an account? Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
