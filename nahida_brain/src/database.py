import sqlite3
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "nahida.db"


def get_connection():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def column_exists(
    conn,
    table_name,
    column_name,
):
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
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT
        )
        """
    )

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

    if not column_exists(
        conn,
        "messages",
        "session_id",
    ):
        cursor.execute(
            """
            ALTER TABLE messages
            ADD COLUMN session_id INTEGER
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

    memory_columns = {
        "memory_type": "TEXT NOT NULL DEFAULT 'fixed'",
        "confidence": "REAL NOT NULL DEFAULT 1.0",
        "source_type": "TEXT NOT NULL DEFAULT 'user_explicit'",
        "expires_at": "TEXT",
        "valid_from": "TEXT",
        "valid_until": "TEXT",
        "is_core": "INTEGER NOT NULL DEFAULT 0",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "last_confirmed_at": "TEXT",
        "superseded_by": "INTEGER",
        "metadata_json": "TEXT",
    }

    for column_name, column_type in memory_columns.items():
        if not column_exists(
            conn,
            "memories",
            column_name,
        ):
            cursor.execute(
                f"""
                ALTER TABLE memories
                ADD COLUMN {column_name} {column_type}
                """
            )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_contexts (
            session_id INTEGER PRIMARY KEY,
            context_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id)
                REFERENCES sessions(id)
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            start_at TEXT NOT NULL,
            end_at TEXT,
            all_day INTEGER NOT NULL DEFAULT 0,
            time_precision TEXT NOT NULL DEFAULT 'exact',
            time_label TEXT,
            timezone TEXT,
            recurrence_rule TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            source_message_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (source_message_id)
                REFERENCES messages(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS event_occurrence_state (
            event_id INTEGER NOT NULL,
            occurrence_date TEXT NOT NULL,
            occurrence_status TEXT,
            surfaced_at TEXT,
            acknowledged_at TEXT,
            override_title TEXT,
            override_location TEXT,
            override_start_at TEXT,
            override_end_at TEXT,
            override_all_day INTEGER,
            override_time_precision TEXT,
            override_time_label TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (event_id, occurrence_date),
            FOREIGN KEY (event_id)
                REFERENCES events(id)
        )
        """
    )

    occurrence_columns = {
        "override_title": "TEXT",
        "override_location": "TEXT",
        "override_start_at": "TEXT",
        "override_end_at": "TEXT",
        "override_all_day": "INTEGER",
        "override_time_precision": "TEXT",
        "override_time_label": "TEXT",
    }

    for column_name, column_type in occurrence_columns.items():
        if not column_exists(
            conn,
            "event_occurrence_state",
            column_name,
        ):
            cursor.execute(
                f"""
                ALTER TABLE event_occurrence_state
                ADD COLUMN {column_name} {column_type}
                """
            )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_status_start
        ON events(status, start_at)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_event_occurrence_date
        ON event_occurrence_state(occurrence_date)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_type_active
        ON memories(memory_type, active, status)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_expiry
        ON memories(expires_at)
        """
    )

    conn.commit()
    conn.close()


def create_session():
    conn = get_connection()
    cursor = conn.cursor()

    started_at = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO sessions (
            started_at
        )
        VALUES (?)
        """,
        (started_at,),
    )

    session_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return session_id


def end_session(session_id):
    conn = get_connection()
    cursor = conn.cursor()

    ended_at = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE sessions
        SET ended_at = ?
        WHERE id = ?
        """,
        (
            ended_at,
            session_id,
        ),
    )

    conn.commit()
    conn.close()


