"""Engine and session handling. SQLite for local runs, PostgreSQL through DATABASE_URL."""
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Always timezone-aware UTC in Python, whichever database is underneath."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to UTCDateTime")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if ":memory:" in url or url == "sqlite://":
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _pragmas(conn, _):  # pragma: no cover - trivial
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if ":memory:" not in url and url != "sqlite://":
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401 - registers tables

    Base.metadata.create_all(engine)


def fail_interrupted_investigations() -> int:
    """Investigations run inside the API process, so any still 'running' at startup died with the last one."""
    from .models import Incident
    from .services import audit

    with session_scope() as db:
        stuck = db.scalars(select(Incident).where(Incident.status == "running")).all()
        for incident in stuck:
            incident.status = "failed"
            incident.title = "Investigation interrupted"
            incident.error = "The server restarted during this investigation. Run it again."
            audit.record(db, incident.tenant_id, "system", "investigation.interrupted", "incident", incident.id, {})
        return len(stuck)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
