import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    STORAGE_DIR=f"{_tmp}/storage",
    ADMIN_EMAIL="admin@example.com",
    ADMIN_PASSWORD="AdminPass123",
    MAX_UPLOAD_MB="1",
    OCR_ENABLED="false",
    CLASSIFIER_PATH=f"{_tmp}/doc_classifier.pt",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def make_user(client):
    def _make(email, password="password123"):
        client.post("/api/auth/register", json={"full_name": "Test User", "email": email, "password": password, "consent": True})
        token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
