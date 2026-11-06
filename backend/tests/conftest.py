import os
import uuid

os.environ["NEXUS_ENV"] = "test"
os.environ.setdefault("NEXUS_DATABASE_URL", "sqlite://")  # CI also runs these on PostgreSQL
os.environ["NEXUS_JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-signing"
os.environ["OPENAI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def fresh_db():
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, org="Acme") -> dict:
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/auth/register", json={"organization": org, "name": "Admin", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    return auth(res.json()["token"])


def add_user(client, admin_headers, role: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/users", headers=admin_headers, json={"name": role, "email": email, "password": PASSWORD, "role": role})
    assert res.status_code == 201, res.text
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return auth(login.json()["token"])


def project(client, headers) -> str:
    return client.post("/api/projects", headers=headers, json={"name": "Checkout"}).json()["id"]


def investigate(client, headers, project_id) -> dict:
    assert client.post(f"/api/projects/{project_id}/demo", headers=headers).status_code == 200
    res = client.post(f"/api/projects/{project_id}/investigations", headers=headers)
    assert res.status_code == 202, res.text
    # TestClient runs the background task before returning.
    return client.get(f"/api/incidents/{res.json()['id']}", headers=headers).json()
