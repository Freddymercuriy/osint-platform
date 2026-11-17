"""Bosqich 0: autentifikatsiya, rollar, admin himoyasi, ro'yxatdan o'tish, SECRET_KEY."""

import pytest
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.security import create_access_token, decode_access_token
from app.models import User
from app.services.admin_roles import role_for_new_user, sync_admin_roles


async def test_register_login_me(client):
    r = await client.post("/api/auth/register", json={"email": "first@example.com", "password": "password-123"})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "admin"  # birinchi foydalanuvchi (ADMIN_EMAILS bo'sh)

    r = await client.post("/api/auth/register", json={"email": "second@example.com", "password": "password-123"})
    assert r.json()["role"] == "analyst"

    r = await client.post("/api/auth/login", data={"username": "second@example.com", "password": "password-123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "second@example.com"
    assert me.json()["locale"] is None


async def test_login_wrong_password(client, make_user):
    await make_user("u@example.com", password="right-password")
    r = await client.post("/api/auth/login", data={"username": "u@example.com", "password": "wrong-password"})
    assert r.status_code == 401


async def test_duplicate_email_case_insensitive(client, make_user):
    await make_user("Dup@Example.com")
    r = await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "password-123"})
    assert r.status_code == 409


async def test_registration_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "registration_open", False)
    r = await client.post("/api/auth/register", json={"email": "x@example.com", "password": "password-123"})
    assert r.status_code == 403
    cfg = await client.get("/api/auth/config")
    assert cfg.json() == {"registration_open": False}


def test_registration_default_depends_on_environment():
    assert Settings(_env_file=None, environment="development", registration_open=None).registration_allowed is True
    assert Settings(_env_file=None, environment="production", registration_open=None).registration_allowed is False
    assert Settings(_env_file=None, environment="production", registration_open=True).registration_allowed is True


async def test_update_locale(client, analyst_headers):
    r = await client.patch("/api/auth/me", json={"locale": "ru"}, headers=analyst_headers)
    assert r.status_code == 200 and r.json()["locale"] == "ru"
    r = await client.patch("/api/auth/me", json={"locale": "de"}, headers=analyst_headers)
    assert r.status_code == 422


async def test_inactive_user_rejected(client, make_user, db):
    user, headers = await make_user("off@example.com")
    user.is_active = False
    await db.commit()
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401


@pytest.mark.parametrize("method,path", [
    ("post", "/api/events/refresh"),
    ("get", "/api/telegram/status"),
    ("get", "/api/telegram/chats"),
])
async def test_admin_only_routes(client, analyst_headers, method, path):
    r = await getattr(client, method)(path, headers=analyst_headers)
    assert r.status_code == 403
    r = await getattr(client, method)(path)
    assert r.status_code == 401


async def test_admin_can_read_telegram_status(client, admin_headers):
    r = await client.get("/api/telegram/status", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["configured"] is False  # testda Telegram sozlanmagan


async def test_sync_admin_roles_oldest_user(db, make_user):
    await make_user("old@example.com")
    await make_user("new@example.com")
    await sync_admin_roles(db)
    roles = dict((await db.execute(select(User.email, User.role))).all())
    assert roles == {"old@example.com": "admin", "new@example.com": "analyst"}


async def test_sync_admin_roles_admin_emails(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "Boss@Example.com")
    await make_user("old@example.com")
    await make_user("boss@example.com")
    await sync_admin_roles(db)
    roles = dict((await db.execute(select(User.email, User.role))).all())
    assert roles == {"old@example.com": "analyst", "boss@example.com": "admin"}
    assert role_for_new_user("boss@example.com", 5) == "admin"
    assert role_for_new_user("someone@example.com", 0) == "analyst"


def test_secret_key_default_detection():
    assert Settings(_env_file=None, secret_key="change-me").secret_key_is_default
    assert Settings(_env_file=None, secret_key="short").secret_key_is_default
    assert not Settings(_env_file=None, secret_key="x" * 40).secret_key_is_default


def test_production_refuses_default_secret(tmp_path):
    import os
    import subprocess
    import sys

    env = dict(os.environ, ENVIRONMENT="production", SECRET_KEY="change-me")
    proc = subprocess.run([sys.executable, "-c", "import app.main"], env=env, capture_output=True, text=True,
                          cwd=os.path.dirname(os.path.dirname(__file__)))
    assert proc.returncode != 0
    assert "SECRET_KEY" in proc.stderr


def test_jwt_roundtrip_and_tamper():
    token = create_access_token("42")
    assert decode_access_token(token) == "42"
    assert decode_access_token(token[:-2] + "xx") is None
    assert decode_access_token("not-a-token") is None
    assert decode_access_token(create_access_token("42", expires_minutes=-1)) is None
