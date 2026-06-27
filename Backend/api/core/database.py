"""SQLite persistence for users."""

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/simple_tech.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def create_user(email: str, name: str, hashed_password: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, name, hashed_password) VALUES (?, ?, ?)",
            (email.lower().strip(), name.strip(), hashed_password),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        conn.close()
        raise ValueError("Email already registered") from exc
    conn.close()
    user = get_user_by_id(user_id)
    if user is None:
        raise RuntimeError("Failed to create user")
    return user


def get_user_by_email(email: str) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, name, hashed_password, created_at FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, name, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