def save_message(
    role,
    content,
    session_id=None,
):
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
            created_at,
            session_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            role,
            content,
            created_at,
            session_id,
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
    memory_type="fixed",
    confidence=1.0,
    source_type="user_explicit",
    expires_at=None,
    valid_from=None,
    valid_until=None,
    is_core=False,
    metadata_json=None,
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
            updated_at,
            memory_type,
            confidence,
            source_type,
            expires_at,
            valid_from,
            valid_until,
            is_core,
            status,
            last_confirmed_at,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            category,
            content,
            importance,
            source_message_id,
            now,
            now,
            memory_type,
            confidence,
            source_type,
            expires_at,
            valid_from,
            valid_until,
            1 if is_core else 0,
            now,
            metadata_json,
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
    memory_type=None,
    confidence=None,
    expires_at=None,
    is_core=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    updated_at = datetime.now().isoformat(
        timespec="seconds"
    )

    current = cursor.execute(
        "SELECT * FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()

    if current is None:
        conn.close()
        return False

    current_keys = set(current.keys())

    next_memory_type = (
        memory_type
        if memory_type is not None
        else current["memory_type"]
        if "memory_type" in current_keys
        else "fixed"
    )

    next_confidence = (
        confidence
        if confidence is not None
        else current["confidence"]
        if "confidence" in current_keys
        else 1.0
    )

    if memory_type is not None:
        if memory_type == "short_term_episode":
            next_expires_at = expires_at
        else:
            next_expires_at = None
    elif expires_at is not None:
        next_expires_at = expires_at
    else:
        next_expires_at = (
            current["expires_at"]
            if "expires_at" in current_keys
            else None
        )

    next_is_core = (
        1 if is_core else 0
        if is_core is not None
        else current["is_core"]
        if "is_core" in current_keys
        else 0
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
            memory_type = ?,
            confidence = ?,
            expires_at = ?,
            is_core = ?,
            status = 'active',
            active = 1,
            last_confirmed_at = ?
        WHERE id = ?
        """,
        (
            category,
            content,
            importance,
            source_message_id,
            updated_at,
            next_memory_type,
            next_confidence,
            next_expires_at,
            next_is_core,
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


def get_recent_messages(
    limit=20,
    session_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    if session_id is None:
        cursor.execute(
            """
            SELECT *
            FROM messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    else:
        cursor.execute(
            """
            SELECT *
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                session_id,
                limit,
            ),
        )

    rows = cursor.fetchall()

    conn.close()

    return list(
        reversed(rows)
    )


def get_memories(limit=100):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM memories
        WHERE
            active = 1
            AND status = 'active'
            AND (
                expires_at IS NULL
                OR expires_at > ?
            )
        ORDER BY importance DESC, id DESC
        LIMIT ?
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            limit,
        ),
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
            AND status = 'active'
            AND (
                expires_at IS NULL
                OR expires_at > ?
            )
            AND id IN ({placeholders})
        ORDER BY importance DESC
    """

    params = [
        datetime.now().isoformat(timespec="seconds"),
        *memory_ids,
    ]

    cursor.execute(
        query,
        params,
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

def get_global_communication_preferences(
    limit=20,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM memories
        WHERE
            active = 1
            AND category = 'communication'
        ORDER BY importance DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

def get_latest_message():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM messages
        ORDER BY id DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    conn.close()

    return row

def save_event(
    title,
    start_at,
    description=None,
    location=None,
    end_at=None,
    all_day=False,
    time_precision="exact",
    time_label=None,
    timezone=None,
    recurrence_rule=None,
    status="scheduled",
    source_message_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO events (
            title,
            description,
            location,
            start_at,
            end_at,
            all_day,
            time_precision,
            time_label,
            timezone,
            recurrence_rule,
            status,
            source_message_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            location,
            start_at,
            end_at,
            1 if all_day else 0,
            time_precision,
            time_label,
            timezone,
            recurrence_rule,
            status,
            source_message_id,
            now,
            now,
        ),
    )

    event_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return event_id


def update_event(
    event_id,
    title,
    start_at,
    description=None,
    location=None,
    end_at=None,
    all_day=False,
    time_precision="exact",
    time_label=None,
    timezone=None,
    recurrence_rule=None,
    status="scheduled",
    source_message_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE events
        SET
            title = ?,
            description = ?,
            location = ?,
            start_at = ?,
            end_at = ?,
            all_day = ?,
            time_precision = ?,
            time_label = ?,
            timezone = ?,
            recurrence_rule = ?,
            status = ?,
            source_message_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            location,
            start_at,
            end_at,
            1 if all_day else 0,
            time_precision,
            time_label,
            timezone,
            recurrence_rule,
            status,
            source_message_id,
            now,
            event_id,
        ),
    )

    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed > 0


def get_event(event_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (event_id,),
    )

    row = cursor.fetchone()

    conn.close()

    return row


def get_events_by_ids(event_ids):
    if not event_ids:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    placeholders = ",".join(
        "?"
        for _ in event_ids
    )

    query = f"""
        SELECT *
        FROM events
        WHERE id IN ({placeholders})
        ORDER BY start_at ASC, id ASC
    """

    cursor.execute(
        query,
        event_ids,
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_event_candidates(limit=80):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        ORDER BY
            CASE status
                WHEN 'scheduled' THEN 0
                WHEN 'tentative' THEN 1
                WHEN 'completed' THEN 2
                WHEN 'cancelled' THEN 3
                ELSE 4
            END,
            start_at ASC,
            id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_active_events(limit=500):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE status IN ('scheduled', 'tentative')
        ORDER BY start_at ASC, id ASC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def set_event_status(
    event_id,
    status,
    source_message_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE events
        SET
            status = ?,
            source_message_id = COALESCE(?, source_message_id),
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            source_message_id,
            now,
            event_id,
        ),
    )

    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed > 0


def get_event_occurrence_state(
    event_id,
    occurrence_date,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM event_occurrence_state
        WHERE
            event_id = ?
            AND occurrence_date = ?
        """,
        (
            event_id,
            occurrence_date,
        ),
    )

    row = cursor.fetchone()

    conn.close()

    return row


def _upsert_event_occurrence_field(
    event_id,
    occurrence_date,
    field_name,
    value,
):
    allowed_fields = {
        "occurrence_status",
        "surfaced_at",
        "acknowledged_at",
    }

    if field_name not in allowed_fields:
        raise ValueError(
            f"Unsupported occurrence field: {field_name}"
        )

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    query = f"""
        INSERT INTO event_occurrence_state (
            event_id,
            occurrence_date,
            {field_name},
            updated_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(event_id, occurrence_date)
        DO UPDATE SET
            {field_name} = excluded.{field_name},
            updated_at = excluded.updated_at
    """

    cursor.execute(
        query,
        (
            event_id,
            occurrence_date,
            value,
            now,
        ),
    )

    conn.commit()
    conn.close()


def mark_event_occurrence_surfaced(
    event_id,
    occurrence_date,
):
    now = datetime.now().isoformat(
        timespec="seconds"
    )

    _upsert_event_occurrence_field(
        event_id=event_id,
        occurrence_date=occurrence_date,
        field_name="surfaced_at",
        value=now,
    )


def mark_event_occurrence_acknowledged(
    event_id,
    occurrence_date,
):
    now = datetime.now().isoformat(
        timespec="seconds"
    )

    _upsert_event_occurrence_field(
        event_id=event_id,
        occurrence_date=occurrence_date,
        field_name="acknowledged_at",
        value=now,
    )


def set_event_occurrence_status(
    event_id,
    occurrence_date,
    status,
):
    _upsert_event_occurrence_field(
        event_id=event_id,
        occurrence_date=occurrence_date,
        field_name="occurrence_status",
        value=status,
    )


def count_event_interactions_for_date(
    occurrence_date,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM event_occurrence_state
        WHERE
            substr(surfaced_at, 1, 10) = ?
            OR substr(acknowledged_at, 1, 10) = ?
        """,
        (
            occurrence_date,
            occurrence_date,
        ),
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return 0

    return int(row["count"])

def set_event_occurrence_override(
    event_id,
    occurrence_date,
    title=None,
    location=None,
    start_at=None,
    end_at=None,
    all_day=None,
    time_precision=None,
    time_label=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO event_occurrence_state (
            event_id,
            occurrence_date,
            override_title,
            override_location,
            override_start_at,
            override_end_at,
            override_all_day,
            override_time_precision,
            override_time_label,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id, occurrence_date)
        DO UPDATE SET
            override_title = excluded.override_title,
            override_location = excluded.override_location,
            override_start_at = excluded.override_start_at,
            override_end_at = excluded.override_end_at,
            override_all_day = excluded.override_all_day,
            override_time_precision = excluded.override_time_precision,
            override_time_label = excluded.override_time_label,
            updated_at = excluded.updated_at
        """,
        (
            event_id,
            occurrence_date,
            title,
            location,
            start_at,
            end_at,
            (
                None
                if all_day is None
                else 1 if all_day else 0
            ),
            time_precision,
            time_label,
            now,
        ),
    )

    conn.commit()
    conn.close()


def get_event_occurrence_overrides_for_date(
    active_date,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            events.*,
            event_occurrence_state.occurrence_date AS state_occurrence_date,
            event_occurrence_state.occurrence_status AS state_occurrence_status,
            event_occurrence_state.surfaced_at AS state_surfaced_at,
            event_occurrence_state.acknowledged_at AS state_acknowledged_at,
            event_occurrence_state.override_title AS state_override_title,
            event_occurrence_state.override_location AS state_override_location,
            event_occurrence_state.override_start_at AS state_override_start_at,
            event_occurrence_state.override_end_at AS state_override_end_at,
            event_occurrence_state.override_all_day AS state_override_all_day,
            event_occurrence_state.override_time_precision AS state_override_time_precision,
            event_occurrence_state.override_time_label AS state_override_time_label
        FROM event_occurrence_state
        JOIN events
            ON events.id = event_occurrence_state.event_id
        WHERE
            events.status IN ('scheduled', 'tentative')
            AND event_occurrence_state.override_start_at IS NOT NULL
            AND substr(
                event_occurrence_state.override_start_at,
                1,
                10
            ) = ?
        ORDER BY event_occurrence_state.override_start_at ASC
        """,
        (active_date,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows



def get_event_occurrence_states_for_event_ids(
    event_ids,
    limit=300,
):
    if not event_ids:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    placeholders = ",".join(
        "?"
        for _ in event_ids
    )

    query = f"""
        SELECT *
        FROM event_occurrence_state
        WHERE
            event_id IN ({placeholders})
            AND (
                occurrence_status IS NOT NULL
                OR override_start_at IS NOT NULL
                OR override_title IS NOT NULL
                OR override_location IS NOT NULL
            )
        ORDER BY occurrence_date ASC
        LIMIT ?
    """

    params = list(event_ids)
    params.append(limit)

    cursor.execute(
        query,
        params,
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def cleanup_expired_memories():
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE memories
        SET
            active = 0,
            status = 'expired',
            updated_at = ?
        WHERE
            active = 1
            AND status = 'active'
            AND expires_at IS NOT NULL
            AND expires_at <= ?
        """,
        (now, now),
    )

    changed = cursor.rowcount
    conn.commit()
    conn.close()

    return changed


def get_core_memories(limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        SELECT *
        FROM memories
        WHERE
            active = 1
            AND status = 'active'
            AND is_core = 1
            AND memory_type = 'fixed'
            AND category != 'communication'
            AND (
                expires_at IS NULL
                OR expires_at > ?
            )
        ORDER BY importance DESC, id DESC
        LIMIT ?
        """,
        (now, limit),
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def save_session_context(
    session_id,
    context_json,
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        INSERT INTO session_contexts (
            session_id,
            context_json,
            updated_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(session_id)
        DO UPDATE SET
            context_json = excluded.context_json,
            updated_at = excluded.updated_at
        """,
        (session_id, context_json, now),
    )

    conn.commit()
    conn.close()


def get_session_context(session_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM session_contexts
        WHERE session_id = ?
        """,
        (session_id,),
    )

    row = cursor.fetchone()
    conn.close()
    return row
