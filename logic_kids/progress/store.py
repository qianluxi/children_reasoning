"""儿童进度存储（专家意见第十三节：儿童能力模型）。

用 SQLite 记录：
  · children   儿童档案
  · attempts   每次答题（儿童、题目、题型、对错、用时）

并据此计算每个题型的掌握度（最近 N 次的正确率），供自适应出题使用。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from ..config import DB_PATH, ensure_dirs

WINDOW = 10  # 掌握度按最近 N 次计算

_SCHEMA = """
CREATE TABLE IF NOT EXISTS children (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id    INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    qtype       TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    time_ms     INTEGER,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(child_id) REFERENCES children(id)
);
CREATE INDEX IF NOT EXISTS idx_attempts_child ON attempts(child_id, qtype);
"""


@contextmanager
def _conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


def create_child(name: str) -> int:
    init_db()
    with _conn() as c:
        cur = c.execute("INSERT INTO children(name) VALUES(?)", (name,))
        return cur.lastrowid


def get_or_create_child(name: str) -> int:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT id FROM children WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = c.execute("INSERT INTO children(name) VALUES(?)", (name,))
        return cur.lastrowid


def list_children() -> list:
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT id, name FROM children ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def record_attempt(child_id: int, question_id: str, qtype: str,
                   correct: bool, time_ms: int = None) -> None:
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO attempts(child_id, question_id, qtype, correct, time_ms) "
            "VALUES(?,?,?,?,?)",
            (child_id, question_id, qtype, 1 if correct else 0, time_ms))


def recent_attempts(child_id: int, qtype: str, limit: int = WINDOW) -> list:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT correct FROM attempts WHERE child_id=? AND qtype=? "
            "ORDER BY id DESC LIMIT ?", (child_id, qtype, limit)).fetchall()
        return [r["correct"] for r in rows]


def mastery(child_id: int, qtype: str) -> float | None:
    """某题型掌握度（0..1）；无记录返回 None。"""
    rec = recent_attempts(child_id, qtype)
    if not rec:
        return None
    return sum(rec) / len(rec)


def profile(child_id: int, types: list) -> dict:
    """返回 {题型: {mastery, attempts}} 能力画像。"""
    result = {}
    for t in types:
        rec = recent_attempts(child_id, t)
        result[t] = {
            "mastery": (sum(rec) / len(rec)) if rec else None,
            "attempts": len(rec),
        }
    return result


def total_attempts(child_id: int) -> int:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) n FROM attempts WHERE child_id=?",
                        (child_id,)).fetchone()
        return row["n"]


def stars_earned(child_id: int) -> int:
    """累计答对数（作为星星）。"""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) n FROM attempts WHERE child_id=? AND correct=1",
                        (child_id,)).fetchone()
        return row["n"]
