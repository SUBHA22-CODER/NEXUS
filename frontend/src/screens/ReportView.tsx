import { useState } from "react";
import { useParams } from "react-router-dom";
import { downloadReport, get, type Report } from "../api";
import { Button, Chip, Confidence, ErrorNote, Loading, Method, PageHead, Station, fmtDate, useData } from "../ui";

export default function ReportView() {
  const { iid = "" } = useParams();
  const report = useData(() => get<Report>(`/incidents/${iid}/report`), [iid]);
  const [error, setError] = useState("");
  const r = report.data;

  return (
    <>
      <PageHead eyebrow={r ? `${r.project} · ${fmtDate(r.created_at)}` : "Report"} title={r?.title ?? "Final report"}>
        <Button onClick={() => window.print()}>Print or save as PDF</Button>
        <Button variant="primary" onClick={() => downloadReport(iid).catch((e: Error) => setError(e.message))}>Download Markdown</Button>
      </PageHead>
      <ErrorNote message={error || report.error} />
      {!r && !report.error && <Loading />}
      {r && (
        <article className="card rise space-y-7 p-5 md:p-8">
          <section>
            <p className="flex flex-wrap items-center gap-2"><Chip value={r.severity} /> <Chip value={r.status} /> <span className="font-mono text-sm">Risk {r.risk_score}/100</span> <Method value={r.narrative_method} /></p>
            <p className="mt-3 max-w-3xl text-lg leading-relaxed">{r.summary}</p>
          </section>
          <section>
            <h2 className="border-b border-ink pb-1 font-display text-xl font-bold">Findings</h2>
            <ul className="mt-2 divide-y divide-rule">
              {r.findings.map((f, i) => (
                <li key={i} className="py-2.5">
                  <p className="flex flex-wrap items-center gap-2 font-semibold"><Station domain={f.domain} size={10} /> {f.title} <Confidence value={f.confidence} /> <Method value={f.method} /></p>
                  <p className="text-sm text-muted [overflow-wrap:anywhere]">{f.detail}</p>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="border-b border-ink pb-1 font-display text-xl font-bold">How the problems connect</h2>
            <ul className="mt-2 divide-y divide-rule text-sm">
              {r.hypotheses.map((h, i) => (
                <li key={i} className="py-2">
                  <strong className="font-semibold">{h.source} → {h.target}</strong> <span className="text-muted">({h.relation})</span> <Chip value={h.status} />
                  <span className="mt-0.5 block text-muted">{h.explanation}</span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="border-b border-ink pb-1 font-display text-xl font-bold">What is uncertain</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {r.uncertainties.length ? r.uncertainties.map((u) => <li key={u}>{u}</li>) : <li>Nothing flagged.</li>}
            </ul>
          </section>
          <section>
            <h2 className="border-b border-ink pb-1 font-display text-xl font-bold">Actions</h2>
            <ul className="mt-2 divide-y divide-rule text-sm">
              {r.recommendations.map((a, i) => (
                <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{a.title}{a.verification?.reason && <span className="block text-xs text-muted">{a.verification.reason}</span>}</span>
                  <span className="flex gap-1.5">{a.connector === "simulated" && <Chip value="pending" label="Simulated" />}<Chip value={a.status} /></span>
                </li>
              ))}
            </ul>
          </section>
          {r.tasks.length > 0 && (
            <section>
              <h2 className="border-b border-ink pb-1 font-display text-xl font-bold">Tasks</h2>
              <ul className="mt-2 divide-y divide-rule text-sm">
                {r.tasks.map((t, i) => (
                  <li key={i} className="flex flex-wrap justify-between gap-2 py-2">
                    <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{t.title}</span>
                    <span className="text-muted">{t.owner || "No owner"} · {t.deadline || "No deadline"} · {t.status.replace("_", " ")}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <p className="font-mono text-xs text-muted">{r.evidence.length} evidence records back this report. The Markdown export includes all of them.</p>
        </article>
      )}
    </>
  );
}
