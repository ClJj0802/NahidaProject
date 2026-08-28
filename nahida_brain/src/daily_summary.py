from datetime import datetime

from src.database import (
    get_messages_for_date,
    save_daily_summary,
)

from src.llm_client import chat_completion


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
"""


def build_messages_text(messages):
    lines = []

    for message in messages:
        lines.append(
            f"{message['created_at']} "
            f"{message['role'].upper()}: "
            f"{message['content']}"
        )

    return "\n".join(lines)


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

    messages_text = build_messages_text(
        messages
    )

    prompt = f"""
Date:
{date_string}

Messages from that day:

{messages_text}

Create a concise daily episodic summary.
"""

    summary = chat_completion(
        messages=[
            {
                "role": "system",
                "content": DAILY_SUMMARY_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        max_tokens=400,
    )

    summary = summary.strip()

    if not summary:
        return None

    save_daily_summary(
        summary_date=date_string,
        summary=summary,
    )

    return summary