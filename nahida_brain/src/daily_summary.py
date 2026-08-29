from datetime import datetime

from src.database import (
    get_messages_for_date,
    save_daily_summary,
)

from src.llm_client import chat_completion


MAX_MESSAGE_CHARS = 3500
MAX_MERGE_CHARS = 4500

CHUNK_SUMMARY_MAX_TOKENS = 250
FINAL_SUMMARY_MAX_TOKENS = 400


DAILY_SUMMARY_SYSTEM_PROMPT = """
You create daily episodic summaries for an AI companion named Nahida.

Summarize what meaningfully happened to the user during the specified day.

This is different from long-term memory.

Daily summaries may contain:
- Things the user did
- Things the user worked on
- Important conversations
- Temporary feelings or states
- Progress made on projects
- Decisions made that day
- Activities or events
- Plans mentioned during the day

Do not include:
- Greetings
- Trivial acknowledgements
- Repeated statements
- Empty conversational filler

Important rules:

Only use information present in the provided messages.

Do not invent details.

Do not assume events happened if the user only asked a question about them.

Keep the summary concise.

Use short factual bullet points.

Write in third person using "The user".

Return only the summary text.

If the user explicitly establishes a nickname, preferred name,
relationship term, or form of address, it may be included.

When the user corrects the spelling or wording of a nickname,
use only the latest clearly confirmed version.

Do not describe the correction process unless it is itself important.

When the user's plan changes during the day, the latest explicit state
has priority.

Do not summarize an outdated plan as though it is still current.

If an earlier plan and a later decision conflict, combine them into one
fact that clearly shows the change.

ATOMIC FACTS

Each bullet point should contain one main fact or one tightly related
group of facts.

Do not combine unrelated topics into the same bullet.

PRESERVE SPECIFICITY

Preserve important specific terms stated by the user.

If the user says "弓道", prefer "kyudo" rather than the broader
"archery".

If the user names an event, project, technology, or product,
preserve its specific name.

Do not generalize specific information unnecessarily.

PRESERVE UNCERTAINTY

Preserve how certain the user is about a statement.

Do not convert possibilities or considerations into definite plans.

NICKNAMES AND CORRECTIONS

When the user establishes or corrects a nickname, keep only the latest
clearly confirmed version.

Do not summarize the correction process unless it is important.

Prefer 5 to 10 precise atomic bullet points over a smaller number of
broad bullet points containing many unrelated facts.
"""


DAILY_MERGE_SYSTEM_PROMPT = """
You consolidate partial daily episodic summaries for an AI companion
named Nahida.

The partial summaries are ordered chronologically.

Rules:
- Only use facts present in the supplied summaries.
- Do not invent information.
- Remove duplicates.
- Preserve important specific names and technical terms.
- Preserve uncertainty.
- If later information conflicts with earlier information, prefer the
  latest explicit state.
- Keep meaningful changes of plan when relevant.
- Do not include greetings or conversational filler.
- Write in third person using "The user".
- Use short atomic bullet points.
- Prefer 5 to 10 precise bullet points.
- Return only the final summary text.
"""


def build_message_line(message):
    return (
        f"{message['created_at']} "
        f"{message['role'].upper()}: "
        f"{message['content']}"
    )


def build_messages_text(messages):
    return "\n".join(
        build_message_line(message)
        for message in messages
    )


def split_long_text(
    text,
    max_chars,
):
    if len(text) <= max_chars:
        return [text]

    parts = []

    start = 0

    while start < len(text):
        end = min(
            start + max_chars,
            len(text),
        )

        parts.append(
            text[start:end]
        )

        start = end

    return parts


def build_message_chunks(
    messages,
    max_chars=MAX_MESSAGE_CHARS,
):
    chunks = []

    current_lines = []
    current_size = 0

    for message in messages:
        line = build_message_line(
            message
        )

        pieces = split_long_text(
            line,
            max_chars,
        )

        for piece in pieces:
            extra_size = (
                len(piece)
                + (
                    1
                    if current_lines
                    else 0
                )
            )

            if (
                current_lines
                and current_size
                + extra_size
                > max_chars
            ):
                chunks.append(
                    "\n".join(
                        current_lines
                    )
                )

                current_lines = []
                current_size = 0

            current_lines.append(
                piece
            )

            current_size += (
                len(piece)
                + (
                    1
                    if len(current_lines) > 1
                    else 0
                )
            )

    if current_lines:
        chunks.append(
            "\n".join(
                current_lines
            )
        )

    return chunks


