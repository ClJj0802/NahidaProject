import json
import re
from dataclasses import dataclass

from src.active_context import (
    empty_active_context,
    normalize_active_context,
    format_active_context,
)
from src.llm_client import chat_completion


VALID_ACTIONS = {
    "add",
    "update",
}

VALID_MEMORY_TYPES = {
    "fixed",
    "short_term_episode",
    "autobiographical",
}

VALID_CATEGORIES = {
    "preference",
    "personal",
    "project",
    "decision",
    "goal",
    "relationship",
    "explicit",
    "communication",
    "other",
}

VALID_TTL_DAYS = {
    1,
    3,
    7,
    30,
}


@dataclass
class MemoryOperation:
    action: str
    target_memory_id: int | None
    memory_type: str
    category: str
    content: str
    importance: int
    confidence: float
    ttl_days: int | None
    is_core: bool
    reason: str | None


@dataclass
class MemoryDecision:
    operations: list[MemoryOperation]
    relevant_memory_ids: list[int]
    active_context: dict
    reason: str | None


MEMORY_SYSTEM_PROMPT = r"""
You manage memory and active conversation context for an AI companion named Nahida.

You receive:

1. Existing persistent memories
2. The current Active Context
3. Recent conversation before the latest message
4. The latest user message

You have THREE independent jobs:

A. UPDATE ACTIVE CONTEXT
B. RETRIEVE EXISTING MEMORIES
C. WRITE NEW OR UPDATED MEMORIES

Return one JSON object only.

==================================================
A. ACTIVE CONTEXT
==================================================

Active Context tracks the CURRENT conversation topic, people, entities,
and pronoun/reference resolution.

It is short-lived and is NOT permanent memory.

Use it to distinguish people such as:

- the coworker the user dislikes
- another coworker the user enjoys working with
- the user's manager
- a friend
- a project currently being discussed

Reuse an existing entity key whenever the same person/entity is referenced.

When a new unnamed entity is introduced, create a short stable ASCII key,
for example:

coworker_disliked
coworker_good
manager
friend_apex
project_new

Do not rename an existing entity key merely because a new alias is used.

The "latest_reference" field should resolve an ambiguous reference in the
latest message when the surrounding conversation makes it clear.

Example:

If active context contains:

coworker_disliked = coworker who often suspects the user's intentions
coworker_good = coworker the user enjoys working with

and the latest message is:

"现在领导又叫我跟她合作。"

If "她" refers to coworker_disliked, return:

"latest_reference": {
  "surface": "她",
  "entity_key": "coworker_disliked"
}

Never merge two different people just because they have the same role.

Keep at most 12 active entities.

==================================================
B. MEMORY RETRIEVAL
==================================================

Return the smallest set of existing memory IDs that genuinely help answer
the latest user message.

Do not retrieve a memory merely because it is vaguely related.
Do not retrieve communication memories unless the user explicitly asks about
communication preferences; they are injected globally elsewhere.

Existing short-term memories are valid recent context until they expire.
Existing fixed memories are durable facts.
Existing autobiographical memories are important past experiences.

==================================================
C. MEMORY WRITING
==================================================

A single user message may create ZERO, ONE, OR MULTIPLE memory operations.

Use these memory types:

1. fixed
2. short_term_episode
3. autobiographical

--------------------------------------------------
FIXED
--------------------------------------------------

Use for durable facts expected to remain useful for months or years.

Examples:
- occupation
- current company
- stable preferences
- important relationships
- pet ownership
- club membership
- durable life state
- stable communication preference
- important long-running project fact

Do NOT use fixed for temporary daily details.

--------------------------------------------------
SHORT_TERM_EPISODE
--------------------------------------------------

Use for recent high-detail life context that should eventually expire.

Examples:
- ate nasi lemak this morning
- feels frustrated today because of a coworker
- drank Mixue today
- bought a favorite plush toy today
- recently had a specific workplace incident
- plans to play Apex later today

Preserve useful detail, especially who did what and why it matters.

TTL rules:

1 day:
very minor temporary detail

3 days:
normal daily-life detail

7 days:
important recent situation, emotion, conflict, or ongoing short episode

30 days:
unusually meaningful recent episode that may later be promoted

--------------------------------------------------
AUTOBIOGRAPHICAL
--------------------------------------------------

Use only for a genuinely important life experience that has happened and is
worth keeping for the long term.

Examples:
- first trip to Japan
- graduation
- adopting an important pet
- leaving a company after a major chapter of life

Do not overuse this type.

==================================================
TEMPORAL EVENT COEXISTENCE
==================================================

A separate structured Event system manages authoritative schedules,
appointments, deadlines, trips, and recurring events.

Do NOT store a scheduled occurrence as FIXED just because it is in the future.

However, a same-day or recent plan may also be kept as a SHORT_TERM_EPISODE
when it is useful immediate conversational context.

The Event system remains authoritative for exact schedule/status.

==================================================
MULTIPLE MEMORIES FROM ONE MESSAGE
==================================================

Example:

"我今天养了一只猫，叫Momo。"

Possible operations:

1. fixed:
   "The user has a cat named Momo."

2. short_term_episode:
   "The user adopted a cat named Momo today."

A later memory consolidation process may promote important episodes.

==================================================
UPDATES
==================================================

Use update when a memory has changed or become more accurate.

Examples:

Existing:
"The user plans to resign from their job."

Latest:
"我已经辞职了。"

Update the existing memory rather than adding a duplicate.

Do not overwrite a separate fact that remains true.

==================================================
CONFIDENCE
==================================================

Use confidence from 0.0 to 1.0.

Explicit user statement:
0.95 - 1.00

Strong inference from clear context:
0.70 - 0.85

Weak inference:
0.40 - 0.60

Do not permanently store weak model guesses.

==================================================
CORE MEMORY
==================================================

Set is_core=true only for a small number of very important, frequently useful
fixed memories that should be injected in every conversation.

Examples may include:
- occupation
- major current life state
- the user's central relationship with Nahida
- major long-running project identity

Most fixed memories should NOT be core.

==================================================
WRITING STYLE
==================================================

Memory content must be short, self-contained factual statements.

Prefer:
"The user is a programmer."

Avoid:
"The user told Nahida that they are a programmer."

For short-term episodes, preserve enough detail to distinguish entities and
causal relationships.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON with exactly these top-level keys:

{
  "relevant_memory_ids": [],
  "active_context": {
    "topic": null,
    "last_entity_key": null,
    "latest_reference": null,
    "entities": []
  },
  "operations": [],
  "reason": null
}

Each entity must use:

{
  "key": "coworker_disliked",
  "role": "coworker",
  "description": "coworker who often suspects the user's intentions",
  "aliases": ["之前那个女同事", "讨厌的同事"]
}

Each operation must use:

{
  "action": "add|update",
  "target_memory_id": null,
  "memory_type": "fixed|short_term_episode|autobiographical",
  "category": "preference|personal|project|decision|goal|relationship|explicit|communication|other",
  "importance": 1,
  "confidence": 1.0,
  "ttl_days": null,
  "is_core": false,
  "memory": "...",
  "reason": "..."
}

Rules:
- target_memory_id must be null for add.
- target_memory_id must be a valid existing ID for update.
- ttl_days must be null for fixed/autobiographical.
- ttl_days must be one of 1, 3, 7, 30 for short_term_episode.
- Return no operation for greetings, filler, or facts not worth storing.
- Never invent an existing memory ID.
- Do not use Markdown or code fences.
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
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(
                f"Model did not return valid JSON:\n{text}"
            )
        return json.loads(match.group(0))


def build_conversation_context(messages):
    lines = []

    for message in messages:
        lines.append(
            f"{message['role'].upper()}: {message['content']}"
        )

    return "\n".join(lines) if lines else "(none)"


def build_memory_context(memories):
    lines = []

    for memory in memories:
        keys = set(memory.keys())
        memory_type = (
            memory["memory_type"]
            if "memory_type" in keys
            else "fixed"
        )
        expires_at = (
            memory["expires_at"]
            if "expires_at" in keys
            else None
        )
        confidence = (
            memory["confidence"]
            if "confidence" in keys
            else 1.0
        )

        lines.append(
            " | ".join(
                [
                    f"ID {memory['id']}",
                    f"type={memory_type}",
                    f"category={memory['category']}",
                    f"importance={memory['importance']}",
                    f"confidence={confidence}",
                    f"expires={expires_at or '-'}",
                    memory["content"],
                ]
            )
        )

    return "\n".join(lines) if lines else "(none)"


def _normalize_relevant_ids(raw_ids, valid_ids):
    if not isinstance(raw_ids, list):
        return []

    result = []
    seen = set()

    for raw_id in raw_ids:
        try:
            memory_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if memory_id not in valid_ids or memory_id in seen:
            continue

        seen.add(memory_id)
        result.append(memory_id)

    return result


def _normalize_operation(raw, valid_ids):
    if not isinstance(raw, dict):
        return None

    action = str(raw.get("action", "")).lower().strip()
    if action not in VALID_ACTIONS:
        return None

    memory_type = str(
        raw.get("memory_type", "fixed")
    ).lower().strip()
    if memory_type not in VALID_MEMORY_TYPES:
        memory_type = "fixed"

    category = str(raw.get("category", "other")).lower().strip()
    if category not in VALID_CATEGORIES:
        category = "other"

    content = str(raw.get("memory", "")).strip()
    if not content:
        return None

    try:
        importance = int(raw.get("importance", 5))
    except (TypeError, ValueError):
        importance = 5
    importance = max(1, min(10, importance))

    try:
        confidence = float(raw.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 1.0
    confidence = max(0.0, min(1.0, confidence))

    ttl_days = raw.get("ttl_days")
    if memory_type == "short_term_episode":
        try:
            ttl_days = int(ttl_days)
        except (TypeError, ValueError):
            ttl_days = 3

        if ttl_days not in VALID_TTL_DAYS:
            ttl_days = min(
                VALID_TTL_DAYS,
                key=lambda value: abs(value - ttl_days),
            )
    else:
        ttl_days = None

    is_core = bool(raw.get("is_core", False))
    if memory_type != "fixed":
        is_core = False

    target_memory_id = raw.get("target_memory_id")

    if action == "add":
        target_memory_id = None
    else:
        try:
            target_memory_id = int(target_memory_id)
        except (TypeError, ValueError):
            return None

        if target_memory_id not in valid_ids:
            return None

    reason = raw.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None

    return MemoryOperation(
        action=action,
        target_memory_id=target_memory_id,
        memory_type=memory_type,
        category=category,
        content=content,
        importance=importance,
        confidence=confidence,
        ttl_days=ttl_days,
        is_core=is_core,
        reason=reason,
    )


def analyze_memory(
    latest_message,
    recent_messages,
    existing_memories,
    active_context=None,
):
    active_context = normalize_active_context(
        active_context or empty_active_context()
    )

    memory_context = build_memory_context(existing_memories)
    conversation_context = build_conversation_context(recent_messages)
    active_context_text = format_active_context(active_context)

    prompt = f"""
Existing persistent memories:

{memory_context}

Current Active Context:

{active_context_text}

Recent conversation before the latest message:

{conversation_context}

Latest user message:

{latest_message}

Perform all three jobs:

1. Update Active Context and resolve the latest references.
2. Select relevant existing memory IDs.
3. Return zero or more memory write operations.

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
        max_tokens=700,
    )

    result = extract_json(response)

    valid_ids = {int(memory["id"]) for memory in existing_memories}

    relevant_memory_ids = _normalize_relevant_ids(
        result.get("relevant_memory_ids", []),
        valid_ids,
    )

    new_active_context = normalize_active_context(
        result.get("active_context", active_context)
    )

    raw_operations = result.get("operations", [])
    operations = []

    if isinstance(raw_operations, list):
        for raw in raw_operations[:4]:
            operation = _normalize_operation(raw, valid_ids)
            if operation is not None:
                operations.append(operation)

    reason = result.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None

    return MemoryDecision(
        operations=operations,
        relevant_memory_ids=relevant_memory_ids,
        active_context=new_active_context,
        reason=reason,
    )
