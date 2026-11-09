from app.db.session import SessionLocal
from app.models import AdmissionApplication, User
from app.services.duplicates import detect_duplicates, similarity

A = {"full_name": "ANANYA RAO", "date_of_birth": "14/06/2008", "sslc_register_number": "1234567", "puc_register_number": "87654321"}


def test_similarity():
    s, why = similarity(A, {**A, "full_name": "Rao Ananya"})
    assert s >= 0.85 and "Same date of birth" in why
    s, why = similarity(A, {"full_name": "ROHAN SHETTY", "date_of_birth": "01/01/2007", "sslc_register_number": "1234567"})
    assert s >= 0.9 and "Same SSLC register number" in why  # an identifier match always gets flagged
    assert similarity(A, {"full_name": "ROHAN SHETTY", "date_of_birth": "01/01/2007", "sslc_register_number": "999", "puc_register_number": "888"})[0] < 0.6


def login_admin(client):
    t = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def submit_directly(email, values, make_user):
    h = make_user(email)
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).one()
        app = db.query(AdmissionApplication).filter_by(user_id=user.id).one()
        app.status, app.form_data = "submitted", {"final": values}
        db.commit()
        return h, app.id


def test_duplicates_and_admin_review(client, make_user):
    h1, id1 = submit_directly("dup1@example.com", A, make_user)
    h2, id2 = submit_directly("dup2@example.com", {**A, "full_name": "Ananya  Rao"}, make_user)
    _, id3 = submit_directly("other@example.com", {"full_name": "KARTHIK NAIK", "date_of_birth": "02/02/2005",
                                                  "sslc_register_number": "5555555", "puc_register_number": "4444"}, make_user)
    with SessionLocal() as db:
        found = detect_duplicates(db, db.get(AdmissionApplication, id2))
        assert [(r.matched_application_id) for r in found] == [id1]
        assert detect_duplicates(db, db.get(AdmissionApplication, id3)) == []

    adm = login_admin(client)
    student = make_user("plain@example.com")
    assert client.get("/api/admin/stats", headers=student).status_code == 403
    assert client.get("/api/admin/stats").status_code == 401
    st = client.get("/api/admin/stats", headers=adm).json()
    assert st["pending_review"] >= 3 and st["total_applications"] >= st["pending_review"]

    # search by name and by register number
    assert [a["id"] for a in client.get("/api/admin/applications?q=karthik", headers=adm).json()] == [id3]
    assert {a["id"] for a in client.get("/api/admin/applications?q=87654321", headers=adm).json()} == {id1, id2}
    dup_row = next(a for a in client.get("/api/admin/applications?q=dup2", headers=adm).json())
    assert dup_row["possible_duplicates"] == 1

    detail = client.get(f"/api/admin/applications/{id2}", headers=adm).json()
    assert detail["student"]["email"] == "dup2@example.com" and detail["duplicates"][0]["other_application_id"] == id1
    assert detail["duplicates"][0]["reasons"] and detail["status"] == "submitted"
    assert client.get("/api/admin/applications/99999", headers=adm).status_code == 404
    assert client.post(f"/api/admin/duplicates/{detail['duplicates'][0]['id']}/review", headers=adm).json()["reviewed"] is True

    # review decisions
    assert client.post(f"/api/admin/applications/{id2}/review", json={"decision": "correction_requested"}, headers=adm).status_code == 422
    assert client.post(f"/api/admin/applications/{id2}/review", json={"decision": "maybe"}, headers=adm).status_code == 422
    assert client.post(f"/api/admin/applications/{id2}/review", json={"decision": "correction_requested", "comments": "Fix the name spelling"}, headers=adm).json()["status"] == "correction_requested"
    me = client.get("/api/applications/me", headers=h2).json()
    assert me["status"] == "correction_requested" and me["review_comment"] == "Fix the name spelling"
    assert client.get("/api/applications/me/form", headers=h2).json()["editable"] is True  # student can fix and resubmit
    assert client.post(f"/api/admin/applications/{id2}/review", json={"decision": "approved"}, headers=adm).status_code == 409
    assert client.post(f"/api/admin/applications/{id1}/review", json={"decision": "approved"}, headers=adm).json()["status"] == "approved"
    hist = client.get(f"/api/admin/applications/{id1}", headers=adm).json()["history"]
    assert hist[0]["decision"] == "approved" and hist[0]["admin"] == "admin@example.com"
