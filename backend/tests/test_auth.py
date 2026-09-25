"""D13 — access control: token signing, login, the protected gate, owner-only allowlist mgmt."""
from __future__ import annotations

from app.services import access_service
from app.services.token_service import make_token, verify_token


# ── token unit tests ─────────────────────────────────────────────────────────
def test_token_round_trip_and_tamper():
    tok = make_token("a@b.com", True, secret="s1")
    payload = verify_token(tok, secret="s1")
    assert payload["email"] == "a@b.com" and payload["owner"] is True
    assert verify_token(tok, secret="other") is None       # wrong secret
    assert verify_token(tok[:-2] + "xx", secret="s1") is None  # tampered signature


def test_expired_token_rejected():
    tok = make_token("a@b.com", False, ttl_hours=-1, secret="s1")
    assert verify_token(tok, secret="s1") is None


# ── login + gate (real auth via anon_client) ─────────────────────────────────
async def test_protected_route_requires_auth(anon_client, async_session):
    r = await anon_client.get("/api/v1/engagements/clients")
    assert r.status_code == 401  # gate is closed without a token


async def test_health_is_public(anon_client):
    assert (await anon_client.get("/health")).status_code == 200


async def test_login_then_access(anon_client, async_session):
    await access_service.add_user(async_session, "eric@example.com", "secret123", is_owner=True)

    bad = await anon_client.post("/api/v1/auth/login",
                                 json={"email": "eric@example.com", "passcode": "wrong"})
    assert bad.status_code == 401

    ok = await anon_client.post("/api/v1/auth/login",
                                json={"email": "eric@example.com", "passcode": "secret123"})
    assert ok.status_code == 200
    token = ok.json()["token"]
    assert ok.json()["owner"] is True

    # Token unlocks protected routes.
    headers = {"Authorization": f"Bearer {token}"}
    r = await anon_client.get("/api/v1/engagements/clients", headers=headers)
    assert r.status_code == 200


async def test_access_management_is_owner_only(anon_client, async_session):
    await access_service.add_user(async_session, "owner@x.com", "ownerpass", is_owner=True)
    await access_service.add_user(async_session, "viewer@x.com", "viewpass", is_owner=False)

    async def token_for(email, passcode):
        r = await anon_client.post("/api/v1/auth/login",
                                   json={"email": email, "passcode": passcode})
        return r.json()["token"]

    viewer_h = {"Authorization": f"Bearer {await token_for('viewer@x.com', 'viewpass')}"}
    owner_h = {"Authorization": f"Bearer {await token_for('owner@x.com', 'ownerpass')}"}

    # Viewer cannot manage the allowlist.
    assert (await anon_client.get("/api/v1/access", headers=viewer_h)).status_code == 403
    # Owner can add a user.
    added = await anon_client.post("/api/v1/access", headers=owner_h,
                                   json={"email": "new@x.com", "passcode": "newpass"})
    assert added.status_code == 201
    listed = await anon_client.get("/api/v1/access", headers=owner_h)
    assert any(u["email"] == "new@x.com" for u in listed.json()["users"])


async def test_bootstrap_seeds_owners_from_env(async_session, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ACCESS_USERS", "boss@x.com:bosspass")
    added = await access_service.bootstrap(async_session)
    assert added == 1
    user = await access_service.verify(async_session, "boss@x.com", "bosspass")
    assert user is not None and user.is_owner is True
    # Idempotent: a second bootstrap with users present adds nothing.
    assert await access_service.bootstrap(async_session) == 0
