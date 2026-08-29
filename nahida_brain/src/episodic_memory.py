import json
import re
from datetime import datetime

from src.database import (
    get_recent_daily_summaries,
)

from src.llm_client import (
    chat_completion,
)


RECALL_HINTS = (
    "今天",
    "昨天",
    "前天",
    "明天",
    "后天",
    "早上",
    "上午",
    "中午",
    "下午",
    "晚上",
    "之前",
    "以前",
    "前几天",
    "上次",
    "刚才",
    "刚刚",
    "记得",
    "还记得",
    "来着",
    "说过",
    "提过",
    "做过",
    "干嘛",
    "发生",
    "聊过",
    "计划",
    "打算",
    "today",
    "yesterday",
    "tomorrow",
    "earlier",
    "before",
    "last time",
    "remember",
    "this morning",
)


EPISODIC_RETRIEVAL_PROMPT = """
You retrieve episodic memories for Nahida.

You will receive:

1. The current date
2. The user's latest message
3. A catalog of facts extracted from dated daily summaries

Each fact has a unique ID such as:

E001
E002
E003

Your job is to select the smallest set of fact IDs that genuinely help
answer the user's current message.


IMPORTANT

Return only facts that directly help answer the current question.

Do not select facts merely because they are from the same day.

Do not select facts merely because they concern the user.

Do not select adjacent or loosely related information.

When uncertain, prefer selecting fewer facts.


TEMPORAL REASONING

Pay attention to:

- the date of the daily summary
- the current date
- expressions such as today, yesterday, tomorrow, the next day,
  earlier, last time, and this morning

A future plan may appear inside an earlier daily summary.

Example:

Current date:
2026-08-29

Fact:

E003 | 2026-08-29 |
The user planned to attend a comic convention the following day.

User:

"明天我要去哪里来着？"

Correct:

{
  "relevant_fact_ids": ["E003"]
}


Another example:

Facts:

E001 | 2026-08-29 |
The user played Apex Legends with friends in the morning.

E002 | 2026-08-29 |
The user likes matcha.

User:

"今天早上我干嘛了？"

Correct:

{
  "relevant_fact_ids": ["E001"]
}


Another example:

E001 | 2026-08-29 |
The user is a programmer.

E002 | 2026-08-29 |
The user planned to visit a comic convention the following day.

User:

"我明天是不是要去漫展？"

Correct:

{
  "relevant_fact_ids": ["E002"]
}


If nothing in the catalog supports the user's question:

{
  "relevant_fact_ids": []
}


MEMORY ACCURACY

Do not invent facts.

Do not infer unsupported events.

Only return fact IDs that actually exist in the provided catalog.

Never rewrite or create new facts.

Return ONLY valid JSON.

Do not use Markdown.

Do not use code fences.

Output format:

{
  "relevant_fact_ids": ["E001", "E003"]
}
"""


def should_check_episodic_memory(text):
    lowered = text.lower().strip()

    current_time_questions = (
        "今天几号",
        "今天是几号",
        "现在几号",
        "今天星期几",
        "今天礼拜几",
        "现在几点",
        "几点了",
        "现在什么时间",
        "现在是几点",
        "what time is it",
        "what date is it",
        "what day is it",
    )

    if any(
        pattern in lowered
        for pattern in current_time_questions
    ):
        return False

    return any(
        hint in lowered
        for hint in RECALL_HINTS
    )


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


def split_summary_facts(summary):
    facts = []

    for line in summary.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("-"):
            line = line[1:].strip()

        if line:
            facts.append(line)

    return facts


def build_fact_catalog(summaries):
    catalog = []
    counter = 1

    for summary in summaries:
        summary_date = (
            summary["summary_date"]
        )

        facts = split_summary_facts(
            summary["summary"]
        )

        for fact in facts:
            fact_id = f"E{counter:03d}"

            catalog.append(
                {
                    "id": fact_id,
                    "date": summary_date,
                    "fact": fact,
                }
            )

            counter += 1

    return catalog


def format_fact_catalog(catalog):
    lines = []

    for item in catalog:
        lines.append(
            f"{item['id']} | "
            f"{item['date']} | "
            f"{item['fact']}"
        )

    if not lines:
        return "(none)"

    return "\n".join(lines)


def retrieve_relevant_episodic_facts(
    user_message,
    limit=14,
):
    if not should_check_episodic_memory(
        user_message
    ):
        return []

    summaries = (
        get_recent_daily_summaries(
            limit
        )
    )

    if not summaries:
        return []

    catalog = build_fact_catalog(
        summaries
    )

    if not catalog:
        return []

    catalog_text = format_fact_catalog(
        catalog
    )

    current_date = (
        datetime.now()
        .date()
        .isoformat()
    )

    prompt = f"""
Current date:

{current_date}


Latest user message:

{user_message}


Available episodic facts:

{catalog_text}


Select only the smallest set of fact IDs that directly help answer
the user's latest message.

Return JSON only.
"""

    response = chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    EPISODIC_RETRIEVAL_PROMPT
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
        max_tokens=120,
    )

    result = extract_json(
        response
    )

    raw_ids = result.get(
        "relevant_fact_ids",
        [],
    )

    if not isinstance(
        raw_ids,
        list,
    ):
        return []

    valid_facts = {
        item["id"]: item
        for item in catalog
    }

    selected = []

    seen_ids = set()

    for fact_id in raw_ids:
        fact_id = str(
            fact_id
        ).strip()

        if fact_id in seen_ids:
            continue

        if fact_id not in valid_facts:
            continue

        seen_ids.add(
            fact_id
        )

        selected.append(
            valid_facts[fact_id]
        )

    return selected