def summarize_message_chunk(
    date_string,
    chunk_text,
    chunk_index,
    total_chunks,
):
    prompt = f"""
Date:
{date_string}

This is conversation segment {chunk_index} of {total_chunks}.
Segments are ordered chronologically.

Messages:

{chunk_text}

Create a concise episodic summary of only the meaningful information
contained in this segment.

Do not assume this segment contains the final state of the day.
Later segments may contain updates or corrections.
"""

    summary = chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    DAILY_SUMMARY_SYSTEM_PROMPT
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        max_tokens=(
            CHUNK_SUMMARY_MAX_TOKENS
        ),
    )

    return summary.strip()


def build_summary_groups(
    summaries,
    max_chars=MAX_MERGE_CHARS,
):
    groups = []

    current_group = []
    current_size = 0

    for summary in summaries:
        extra_size = (
            len(summary)
            + 50
        )

        if (
            current_group
            and current_size
            + extra_size
            > max_chars
        ):
            groups.append(
                current_group
            )

            current_group = []
            current_size = 0

        current_group.append(
            summary
        )

        current_size += extra_size

    if current_group:
        groups.append(
            current_group
        )

    if (
        len(groups) == len(summaries)
        and len(summaries) > 1
    ):
        groups = [
            summaries[index:index + 2]
            for index in range(
                0,
                len(summaries),
                2,
            )
        ]

    return groups


def merge_summary_group(
    date_string,
    summaries,
    final=False,
):
    sections = []

    for index, summary in enumerate(
        summaries,
        start=1,
    ):
        sections.append(
            f"""
--- Chronological segment {index} ---

{summary}
"""
        )

    combined = "\n".join(
        sections
    )

    prompt = f"""
Date:
{date_string}

Below are chronological partial summaries from the same day.

{combined}

Merge them into one coherent daily episodic summary.

Later segments represent later events and therefore take priority when
there are corrections, updated plans, or conflicting states.
"""

    max_tokens = (
        FINAL_SUMMARY_MAX_TOKENS
        if final
        else CHUNK_SUMMARY_MAX_TOKENS
    )

    summary = chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    DAILY_MERGE_SYSTEM_PROMPT
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        max_tokens=max_tokens,
    )

    return summary.strip()


def merge_summaries(
    date_string,
    summaries,
):
    summaries = [
        summary
        for summary in summaries
        if summary
    ]

    if not summaries:
        return None

    if len(summaries) == 1:
        return summaries[0]

    round_number = 1

    while len(summaries) > 1:
        groups = build_summary_groups(
            summaries
        )

        print(
            f"[Daily] Merge round "
            f"{round_number}: "
            f"{len(summaries)} summaries "
            f"-> {len(groups)} groups"
        )

        merged = []

        for index, group in enumerate(
            groups,
            start=1,
        ):
            final = (
                len(groups) == 1
            )

            print(
                f"[Daily] Merging group "
                f"{index}/{len(groups)}..."
            )

            result = merge_summary_group(
                date_string=date_string,
                summaries=group,
                final=final,
            )

            if result:
                merged.append(
                    result
                )

        if not merged:
            return None

        summaries = merged

        round_number += 1

    return summaries[0]


def generate_daily_summary(
    date_string=None,
):
    if date_string is None:
        date_string = (
            datetime.now()
            .date()
            .isoformat()
        )

    messages = get_messages_for_date(
        date_string
    )

    if not messages:
        return None

    chunks = build_message_chunks(
        messages
    )

    total_chars = sum(
        len(chunk)
        for chunk in chunks
    )

    print(
        f"[Daily] Messages: "
        f"{len(messages)}"
    )

    print(
        f"[Daily] Conversation chars: "
        f"{total_chars}"
    )

    print(
        f"[Daily] Chunks: "
        f"{len(chunks)}"
    )

    chunk_summaries = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        print(
            f"[Daily] Summarizing chunk "
            f"{index}/{len(chunks)} "
            f"({len(chunk)} chars)..."
        )

        try:
            summary = (
                summarize_message_chunk(
                    date_string=(
                        date_string
                    ),
                    chunk_text=chunk,
                    chunk_index=index,
                    total_chunks=len(
                        chunks
                    ),
                )
            )

        except Exception as exc:
            print(
                f"[Daily] Chunk "
                f"{index} failed: "
                f"{exc}"
            )
            continue

        if summary:
            chunk_summaries.append(
                summary
            )

    if not chunk_summaries:
        return None

    if len(chunk_summaries) == 1:
        final_summary = (
            chunk_summaries[0]
        )

    else:
        final_summary = (
            merge_summaries(
                date_string=(
                    date_string
                ),
                summaries=(
                    chunk_summaries
                ),
            )
        )

    if not final_summary:
        return None

    final_summary = (
        final_summary.strip()
    )

    save_daily_summary(
        summary_date=date_string,
        summary=final_summary,
    )

    return final_summary