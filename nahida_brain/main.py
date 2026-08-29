from datetime import datetime

from voice_input import VoiceInput

from src.database import (
    init_db,
    create_session,
    end_session,
    save_message,
    save_memory,
    update_memory,
    get_memories,
    get_recent_messages,
    get_recent_daily_summaries,
    get_latest_message,
)

from src.memory_filter import (
    analyze_memory,
)

from src.daily_summary import (
    generate_daily_summary,
)

from src.episodic_memory import (
    retrieve_relevant_episodic_facts,
)

from src.chat import (
    generate_nahida_response,
)


def get_current_date():
    return (
        datetime.now()
        .date()
        .isoformat()
    )


def handle_day_rollover(
    active_date,
    day_dirty,
):
    current_date = (
        get_current_date()
    )

    if current_date == active_date:
        return (
            active_date,
            day_dirty,
        )

    print()
    print(
        f"[Daily] Date changed: "
        f"{active_date} -> "
        f"{current_date}"
    )

    if day_dirty:
        auto_update_daily_summary(
            active_date
        )

    print(
        f"[Daily] Starting "
        f"{current_date}."
    )
    print()

    return (
        current_date,
        False,
    )


def build_interaction_gap(
    last_message,
    session_id,
):
    if last_message is None:
        return None

    try:
        last_time = datetime.fromisoformat(
            last_message["created_at"]
        )
    except (TypeError, ValueError):
        return None

    now = datetime.now()

    delta = now - last_time

    seconds = max(
        0,
        int(delta.total_seconds()),
    )

    previous_session_id = (
        last_message["session_id"]
    )

    return {
        "seconds": seconds,
        "same_session": (
            previous_session_id
            == session_id
        ),
        "last_interaction_at": (
            last_message["created_at"]
        ),
    }


def process_memory(
    text,
    message_id,
    previous_messages,
):
    existing_memories = get_memories(100)

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
        if decision.target_memory_id is None:
            return relevant_memory_ids

        valid_ids = {
            memory["id"]
            for memory in existing_memories
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


def chat_with_nahida(
    text,
    session_id,
):
    last_message = (
        get_latest_message()
    )

    interaction_gap = (
        build_interaction_gap(
            last_message=last_message,
            session_id=session_id,
        )
    )

    previous_messages = (
        get_recent_messages(
            limit=8,
            session_id=session_id,
        )
    )

    message_id = save_message(
        role="user",
        content=text,
        session_id=session_id,
    )

    relevant_memory_ids = (
        process_memory(
            text=text,
            message_id=message_id,
            previous_messages=previous_messages,
        )
    )

    print(
        "[Debug] Relevant memory IDs: "
        f"{relevant_memory_ids}"
    )

    try:
        episodic_facts = (
            retrieve_relevant_episodic_facts(
                text
            )
        )

    except Exception as exc:
        print(
            f"[Episodic] Failed: {exc}"
        )
        episodic_facts = []

    if episodic_facts:
        print(
            "[Episodic] Relevant:"
        )

        for item in episodic_facts:
            print(
                f"  {item['id']} "
                f"[{item['date']}] "
                f"{item['fact']}"
            )

    print("[Nahida] Thinking...")

    try:
        response = (
            generate_nahida_response(
                session_id=session_id,
                relevant_memory_ids=(
                    relevant_memory_ids
                ),
                episodic_facts=(
                    episodic_facts
                ),
                interaction_gap=(
                    interaction_gap
                ),
            )
        )

    except Exception as exc:
        print(
            f"[Nahida] Failed: {exc}"
        )
        return

    save_message(
        role="assistant",
        content=response,
        session_id=session_id,
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

        print(
            memory["content"]
        )
        print()


def show_recent_messages():
    messages = get_recent_messages(
        30
    )

    print()
    print("=== Recent Messages ===")

    for message in messages:
        print(
            f"{message['created_at']} "
            f"session="
            f"{message['session_id']} "
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
            generate_daily_summary(
                today
            )
        )

    except Exception as exc:
        print(
            f"[Daily] Failed: {exc}"
        )
        return False

    if summary is None:
        print(
            "[Daily] No messages "
            "to summarize."
        )
        return False

    print()
    print(
        f"=== Daily Summary: "
        f"{today} ==="
    )

    print(summary)
    print()

    return True


def auto_update_daily_summary(
    date_string,
):
    print()
    print(
        f"[Daily] Updating "
        f"{date_string}..."
    )

    try:
        summary = (
            generate_daily_summary(
                date_string
            )
        )

    except Exception as exc:
        print(
            f"[Daily] Auto update failed: "
            f"{exc}"
        )
        return False

    if summary is None:
        print(
            "[Daily] Nothing to update."
        )
        return False

    print(
        "[Daily] Summary updated."
    )

    return True


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

        print(
            item["summary"]
        )

    print()


def main():
    init_db()

    session_id = create_session()

    voice = VoiceInput()

    active_date = (
        get_current_date()
    )

    day_dirty = False

    print(
        "Nahida Brain V6.7"
    )
    print(
        f"Session ID: {session_id}"
    )
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

    print(
        "Press Enter for voice input, "
        "or type normally."
    )
    print()

    try:
        while True:
            text = input(
                "You > "
            ).strip()

            if not text:
                text = voice.listen()

                if not text:
                    continue

                print()
                print(
                    f"You > {text}"
                )

            active_date, day_dirty = (
                handle_day_rollover(
                    active_date,
                    day_dirty,
                )
            )

            if text == "/exit":
                break

            if text == "/memory":
                show_memories()
                continue

            if text == "/history":
                show_recent_messages()
                continue

            if text == "/summary":
                success = (
                    summarize_today()
                )

                if success:
                    day_dirty = False

                continue

            if text == "/summaries":
                show_daily_summaries()
                continue

            day_dirty = True

            chat_with_nahida(
                text=text,
                session_id=session_id,
            )

    finally:
        if day_dirty:
            auto_update_daily_summary(
                active_date
            )

        end_session(
            session_id
        )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print()
        print(
            "Nahida Brain stopped."
        )