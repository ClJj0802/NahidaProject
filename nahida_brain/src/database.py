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


def column_exists(conn, table_name, column_name):
    cursor = conn.cursor()

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = cursor.fetchall()

    return any(
        column["name"] == column_name
        for column in columns
    )


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

    if not column_exists(
        conn,
        "memories",
        "updated_at",
    ):
        cursor.execute(
            """
            ALTER TABLE memories
            ADD COLUMN updated_at TEXT
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

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

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

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO memories (
            category,
            content,
            importance,
            source_message_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            category,
            content,
            importance,
            source_message_id,
            now,
            now,
        ),
    )

    memory_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return memory_id


def update_memory(
    memory_id,
    category,
    content,
    importance,
    source_message_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    updated_at = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE memories
        SET
            category = ?,
            content = ?,
            importance = ?,
            source_message_id = ?,
            updated_at = ?,
            active = 1
        WHERE id = ?
        """,
        (
            category,
            content,
            importance,
            source_message_id,
            updated_at,
            memory_id,
        ),
    )

    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed > 0


def deactivate_memory(memory_id):
    conn = get_connection()
    cursor = conn.cursor()

    updated_at = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE memories
        SET
            active = 0,
            updated_at = ?
        WHERE id = ?
        """,
        (
            updated_at,
            memory_id,
        ),
    )

    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed > 0


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


def get_memories(limit=100):
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


def get_memory(memory_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM memories
        WHERE id = ?
        """,
        (memory_id,),
    )

    row = cursor.fetchone()

    conn.close()

    return row


def get_messages_for_date(date_string):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM messages
        WHERE created_at LIKE ?
        ORDER BY id ASC
        """,
        (f"{date_string}%",),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

def save_daily_summary(
    summary_date,
    summary,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO daily_summaries (
            summary_date,
            summary,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(summary_date)
        DO UPDATE SET
            summary = excluded.summary,
            updated_at = excluded.updated_at
        """,
        (
            summary_date,
            summary,
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()


def get_daily_summary(summary_date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM daily_summaries
        WHERE summary_date = ?
        """,
        (summary_date,),
    )

    row = cursor.fetchone()

    conn.close()

    return row


def get_recent_daily_summaries(limit=7):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM daily_summaries
        ORDER BY summary_date DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

def get_memories_by_ids(memory_ids):
    if not memory_ids:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    placeholders = ",".join(
        "?"
        for _ in memory_ids
    )

    query = f"""
        SELECT *
        FROM memories
        WHERE
            active = 1
            AND id IN ({placeholders})
        ORDER BY importance DESC
    """

    cursor.execute(
        query,
        memory_ids,
    )

    rows = cursor.fetchall()

    conn.close()

    return rows