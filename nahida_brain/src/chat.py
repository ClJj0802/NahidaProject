from pathlib import Path

from src.database import (
    get_memories_by_ids,
    get_recent_messages,
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


def build_memory_context(memory_ids):
    memories = get_memories_by_ids(
        memory_ids
    )

    if not memories:
        return "No relevant long-term memories."

    lines = []

    for memory in memories:
        lines.append(
            f"- {memory['content']}"
        )

    return "\n".join(lines)


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


def generate_nahida_response(
    relevant_memory_ids=None,
):
    if relevant_memory_ids is None:
        relevant_memory_ids = []

    persona = load_persona()

    memories = build_memory_context(
        relevant_memory_ids
    )

    conversation = build_recent_conversation(
        limit=16
    )

    system_context = f"""
{persona}

RELEVANT LONG-TERM MEMORIES:

{memories}

Important:
Only use the memories above when they are genuinely relevant.
Do not mention memories merely to demonstrate that you remember them.
Answer the user's current message naturally.
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
        max_tokens=220,
    ).strip()