"""Smoke tests that don't require network / a Fireworks key.

Run from the backend/ directory:  pytest
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_conversation_db_crud():
    # DB layer works (chat persistence relies on it) independent of the HTTP surface.
    from app import db

    cid = db.create_conversation("smoke test")
    assert any(c["id"] == cid for c in db.list_conversations())
    db.add_message(cid, "user", "hi")
    assert db.get_messages(cid)[0]["content"] == "hi"


def test_conversations_endpoint_gated_by_default():
    # Public-safe default: list/detail are NOT exposed (no cross-visitor leak).
    from app.config import get_settings

    expected = 200 if get_settings().expose_conversations else 404
    assert client.get("/api/conversations").status_code == expected


def test_rag_module_imports():
    # Importing must not require a key or network (heavy deps are lazy).
    import app.rag  # noqa: F401


def test_security_headers_present():
    from app.config import get_settings

    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    csp = r.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors" in csp

    # Framing policy depends on config: locked by default, opened per-origin when
    # EMBED_ORIGINS is set (then X-Frame-Options is dropped — it has no allow-list).
    if get_settings().embed_origins:
        assert r.headers.get("X-Frame-Options") is None
        assert "frame-ancestors 'self'" in csp
    else:
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "frame-ancestors 'none'" in csp


def test_safe_filename_blocks_traversal():
    import pytest
    from fastapi import HTTPException

    from app.security import safe_filename

    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("/etc/shadow") == "shadow"
    assert safe_filename("notes.pdf") == "notes.pdf"
    for bad in ("..", "", "/"):
        with pytest.raises(HTTPException):
            safe_filename(bad)


def test_empty_message_rejected():
    r = client.post("/api/chat", json={"message": "   "})
    assert r.status_code == 400


def test_calculator_tool_is_safe():
    from app.tools import calculator

    assert calculator.invoke({"expression": "2 * (3 + 4)"}) == "14"
    # no code execution / imports
    assert "Error" in calculator.invoke({"expression": "__import__('os').system('echo hi')"})


def test_agent_modules_import():
    import app.agent  # noqa: F401
    import app.tools  # noqa: F401


def test_public_upload_disabled_by_default():
    r = client.post("/api/documents", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 403


def test_ingest_url_withheld_by_default():
    from app import tools

    names = {t.name for t in tools.active_tools()}
    assert "ingest_url" not in names          # KB is read-only to visitors
    assert "search_documents" in names        # read tools still available


def test_health_reports_cost_cap():
    body = client.get("/api/health").json()
    assert "daily_cost_cap_usd" in body
    assert "spent_today_usd" in body


def test_daily_cost_cap_blocks_chat():
    """When the day's estimated spend exceeds the cap, /api/chat returns 429."""
    from app import cost

    before = cost.METER._spent  # noqa: SLF001 (test introspection)
    try:
        cost.METER.add(10_000.0)  # blow past any sane cap
        r = client.post("/api/chat", json={"message": "hello"})
        assert r.status_code == 429
    finally:
        cost.METER._spent = before  # restore so other tests are unaffected
