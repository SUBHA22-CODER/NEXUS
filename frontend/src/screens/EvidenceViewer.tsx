import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { get, type Domain, type EvidenceItem } from "../api";
import { Button, Chip, DOMAIN, DOMAINS, ErrorNote, Loading, PageHead, Station, useData } from "../ui";

export default function EvidenceViewer() {
  const { iid = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const evidence = useData(() => get<EvidenceItem[]>(`/incidents/${iid}/evidence`), [iid]);
  const [domain, setDomain] = useState<Domain | "all">("all");
  const ids = params.get("ids")?.split(",").filter(Boolean) ?? [];

  const items = (evidence.data ?? []).filter((e) => (ids.length ? ids.includes(e.id) : true) && (domain === "all" || e.domain === domain));

  return (
    <>
      <PageHead eyebrow="Traceability" title="Evidence and sources" />
      <div className="no-print mb-4 flex flex-wrap items-center gap-2">
        {(["all", ...DOMAINS] as const).map((d) => (
          <button
            key={d}
            type="button"
            aria-pressed={domain === d}
            onClick={() => setDomain(d)}
            className={`flex cursor-pointer items-center gap-1.5 rounded border px-2.5 py-1 text-sm font-medium ${domain === d ? "border-ink bg-ink text-paper" : "border-rule bg-card"}`}
          >
            {d !== "all" && <Station domain={d} size={9} />}
            {d === "all" ? "All" : (DOMAIN[d]?.label || d)}
          </button>
        ))}
        {ids.length > 0 && <Button variant="ghost" onClick={() => setParams({})}>Showing {ids.length} linked, show all</Button>}
      </div>
      <ErrorNote message={evidence.error} />
      {!evidence.data && !evidence.error && <Loading />}
      {evidence.data && items.length === 0 && <p className="text-muted">No evidence matches this filter.</p>}
      <ul className="space-y-2">
        {items.map((e, i) => (
          <li key={e.id} className="card rise p-4" style={{ animationDelay: `${Math.min(i, 12) * 0.025}s` }}>
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              <Station domain={e.domain} size={10} /> {e.claim || "Source"}
              {e.kind === "calculation" && <Chip value="info" label="Calculation" />}
            </p>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-sm bg-ink px-3 py-2 font-mono text-xs leading-relaxed text-paper [overflow-wrap:anywhere]">{e.excerpt}</pre>
            <p className="mt-1.5 font-mono text-xs text-muted">{e.source_file}, {e.source_locator}</p>
          </li>
        ))}
      </ul>
    </>
  );
}
