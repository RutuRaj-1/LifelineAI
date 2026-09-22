def test_register_and_login(client):
    r = client.post("/api/auth/register", json={
        "email": "alice@example.com", "password": "supersecret1", "full_name": "Alice Test", "role": "patient",
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    assert r.json()["user"]["role"] == "patient"

    r2 = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "supersecret1"})
    assert r2.status_code == 200

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "email": "bob@example.com", "password": "supersecret1", "full_name": "Bob Test", "role": "patient",
    })
    r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_duplicate_email_rejected(client):
    body = {"email": "dup@example.com", "password": "supersecret1", "full_name": "Dup", "role": "patient"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_unauthenticated_request_rejected(client):
    r = client.get("/api/patient/me")
    assert r.status_code == 401
