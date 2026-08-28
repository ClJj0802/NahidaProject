import json
import re
from dataclasses import dataclass

from src.llm_client import chat_completion


@dataclass
class MemoryCandidate:
    category: str
    content: str
    importance: int


MEMORY_SYSTEM_PROMPT = """
You are the memory manager for a long-term AI companion named Nahida.

Your job is to decide whether the user's latest message contains information
that will still be useful in future conversations.

Do not save ordinary conversation just because it happened.

Good long-term memories include:
- Stable user preferences
- Long-term habits
- Important personal preferences
- Project decisions
- Important project state
- Long-term goals
- Important relationships or recurring entities
- Explicit requests to remember something
- Important facts that will likely matter again

Do NOT save:
- Greetings
- Small talk
- Temporary emotions
- Temporary status
- One-time questions
- Assistant answers
- Information that only matters for the current conversation
- Trivial acknowledgements such as "ok", "yes", "haha"
- Raw conversational references such as "use this one"
  unless the context clearly identifies what "this one" means

If a memory should be saved, rewrite it into a short,
self-contained factual statement.

The memory must make sense even if read several months later.

Categories:
- preference
- project
- decision
- goal
- relationship
- personal
- explicit
- other

Importance:
1-3 = low
4-6 = useful
7-8 = important
9 = very important
10 = explicitly requested permanent memory

Return ONLY valid JSON.

If it should be remembered:

{
  "should_remember": true,
  "category": "decision",
  "importance": 8,
  "memory": "Nahida uses SenseVoiceSmall as the primary STT engine."
}

If it should not be remembered:

{
  "should_remember": false,
  "category": null,
  "importance": 0,
  "memory": null
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


def build_context(messages):
    lines = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        lines.append(
            f"{role.upper()}: {content}"
        )

    return "\n".join(lines)


def analyze_memory(
    latest_message,
    recent_messages,
):
    context = build_context(recent_messages)

    prompt = f"""
Recent conversation:

{context}

Latest user message:

{latest_message}

Analyze only whether the latest user message creates or updates
useful long-term memory.

Use the recent conversation only to resolve context and references.

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
        max_tokens=200,
    )

    result = extract_json(response)

    if not result.get("should_remember"):
        return None

    category = result.get("category")
    memory = result.get("memory")
    importance = result.get("importance", 5)

    if not category or not memory:
        return None

    try:
        importance = int(importance)
    except (TypeError, ValueError):
        importance = 5

    importance = max(
        1,
        min(10, importance),
    )

    return MemoryCandidate(
        category=category,
        content=memory.strip(),
        importance=importance,
    )