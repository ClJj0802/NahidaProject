from datetime import datetime
from pathlib import Path

from src.database import (
    get_core_memories,
    get_global_communication_preferences,
    get_memories_by_ids,
    get_recent_messages,
)
from src.active_context import format_active_context
from src.llm_client import chat_completion


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


def build_core_memory_context():
    memories = get_core_memories()

    if not memories:
        return "No core long-term memories."

    return "\n".join(
        f"- {memory['content']}"
        for memory in memories
    )


def build_active_context(active_context):
    return format_active_context(
        active_context or {}
    )


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


def format_event_time(event):
    start_at = event.get("start_at")

    if not start_at:
        return "Unknown time"

    try:
        start = datetime.fromisoformat(
            start_at
        )
    except ValueError:
        return start_at

    precision = event.get(
        "time_precision",
        "exact",
    )

    if precision == "date":
        result = start.strftime(
            "%Y-%m-%d"
        )

    elif precision == "daypart":
        daypart = event.get(
            "time_label"
        ) or "unspecified daypart"

        result = (
            f"{start.strftime('%Y-%m-%d')} "
            f"({daypart})"
        )

    else:
        result = start.strftime(
            "%Y-%m-%d %H:%M"
        )

    end_at = event.get("end_at")

    if end_at:
        try:
            end = datetime.fromisoformat(
                end_at
            )

            if precision == "date":
                end_text = end.strftime(
                    "%Y-%m-%d"
                )
            else:
                end_text = end.strftime(
                    "%Y-%m-%d %H:%M"
                )

            if end_text not in result:
                result = (
                    f"{result} to {end_text}"
                )

        except ValueError:
            pass

    return result


def build_event_context(events):
    if not events:
        return "No relevant structured events."

    lines = []

    for event in events:
        lines.append(
            f"- {event['title']}"
        )
        lines.append(
            f"  Time: {format_event_time(event)}"
        )
        lines.append(
            f"  Status: {event.get('status', 'scheduled')}"
        )

        location = event.get("location")

        if location:
            lines.append(
                f"  Location: {location}"
            )

        recurrence = event.get(
            "recurrence_rule"
        )

        if recurrence:
            lines.append(
                f"  Recurrence: {recurrence}"
            )

        if event.get("is_override"):
            lines.append(
                "  This occurrence was moved from: "
                f"{event.get('original_occurrence_date')}"
            )

        description = event.get(
            "description"
        )

        if description:
            lines.append(
                f"  Details: {description}"
            )

        exceptions = event.get(
            "occurrence_exceptions",
            [],
        )

        for exception in exceptions:
            occurrence_date = exception.get(
                "occurrence_date"
            )
            occurrence_status = exception.get(
                "occurrence_status"
            )
            override_start = exception.get(
                "override_start_at"
            )

            if occurrence_status:
                lines.append(
                    "  Occurrence exception: "
                    f"{occurrence_date} is "
                    f"{occurrence_status}"
                )

            if override_start:
                try:
                    moved = datetime.fromisoformat(
                        override_start
                    )
                    moved_text = moved.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                except ValueError:
                    moved_text = override_start

                lines.append(
                    "  Occurrence exception: "
                    f"{occurrence_date} moved to "
                    f"{moved_text}"
                )

    return "\n".join(lines)


def build_current_event_context(events):
    if not events:
        return "No scheduled events are active today."

    return build_event_context(events)


def build_proactive_event_context(event):
    if not event:
        return (
            "No proactive event mention is available "
            "for this turn."
        )

    return build_event_context(
        [event]
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
    relevant_events=None,
    current_events=None,
    proactive_event=None,
    active_context=None,
):
    if relevant_memory_ids is None:
        relevant_memory_ids = []

    if episodic_facts is None:
        episodic_facts = []

    if relevant_events is None:
        relevant_events = []

    if current_events is None:
        current_events = []

    persona = load_persona()

    interaction_context = (
        build_interaction_context(
            interaction_gap
        )
    )

    global_communication = (
        build_global_communication_context()
    )

    core_memories = (
        build_core_memory_context()
    )

    active_context_text = (
        build_active_context(
            active_context
        )
    )

    memories = build_memory_context(
        relevant_memory_ids
    )

    episodic_context = (
        build_episodic_context(
            episodic_facts
        )
    )

    relevant_event_context = (
        build_event_context(
            relevant_events
        )
    )

    current_event_context = (
        build_current_event_context(
            current_events
        )
    )

    proactive_event_context = (
        build_proactive_event_context(
            proactive_event
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

{global_communication}

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


RELEVANT STRUCTURED EVENTS:

{relevant_event_context}


TODAY'S EVENT AWARENESS:

{current_event_context}


STRUCTURED EVENT RULES

Structured events are the authoritative source for the user's scheduled
plans, appointments, deadlines, and recurring activities.

A scheduled event proves that the user planned or scheduled something.
It does NOT prove that the event actually happened.

Do not say that an event happened unless the current conversation,
a completed event state, or another trusted memory supports that claim.

Use "tentative" events with uncertain wording. Do not present them as fixed.

If structured event information conflicts with an older episodic summary
about the current schedule, trust the structured event information for the
current plan. The episodic summary may still describe what the user had said
at that earlier time.

Do not mention today's events merely because they are present above.
They are awareness context, not a command to remind the user.

If the user asks about today's plans, a specific event, a date, a deadline,
or something directly connected to an event, use the event information
naturally and accurately.


ONE-TIME PROACTIVE EVENT OPPORTUNITY:

{proactive_event_context}


PROACTIVE EVENT BEHAVIOR

If a proactive event is provided above, you MAY casually acknowledge it once
if it fits naturally with the user's current message.

You are not required to mention it.

Do not force it into an unrelated technical or serious conversation.

Prefer a short, natural acknowledgement over a reminder-style message.

Do not interrogate the user about preparation, departure time, packing,
or other details unless the conversation naturally invites such a question.

Prefer statements such as:
"今天就是露营的日子了呢～"

over repeatedly asking reminder-like questions.

If no proactive event is provided, do not spontaneously bring up an event
solely because it appears in today's event awareness.

Never behave like a repetitive calendar notification system.


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

ACTIVE CONVERSATION CONTEXT:

{active_context_text}


ACTIVE CONTEXT RULES

The active conversation context is the authoritative short-lived map of the
current topic and currently discussed entities.

Use it to resolve pronouns and references such as:
- 她
- 他
- 那个人
- 之前那个同事
- 刚刚说的项目

If the active context explicitly resolves the latest reference to an entity,
do not silently switch that reference to another entity just because another
person has a similar role or appears nearby in the conversation.

Different entity keys represent different people/entities. Keep them distinct.


CORE LONG-TERM MEMORIES:

{core_memories}


CORE MEMORY RULES

Core memories are a very small set of durable, frequently useful facts.
They are always available, but do not bring them up unless relevant.


RELEVANT LONG-TERM / RECENT MEMORIES:

{memories}


RELEVANT EPISODIC MEMORIES:

{episodic_context}


MEMORY USAGE RULES

The relevant memories above are trusted information retrieved from
Nahida's memory system.

If a relevant episodic memory is provided, use it when answering the
user's question.

Do NOT say that you forgot something when the answer is directly
supported by a relevant memory or structured event above.

The phrase "the following day" in an episodic memory is relative to that
memory's date.

Use memory naturally.
Do not mention databases, retrieval, summaries, event IDs, or memory IDs.


MEMORY ACCURACY

Only claim to remember something when it is supported by:

1. Relevant structured events
2. Today's structured event awareness when directly relevant
3. Relevant long-term memories
4. Relevant episodic memories
5. The current session conversation

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
memory or event is available, answer confidently but naturally.
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
