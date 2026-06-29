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


def test_conversation_crud():
    r = client.post("/api/conversations", json={"title": "smoke test"})
    assert r.status_code == 200
    cid = r.json()["id"]

    listed = client.get("/api/conversations").json()
    assert any(c["id"] == cid for c in listed)

    detail = client.get(f"/api/conversations/{cid}")
    assert detail.status_code == 200
    assert detail.json()["conversation"]["id"] == cid


def test_rag_module_imports():
    # Importing must not require a key or network (heavy deps are lazy).
    import app.rag  # noqa: F401


def test_security_headers_present():
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


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
