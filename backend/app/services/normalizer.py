"""Converts raw logs, CSVs and transcripts into the common event schema."""
import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from ..schemas import NormalizedEvent

_LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\s+"
    r"(?P<service>[\w.-]+)\s+(?P<msg>.*)$",
    re.IGNORECASE,
)
_KV = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
_UTTERANCE = re.compile(r"^(?:\[(?P<time>\d{1,2}:\d{2})\]\s*)?(?P<speaker>[A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3}):\s+(?P<text>\S.*)$")
_LEVEL_SEVERITY = {
    "WARN": "warning",
    "WARNING": "warning",
    "ERROR": "high",
    "FATAL": "critical",
    "CRITICAL": "critical",
}
TEXT_SUFFIXES = (".log", ".txt", ".csv", ".jsonl", ".md")


class UnsupportedFile(ValueError):
    pass


@dataclass
class ParsedDependency:
    source: str
    target: str
    relation: str
    source_domain: str
    target_domain: str
    origin: str


@dataclass
class NormalizeResult:
    kind: str
    events: list[NormalizedEvent] = field(default_factory=list)
    dependencies: list[ParsedDependency] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace(" ", "T", 1).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _parse_kv(message: str) -> dict:
    return {k: v.strip('"') for k, v in _KV.findall(message)}


def _log_event(ts, level, service, msg, attrs, filename, locator, raw) -> NormalizedEvent:
    level = level.upper()
    if service == "deploy-bot" or msg.lower().startswith("deploy "):
        entity = attrs.get("service", service)
        event_type = "deploy"
        summary = f"Deployed {entity} {attrs.get('version', '')}".strip()
        if attrs.get("change"):
            summary += f" ({attrs['change']})"
        severity = "info"
    else:
        entity = service
        event_type = {"ERROR": "service_error", "FATAL": "service_error", "CRITICAL": "service_error"}.get(
            level, "service_warning" if level in ("WARN", "WARNING") else "service_info"
        )
        summary = f"{service}: {msg}"
        severity = _LEVEL_SEVERITY.get(level, "info")
    return NormalizedEvent(
        domain="infrastructure",
        event_type=event_type,
        severity=severity,
        occurred_at=parse_timestamp(ts).isoformat(),
        entity=entity,
        summary=summary[:500],
        attributes={"level": level, **attrs},
        source_file=filename,
        source_locator=locator,
        raw=raw[:2000],
    )


def normalize_log(filename: str, text: str) -> NormalizeResult:
    result = NormalizeResult("log")
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        locator = f"line {number}"
        try:
            if line.startswith("{"):
                obj = json.loads(line)
                msg = str(obj.get("message") or obj.get("msg") or "")
                attrs = {str(k): v for k, v in obj.items() if k not in ("timestamp", "ts", "level", "service", "message", "msg")}
                result.events.append(
                    _log_event(obj.get("timestamp") or obj["ts"], str(obj["level"]), str(obj["service"]), msg, attrs, filename, locator, line)
                )
                continue
            match = _LOG_LINE.match(line)
            if not match:
                result.rejected.append({"locator": locator, "reason": "Does not match the log format"})
                continue
            msg = match["msg"]
            result.events.append(
                _log_event(match["ts"], match["level"], match["service"], msg, _parse_kv(msg), filename, locator, line)
            )
        except (ValueError, KeyError, TypeError) as exc:
            result.rejected.append({"locator": locator, "reason": f"Invalid log entry: {exc}"})
    return result


def _number(row: dict, key: str, *, required: bool = True, default: float | None = None) -> float | None:
    raw = (row.get(key) or "").strip()
    if raw == "":
        if required:
            raise ValueError(f"{key} is required")
        return default
    value = float(raw)
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        raise ValueError(f"{key} must be a non-negative number")
    return value


def _inventory_row(row: dict, filename: str, locator: str, raw: str, now: datetime) -> NormalizedEvent:
    sku = (row.get("sku") or "").strip()
    if not sku:
        raise ValueError("sku is required")
    on_hand = _number(row, "on_hand")
    demand = _number(row, "daily_demand")
    as_of = parse_timestamp(row["as_of"]) if (row.get("as_of") or "").strip() else now
    attrs = {
        "sku": sku,
        "name": (row.get("name") or sku).strip(),
        "on_hand": on_hand,
        "daily_demand": demand,
        "safety_stock": _number(row, "safety_stock", required=False, default=0.0),
        "supplier_id": (row.get("supplier_id") or "").strip(),
        "inbound_eta_days": _number(row, "inbound_eta_days", required=False),
        "unit_price": _number(row, "unit_price", required=False, default=0.0),
    }
    return NormalizedEvent(
        domain="supply",
        event_type="inventory_snapshot",
        occurred_at=as_of.isoformat(),
        entity=sku,
        summary=f"{attrs['name']}: {on_hand:g} on hand, demand {demand:g}/day",
        attributes=attrs,
        source_file=filename,
        source_locator=locator,
        raw=raw,
    )


