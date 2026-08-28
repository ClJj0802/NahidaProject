from src.database import (
    init_db,
    save_message,
    save_memory,
    update_memory,
    get_memories,
    get_recent_messages,
)

from src.memory_filter import analyze_memory


def process_user_message(text):
    previous_messages = get_recent_messages(10)
    existing_memories = get_memories(100)

    message_id = save_message(
        role="user",
        content=text,
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
        return

    if decision.action == "ignore":
        print("[Memory] IGNORE")

        if decision.reason:
            print(
                f"[Memory] Reason: "
                f"{decision.reason}"
            )

        return

    if decision.action == "add":
        if (
            not decision.category
            or not decision.content
        ):
            print(
                "[Memory] Invalid ADD result"
            )
            return

        memory_id = save_memory(
            category=decision.category,
            content=decision.content,
            importance=decision.importance,
            source_message_id=message_id,
        )

        print(
            f"[Memory] ADD #{memory_id}"
        )

        print(
            f"[Memory] "
            f"[{decision.category}] "
            f"importance="
            f"{decision.importance}"
        )

        print(
            f"[Memory] {decision.content}"
        )

        return

    if decision.action == "update":
        if decision.target_memory_id is None:
            print(
                "[Memory] UPDATE missing "
                "target_memory_id"
            )
            return

        valid_ids = {
            memory["id"]
            for memory in existing_memories
        }

        if (
            decision.target_memory_id
            not in valid_ids
        ):
            print(
                "[Memory] Invalid UPDATE "
                "target"
            )
            return

        if (
            not decision.category
            or not decision.content
        ):
            print(
                "[Memory] Invalid UPDATE "
                "content"
            )
            return

        success = update_memory(
            memory_id=decision.target_memory_id,
            category=decision.category,
            content=decision.content,
            importance=decision.importance,
            source_message_id=message_id,
        )

        if not success:
            print(
                "[Memory] UPDATE failed"
            )
            return

        print(
            f"[Memory] UPDATE "
            f"#{decision.target_memory_id}"
        )

        print(
            f"[Memory] "
            f"[{decision.category}] "
            f"importance="
            f"{decision.importance}"
        )

        print(
            f"[Memory] {decision.content}"
        )

        if decision.reason:
            print(
                f"[Memory] Reason: "
                f"{decision.reason}"
            )


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

        print(
            f"Created: "
            f"{memory['created_at']}"
        )

        if memory["updated_at"]:
            print(
                f"Updated: "
                f"{memory['updated_at']}"
            )

        print()


def show_recent_messages():
    messages = get_recent_messages(20)

    print()
    print("=== Recent Messages ===")

    for message in messages:
        print(
            f"{message['created_at']} "
            f"{message['role']}: "
            f"{message['content']}"
        )


def main():
    init_db()

    print("Nahida Memory V3")
    print()
    print("Commands:")
    print(
        "/memory   Show long-term memories"
    )
    print(
        "/history  Show recent messages"
    )
    print(
        "/exit     Exit"
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

        if not text:
            continue

        process_user_message(text)


if __name__ == "__main__":
    main()