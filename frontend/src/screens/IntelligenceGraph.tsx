import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useProject } from "../App";
import { get, type Domain, type GraphData } from "../api";
import { Chip, Confidence, DOMAIN, Empty, ErrorNote, Loading, PageHead, Station, useData } from "../ui";

const DEFAULT_LANES: Domain[] = ["communication", "infrastructure", "supply", "execution"];
const COL = 178;
const ROW = 92;
const LEFT = 150;
const TOP = 46;

function wrap(label: string, max = 20, lines = 3): string[] {
  const out: string[] = [];
  let line = "";
  for (const word of label.split(" ")) {
    if (line && (line + " " + word).length > max) {
      out.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) out.push(line);
  return out.length > lines ? [...out.slice(0, lines - 1), `${out[lines - 1].slice(0, max - 1)}…`] : out;
}

/** Stations go in a lane per domain and a column per step along the longest route that reaches them. */
function layout(graph: GraphData) {
  const depth = new Map(graph.nodes.map((n) => [n.id, 0]));
  // Bounded by node count, so a cycle in the input cannot hang the page.
  for (let i = 0; i < graph.nodes.length; i++) {
    for (const e of graph.edges) {
      if (e.source !== e.target) {
        const next = (depth.get(e.source) ?? 0) + 1;
        if (next > (depth.get(e.target) ?? 0) && next <= graph.nodes.length) depth.set(e.target, next);
      }
    }
  }
  // A feeder such as a supplier sits just before what it feeds, not at the far left with a long line across.
  for (let i = 0; i < graph.nodes.length; i++) {
    for (const n of graph.nodes) {
      const targets = graph.edges.filter((e) => e.source === n.id && e.target !== n.id).map((e) => depth.get(e.target) ?? 0);
      const hasInput = graph.edges.some((e) => e.target === n.id);
      if (targets.length && !hasInput) depth.set(n.id, Math.max(0, Math.min(...targets) - 1));
    }
  }
  const slots = new Map<string, number>();
  const placed = graph.nodes.map((n) => {
    const key = `${n.domain}:${depth.get(n.id)}`;
    const stack = slots.get(key) ?? 0;
    slots.set(key, stack + 1);
    return { ...n, col: depth.get(n.id) ?? 0, stack };
  });

  const nodeDomains = Array.from(new Set(graph.nodes.map((n) => n.domain)));
  const lanes = [...DEFAULT_LANES, ...nodeDomains.filter((d) => !DEFAULT_LANES.includes(d))];

  const laneRows = new Map<Domain, number>(lanes.map((d) => [d, 1]));
  placed.forEach((n) => laneRows.set(n.domain, Math.max(laneRows.get(n.domain) ?? 1, n.stack + 1)));
  const laneY = new Map<Domain, number>();
  let y = TOP;
  for (const d of lanes) {
    laneY.set(d, y);
    y += (laneRows.get(d) ?? 1) * ROW;
  }
  const pos = new Map(placed.map((n) => [n.id, { x: LEFT + n.col * COL, y: (laneY.get(n.domain) ?? 0) + n.stack * ROW }]));
  const cols = Math.max(...placed.map((n) => n.col), 0) + 1;
  return { placed, pos, laneY, laneRows, lanes, width: LEFT + cols * COL + 40, height: y };
}

function edgePath(a: { x: number; y: number }, b: { x: number; y: number }) {
  if (a.y === b.y && Math.abs(a.x - b.x) > 0) return `M${a.x} ${a.y} L${b.x} ${b.y}`;
  const mid = (a.x + b.x) / 2;
  return `M${a.x} ${a.y} C${mid} ${a.y} ${mid} ${b.y} ${b.x} ${b.y}`;
}

export default function IntelligenceGraph() {
  const { iid = "" } = useParams();
  const { project } = useProject();
  const graph = useData(() => get<GraphData>(`/incidents/${iid}/graph`), [iid]);
  const [selected, setSelected] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const shape = useMemo(() => (graph.data?.nodes.length ? layout(graph.data) : null), [graph.data]);

  if (graph.error) return <ErrorNote message={graph.error} />;
  if (!graph.data) return <Loading />;
  const { edges, nodes } = graph.data;
  const domainOf = new Map(nodes.map((n) => [n.id, n.domain]));
  const active = (i: number) => {
    if (selected !== null) return selected === i;
    if (focus) return edges[i].source === focus || edges[i].target === focus;
    return true;
  };
  const visible = focus ? edges.map((e, i) => ({ e, i })).filter(({ e }) => e.source === focus || e.target === focus) : edges.map((e, i) => ({ e, i }));
  const crossing = edges.filter((e) => domainOf.get(e.source) !== domainOf.get(e.target)).length;

  return (
    <>
      <PageHead eyebrow="How the problems connect" title="Intelligence Graph">
        <span className="font-mono text-sm">{edges.length} links, {crossing} cross-domain</span>
      </PageHead>
      {!shape ? (
        <Empty title="No connections found"><p className="text-muted">This investigation didn't find links between entities.</p></Empty>
      ) : (
        <div className="space-y-5">
          <div className="card rise overflow-x-auto p-2">
            <svg
              width={shape.width}
              height={shape.height}
              viewBox={`0 0 ${shape.width} ${shape.height}`}
              role="group"
              aria-label="Map of connections between infrastructure, supply, communication and execution"
              onClick={(e) => { if (e.target === e.currentTarget) { setSelected(null); setFocus(null); } }}
            >
              {shape.lanes.map((d) => {
                const y = shape.laneY.get(d) ?? 0;
                const dom = DOMAIN[d] || DOMAIN.infrastructure;
                return (
                  <g key={d}>
                    <line x1={0} x2={shape.width} y1={y} y2={y} stroke={dom.color} strokeOpacity={0.14} strokeWidth={22} />
                    <text x={6} y={y + 4} fontFamily="var(--font-mono)" fontSize={10} fontWeight={600} fill={dom.color} style={{ textTransform: "uppercase" }}>{dom.label}</text>
                  </g>
                );
              })}
              {edges.map((e, i) => {
                const a = shape.pos.get(e.source)!;
                const b = shape.pos.get(e.target)!;
                const color = (DOMAIN[domainOf.get(e.source) ?? "infrastructure"] || DOMAIN.infrastructure).color;
                const on = active(i);
                return (
                  <g key={i} className="cursor-pointer" onClick={() => { setSelected(selected === i ? null : i); setFocus(null); }}>
                    <path d={edgePath(a, b)} fill="none" stroke="transparent" strokeWidth={20} />
                    <path
                      d={edgePath(a, b)}
                      fill="none"
                      stroke={color}
                      strokeWidth={selected === i ? 8 : 5.5}
                      strokeLinecap="round"
                      strokeOpacity={on ? 1 : 0.14}
                      strokeDasharray={e.status === "inferred" ? "3 10" : undefined}
                      className={e.status === "inferred" ? "route-dashed" : "route-draw"}
                      style={{ animationDelay: `${i * 0.04}s`, transition: "stroke-opacity .15s" }}
                    />
                    <title>{e.source} → {e.target}: {e.relation}</title>
                  </g>
                );
              })}
              {shape.placed.map((n) => {
                const p = shape.pos.get(n.id)!;
                const lines = wrap(n.label);
                const dim = focus && focus !== n.id && !edges.some((e) => (e.source === focus && e.target === n.id) || (e.target === focus && e.source === n.id));
                const nodeDom = DOMAIN[n.domain] || DOMAIN.infrastructure;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${p.x} ${p.y})`}
                    className="cursor-pointer"
                    opacity={dim ? 0.3 : 1}
                    tabIndex={0}
                    role="button"
                    aria-label={`${n.label}, ${nodeDom.label}. Show its links.`}
                    onClick={() => { setFocus(focus === n.id ? null : n.id); setSelected(null); }}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFocus(focus === n.id ? null : n.id); setSelected(null); } }}
                  >
                    <circle r={focus === n.id ? 13 : 10} fill="var(--color-card)" stroke={focus === n.id ? "var(--color-ink)" : nodeDom.color} strokeWidth={5} />
                    {lines.map((line, i) => (
                      <text key={i} y={26 + i * 13} textAnchor="middle" fontSize={11.5} fontWeight={600} fill="var(--color-ink)" paintOrder="stroke" stroke="var(--color-card)" strokeWidth={3.5}>{line}</text>
                    ))}
                  </g>
                );
              })}
            </svg>
          </div>
          <p className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
            <span className="flex items-center gap-2"><svg width="34" height="6" aria-hidden><line x1="2" x2="32" y1="3" y2="3" stroke="currentColor" strokeWidth="4" strokeLinecap="round" /></svg> Observed in the data</span>
            <span className="flex items-center gap-2"><svg width="34" height="6" aria-hidden><line x1="2" x2="32" y1="3" y2="3" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 7" /></svg> Inferred, not proven</span>
            <span>Select a station or line to focus it.</span>
            {(focus || selected !== null) && <button type="button" className="cursor-pointer font-semibold text-ink underline" onClick={() => { setFocus(null); setSelected(null); }}>Clear focus</button>}
          </p>
          <section>
            <h2 className="font-display text-xl font-bold">{focus ? `Links for ${focus}` : "All links"}</h2>
            <ul className="mt-2 divide-y divide-rule border-y border-rule">
              {visible.map(({ e, i }) => (
                <li key={i} className={selected === i ? "bg-ink/5" : ""}>
                  <button type="button" onClick={() => setSelected(selected === i ? null : i)} className="w-full cursor-pointer px-2 py-3 text-left">
                    <span className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                      <Station domain={domainOf.get(e.source) ?? "infrastructure"} size={10} /> {e.source}
                      <span className="font-mono text-xs font-normal text-muted">— {e.relation} →</span>
                      <Station domain={domainOf.get(e.target) ?? "infrastructure"} size={10} /> <span className="[overflow-wrap:anywhere]">{e.target}</span>
                      <Chip value={e.status} /> <Confidence value={e.confidence} />
                    </span>
                    <span className="mt-1 block text-sm text-muted">{e.explanation}</span>
                  </button>
                  {selected === i && e.evidence_ids.length > 0 && (
                    <Link to={`/p/${project.id}/i/${iid}/evidence?ids=${e.evidence_ids.join(",")}`} className="block px-2 pb-3 text-sm font-semibold underline">
                      View {e.evidence_ids.length} source{e.evidence_ids.length === 1 ? "" : "s"} →
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}
