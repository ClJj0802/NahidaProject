import os
from datetime import datetime

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
    get_event_candidates,
)

from src.memory_filter import analyze_memory
from src.daily_summary import generate_daily_summary
from src.episodic_memory import retrieve_relevant_episodic_facts
from src.temporal_memory import (
    get_event_occurrences_for_date,
    get_proactive_event_opportunity,
    get_relevant_events,
    mark_proactive_event_surfaced,
    mark_relevant_current_events_acknowledged,
    process_temporal_memory,
)
from src.chat import generate_nahida_response
from src.tts_client import TTSClient


TTS_API_BASE = "http://127.0.0.1:9880"

TTS_GPT_WEIGHTS = (
    r"D:\Users\User\Desktop\NahidaProject\GPT-SoVITS"
    r"\GPT_weights_v2Pro\Nahida-e15.ckpt"
)

TTS_SOVITS_WEIGHTS = (
    r"D:\Users\User\Desktop\NahidaProject\GPT-SoVITS"
    r"\SoVITS_weights_v2Pro\Nahida_e8_s152.pth"
)

TTS_REFERENCE_AUDIO = (
    r"D:\Users\User\Desktop\NahidaProject\GPT-SoVITS"
    r"\output\slicer_opt"
    r"\Nahida_Voice_Example.wav_0000697280_0000824640.wav"
)

TTS_REFERENCE_TEXT = "不知道干什么的话，要不要我带你去转转呀？"


def env_flag(name, default=False):
    default_value = "1" if default else "0"
    value = os.getenv(name, default_value)

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def create_voice_input():
    if not env_flag(
        "NAHIDA_SENSEVOICE_STT",
        default=False,
    ):
        print("[SenseVoice STT] Disabled.")
        return None

    print("[SenseVoice STT] Starting...")

    try:
        from voice_input import VoiceInput

        voice = VoiceInput()

        print("[SenseVoice STT] Ready.")
        return voice

    except Exception as exc:
        print(
            f"[SenseVoice STT] Failed: {exc}"
        )
        print(
            "[SenseVoice STT] Falling back "
            "to keyboard input."
        )
        return None


def create_tts_client():
    if not env_flag(
        "NAHIDA_TTS",
        default=True,
    ):
        print("[TTS] Disabled by configuration.")
        return None

    try:
        tts = TTSClient(
            api_base=TTS_API_BASE,
            gpt_weights=TTS_GPT_WEIGHTS,
            sovits_weights=TTS_SOVITS_WEIGHTS,
            ref_audio_path=TTS_REFERENCE_AUDIO,
            prompt_text=TTS_REFERENCE_TEXT,
            prompt_lang="zh",
            text_lang="zh",
        )

        tts.configure()

        print("[TTS] Nahida voice ready.")
        return tts

    except Exception as exc:
        print(f"[TTS] Disabled: {exc}")
        print(
            "[TTS] Start GPT-SoVITS API "
            "on 127.0.0.1:9880 to enable voice."
        )
        return None


def get_current_date():
    return datetime.now().date().isoformat()


def handle_day_rollover(
    active_date,
    day_dirty,
):
    current_date = get_current_date()

    if current_date == active_date:
        return active_date, day_dirty

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

    return current_date, False


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
            memory_id=decision.target_memory_id,
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
    tts=None,
):
    last_message = get_latest_message()

    interaction_gap = build_interaction_gap(
        last_message=last_message,
        session_id=session_id,
    )

    previous_messages = get_recent_messages(
        limit=8,
        session_id=session_id,
    )

    message_id = save_message(
        role="user",
        content=text,
        session_id=session_id,
    )

    relevant_event_ids = (
        process_temporal_memory(
            latest_message=text,
            message_id=message_id,
            recent_messages=previous_messages,
        )
    )

    current_events = (
        get_event_occurrences_for_date()
    )

    mark_relevant_current_events_acknowledged(
        relevant_event_ids=(
            relevant_event_ids
        ),
        current_occurrences=current_events,
    )

    proactive_event = (
        get_proactive_event_opportunity(
            current_events
        )
    )

    relevant_events = get_relevant_events(
        relevant_event_ids
    )

    if relevant_event_ids:
        print(
            "[Debug] Relevant event IDs: "
            f"{relevant_event_ids}"
        )

    if current_events:
        print("[Temporal] Today:")

        for event in current_events:
            print(
                f"  #{event['id']} "
                f"{event['title']} "
                f"@ {event['start_at']}"
            )

    if proactive_event:
        print(
            "[Temporal] Proactive opportunity: "
            f"#{proactive_event['id']} "
            f"{proactive_event['title']}"
        )

    relevant_memory_ids = process_memory(
        text=text,
        message_id=message_id,
        previous_messages=previous_messages,
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
                relevant_events=(
                    relevant_events
                ),
                current_events=(
                    current_events
                ),
                proactive_event=(
                    proactive_event
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

    if proactive_event:
        mark_proactive_event_surfaced(
            proactive_event
        )

    print()
    print(
        f"Nahida > {response}"
    )
    print()

    if tts is not None:
        try:
            print("[TTS] Speaking...")
            tts.speak(response)

        except Exception as exc:
            print(
                f"[TTS] Failed: {exc}"
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


def show_events():
    events = get_event_candidates(
        limit=50
    )

    print()
    print("=== Structured Events ===")

    if not events:
        print("No events.")
        print()
        return

    for event in events:
        print()
        print(
            f"#{event['id']} "
            f"[{event['status']}] "
            f"{event['title']}"
        )
        print(
            f"  start: {event['start_at']}"
        )

        if event["end_at"]:
            print(
                f"  end:   {event['end_at']}"
            )

        if event["time_precision"] != "exact":
            print(
                "  precision: "
                f"{event['time_precision']}"
            )

        if event["time_label"]:
            print(
                f"  daypart: {event['time_label']}"
            )

        if event["location"]:
            print(
                f"  location: {event['location']}"
            )

        if event["recurrence_rule"]:
            print(
                "  recurrence: "
                f"{event['recurrence_rule']}"
            )

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

        print(
            item["summary"]
        )

    print()


def main():
    init_db()

    session_id = create_session()

    voice = create_voice_input()

    tts = create_tts_client()

    active_date = get_current_date()
    day_dirty = False

    print(
        "Nahida Brain V6.11"
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
        "/events     Show structured events"
    )
    print(
        "/exit       Exit"
    )
    print()

    if voice is not None:
        print(
            "Press Enter for voice input, "
            "or type normally."
        )
    else:
        print(
            "SenseVoice STT is disabled "
            "or unavailable. Type normally."
        )

    print()

    try:
        while True:
            text = input(
                "You > "
            ).strip()

            if not text:
                if voice is None:
                    continue

                try:
                    text = voice.listen()

                except Exception as exc:
                    print(
                        f"[Voice Input] Failed: "
                        f"{exc}"
                    )
                    continue

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
                success = summarize_today()

                if success:
                    day_dirty = False

                continue

            if text == "/summaries":
                show_daily_summaries()
                continue

            if text == "/events":
                show_events()
                continue

            day_dirty = True

            chat_with_nahida(
                text=text,
                session_id=session_id,
                tts=tts,
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