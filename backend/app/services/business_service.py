"""Deterministic supply calculations. The LLM may explain these numbers but never produces them."""
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StockoutRisk:
    usable_units: float
    daily_demand: float
    days_of_cover: float | None  # None means demand is zero, so stock never runs out
    replenishment_days: float
    coverage_gap_days: float
    units_short: int
    risk_level: str
    formula: str

    def to_dict(self) -> dict:
        return asdict(self)


def classify_risk(days_of_cover: float | None, gap_days: float) -> str:
    if days_of_cover is None or gap_days <= 0:
        return "low"
    if days_of_cover <= 2:
        return "critical"
    return "high"


def stockout_risk(
    on_hand: float,
    daily_demand: float,
    replenishment_days: float,
    safety_stock: float = 0,
    committed_units: float = 0,
) -> StockoutRisk:
    """Days of cover = usable stock / demand. Gap = replenishment time - days of cover, floored at zero.

    Assumes constant demand. `committed_units` are held-up orders that will draw on stock once they
    are released.
    """
    for name, value in {
        "on_hand": on_hand,
        "daily_demand": daily_demand,
        "replenishment_days": replenishment_days,
        "safety_stock": safety_stock,
        "committed_units": committed_units,
    }.items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite, non-negative number, got {value}")
    usable = max(0.0, on_hand - safety_stock - committed_units)
    if daily_demand == 0:
        return StockoutRisk(usable, 0.0, None, replenishment_days, 0.0, 0, "low", "Zero demand: no stockout expected")
    cover = usable / daily_demand
    gap = max(0.0, replenishment_days - cover)
    deductions = ""
    if safety_stock:
        deductions += f" - {safety_stock:g} safety"
    if committed_units:
        deductions += f" - {committed_units:g} committed"
    return StockoutRisk(
        usable_units=usable,
        daily_demand=daily_demand,
        days_of_cover=round(cover, 2),
        replenishment_days=replenishment_days,
        coverage_gap_days=round(gap, 2),
        units_short=math.ceil(round(gap * daily_demand, 6)),
        risk_level=classify_risk(cover, gap),
        formula=(
            f"cover = ({on_hand:g}{deductions}) / {daily_demand:g} per day = {cover:.2f} days; "
            f"gap = max(0, {replenishment_days:g} - {cover:.2f}) = {gap:.2f} days"
        ),
    )


def compare_suppliers(
    options: list[dict], days_of_cover: float, units_short: int, daily_demand: float, unit_price: float
) -> list[dict]:
    """Rank alternatives by remaining shortfall, then total cost, then reliability.

    Order quantity is what the shortfall needs, raised to the supplier's minimum order and capped at capacity.
    """
    ranked = []
    for opt in options:
        lead = float(opt["lead_time_days"])
        qty = max(units_short, int(opt.get("min_order", 0) or 0))
        capacity = opt.get("capacity")
        if capacity not in (None, ""):
            qty = min(qty, int(capacity))
        days_exposed = max(0.0, lead - days_of_cover)
        lost_units = math.ceil(round(days_exposed * daily_demand, 6))
        unit_cost = float(opt["unit_cost"])
        cost = round(qty * unit_cost, 2)
        ranked.append(
            {
                "supplier_id": opt["supplier_id"],
                "name": opt.get("name", opt["supplier_id"]),
                "lead_time_days": lead,
                "unit_cost": unit_cost,
                "reliability": float(opt.get("reliability", 0) or 0),
                "order_units": qty,
                "estimated_cost": cost,
                "days_exposed": round(days_exposed, 2),
                "units_lost_before_arrival": lost_units,
                "revenue_at_risk_remaining": round(lost_units * unit_price, 2),
                "closes_gap": days_exposed == 0,
                "covers_shortfall": qty >= units_short,
                "event_id": opt.get("event_id"),
            }
        )
    ranked.sort(key=lambda r: (not r["covers_shortfall"], r["units_lost_before_arrival"], r["estimated_cost"], -r["reliability"]))
    return ranked
