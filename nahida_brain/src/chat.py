from pathlib import Path

from src.database import (
    get_memories,
    get_recent_messages,
    get_recent_daily_summaries,
)

from src.llm_client import chat_completion


BASE_DIR = Path(__file__).resolve().parent.parent

PERSONA_PATH = (
    BASE_DIR
    / "persona"
    / "nahida_system.txt"
)


def load_persona():
    return PERSONA_PATH.read_text(
        encoding="utf-8"
    ).strip()


def build_memory_context(limit=30):
    memories = get_memories(limit)

    if not memories:
        return "No relevant long-term memories."

    lines = []

    for memory in memories:
        lines.append(
            f"- {memory['content']}"
        )

    return "\n".join(lines)


def build_daily_context(limit=7):
    summaries = get_recent_daily_summaries(
        limit
    )

    if not summaries:
        return "No recent daily summaries."

    lines = []

    for item in reversed(summaries):
        lines.append(
            f"[{item['summary_date']}]"
        )
        lines.append(
            item["summary"]
        )
        lines.append("")

    return "\n".join(lines).strip()


def build_recent_conversation(limit=16):
    rows = get_recent_messages(limit)

    messages = []

    for row in rows:
        role = row["role"]

        if role not in {
            "user",
            "assistant",
        }:
            continue

        messages.append(
            {
                "role": role,
                "content": row["content"],
            }
        )

    return messages


def generate_nahida_response():
    persona = load_persona()

    memories = build_memory_context(
        limit=30
    )

    daily_context = build_daily_context(
        limit=7
    )

    conversation = (
        build_recent_conversation(
            limit=16
        )
    )

    system_context = f"""
{persona}

LONG-TERM MEMORIES:

{memories}

RECENT DAILY MEMORIES:

{daily_context}
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_context,
        }
    ]

    messages.extend(conversation)

    return chat_completion(
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    ).strip()