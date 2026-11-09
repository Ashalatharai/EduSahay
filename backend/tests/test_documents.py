import base64
import os

from app.core.config import settings

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PDF = b"%PDF-1.4\n%fake test pdf\n"


def up(c, h, slot, name, data, mime="application/octet-stream"):
    return c.post(f"/api/documents/{slot}", files={"file": (name, data, mime)}, headers=h)


def test_documents_flow(client, make_user):
    c = client
    h = make_user("docs@example.com")
    other = make_user("other@example.com")
    admin = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
        "email": "admin@example.com", "password": "AdminPass123"}).json()["access_token"]}

    # access and validation
    assert c.post("/api/documents/aadhaar", files={"file": ("a.png", PNG)}).status_code == 401
    assert up(c, h, "passport", "a.png", PNG).status_code == 404
    assert up(c, h, "aadhaar", "a.gif", b"GIF89a").status_code == 400
    assert up(c, h, "aadhaar", "fake.png", b"just text").status_code == 400
    assert up(c, h, "aadhaar", "empty.png", b"").status_code == 400
    assert up(c, h, "aadhaar", "big.png", PNG[:8] + b"0" * (1024 * 1024)).status_code == 413
    assert c.get("/api/applications/me", headers=h).json()["status"] == "documents_not_uploaded"

    # upload, private retrieval, encryption at rest
    r = up(c, h, "aadhaar", "aadhaar.png", PNG)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert "stored_path" not in r.text
    assert c.get(f"/api/documents/{doc_id}/file", headers=h).content == PNG
    assert c.get(f"/api/documents/{doc_id}/file").status_code == 401
    assert c.get(f"/api/documents/{doc_id}/file", headers=other).status_code == 404
    assert c.get(f"/api/documents/{doc_id}/file", headers=admin).status_code == 200
    stored = [open(os.path.join(settings.storage_dir, f), "rb").read() for f in os.listdir(settings.storage_dir)]
    assert stored and all(PNG not in s for s in stored)

    # replace keeps one active document per slot
    r2 = up(c, h, "aadhaar", "aadhaar2.png", PNG)
    assert c.get(f"/api/documents/{doc_id}/file", headers=h).status_code == 404
    docs = c.get("/api/documents", headers=h).json()
    assert [d["slot"] for d in docs] == ["aadhaar"] and docs[0]["id"] == r2.json()["id"]

    # status follows uploads
    up(c, h, "sslc", "sslc.pdf", PDF)
    assert c.get("/api/applications/me", headers=h).json()["status"] == "documents_not_uploaded"
    puc = up(c, h, "puc", "puc.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20)
    assert puc.status_code == 201
    assert c.get("/api/applications/me", headers=h).json()["status"] == "documents_uploaded"

    # delete
    assert c.delete(f"/api/documents/{puc.json()['id']}", headers=other).status_code == 404
    assert c.delete(f"/api/documents/{puc.json()['id']}", headers=h).status_code == 204
    assert c.get("/api/applications/me", headers=h).json()["status"] == "documents_not_uploaded"
