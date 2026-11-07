"""Upload validation and persistence. Re-uploading the same file adds nothing (idempotent by content)."""
import hashlib
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import utcnow
from ..models import Dependency, OperationalEvent, UploadedFile, User
from . import audit
from .normalizer import UnsupportedFile, normalize_file, parse_timestamp


class IngestionError(ValueError):
    pass


def _safe_name(filename: str) -> str:
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    if not name:
        raise IngestionError("File has no name")
    return name[:200]


def ingest_bytes(db: Session, user: User, project_id: uuid.UUID, filename: str, content: bytes) -> dict:
    settings = get_settings()
    name = _safe_name(filename)
    if len(content) > settings.max_upload_bytes:
        raise IngestionError(f"{name} exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    if not content.strip():
        raise IngestionError(f"{name} is empty")
    if b"\x00" in content[:4096]:
        raise IngestionError(f"{name} looks like a binary file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestionError(f"{name} is not valid UTF-8") from None
    if text.count("\n") > settings.max_lines_per_file:
        raise IngestionError(f"{name} has more than {settings.max_lines_per_file} lines")

    try:
        result = normalize_file(name, text, utcnow())
    except UnsupportedFile as exc:
        raise IngestionError(f"{name}: {exc}") from None
    if not result.events and not result.dependencies:
        reason = result.rejected[0]["reason"] if result.rejected else "no usable records"
        raise IngestionError(f"{name}: nothing could be read ({reason})")

    existing = set(db.scalars(select(OperationalEvent.dedupe_key).where(OperationalEvent.project_id == project_id)))
    added = 0
    for ev in result.events:
        # Keyed on content, not time, so timeless CSV rows still dedupe on re-upload.
        key = hashlib.sha256(f"{name}|{ev.source_locator}|{ev.event_type}|{ev.raw}".encode()).hexdigest()
        if key in existing:
            continue
        existing.add(key)
        db.add(
            OperationalEvent(
                tenant_id=user.tenant_id,
                project_id=project_id,
                domain=ev.domain,
                event_type=ev.event_type,
                severity=ev.severity,
                occurred_at=parse_timestamp(ev.occurred_at),
                entity=ev.entity,
                summary=ev.summary,
                attributes=ev.attributes,
                source_file=ev.source_file,
                source_locator=ev.source_locator,
                raw=ev.raw,
                dedupe_key=key,
                ingested_at=utcnow(),
            )
        )
        added += 1

    deps_added = 0
    known = {(d.source, d.target) for d in db.scalars(select(Dependency).where(Dependency.project_id == project_id))}
    for dep in result.dependencies:
        if (dep.source, dep.target) in known:
            continue
        known.add((dep.source, dep.target))
        db.add(
            Dependency(
                tenant_id=user.tenant_id,
                project_id=project_id,
                source=dep.source,
                target=dep.target,
                relation=dep.relation,
                source_domain=dep.source_domain,
                target_domain=dep.target_domain,
                origin=dep.origin,
            )
        )
        deps_added += 1

    file_rec = UploadedFile(
        tenant_id=user.tenant_id,
        project_id=project_id,
        filename=name,
        file_type=result.kind,
        file_size=len(content),
        status="processed" if not result.rejected else ("partial" if (added or deps_added) else "failed"),
        events_count=added,
        dependencies_count=deps_added,
        created_by=user.email,
    )
    db.add(file_rec)
    db.flush()

    audit.record(
        db, user.tenant_id, user.email, "data.ingested", "project", project_id,
        {"file": name, "kind": result.kind, "events_added": added, "dependencies_added": deps_added, "rejected": len(result.rejected)},
    )
    return {
        "id": str(file_rec.id),
        "file": name,
        "kind": result.kind,
        "file_size": len(content),
        "events_added": added,
        "dependencies_added": deps_added,
        "duplicates_skipped": len(result.events) + len(result.dependencies) - added - deps_added,
        "rejected": result.rejected[:50],
        "rejected_count": len(result.rejected),
    }


def record_failed_file(db: Session, user: User, project_id: uuid.UUID, filename: str, content_size: int, error_msg: str) -> UploadedFile:
    file_rec = UploadedFile(
        tenant_id=user.tenant_id,
        project_id=project_id,
        filename=_safe_name(filename),
        file_type=filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown",
        file_size=content_size,
        status="failed",
        events_count=0,
        dependencies_count=0,
        error_message=error_msg[:1000],
        created_by=user.email,
    )
    db.add(file_rec)
    db.flush()
    return file_rec


def delete_uploaded_file(db: Session, user: User, project_id: uuid.UUID, file_id: uuid.UUID) -> bool:
    from sqlalchemy import delete

    file_rec = db.get(UploadedFile, file_id)
    if not file_rec or file_rec.project_id != project_id or file_rec.tenant_id != user.tenant_id:
        return False

    filename = file_rec.filename
    # Delete associated operational events
    db.execute(
        delete(OperationalEvent).where(
            OperationalEvent.project_id == project_id,
            OperationalEvent.source_file == filename,
        )
    )
    # Delete associated dependencies
    db.execute(
        delete(Dependency).where(
            Dependency.project_id == project_id,
            Dependency.origin.startswith(filename),
        )
    )
    db.delete(file_rec)
    audit.record(
        db, user.tenant_id, user.email, "file.deleted", "uploaded_file", file_id,
        {"filename": filename},
    )
    db.commit()
    return True
