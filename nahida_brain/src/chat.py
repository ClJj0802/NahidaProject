from datetime import datetime
from pathlib import Path

from src.database import (
    get_memories_by_ids,
    get_recent_messages,
    get_global_communication_preferences,
)

from src.llm_client import (
    chat_completion,
)

from datetime import datetime

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

PERSONA_PATH = (
    BASE_DIR
    / "persona"
    / "nahida_system.txt"
)

def build_interaction_context(
    interaction_gap,
):
    if not interaction_gap:
        return (
            "No previous interaction information."
        )

    seconds = interaction_gap.get(
        "seconds",
        0,
    )

    same_session = interaction_gap.get(
        "same_session",
        False,
    )

    if seconds < 60:
        duration = (
            "less than one minute"
        )

    elif seconds < 3600:
        minutes = seconds // 60

        duration = (
            f"about {minutes} minutes"
        )

    elif seconds < 86400:
        hours = seconds // 3600

        duration = (
            f"about {hours} hours"
        )

    else:
        days = seconds // 86400

        duration = (
            f"about {days} days"
        )

    session_text = (
        "the current session"
        if same_session
        else "a previous session"
    )

    return (
        f"Time since the previous interaction: "
        f"{duration}\n"
        f"Previous interaction was in: "
        f"{session_text}"
    )

def build_global_communication_context():
    preferences = (
        get_global_communication_preferences()
    )

    if not preferences:
        return (
            "No global communication preferences."
        )

    lines = []

    for preference in preferences:
        lines.append(
            f"- {preference['content']}"
        )

    return "\n".join(lines)

def build_time_context():
    now = datetime.now().astimezone()

    return (
        f"Current date: {now.strftime('%Y-%m-%d')}\n"
        f"Day of week: {now.strftime('%A')}\n"
        f"Current local time: {now.strftime('%H:%M')}\n"
        f"Timezone: {now.strftime('%z')}"
    )

def load_persona():
    return PERSONA_PATH.read_text(
        encoding="utf-8"
    ).strip()


def build_memory_context(
    memory_ids,
):
    memories = get_memories_by_ids(
        memory_ids
    )

    memories = [
        memory
        for memory in memories
        if memory["category"]
        != "communication"
    ]

    if not memories:
        return (
            "No relevant long-term memories."
        )

    lines = []

    for memory in memories:
        lines.append(
            f"- {memory['content']}"
        )

    return "\n".join(
        lines
    )


def build_episodic_context(
    episodic_facts,
):
    if not episodic_facts:
        return (
            "No relevant episodic memories."
        )

    lines = []

    for item in episodic_facts:
        lines.append(
            f"- Memory date: {item['date']}"
        )

        lines.append(
            f"  Fact: {item['fact']}"
        )

    return "\n".join(
        lines
    )


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
    episodic_facts=None,
    interaction_gap=None,
):
    if relevant_memory_ids is None:
        relevant_memory_ids = []

    if episodic_facts is None:
        episodic_facts = []

    persona = load_persona()

    interaction_context = (
        build_interaction_context(
            interaction_gap
        )
    )

    global_communication = (
    build_global_communication_context()
)

    memories = build_memory_context(
        relevant_memory_ids
    )

    episodic_context = (
        build_episodic_context(
            episodic_facts
        )
    )

    conversation = (
        build_recent_conversation(
            session_id=session_id,
            limit=8,
        )
    )

    time_context = build_time_context()

    system_context = f"""
{persona}

GLOBAL COMMUNICATION RULES

The communication preferences above are persistent instructions about
how the user prefers Nahida to communicate.

Apply them naturally in every response.

Do not explicitly mention that these preferences came from memory.

Do not quote them back to the user unless the user specifically asks.

Communication preferences affect response style, not factual content.

CURRENT TEMPORAL CONTEXT:

{time_context}


TIME AWARENESS

The temporal context above represents the user's current local date and time.

Use it naturally when the conversation depends on time.

You may use it to understand:
- today
- tomorrow
- yesterday
- morning
- afternoon
- evening
- tonight
- the current date
- the current day of the week
- the current local time

If the user asks what time it is, answer using the current local time above.

Do not pretend that you cannot know the current time when a current
local time is provided.

Do not unnecessarily mention the exact date or time in normal conversation.

Use temporal information only when it is relevant.

INTERACTION CONTEXT:

{interaction_context}


INTERACTION AWARENESS

The interaction context tells you approximately how much time has passed
since the user's previous conversation message.

Use this information only when it naturally matters.

Do not mention the elapsed time in every response.

For very short gaps, treat the conversation as continuous.

If only a few minutes have passed, normally do not comment on the user's
absence.

If several hours have passed, you may naturally acknowledge that the
user has returned when appropriate.

If one or more days have passed, you may naturally react as though you
have not spoken for a while.

Changing sessions does not automatically mean a long time has passed.
Always consider the actual elapsed time.

Do not exaggerate the time apart.

Do not say:
"You finally came back after so long"

when only a short amount of time has passed.

Examples of natural behavior:

Short gap:
Continue the conversation normally.

Several hours:
"回来啦～"

A day or longer:
"你回来啦，今天过得怎么样？"

These are behavioral examples, not mandatory phrases.

Do not force a greeting when it would interrupt the user's current topic.

RELEVANT LONG-TERM MEMORIES:

{memories}


RELEVANT EPISODIC MEMORIES:

{episodic_context}


MEMORY USAGE RULES

The relevant memories above are trusted information retrieved from
Nahida's memory system.

If a relevant episodic memory is provided, use it when answering the
user's question.

Do NOT say that you forgot something when the answer is directly
supported by a relevant memory above.

For example, if an episodic memory says:

Memory date: 2026-08-29
Fact: The user planned to attend a comic convention the following day.

and the current date is 2026-08-29 and the user asks where they plan
to go tomorrow, then the correct remembered answer is:

The user planned to attend a comic convention.

The phrase "the following day" is relative to the memory date.

Use the memory naturally.
Do not mention databases, retrieval, summaries, or memory IDs.


MEMORY ACCURACY

Only claim to remember something when it is supported by:

1. Relevant long-term memories
2. Relevant episodic memories
3. The current session conversation

If supporting information exists, trust and use it.

If no supporting information exists, do not guess.

Never invent unsupported details such as:
- places
- activities
- clothing
- people
- food
- plans
- dates
- events

Do not add details that are not present in the supporting information.

Do not bring up unrelated memories merely to show that you remember
the user.


RESPONSE STYLE

Answer the user's current message directly.

For casual conversation, keep responses short and natural.

If the user is asking whether you remember something and a relevant
memory is available, answer confidently but naturally.
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
        temperature=0.45,
        max_tokens=160,
    ).strip()