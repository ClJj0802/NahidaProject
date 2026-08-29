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
        return (
            "No relevant long-term memories."
        )

    lines = []

    for memory in memories:
        lines.append(
            f"- {memory['content']}"
        )

    return "\n".join(lines)


def build_recent_conversation(
    session_id,
    limit=8,
):
    rows = get_recent_messages(
        limit=limit,
        session_id=session_id,
    )

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
    session_id,
    relevant_memory_ids=None,
):
    if relevant_memory_ids is None:
        relevant_memory_ids = []

    persona = load_persona()

    memories = build_memory_context(
        relevant_memory_ids
    )

    conversation = (
        build_recent_conversation(
            session_id=session_id,
            limit=8,
        )
    )

    system_context = f"""
{persona}

RELEVANT LONG-TERM MEMORIES:

{memories}

Important:
Only use these memories if they directly help with the current message.

The recent conversation contains only the current chat session.

Do not bring up earlier topics merely because they appeared recently.

If the user's current message changes the subject, follow the new subject.

For ordinary affectionate or casual messages, a short response is usually better.
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_context,
        }
    ]

    messages.extend(
        conversation
    )

    return chat_completion(
        messages=messages,
        temperature=0.55,
        max_tokens=180,
    ).strip()