def _supplier_row(row: dict, filename: str, locator: str, raw: str, now: datetime) -> NormalizedEvent:
    supplier_id = (row.get("supplier_id") or "").strip()
    sku = (row.get("sku") or "").strip()
    if not supplier_id or not sku:
        raise ValueError("supplier_id and sku are required")
    attrs = {
        "supplier_id": supplier_id,
        "name": (row.get("name") or supplier_id).strip(),
        "sku": sku,
        "lead_time_days": _number(row, "lead_time_days"),
        "unit_cost": _number(row, "unit_cost"),
        "min_order": _number(row, "min_order", required=False, default=0.0),
        "capacity": _number(row, "capacity", required=False),
        "reliability": _number(row, "reliability", required=False, default=0.0),
    }
    return NormalizedEvent(
        domain="supply",
        event_type="supplier_option",
        occurred_at=now.isoformat(),
        entity=sku,
        summary=f"{attrs['name']} can supply {sku} in {attrs['lead_time_days']:g} day{'' if attrs['lead_time_days'] == 1 else 's'} at {attrs['unit_cost']:g}/unit",
        attributes=attrs,
        source_file=filename,
        source_locator=locator,
        raw=raw,
    )


def _task_row(row: dict, filename: str, locator: str, raw: str, now: datetime) -> NormalizedEvent:
    title = (row.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    owner = (row.get("owner") or "").strip()
    return NormalizedEvent(
        domain="execution",
        event_type="task_record",
        severity="info" if owner else "warning",
        occurred_at=now.isoformat(),
        entity=(row.get("task_id") or title).strip()[:200],
        summary=f"Task '{title}': {'owner ' + owner if owner else 'no owner assigned'}",
        attributes={
            "task_id": (row.get("task_id") or "").strip(),
            "title": title,
            "owner": owner,
            "status": (row.get("status") or "open").strip().lower(),
            "deadline": (row.get("deadline") or "").strip(),
            "service": (row.get("service") or "").strip(),
        },
        source_file=filename,
        source_locator=locator,
        raw=raw,
    )


_CSV_SCHEMAS = [
    ("dependencies", {"source", "target"}, None),
    ("inventory", {"sku", "on_hand", "daily_demand"}, _inventory_row),
    ("suppliers", {"supplier_id", "sku", "lead_time_days", "unit_cost"}, _supplier_row),
    ("tasks", {"title", "owner"}, _task_row),
]


def normalize_csv(filename: str, text: str, now: datetime) -> NormalizeResult:
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or []) if h}
    reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
    for kind, required, builder in _CSV_SCHEMAS:
        if required <= headers:
            break
    else:
        expected = "; ".join(", ".join(sorted(r)) for _, r, _ in _CSV_SCHEMAS)
        raise UnsupportedFile(f"Unrecognised CSV columns. Expected one of: {expected}")
    result = NormalizeResult(kind)
    for number, row in enumerate(reader, 2):
        locator = f"row {number}"
        raw = ",".join(str(v) for v in row.values() if not isinstance(v, list))
        try:
            if kind == "dependencies":
                source, target = (row.get("source") or "").strip(), (row.get("target") or "").strip()
                if not source or not target:
                    raise ValueError("source and target are required")
                if source == target:
                    raise ValueError("a dependency cannot point at itself")
                result.dependencies.append(
                    ParsedDependency(
                        source,
                        target,
                        (row.get("relation") or "depends").strip(),
                        (row.get("source_domain") or "infrastructure").strip(),
                        (row.get("target_domain") or "infrastructure").strip(),
                        f"{filename} {locator}",
                    )
                )
            else:
                result.events.append(builder(row, filename, locator, raw, now))
        except (ValueError, TypeError) as exc:
            result.rejected.append({"locator": locator, "reason": str(exc)})
    return result


def looks_like_transcript(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    return sum(1 for ln in lines if _UTTERANCE.match(ln)) >= max(2, len(lines) // 2)


def normalize_transcript(filename: str, text: str, now: datetime) -> NormalizeResult:
    result = NormalizeResult("transcript")
    meeting_date: date = now.date()
    meeting_name = ""
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        locator = f"line {number}"
        lowered = line.lower()
        if lowered.startswith("date:"):
            try:
                meeting_date = date.fromisoformat(line.split(":", 1)[1].strip())
            except ValueError:
                result.rejected.append({"locator": locator, "reason": "Date header is not YYYY-MM-DD"})
            continue
        if lowered.startswith("meeting:"):
            meeting_name = line.split(":", 1)[1].strip()
            continue
        match = _UTTERANCE.match(line)
        if not match:
            result.rejected.append({"locator": locator, "reason": "Not in 'Speaker: text' form"})
            continue
        occurred = now
        if match["time"]:
            hour, minute = map(int, match["time"].split(":"))
            if hour > 23 or minute > 59:
                result.rejected.append({"locator": locator, "reason": "Invalid time"})
                continue
            occurred = datetime(meeting_date.year, meeting_date.month, meeting_date.day, hour, minute, tzinfo=UTC)
        result.events.append(
            NormalizedEvent(
                domain="communication",
                event_type="utterance",
                occurred_at=occurred.isoformat(),
                entity=match["speaker"],
                summary=match["text"][:500],
                attributes={"speaker": match["speaker"], "meeting": meeting_name},
                source_file=filename,
                source_locator=locator,
                raw=line[:2000],
            )
        )
    return result


def normalize_file(filename: str, text: str, now: datetime) -> NormalizeResult:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return normalize_csv(filename, text, now)
    if lowered.endswith((".log", ".jsonl")):
        return normalize_log(filename, text)
    if lowered.endswith((".txt", ".md")):
        return normalize_transcript(filename, text, now) if looks_like_transcript(text) else normalize_log(filename, text)
    raise UnsupportedFile(f"Unsupported file type. Allowed: {', '.join(TEXT_SUFFIXES)}")
