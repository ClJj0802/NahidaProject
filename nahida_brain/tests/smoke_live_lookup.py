"""Real isolated weather/page lookups with synthetic Brain history and private-DB guards."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "nahida_brain"))
from src import chat, database, live_lookup


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    research_db = ROOT / "Nahida's file/research/db/research.db"
    before = hashlib.sha256(research_db.read_bytes()).hexdigest()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "synthetic_chat": True,
              "personal_database_access": "blocked by test guard", "answer_model_calls": 0, "tests": []}
    history = []
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"NAHIDA_LIVE_LOOKUP": "1"}))
        stack.enter_context(patch.object(live_lookup, "_SESSIONS", {}))
        stack.enter_context(patch.object(database, "get_connection", side_effect=AssertionError("Personal DB accessed")))
        stack.enter_context(patch.object(chat, "load_persona", return_value="Synthetic Chinese persona"))
        for name in ("get_global_communication_preferences", "get_core_memories"):
            stack.enter_context(patch.object(chat, name, return_value=[]))
        stack.enter_context(patch.object(chat, "get_memories_by_ids", return_value=[{"category": "work", "content": "SECRET synthetic workplace, never send"}]))
        recent = stack.enter_context(patch.object(chat, "get_recent_messages", return_value=[]))
        model = stack.enter_context(patch.object(chat, "chat_completion", side_effect=AssertionError("Unexpected answer generation")))
        helper = stack.enter_context(patch.object(live_lookup, "run_lookup", wraps=live_lookup.run_lookup))

        def ask(text, expected_calls, label):
            history.append({"role": "user", "content": text})
            recent.return_value = history
            answer = chat.generate_nahida_response("synthetic-live-smoke", latest_message=text, relevant_memory_ids=[999999],
                                                  active_context={"topic": "SECRET synthetic workplace"})
            history.append({"role": "assistant", "content": answer})
            observation = {"case": label, "question": text, "answer": answer, "helper_calls_total": helper.call_count,
                           "receipt": live_lookup.session_state("synthetic-live-smoke").get("receipt")}
            report["tests"].append(observation)
            print(json.dumps(observation, ensure_ascii=False, indent=2), flush=True)
            if helper.call_count != expected_calls or "SECRET" in json.dumps(helper.call_args_list, default=str):
                raise AssertionError("Incorrect lookup routing or private-context transmission")
            model.assert_not_called()
            return answer

        assert "城市或街区" in ask("宝宝~我公司附近有什么好吃的啊", 0, "food_needs_public_location")
        assert "城市或街区" in ask("来帮我查查看吧", 0, "elliptical_followup")
        weather = ask("或者你帮我看看现在puchong的天气如何", 1, "real_puchong_weather")
        assert "天气模型估计" in weather and "Selangor" in weather and "https://api.open-meteo.com/" in weather
        assert "确实发起" in ask("你确定你有上网找了？", 1, "weather_execution_receipt")
        assert "不是新的搜索" in ask("你从哪里找到的啊", 1, "weather_sources")
        page = ask("帮我打开 https://example.com/ 看看", 2, "real_public_page")
        assert "Example Domain" in page and "实际打开" in page
        assert "确实发起" in ask("你真的查过了吗？", 2, "page_execution_receipt")
        for call in helper.call_args_list:
            assert set(call.args[0]) == {"kind", "query"}
    report["research_database_unchanged"] = hashlib.sha256(research_db.read_bytes()).hexdigest() == before
    assert report["research_database_unchanged"]
    output = ROOT / "nahida-agent-stack/logs/brain-live-lookup-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Smoke report: " + str(output))


if __name__ == "__main__":
    main()
