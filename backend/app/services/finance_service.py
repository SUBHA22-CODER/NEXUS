"""Deterministic payments/finance analysis. All money math is pure Python."""
from collections import defaultdict


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[int(len(ordered) * 0.95) - 1] if len(ordered) >= 20 else ordered[-1], 1)


def analyze(events: list[dict]) -> dict:
    """Returns {"assessments": [...]}, one per payment gateway, plus aggregate
    transaction success rate, backlog, revenue exposure and latency."""
    txs = [e for e in events if e["event_type"] == "transaction"]
    by_gateway: dict[str, list[dict]] = defaultdict(list)
    for e in txs:
        by_gateway[e["entity"]].append(e)

    assessments: list[dict] = []
    for gw in sorted(by_gateway):
        evs = by_gateway[gw]
        n = len(evs)
        ok = sum(1 for e in evs if e["attributes"].get("status") == "success")
        bad = [e for e in evs if e["attributes"].get("status") in ("failed", "timeout", "declined")]
        rate = ok / n if n else 0.0
        backlog = sum(1 for e in bad if e["attributes"].get("status") in ("failed", "timeout"))
        exposure = round(sum(float(e["attributes"].get("amount") or 0) for e in bad), 2)
        latencies = [float(e["attributes"]["latency_ms"]) for e in evs if e["attributes"].get("latency_ms") is not None]
        if n and rate >= 0.95 and not backlog:
            risk = "low"
            sev = "info"
        elif rate < 0.8 or backlog >= 5:
            risk = "critical"
            sev = "critical"
        else:
            risk = "high"
            sev = "high"
        assessments.append({
            "kind": "payment_health",
            "entity": gw,
            "risk_level": risk,
            "severity": sev,
            "title": f"{gw}: {rate * 100:.0f}% transaction success",
            "detail": f"{ok}/{n} transactions succeeded; {backlog} failed or timed out; "
            f"{exposure:,.2f} of revenue exposure."
            + (f" p95 latency {_p95(latencies)} ms." if latencies else ""),
            "affected": [gw],
            "metrics": {
                "success_rate": round(rate, 3), "total": n, "succeeded": ok,
                "backlog": backlog, "revenue_exposure": exposure, "p95_latency_ms": _p95(latencies),
            },
        })

    return {"assessments": assessments}
