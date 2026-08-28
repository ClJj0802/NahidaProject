from src.database import (
    init_db,
    save_message,
    save_memory,
    get_memories,
    get_recent_messages,
)
from src.memory_filter import analyze_memory


def process_user_message(text):
    message_id = save_message(
        role="user",
        content=text,
    )

    recent_messages = get_recent_messages(10)

    print("[Memory] Analyzing...")

    try:
        memory = analyze_memory(
            latest_message=text,
            recent_messages=recent_messages,
        )

    except Exception as exc:
        print(f"[Memory] Analysis failed: {exc}")
        return

    if memory is None:
        print("[Memory] Not important")
        return

    memory_id = save_memory(
        category=memory.category,
        content=memory.content,
        importance=memory.importance,
        source_message_id=message_id,
    )

    print(
        f"[Memory] Saved #{memory_id} "
        f"[{memory.category}] "
        f"importance={memory.importance}"
    )

    print(
        f"[Memory] {memory.content}"
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
            f"importance={memory['importance']}"
        )

        print(memory["content"])
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

    print("Nahida Memory V2")
    print()
    print("Commands:")
    print("/memory   Show long-term memories")
    print("/history  Show recent messages")
    print("/exit     Exit")
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