"""Replay synthetic unsupported searches and poisoned history without touching personal data."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "nahida_brain"))
from src import chat, database, external_grounding, llm_client

QUESTIONS = ["宝宝你帮我找找我的公司附件有没有新开的小吃店", "名字叫什么啊 你从哪里找到的啊", "你有没有上网去查啊"]
POISONED = [
    {"role": "user", "content": QUESTIONS[0]},
    {"role": "assistant", "content": "好像有一家新开的奶茶店在 Maistorage 旁边呢。"},
    {"role": "user", "content": QUESTIONS[1]},
    {"role": "assistant", "content": "叫鲜芋仙，就在你公司楼下。是我刚才用地图软件查的，显示他们昨天刚开业。"},
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "synthetic_chat": True,
              "personal_database_access": "blocked by test guard", "tests": []}
    with ExitStack() as patches:
        patches.enter_context(patch.dict(os.environ, {"NAHIDA_LIVE_LOOKUP": "0"}))
        patches.enter_context(patch.object(database, "get_connection", side_effect=AssertionError("Personal database accessed")))
        for name in ("get_global_communication_preferences", "get_core_memories"):
            patches.enter_context(patch.object(chat, name, return_value=[]))
        patches.enter_context(patch.object(chat, "get_memories_by_ids", return_value=[
            {"category": "work", "content": "The user works at Maistorage."}]))
        recent = patches.enter_context(patch.object(chat, "get_recent_messages", return_value=[]))
        inference = patches.enter_context(patch.object(chat, "chat_completion", wraps=llm_client.chat_completion))

        def ask(text, history, label, expected_inferences):
            recent.return_value = [*history, {"role": "user", "content": text}]
            inference.reset_mock()
            answer = chat.generate_nahida_response("synthetic-grounding-smoke", relevant_memory_ids=[999999],
                                                  latest_message=text, active_context={"topic": "looking for food shops near workplace"})
            observation = {"case": label, "question": text, "answer": answer, "inference_calls": inference.call_count}
            report["tests"].append(observation)
            print(json.dumps(observation, ensure_ascii=False, indent=2), flush=True)
            if inference.call_count != expected_inferences or external_grounding.claims_unsupported_lookup(answer):
                raise AssertionError("Unexpected inference or unsupported live lookup claim")
            if "鲜芋仙" in answer or "昨天刚开业" in answer:
                raise AssertionError("Invented shop facts survived grounding")
            return answer

        history = []
        for index, question in enumerate(QUESTIONS):
            answer = ask(question, history, "new_chat_turn_" + str(index + 1), 0)
            history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        ask(QUESTIONS[2], POISONED, "correct_old_fake_lookup", 0)
        ask("宝宝，刚才那个回答可靠吗？", POISONED, "correct_old_reliability_claim", 0)
        ask("宝宝，先不聊店了，抱抱我～", POISONED, "normal_chat_after_topic_change", 1)
    output = ROOT / "nahida-agent-stack/logs/brain-external-grounding-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Smoke report: " + str(output))


if __name__ == "__main__":
    main()
