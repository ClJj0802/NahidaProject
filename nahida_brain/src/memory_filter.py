import json
import re
from dataclasses import dataclass

from src.llm_client import chat_completion


@dataclass
class MemoryDecision:
    action: str
    category: str | None
    content: str | None
    importance: int
    target_memory_id: int | None
    reason: str | None


MEMORY_SYSTEM_PROMPT = """
You manage long-term memory for an AI companion named Nahida.

Analyze the user's latest message using:
1. Recent conversation context
2. Existing long-term memories

Your job is to choose exactly one action:

ADD
Create a new long-term memory when the latest message contains a useful,
durable fact that is not already represented.

UPDATE
Modify an existing memory when:
- The same fact has changed
- A preference changed
- A previous plan has progressed
- New information makes an existing memory more accurate
- A previous memory became outdated
- The latest message clarifies an existing memory

IGNORE
Do nothing when:
- The information is already stored with essentially the same meaning
- It is greeting or small talk
- It is temporary daily chatter
- It is an ordinary one-time question
- It is not useful for future conversations

Important rules:

Do not create duplicate memories.

If an existing memory already expresses the same fact, use IGNORE.

If the new information replaces or changes an existing fact,
use UPDATE and provide target_memory_id.

Preserve distinct facts separately.

For example:
"The user is a programmer."
and
"The user plans to resign from their current job."
are different facts and should not replace each other.

Rewrite memories as short, self-contained factual statements.

Avoid conversational wording such as:
"the user said..."
"the user told Nahida..."
"according to the user..."

Prefer:
"The user likes hamburgers."

Instead of:
"The user said they really like hamburgers."

Categories:
- preference
- personal
- project
- decision
- goal
- relationship
- explicit
- other

Use goal for important ongoing plans or intended future changes.

Importance:
1-3 = minor
4-6 = useful
7-8 = important
9 = very important
10 = explicitly requested permanent memory

Return ONLY valid JSON.

ADD example:

{
  "action": "add",
  "target_memory_id": null,
  "category": "preference",
  "importance": 5,
  "memory": "The user likes hamburgers.",
  "reason": "New stable preference."
}

UPDATE example:

{
  "action": "update",
  "target_memory_id": 4,
  "category": "personal",
  "importance": 8,
  "memory": "The user has resigned from their job.",
  "reason": "The previous plan to resign has now happened."
}

IGNORE example:

{
  "action": "ignore",
  "target_memory_id": 2,
  "category": null,
  "importance": 0,
  "memory": null,
  "reason": "This preference is already stored."
}
"""


def extract_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                f"Model did not return valid JSON:\n{text}"
            )

        return json.loads(match.group(0))


def build_conversation_context(messages):
    lines = []

    for message in messages:
        lines.append(
            f"{message['role'].upper()}: "
            f"{message['content']}"
        )

    if not lines:
        return "(none)"

    return "\n".join(lines)


def build_memory_context(memories):
    lines = []

    for memory in memories:
        lines.append(
            f"ID {memory['id']} | "
            f"{memory['category']} | "
            f"importance={memory['importance']} | "
            f"{memory['content']}"
        )

    if not lines:
        return "(none)"

    return "\n".join(lines)


def analyze_memory(
    latest_message,
    recent_messages,
    existing_memories,
):
    conversation_context = (
        build_conversation_context(
            recent_messages
        )
    )

    memory_context = build_memory_context(
        existing_memories
    )

    prompt = f"""
Existing long-term memories:

{memory_context}

Recent conversation before the latest message:

{conversation_context}

Latest user message:

{latest_message}

Determine whether this should ADD a memory,
UPDATE an existing memory,
or be IGNOREd.

Return JSON only.
"""

    response = chat_completion(
        messages=[
            {
                "role": "system",
                "content": MEMORY_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
        max_tokens=250,
    )

    result = extract_json(response)

    action = str(
        result.get(
            "action",
            "ignore",
        )
    ).lower()

    if action not in {
        "add",
        "update",
        "ignore",
    }:
        action = "ignore"

    target_memory_id = result.get(
        "target_memory_id"
    )

    if target_memory_id is not None:
        try:
            target_memory_id = int(
                target_memory_id
            )
        except (TypeError, ValueError):
            target_memory_id = None

    importance = result.get(
        "importance",
        0,
    )

    try:
        importance = int(importance)
    except (TypeError, ValueError):
        importance = 0

    importance = max(
        0,
        min(10, importance),
    )

    return MemoryDecision(
        action=action,
        target_memory_id=target_memory_id,
        category=result.get("category"),
        content=result.get("memory"),
        importance=importance,
        reason=result.get("reason"),
    )