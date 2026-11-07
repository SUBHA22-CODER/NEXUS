import { useCallback, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Domain } from "./api";

export const DOMAIN: Record<Domain, { label: string; color: string; text: string; bg: string }> = {
  infrastructure: { label: "Infrastructure", color: "var(--color-infra)", text: "text-infra", bg: "bg-infra" },
  supply: { label: "Supply", color: "var(--color-supply)", text: "text-supply", bg: "bg-supply" },
  communication: { label: "Communication", color: "var(--color-comms)", text: "text-comms", bg: "bg-comms" },
  execution: { label: "Execution", color: "var(--color-exec)", text: "text-exec", bg: "bg-exec" },
  security: { label: "Security", color: "var(--color-security)", text: "text-red-700", bg: "bg-red-700" },
  finance: { label: "Finance", color: "var(--color-finance)", text: "text-emerald-700", bg: "bg-emerald-700" },
  manufacturing: { label: "Manufacturing", color: "var(--color-mfg)", text: "text-indigo-600", bg: "bg-indigo-600" },
  tabular: { label: "Tabular", color: "var(--color-tabular)", text: "text-slate-600", bg: "bg-slate-600" },
};
export const DOMAINS = Object.keys(DOMAIN) as Domain[];

export const STATUS_LABEL: Record<string, string> = {
  running: "Investigating",
  awaiting_approval: "Awaiting approval",
  in_recovery: "In recovery",
  resolved: "Resolved",
  closed_no_action: "No action needed",
  failed: "Failed",
};

const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtMoney = (n: number) => money.format(n);
export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

/** Loads data and optionally keeps refreshing it. A failed refresh keeps showing the last good data. */
export function useData<T>(load: () => Promise<T>, deps: unknown[], pollMs?: number | ((data: T | undefined) => number | null)) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const latest = useRef(0);
  const dataRef = useRef<T>(undefined);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(async () => {
    const ticket = ++latest.current;
    try {
      const value = await load();
      if (ticket === latest.current) {
        dataRef.current = value;
        setData(value);
        setError("");
      }
    } catch (e) {
      if (ticket === latest.current) setError((e as Error).message);
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  }, deps);

  useEffect(() => {
    setLoading(true);
    dataRef.current = undefined;
    setData(undefined);
    let timer: number | undefined;
    let stopped = false;
    const tick = async () => {
      await reload();
      if (stopped) return;
      const wait = typeof pollMs === "function" ? pollMs(dataRef.current) : pollMs;
      if (wait) timer = window.setTimeout(tick, wait);
    };
    tick();
    return () => {
      stopped = true;
      latest.current++;
      window.clearTimeout(timer);
    };
  }, [reload]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, error, loading, reload };
}

export function Button({ variant = "secondary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const styles = {
    primary: "bg-ink text-paper border-ink hover:bg-black",
    secondary: "bg-card text-ink border-ink/40 hover:border-ink",
    danger: "bg-card text-infra border-infra/50 hover:border-infra",
    ghost: "bg-transparent text-muted border-transparent hover:text-ink",
  }[variant];
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex min-h-9 cursor-pointer items-center justify-center gap-2 rounded border px-3.5 py-1.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${styles} ${className}`}
    />
  );
}

/** A link that looks like the primary button, for navigation actions. */
export function LinkButton({ to, primary, children }: { to: string; primary?: boolean; children: ReactNode }) {
  return (
    <Link to={to} className={`inline-flex min-h-9 items-center justify-center rounded border px-3.5 py-1.5 text-sm font-semibold transition-colors ${primary ? "border-ink bg-ink text-paper hover:bg-black" : "border-ink/40 bg-card hover:border-ink"}`}>
      {children}
    </Link>
  );
}

const CHIP_TONES: Record<string, string> = {
  critical: "bg-infra text-white border-infra",
  high: "border-infra text-infra",
  failed: "bg-infra text-white border-infra",
  blocked: "bg-infra text-white border-infra",
  warning: "border-supply text-supply",
  medium: "border-supply text-supply",
  pending: "border-supply text-supply",
  proposed: "border-ink text-ink",
  awaiting_approval: "border-ink text-ink",
  in_recovery: "border-exec text-exec",
  running: "border-exec text-exec",
  executed: "border-exec text-exec",
  low: "border-rule text-muted",
  info: "border-rule text-muted",
  rejected: "border-rule text-muted",
  skipped: "border-rule text-muted",
  closed_no_action: "border-rule text-muted",
  not_applicable: "border-rule text-muted",
  verified: "bg-good text-white border-good",
  resolved: "bg-good text-white border-good",
  completed: "border-good text-good",
  observed: "border-ink text-ink",
  inferred: "border-dashed border-ink/60 text-ink",
};

export function Chip({ value, label }: { value: string; label?: string }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-sm border px-1.5 py-0.5 font-mono text-[0.68rem] font-medium uppercase tracking-wide ${CHIP_TONES[value] ?? "border-rule text-muted"}`}>
      {label ?? STATUS_LABEL[value] ?? value.replaceAll("_", " ")}
    </span>
  );
}

/** A station marker: the ring used for a domain everywhere, from the legend to the graph. */
export function Station({ domain, size = 12 }: { domain: Domain; size?: number }) {
  const meta = DOMAIN[domain] || DOMAIN.infrastructure;
  return (
    <span aria-hidden className="inline-block shrink-0 rounded-full bg-card" style={{ width: size, height: size, border: `${Math.max(2, size / 4)}px solid ${meta.color}` }} />
  );
}

export function PageHead({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="rise mb-6 flex flex-wrap items-end justify-between gap-4 border-b-2 border-ink pb-4">
      <div className="min-w-0">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-1 font-display text-3xl font-bold leading-tight tracking-tight [overflow-wrap:anywhere] md:text-4xl">{title}</h1>
      </div>
      {children && <div className="no-print flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}

export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p role="alert" className="rounded border border-infra/50 bg-infra/5 px-3 py-2 text-sm text-infra">{message}</p>;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 py-8 font-mono text-sm text-muted">
      <span className="pulse-dot inline-block size-2 rounded-full bg-ink" /> {label}…
    </p>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card rise flex flex-col items-start gap-3 p-8">
      <h2 className="font-display text-xl font-bold">{title}</h2>
      {children}
    </div>
  );
}

export function Confidence({ value }: { value: number }) {
  return (
    <span className="font-mono text-xs text-muted" title="Confidence, calculated from the evidence available">
      {Math.round(value * 100)}% conf.
    </span>
  );
}

export function Method({ value }: { value: string }) {
  const label: Record<string, string> = { deterministic: "calculated", rule_based: "rule-based", llm: "AI-assisted", template: "templated" };
  return <span className="font-mono text-xs text-muted">{label[value] ?? value}</span>;
}
