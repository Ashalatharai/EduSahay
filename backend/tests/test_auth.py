from sqlalchemy import inspect

from app.db.session import engine

STUDENT = {"full_name": "Test Student", "email": "Student@Example.com", "password": "password123", "consent": True}


def login(c, email, pw):
    return c.post("/api/auth/login", json={"email": email, "password": pw})


def test_all_flows(client):
    c = client
    assert len(inspect(engine).get_table_names()) >= 10
    assert c.post("/api/auth/register", json={**STUDENT, "consent": False}).status_code == 422
    assert c.post("/api/auth/register", json={**STUDENT, "password": "short"}).status_code == 422
    r = c.post("/api/auth/register", json=STUDENT)
    assert r.status_code == 201 and r.json()["role"] == "student"
    assert "password" not in r.text
    assert c.post("/api/auth/register", json=STUDENT).status_code == 409

    assert login(c, "student@example.com", "wrong").status_code == 401
    t = login(c, "STUDENT@example.com", "password123")
    assert t.status_code == 200
    h = {"Authorization": f"Bearer {t.json()['access_token']}"}

    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/auth/me", headers=h).json()["email"] == "student@example.com"
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401

    assert c.get("/api/admin/stats", headers=h).status_code == 403
    assert c.get("/api/admin/stats").status_code == 401
    at = login(c, "admin@example.com", "AdminPass123").json()
    assert at["user"]["role"] == "admin"
    assert c.get("/api/admin/stats", headers={"Authorization": f"Bearer {at['access_token']}"}).status_code == 200
