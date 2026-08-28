import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "nahida.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            importance INTEGER NOT NULL DEFAULT 5,
            source_message_id INTEGER,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (source_message_id)
                REFERENCES messages(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_date TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def save_message(role, content):
    conn = get_connection()
    cursor = conn.cursor()

    created_at = datetime.now().isoformat(timespec="seconds")

    cursor.execute(
        """
        INSERT INTO messages (
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            role,
            content,
            created_at,
        ),
    )

    message_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return message_id


def save_memory(
    category,
    content,
    importance,
    source_message_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    created_at = datetime.now().isoformat(timespec="seconds")

    cursor.execute(
        """
        INSERT INTO memories (
            category,
            content,
            importance,
            source_message_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            category,
            content,
            importance,
            source_message_id,
            created_at,
        ),
    )

    memory_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return memory_id


def get_recent_messages(limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM messages
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return list(reversed(rows))


def get_memories(limit=50):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM memories
        WHERE active = 1
        ORDER BY importance DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_messages_for_date(date_string):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM messages
        WHERE substr(created_at, 1, 10) = ?
        ORDER BY id ASC
        """,
        (date_string,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows