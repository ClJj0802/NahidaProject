import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from src.database import (
    get_active_events,
    get_event,
    get_event_candidates,
    get_event_occurrence_state,
    get_event_occurrence_overrides_for_date,
    get_event_occurrence_states_for_event_ids,
    get_events_by_ids,
    count_event_interactions_for_date,
    mark_event_occurrence_acknowledged,
    mark_event_occurrence_surfaced,
    save_event,
    set_event_occurrence_override,
    set_event_occurrence_status,
    set_event_status,
    update_event,
)
from src.llm_client import chat_completion


VALID_ACTIONS = {
    "add",
    "update",
    "cancel",
    "complete",
    "ignore",
}

VALID_STATUSES = {
    "scheduled",
    "tentative",
    "cancelled",
    "completed",
}

VALID_TIME_PRECISIONS = {
    "exact",
    "daypart",
    "date",
}

VALID_TIME_LABELS = {
    "morning",
    "afternoon",
    "evening",
    "night",
}

WEEKDAY_CODES = {
    0: "MO",
    1: "TU",
    2: "WE",
    3: "TH",
    4: "FR",
    5: "SA",
    6: "SU",
}

CODE_WEEKDAYS = {
    value: key
    for key, value in WEEKDAY_CODES.items()
}


@dataclass
class TemporalDecision:
    action: str
    target_event_id: int | None
    scope: str
    occurrence_date: str | None
    relevant_event_ids: list[int]
    changed_fields: list[str]
    title: str | None
    description: str | None
    location: str | None
    start_at: str | None
    end_at: str | None
    all_day: bool
    time_precision: str
    time_label: str | None
    timezone: str | None
    recurrence_rule: str | None
    status: str | None
    reason: str | None


TEMPORAL_SYSTEM_PROMPT = """
You manage structured temporal events for an AI companion named Nahida.

You receive:

1. The user's current local date and time
2. Recent conversation context
3. Existing structured events
4. The user's latest message

You have two independent responsibilities:

A. EVENT STORAGE

Decide whether the latest user message should:

- add: create a new scheduled or tentative event
- update: change an existing event
- cancel: cancel an existing event or one occurrence of a recurring event
- complete: mark an existing event or occurrence as completed
- ignore: make no event database change

B. EVENT RETRIEVAL

Return the smallest set of existing event IDs that genuinely help answer
or understand the user's latest message in relevant_event_ids.

Do not retrieve unrelated events merely because they are upcoming.


WHAT COUNTS AS AN EVENT

Create an event when the user expresses a real plan, appointment,
commitment, deadline, scheduled activity, reminder-worthy future action,
or recurring routine with meaningful temporal information.

Examples:

"9月12号我要去露营"
"明天下午去拿包裹"
"今晚8点打Apex"
"这个星期五跟朋友吃饭"
"9月12号到14号去露营"
"每个星期六练弓"
"月底要交报告"
"两小时后要关电脑"

Do not create an event for:

- a question with no asserted plan
- a hypothetical
- an unsupported guess
- a stable long-term goal without a scheduled occurrence
- a vague wish with no meaningful time anchor

Examples that are NOT temporal events:

"以后想学日语"
"如果周六去露营会怎样？"
"我是不是9月12号要去露营？" when no existing event supports it

A durable long-term goal belongs to long-term memory, not this system.
A concrete scheduled occurrence belongs here.


CERTAINTY

Use status "scheduled" for a clear plan or commitment.

Use status "tentative" only when the user describes a genuine but uncertain
plan using language such as maybe, possibly, probably, 应该, 可能, 也许.

Do not turn a hypothetical into a tentative event.


TIME NORMALIZATION

Resolve relative temporal expressions against the supplied current local
 date and time.

Return ISO 8601 local datetimes.

Examples:

2026-09-12T20:00:00+08:00
2026-09-12T00:00:00+08:00

Rules:

- If the user gives an exact clock time, use time_precision "exact".
- If only a date is known, use time_precision "date" and all_day true.
- If the user gives a daypart but no clock time, use time_precision
  "daypart", all_day false, and one of:
  morning, afternoon, evening, night.
- For a daypart event, start_at should use 00:00 on the resolved date.
  Do not invent a fake exact clock time.
- If a month and day are given without a year, choose the nearest sensible
  occurrence based on the current date and conversation context. For a
  future plan, prefer the upcoming occurrence, not a past date.
- Preserve explicit date ranges using start_at and end_at.
- For an all-day multi-day range, end_at should represent the end date at
  23:59:59 local time.
- If the user says "two hours later" or another relative duration, resolve
  it from the supplied current local datetime.

Do not fabricate precision the user did not provide.


RECURRENCE

Use recurrence_rule only for clearly recurring events.

Use a small RFC5545-style subset:

FREQ=DAILY
FREQ=DAILY;INTERVAL=2
FREQ=WEEKLY;BYDAY=SA
FREQ=WEEKLY;BYDAY=MO,WE,FR
FREQ=MONTHLY;BYMONTHDAY=15
FREQ=YEARLY;BYMONTH=9;BYMONTHDAY=12

Optional UNTIL may be appended using YYYY-MM-DD:

FREQ=WEEKLY;BYDAY=SA;UNTIL=2026-12-31

Do not create recurrence for a one-time event.


UPDATES AND CANCELLATIONS

Use target_event_id only when the user clearly refers to an existing event.

For update, use changed_fields to name exactly which event fields the user
wants to change. Valid names are:

title, description, location, start_at, end_at, all_day, time_precision,
time_label, timezone, recurrence_rule, status

Fields not listed in changed_fields are preserved. A field listed in
changed_fields may intentionally be null, for example recurrence_rule=null
when the user says an event should stop repeating.

For cancel or complete:

- scope "event" means the whole one-time event or entire recurring series.
- scope "occurrence" means only one occurrence of a recurring event.
- occurrence_date must be YYYY-MM-DD when scope is "occurrence".

Never cancel or modify an unrelated event just because it is temporally close.

If the user asks about an event without changing it, use action "ignore" and
return its ID in relevant_event_ids.


DUPLICATES

If an existing event already represents the same plan and the user merely
repeats it, use ignore and retrieve that event instead of adding a duplicate.


OUTPUT

Return ONLY valid JSON with exactly these keys:

{
  "action": "add|update|cancel|complete|ignore",
  "target_event_id": null,
  "scope": "event|occurrence",
  "occurrence_date": null,
  "relevant_event_ids": [],
  "changed_fields": [],
  "title": null,
  "description": null,
  "location": null,
  "start_at": null,
  "end_at": null,
  "all_day": false,
  "time_precision": "exact|daypart|date",
  "time_label": null,
  "timezone": null,
  "recurrence_rule": null,
  "status": null,
  "reason": null
}

Do not use Markdown.
Do not use code fences.
Do not add text before or after the JSON.
"""


EVENT_RETRIEVAL_FALLBACK_PROMPT = """
You retrieve structured scheduled events for Nahida.

Select the smallest set of event IDs that genuinely help answer the user's
latest message.

Pay attention to event titles, dates, times, locations, status, and recurrence.
Do not select unrelated events.
Do not invent IDs.

Return only valid JSON:

{
  "relevant_event_ids": []
}
"""


def get_local_now():
    return datetime.now().astimezone()


def get_timezone_label(now=None):
    if now is None:
        now = get_local_now()

    name = now.tzname()
    offset = now.strftime("%z")

    if name and offset:
        return f"{name} ({offset})"

    if name:
        return name

    return offset or "local"


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

        return json.loads(
            match.group(0)
        )


def build_conversation_context(messages):
    lines = []

    for message in messages:
        role = str(
            message["role"]
        ).upper()

        lines.append(
            f"{role}: {message['content']}"
        )

    if not lines:
        return "(none)"

    return "\n".join(lines)


def build_event_catalog(
    events,
    occurrence_states=None,
):
    state_map = {}

    if occurrence_states:
        for state in occurrence_states:
            event_id = int(
                state["event_id"]
            )

            state_map.setdefault(
                event_id,
                [],
            ).append(state)

    lines = []

    for event in events:
        event_id = int(event["id"])

        lines.append(
            " | ".join(
                [
                    f"ID {event_id}",
                    f"status={event['status']}",
                    f"title={event['title']}",
                    f"start={event['start_at']}",
                    f"end={event['end_at'] or '-'}",
                    f"precision={event['time_precision']}",
                    f"daypart={event['time_label'] or '-'}",
                    f"location={event['location'] or '-'}",
                    f"recurrence={event['recurrence_rule'] or '-'}",
                ]
            )
        )

        for state in state_map.get(
            event_id,
            [],
        ):
            details = [
                f"occurrence={state['occurrence_date']}"
            ]

            if state["occurrence_status"]:
                details.append(
                    "status="
                    f"{state['occurrence_status']}"
                )

            if state["override_start_at"]:
                details.append(
                    "moved_start="
                    f"{state['override_start_at']}"
                )

            if state["override_end_at"]:
                details.append(
                    "moved_end="
                    f"{state['override_end_at']}"
                )

            if state["override_title"]:
                details.append(
                    "title="
                    f"{state['override_title']}"
                )

            if state["override_location"]:
                details.append(
                    "location="
                    f"{state['override_location']}"
                )

            lines.append(
                "  exception: "
                + " | ".join(details)
            )

    if not lines:
        return "(none)"

    return "\n".join(lines)


def normalize_optional_text(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def normalize_datetime_value(
    value,
    now,
    default_to_end_of_day=False,
):
    value = normalize_optional_text(value)

    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(value)

    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid ISO datetime: {value}"
            ) from exc

        parsed_time = (
            time(23, 59, 59)
            if default_to_end_of_day
            else time(0, 0, 0)
        )

        parsed = datetime.combine(
            parsed_date,
            parsed_time,
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=now.tzinfo
        )

    return parsed.isoformat(
        timespec="seconds"
    )


def normalize_recurrence_rule(value):
    value = normalize_optional_text(value)

    if value is None:
        return None

    value = value.upper().replace(" ", "")

    if not value.startswith("FREQ="):
        return None

    return value


def parse_id_list(raw_ids, valid_ids):
    if not isinstance(raw_ids, list):
        return []

    result = []
    seen = set()

    for raw_id in raw_ids:
        try:
            event_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if event_id not in valid_ids:
            continue

        if event_id in seen:
            continue

        seen.add(event_id)
        result.append(event_id)

    return result


def analyze_temporal_message(
    latest_message,
    recent_messages,
    existing_events,
):
    now = get_local_now()

    conversation_context = (
        build_conversation_context(
            recent_messages
        )
    )

    event_ids = [
        int(event["id"])
        for event in existing_events
    ]

    occurrence_states = (
        get_event_occurrence_states_for_event_ids(
            event_ids,
            limit=300,
        )
    )

    event_catalog = build_event_catalog(
        existing_events,
        occurrence_states=occurrence_states,
    )

    prompt = f"""
Current local datetime:
{now.isoformat(timespec='seconds')}

Current timezone:
{get_timezone_label(now)}

Recent conversation before the latest message:
{conversation_context}

Existing structured events:
{event_catalog}

Latest user message:
{latest_message}

Analyze event storage and event retrieval.
Return JSON only.
"""

    response = chat_completion(
        messages=[
            {
                "role": "system",
                "content": TEMPORAL_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
        max_tokens=500,
    )

    result = extract_json(response)

    action = str(
        result.get(
            "action",
            "ignore",
        )
    ).lower()

    if action not in VALID_ACTIONS:
        action = "ignore"

    target_event_id = result.get(
        "target_event_id"
    )

    if target_event_id is not None:
        try:
            target_event_id = int(
                target_event_id
            )
        except (TypeError, ValueError):
            target_event_id = None

    valid_ids = {
        int(event["id"])
        for event in existing_events
    }

    if (
        target_event_id is not None
        and target_event_id not in valid_ids
    ):
        target_event_id = None

    relevant_event_ids = parse_id_list(
        result.get(
            "relevant_event_ids",
            [],
        ),
        valid_ids,
    )

    allowed_changed_fields = {
        "title",
        "description",
        "location",
        "start_at",
        "end_at",
        "all_day",
        "time_precision",
        "time_label",
        "timezone",
        "recurrence_rule",
        "status",
    }

    raw_changed_fields = result.get(
        "changed_fields",
        [],
    )

    changed_fields = []

    if isinstance(raw_changed_fields, list):
        for field_name in raw_changed_fields:
            field_name = str(
                field_name
            ).strip()

            if field_name in allowed_changed_fields:
                changed_fields.append(
                    field_name
                )

    changed_fields = list(
        dict.fromkeys(changed_fields)
    )

    scope = str(
        result.get(
            "scope",
            "event",
        )
    ).lower()

    if scope not in {
        "event",
        "occurrence",
    }:
        scope = "event"

    occurrence_date = normalize_optional_text(
        result.get(
            "occurrence_date"
        )
    )

    if occurrence_date is not None:
        try:
            date.fromisoformat(
                occurrence_date
            )
        except ValueError:
            occurrence_date = None

    time_precision = str(
        result.get(
            "time_precision",
            "exact",
        )
    ).lower()

    if time_precision not in VALID_TIME_PRECISIONS:
        time_precision = "exact"

    raw_all_day = result.get(
        "all_day",
        False,
    )

    all_day = bool(raw_all_day)

    if time_precision == "date":
        all_day = True

    time_label = normalize_optional_text(
        result.get(
            "time_label"
        )
    )

    if time_label is not None:
        time_label = time_label.lower()

    if (
        time_precision != "daypart"
        or time_label not in VALID_TIME_LABELS
    ):
        time_label = None

    start_at = normalize_datetime_value(
        result.get(
            "start_at"
        ),
        now=now,
    )

    end_at = normalize_datetime_value(
        result.get(
            "end_at"
        ),
        now=now,
        default_to_end_of_day=all_day,
    )

    if start_at and end_at:
        if (
            datetime.fromisoformat(end_at)
            < datetime.fromisoformat(start_at)
        ):
            end_at = None

    status = normalize_optional_text(
        result.get(
            "status"
        )
    )

    if status is not None:
        status = status.lower()

    if status not in VALID_STATUSES:
        status = None

    recurrence_rule = normalize_recurrence_rule(
        result.get(
            "recurrence_rule"
        )
    )

    decision = TemporalDecision(
        action=action,
        target_event_id=target_event_id,
        scope=scope,
        occurrence_date=occurrence_date,
        relevant_event_ids=(
            relevant_event_ids
        ),
        changed_fields=changed_fields,
        title=normalize_optional_text(
            result.get("title")
        ),
        description=normalize_optional_text(
            result.get("description")
        ),
        location=normalize_optional_text(
            result.get("location")
        ),
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        time_precision=time_precision,
        time_label=time_label,
        timezone=(
            normalize_optional_text(
                result.get("timezone")
            )
            or get_timezone_label(now)
        ),
        recurrence_rule=recurrence_rule,
        status=status,
        reason=normalize_optional_text(
            result.get("reason")
        ),
    )

    if decision.action == "add":
        if (
            not decision.title
            or not decision.start_at
        ):
            decision.action = "ignore"

    if decision.action in {
        "update",
        "cancel",
        "complete",
    }:
        if decision.target_event_id is None:
            decision.action = "ignore"
            decision.scope = "event"
            decision.occurrence_date = None

    if (
        decision.scope == "occurrence"
        and decision.occurrence_date is None
    ):
        decision.scope = "event"

    return decision


def event_to_dict(event):
    if event is None:
        return None

    return {
        key: event[key]
        for key in event.keys()
    }


def event_signature(
    title,
    start_at,
    recurrence_rule,
):
    return (
        title.casefold().strip(),
        start_at,
        recurrence_rule or "",
    )


def find_exact_duplicate(
    existing_events,
    title,
    start_at,
    recurrence_rule,
):
    target = event_signature(
        title,
        start_at,
        recurrence_rule,
    )

    for event in existing_events:
        if event["status"] in {
            "cancelled",
            "completed",
        }:
            continue

        current = event_signature(
            event["title"],
            event["start_at"],
            event["recurrence_rule"],
        )

        if current == target:
            return event

    return None


def merge_event_update(
    current,
    decision,
    source_message_id,
):
    changed = set(
        decision.changed_fields
    )

    if not changed:
        if decision.title is not None:
            changed.add("title")
        if decision.description is not None:
            changed.add("description")
        if decision.location is not None:
            changed.add("location")
        if decision.start_at is not None:
            changed.update(
                {
                    "start_at",
                    "all_day",
                    "time_precision",
                    "time_label",
                    "timezone",
                }
            )
        if decision.end_at is not None:
            changed.add("end_at")
        if decision.recurrence_rule is not None:
            changed.add("recurrence_rule")
        if decision.status is not None:
            changed.add("status")

    title = (
        decision.title
        if "title" in changed
        and decision.title is not None
        else current["title"]
    )

    description = (
        decision.description
        if "description" in changed
        else current["description"]
    )

    location = (
        decision.location
        if "location" in changed
        else current["location"]
    )

    start_at = (
        decision.start_at
        if "start_at" in changed
        and decision.start_at is not None
        else current["start_at"]
    )

    end_at = (
        decision.end_at
        if "end_at" in changed
        else current["end_at"]
    )

    all_day = (
        decision.all_day
        if "all_day" in changed
        else bool(current["all_day"])
    )

    time_precision = (
        decision.time_precision
        if "time_precision" in changed
        else current["time_precision"]
    )

    time_label = (
        decision.time_label
        if "time_label" in changed
        else current["time_label"]
    )

    timezone = (
        decision.timezone
        if "timezone" in changed
        else current["timezone"]
    )

    recurrence_rule = (
        decision.recurrence_rule
        if "recurrence_rule" in changed
        else current["recurrence_rule"]
    )

    status = (
        decision.status
        if "status" in changed
        and decision.status is not None
        else current["status"]
    )

    return update_event(
        event_id=current["id"],
        title=title,
        description=description,
        location=location,
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        time_precision=time_precision,
        time_label=time_label,
        timezone=timezone,
        recurrence_rule=recurrence_rule,
        status=status,
        source_message_id=source_message_id,
    )


def process_temporal_memory(
    latest_message,
    message_id,
    recent_messages,
):
    existing_events = get_event_candidates(
        limit=80
    )

    print("[Temporal] Analyzing...")

    try:
        decision = analyze_temporal_message(
            latest_message=latest_message,
            recent_messages=recent_messages,
            existing_events=existing_events,
        )

    except Exception as exc:
        print(
            f"[Temporal] Analysis failed: {exc}"
        )
        return []

    relevant_event_ids = list(
        decision.relevant_event_ids
    )

    if decision.action == "ignore":
        if relevant_event_ids:
            print(
                "[Temporal] Relevant: "
                f"{relevant_event_ids}"
            )
        else:
            print("[Temporal] IGNORE")

        return relevant_event_ids

    if decision.action == "add":
        duplicate = find_exact_duplicate(
            existing_events=existing_events,
            title=decision.title,
            start_at=decision.start_at,
            recurrence_rule=(
                decision.recurrence_rule
            ),
        )

        if duplicate is not None:
            event_id = int(
                duplicate["id"]
            )

            if event_id not in relevant_event_ids:
                relevant_event_ids.append(
                    event_id
                )

            print(
                f"[Temporal] DUPLICATE #{event_id}: "
                f"{duplicate['title']}"
            )

            return relevant_event_ids

        event_id = save_event(
            title=decision.title,
            description=decision.description,
            location=decision.location,
            start_at=decision.start_at,
            end_at=decision.end_at,
            all_day=decision.all_day,
            time_precision=(
                decision.time_precision
            ),
            time_label=decision.time_label,
            timezone=decision.timezone,
            recurrence_rule=(
                decision.recurrence_rule
            ),
            status=(
                decision.status
                or "scheduled"
            ),
            source_message_id=message_id,
        )

        relevant_event_ids.append(
            event_id
        )

        relevant_event_ids = list(
            dict.fromkeys(
                relevant_event_ids
            )
        )

        print(
            f"[Temporal] ADD #{event_id}: "
            f"{decision.title} @ "
            f"{decision.start_at}"
        )

        return relevant_event_ids

    current = get_event(
        decision.target_event_id
    )

    if current is None:
        print("[Temporal] Target event missing.")
        return relevant_event_ids

    target_event_id = int(
        current["id"]
    )

    if target_event_id not in relevant_event_ids:
        relevant_event_ids.append(
            target_event_id
        )

    if decision.action == "update":
        if decision.scope == "occurrence":
            if not current["recurrence_rule"]:
                print(
                    "[Temporal] Occurrence update requested "
                    "for a non-recurring event."
                )
                return relevant_event_ids

            original_date = date.fromisoformat(
                decision.occurrence_date
            )

            original_start = (
                occurrence_start_for_date(
                    current,
                    original_date,
                )
            )

            original_end = (
                occurrence_end_for_date(
                    current,
                    original_date,
                    original_start,
                )
            )

            changed = set(
                decision.changed_fields
            )

            override_start = (
                decision.start_at
                if "start_at" in changed
                and decision.start_at is not None
                else original_start.isoformat(
                    timespec="seconds"
                )
            )

            override_end = (
                decision.end_at
                if "end_at" in changed
                else (
                    original_end.isoformat(
                        timespec="seconds"
                    )
                    if original_end
                    else None
                )
            )

            override_title = (
                decision.title
                if "title" in changed
                else None
            )

            override_location = (
                decision.location
                if "location" in changed
                else None
            )

            override_all_day = (
                decision.all_day
                if "all_day" in changed
                else bool(current["all_day"])
            )

            override_precision = (
                decision.time_precision
                if "time_precision" in changed
                else current["time_precision"]
            )

            override_time_label = (
                decision.time_label
                if "time_label" in changed
                else current["time_label"]
            )

            set_event_occurrence_override(
                event_id=target_event_id,
                occurrence_date=(
                    decision.occurrence_date
                ),
                title=override_title,
                location=override_location,
                start_at=override_start,
                end_at=override_end,
                all_day=override_all_day,
                time_precision=(
                    override_precision
                ),
                time_label=(
                    override_time_label
                ),
            )

            print(
                f"[Temporal] UPDATE occurrence "
                f"#{target_event_id} "
                f"[{decision.occurrence_date}] "
                f"-> {override_start}"
            )

            return relevant_event_ids

        success = merge_event_update(
            current=current,
            decision=decision,
            source_message_id=message_id,
        )

        if success:
            print(
                f"[Temporal] UPDATE #{target_event_id}"
            )

        return relevant_event_ids

    new_status = (
        "cancelled"
        if decision.action == "cancel"
        else "completed"
    )

    if decision.scope == "occurrence":
        set_event_occurrence_status(
            event_id=target_event_id,
            occurrence_date=(
                decision.occurrence_date
            ),
            status=new_status,
        )

        print(
            f"[Temporal] {new_status.upper()} "
            f"occurrence #{target_event_id} "
            f"[{decision.occurrence_date}]"
        )

    else:
        set_event_status(
            event_id=target_event_id,
            status=new_status,
            source_message_id=message_id,
        )

        print(
            f"[Temporal] {new_status.upper()} "
            f"#{target_event_id}"
        )

    return relevant_event_ids


def parse_recurrence_rule(rule):
    if not rule:
        return {}

    parts = {}

    for component in rule.split(";"):
        if "=" not in component:
            continue

        key, value = component.split(
            "=",
            1,
        )

        key = key.strip().upper()
        value = value.strip().upper()

        if key:
            parts[key] = value

    return parts


def months_between(start_date, target_date):
    return (
        (target_date.year - start_date.year) * 12
        + target_date.month
        - start_date.month
    )


def recurrence_matches_date(
    event,
    target_date,
):
    rule = parse_recurrence_rule(
        event["recurrence_rule"]
    )

    if not rule:
        return False

    start_dt = datetime.fromisoformat(
        event["start_at"]
    )
    start_date = start_dt.date()

    if target_date < start_date:
        return False

    until_text = rule.get("UNTIL")

    if until_text:
        try:
            until_date = date.fromisoformat(
                until_text
            )

            if target_date > until_date:
                return False

        except ValueError:
            pass

    try:
        interval = max(
            1,
            int(rule.get("INTERVAL", "1")),
        )
    except ValueError:
        interval = 1

    frequency = rule.get("FREQ")

    if frequency == "DAILY":
        days = (
            target_date - start_date
        ).days

        return days % interval == 0

    if frequency == "WEEKLY":
        day_codes = rule.get("BYDAY")

        if day_codes:
            allowed_weekdays = {
                CODE_WEEKDAYS[code]
                for code in day_codes.split(",")
                if code in CODE_WEEKDAYS
            }
        else:
            allowed_weekdays = {
                start_date.weekday()
            }

        if target_date.weekday() not in allowed_weekdays:
            return False

        start_week = (
            start_date
            - timedelta(
                days=start_date.weekday()
            )
        )

        target_week = (
            target_date
            - timedelta(
                days=target_date.weekday()
            )
        )

        weeks = (
            target_week - start_week
        ).days // 7

        return weeks % interval == 0

    if frequency == "MONTHLY":
        month_delta = months_between(
            start_date,
            target_date,
        )

        if month_delta % interval != 0:
            return False

        raw_days = rule.get(
            "BYMONTHDAY"
        )

        if raw_days:
            allowed_days = set()

            for value in raw_days.split(","):
                try:
                    allowed_days.add(
                        int(value)
                    )
                except ValueError:
                    pass

            return target_date.day in allowed_days

        return target_date.day == start_date.day

    if frequency == "YEARLY":
        year_delta = (
            target_date.year
            - start_date.year
        )

        if year_delta % interval != 0:
            return False

        try:
            month = int(
                rule.get(
                    "BYMONTH",
                    str(start_date.month),
                )
            )
        except ValueError:
            month = start_date.month

        try:
            month_day = int(
                rule.get(
                    "BYMONTHDAY",
                    str(start_date.day),
                )
            )
        except ValueError:
            month_day = start_date.day

        return (
            target_date.month == month
            and target_date.day == month_day
        )

    return False


def non_recurring_event_matches_date(
    event,
    target_date,
):
    start_dt = datetime.fromisoformat(
        event["start_at"]
    )

    end_text = event["end_at"]

    if end_text:
        end_dt = datetime.fromisoformat(
            end_text
        )
    else:
        end_dt = start_dt

    return (
        start_dt.date()
        <= target_date
        <= end_dt.date()
    )


def event_matches_date(
    event,
    target_date,
):
    if event["recurrence_rule"]:
        return recurrence_matches_date(
            event,
            target_date,
        )

    return non_recurring_event_matches_date(
        event,
        target_date,
    )


def occurrence_start_for_date(
    event,
    target_date,
):
    original = datetime.fromisoformat(
        event["start_at"]
    )

    if not event["recurrence_rule"]:
        return original

    return datetime.combine(
        target_date,
        original.timetz(),
    )


def occurrence_end_for_date(
    event,
    target_date,
    occurrence_start,
):
    end_text = event["end_at"]

    if not end_text:
        return None

    original_start = datetime.fromisoformat(
        event["start_at"]
    )
    original_end = datetime.fromisoformat(
        end_text
    )

    if not event["recurrence_rule"]:
        return original_end

    duration = (
        original_end
        - original_start
    )

    return occurrence_start + duration


def build_event_occurrence(
    event,
    target_date,
    state_occurrence_date=None,
):
    if state_occurrence_date is not None:
        state_date = state_occurrence_date
    elif event["recurrence_rule"]:
        state_date = target_date
    else:
        state_date = datetime.fromisoformat(
            event["start_at"]
        ).date()

    state = get_event_occurrence_state(
        event_id=event["id"],
        occurrence_date=(
            state_date.isoformat()
        ),
    )

    occurrence_status = None

    if state is not None:
        occurrence_status = state[
            "occurrence_status"
        ]

    if occurrence_status in {
        "cancelled",
        "completed",
    }:
        return None

    occurrence_start = (
        occurrence_start_for_date(
            event,
            state_date,
        )
    )

    occurrence_end = (
        occurrence_end_for_date(
            event,
            state_date,
            occurrence_start,
        )
    )

    title = event["title"]
    location = event["location"]
    all_day = bool(event["all_day"])
    is_override = False
    time_precision = event[
        "time_precision"
    ]
    time_label = event["time_label"]

    if state is not None:
        override_start = state[
            "override_start_at"
        ]

        if override_start:
            is_override = True
            occurrence_start = (
                datetime.fromisoformat(
                    override_start
                )
            )

            if (
                occurrence_start.date()
                != target_date
            ):
                return None

        override_end = state[
            "override_end_at"
        ]

        if override_end:
            occurrence_end = (
                datetime.fromisoformat(
                    override_end
                )
            )

        if state["override_title"]:
            title = state[
                "override_title"
            ]

        if state["override_location"]:
            location = state[
                "override_location"
            ]

        if state["override_all_day"] is not None:
            all_day = bool(
                state["override_all_day"]
            )

        if state["override_time_precision"]:
            time_precision = state[
                "override_time_precision"
            ]

        if state["override_time_label"]:
            time_label = state[
                "override_time_label"
            ]

    if occurrence_start.date() != target_date:
        if event["recurrence_rule"]:
            return None

    return {
        "id": int(event["id"]),
        "title": title,
        "description": event["description"],
        "location": location,
        "start_at": occurrence_start.isoformat(
            timespec="seconds"
        ),
        "end_at": (
            occurrence_end.isoformat(
                timespec="seconds"
            )
            if occurrence_end
            else None
        ),
        "all_day": all_day,
        "time_precision": time_precision,
        "time_label": time_label,
        "timezone": event["timezone"],
        "recurrence_rule": event[
            "recurrence_rule"
        ],
        "status": event["status"],
        "occurrence_date": (
            state_date.isoformat()
        ),
        "active_date": (
            target_date.isoformat()
        ),
        "is_override": is_override,
        "original_occurrence_date": (
            state_date.isoformat()
            if is_override
            else None
        ),
    }


def get_event_occurrences_for_date(
    target_date=None,
):
    if target_date is None:
        target_date = get_local_now().date()

    if isinstance(target_date, str):
        target_date = date.fromisoformat(
            target_date
        )

    events = get_active_events(
        limit=500
    )

    occurrences = []

    for event in events:
        try:
            if not event_matches_date(
                event,
                target_date,
            ):
                continue

            occurrence = build_event_occurrence(
                event,
                target_date,
            )

        except (TypeError, ValueError):
            continue

        if occurrence is not None:
            occurrences.append(
                occurrence
            )

    override_rows = (
        get_event_occurrence_overrides_for_date(
            target_date.isoformat()
        )
    )

    existing_keys = {
        (
            item["id"],
            item["occurrence_date"],
        )
        for item in occurrences
    }

    for event in override_rows:
        try:
            state_date = date.fromisoformat(
                event["state_occurrence_date"]
            )

            occurrence = build_event_occurrence(
                event,
                target_date,
                state_occurrence_date=(
                    state_date
                ),
            )

        except (TypeError, ValueError):
            continue

        if occurrence is None:
            continue

        key = (
            occurrence["id"],
            occurrence["occurrence_date"],
        )

        if key in existing_keys:
            continue

        existing_keys.add(key)
        occurrences.append(occurrence)

    occurrences.sort(
        key=lambda item: (
            item["start_at"],
            item["id"],
        )
    )

    return occurrences


def get_relevant_events(event_ids):
    rows = get_events_by_ids(
        event_ids
    )

    events = [
        event_to_dict(row)
        for row in rows
    ]

    if not events:
        return []

    states = (
        get_event_occurrence_states_for_event_ids(
            [
                event["id"]
                for event in events
            ],
            limit=300,
        )
    )

    state_map = {}

    for state in states:
        event_id = int(
            state["event_id"]
        )

        state_map.setdefault(
            event_id,
            [],
        ).append(
            {
                key: state[key]
                for key in state.keys()
                if key not in {
                    "surfaced_at",
                    "acknowledged_at",
                    "updated_at",
                }
            }
        )

    for event in events:
        event["occurrence_exceptions"] = (
            state_map.get(
                event["id"],
                [],
            )
        )

    return events


def mark_relevant_current_events_acknowledged(
    relevant_event_ids,
    current_occurrences,
):
    if not relevant_event_ids:
        return

    relevant_ids = set(
        relevant_event_ids
    )

    for occurrence in current_occurrences:
        if occurrence["id"] not in relevant_ids:
            continue

        mark_event_occurrence_acknowledged(
            event_id=occurrence["id"],
            occurrence_date=(
                occurrence["occurrence_date"]
            ),
        )


def get_proactive_event_opportunity(
    current_occurrences,
    daily_limit=1,
):
    if not current_occurrences:
        return None

    today = get_local_now().date().isoformat()

    interaction_count = (
        count_event_interactions_for_date(
            today
        )
    )

    if interaction_count >= daily_limit:
        return None

    candidates = []

    for occurrence in current_occurrences:
        if occurrence["status"] != "scheduled":
            continue

        state = get_event_occurrence_state(
            event_id=occurrence["id"],
            occurrence_date=(
                occurrence["occurrence_date"]
            ),
        )

        if state is not None:
            if (
                state["surfaced_at"] is not None
                or state["acknowledged_at"]
                is not None
            ):
                continue

        candidates.append(
            occurrence
        )

    if not candidates:
        return None

    all_day = [
        item
        for item in candidates
        if item["all_day"]
        or item["time_precision"] == "date"
    ]

    if all_day:
        return all_day[0]

    now = get_local_now()

    upcoming = []
    past = []

    for item in candidates:
        try:
            start = datetime.fromisoformat(
                item["start_at"]
            )
        except ValueError:
            past.append(item)
            continue

        if start >= now:
            upcoming.append(item)
        else:
            past.append(item)

    if upcoming:
        upcoming.sort(
            key=lambda item: item["start_at"]
        )
        return upcoming[0]

    return past[0] if past else None


def mark_proactive_event_surfaced(event):
    if not event:
        return

    mark_event_occurrence_surfaced(
        event_id=event["id"],
        occurrence_date=(
            event["occurrence_date"]
        ),
    )
