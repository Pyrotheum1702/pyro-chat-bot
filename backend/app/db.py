"""Tiny SQLite persistence layer (stdlib sqlite3 — no ORM).

Stores conversations, their messages, and a record of ingested documents so
chat history survives a restart.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Dict, List, Optional

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,            -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    filename   TEXT NOT NULL,
    chunks     INTEGER NOT NULL,
    created_at REAL NOT NULL
);
"""


@contextmanager
def _conn():
    path = get_settings().sqlite_path
    path.parent.mkdir(parents=True, exist_ok=True)  # resilient if the data dir is missing
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


# --- conversations ---
def create_conversation(title: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO conversations(title, created_at) VALUES (?, ?)",
            (title, time.time()),
        )
        return int(cur.lastrowid)


def get_conversation(cid: int) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
        return dict(row) if row else None


def list_conversations() -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM conversations ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# --- messages ---
def add_message(conversation_id: int, role: str, content: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, time.time()),
        )


def get_messages(conversation_id: int) -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- documents ---
def add_document(filename: str, chunks: int) -> Dict:
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO documents(filename, chunks, created_at) VALUES (?, ?, ?)",
            (filename, chunks, now),
        )
        rid = int(cur.lastrowid)
    return {"id": rid, "filename": filename, "chunks": chunks, "created_at": now}


def list_documents() -> List[Dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
