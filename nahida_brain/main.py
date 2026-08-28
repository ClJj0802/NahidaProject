from datetime import datetime

from src.database import (
    init_db,
    save_message,
    save_memory,
    update_memory,
    get_memories,
    get_recent_messages,
    get_recent_daily_summaries,
)

from src.memory_filter import (
    analyze_memory,
)

from src.daily_summary import (
    generate_daily_summary,
)

from src.chat import (
    generate_nahida_response,
)


def process_memory(
    text,
    message_id,
    previous_messages,
):
    existing_memories = (
        get_memories(100)
    )

    print("[Memory] Analyzing...")

    try:
        decision = analyze_memory(
            latest_message=text,
            recent_messages=previous_messages,
            existing_memories=existing_memories,
        )

    except Exception as exc:
        print(
            f"[Memory] Analysis failed: {exc}"
        )

        return []

    relevant_memory_ids = (
        decision.relevant_memory_ids
    )

    if relevant_memory_ids:
        print(
            "[Memory] Relevant: "
            f"{relevant_memory_ids}"
        )

    if decision.action == "ignore":
        print("[Memory] IGNORE")

        return relevant_memory_ids

    if decision.action == "add":
        if (
            not decision.category
            or not decision.content
        ):
            return relevant_memory_ids

        memory_id = save_memory(
            category=decision.category,
            content=decision.content,
            importance=decision.importance,
            source_message_id=message_id,
        )

        print(
            f"[Memory] ADD #{memory_id}: "
            f"{decision.content}"
        )

        return relevant_memory_ids

    if decision.action == "update":
        if (
            decision.target_memory_id
            is None
        ):
            return relevant_memory_ids

        valid_ids = {
            memory["id"]
            for memory
            in existing_memories
        }

        if (
            decision.target_memory_id
            not in valid_ids
        ):
            return relevant_memory_ids

        if (
            not decision.category
            or not decision.content
        ):
            return relevant_memory_ids

        success = update_memory(
            memory_id=(
                decision.target_memory_id
            ),
            category=decision.category,
            content=decision.content,
            importance=decision.importance,
            source_message_id=message_id,
        )

        if success:
            print(
                f"[Memory] UPDATE "
                f"#{decision.target_memory_id}: "
                f"{decision.content}"
            )

        return relevant_memory_ids

    return relevant_memory_ids


def chat_with_nahida(text):
    previous_messages = get_recent_messages(12)

    message_id = save_message(
        role="user",
        content=text,
    )

    relevant_memory_ids = process_memory(
        text=text,
        message_id=message_id,
        previous_messages=previous_messages,
    )

    print(
        f"[Debug] Relevant memory IDs: "
        f"{relevant_memory_ids}"
    )

    print("[Nahida] Thinking...")

    try:
        response = generate_nahida_response(
            relevant_memory_ids=relevant_memory_ids,
        )

    except Exception as exc:
        print(
            f"[Nahida] Failed: {exc}"
        )
        return

    save_message(
        role="assistant",
        content=response,
    )

    print()
    print(
        f"Nahida > {response}"
    )
    print()

def show_memories():
    memories = get_memories()

    print()
    print("=== Long-term Memories ===")

    if not memories:
        print("No memories.")
        return

    for memory in memories:
        print(
            f"#{memory['id']} "
            f"[{memory['category']}] "
            f"importance="
            f"{memory['importance']}"
        )

        print(memory["content"])
        print()


def show_recent_messages():
    messages = get_recent_messages(30)

    print()
    print("=== Recent Messages ===")

    for message in messages:
        print(
            f"{message['created_at']} "
            f"{message['role']}: "
            f"{message['content']}"
        )

    print()


def summarize_today():
    today = (
        datetime.now()
        .date()
        .isoformat()
    )

    print()
    print(
        f"[Daily] Summarizing {today}..."
    )

    try:
        summary = (
            generate_daily_summary(today)
        )

    except Exception as exc:
        print(
            f"[Daily] Failed: {exc}"
        )
        return

    if summary is None:
        print(
            "[Daily] No messages "
            "to summarize."
        )
        return

    print()
    print(
        f"=== Daily Summary: "
        f"{today} ==="
    )

    print(summary)
    print()


def show_daily_summaries():
    summaries = (
        get_recent_daily_summaries(7)
    )

    print()
    print(
        "=== Recent Daily Summaries ==="
    )

    if not summaries:
        print(
            "No daily summaries."
        )
        return

    for item in summaries:
        print()
        print(
            f"--- "
            f"{item['summary_date']} "
            f"---"
        )

        print(item["summary"])

    print()


def main():
    init_db()

    print("Nahida Brain V5")
    print()

    print("Commands:")
    print(
        "/memory     Show memories"
    )
    print(
        "/history    Show conversation"
    )
    print(
        "/summary    Summarize today"
    )
    print(
        "/summaries  Show summaries"
    )
    print(
        "/exit       Exit"
    )
    print()

    while True:
        text = input("You > ").strip()

        if text == "/exit":
            break

        if text == "/memory":
            show_memories()
            continue

        if text == "/history":
            show_recent_messages()
            continue

        if text == "/summary":
            summarize_today()
            continue

        if text == "/summaries":
            show_daily_summaries()
            continue

        if not text:
            continue

        chat_with_nahida(text)


if __name__ == "__main__":
    main()