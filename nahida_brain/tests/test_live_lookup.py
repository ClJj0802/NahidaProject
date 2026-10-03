"""Chat regression for real lookup routing and receipts; no network or personal DB."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import chat, database, live_lookup as live


def weather_result():
    return {"status": "ok", "performed": True, "kind": "weather", "lookup_id": "synthetic",
            "record": "research/raw/lookups/synthetic/lookup.json",
            "location": {"name": "Puchong", "admin1": "Selangor", "country": "Malaysia"},
            "current": {"temperature_2m": 25, "apparent_temperature": 30, "relative_humidity_2m": 90,
                        "wind_speed_10m": 2, "precipitation": .1, "weather_code": 51, "time": "2026-10-03T09:15"},
            "timezone": "Asia/Kuala_Lumpur", "captured_at": "2026-10-03T09:20+08:00",
            "sources": ["https://geocoding-api.open-meteo.com/v1/search?name=Puchong",
                        "https://api.open-meteo.com/v1/forecast?latitude=3&longitude=101.6"]}


class LiveRoutingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"NAHIDA_LIVE_LOOKUP": "1"}))
        self.stack.enter_context(patch.object(live, "_SESSIONS", {}))
        self.stack.enter_context(patch("sys.stdout", new_callable=io.StringIO))
        self.run = self.stack.enter_context(patch.object(live, "run_lookup", return_value=weather_result()))
        self.history = []

    def ask(self, text):
        self.history.append({"role": "user", "content": text})
        reply = live.try_live_reply("test", text, self.history)
        self.history.append({"role": "assistant", "content": reply or "Ordinary reply"})
        return reply

    def test_exact_weather_request_starts_actual_helper_with_city_only(self):
        reply = self.ask("或者你帮我看看现在puchong的天气如何")
        self.run.assert_called_once_with({"kind": "weather", "query": "puchong"})
        self.assertIn("Selangor", reply)
        self.assertIn("25°C", reply)
        self.assertIn("天气模型估计", reply)
        self.assertIn("https://api.open-meteo.com/", reply)

    def test_initial_food_and_elliptical_followup_ask_location_without_inventing_shops(self):
        self.assertIn("城市或街区", self.ask("宝宝~我公司附近有什么好吃的啊"))
        self.assertIn("城市或街区", self.ask("来帮我查查看吧"))
        self.run.assert_not_called()
        self.run.return_value = {"status": "failed", "performed": True, "message": "无相关结果"}
        self.ask("公司在 Puchong, Malaysia")
        self.run.assert_called_once_with({"kind": "search", "query": "restaurants near Puchong, Malaysia"})

    def test_assistant_fabricated_address_cannot_become_query_context(self):
        self.history = [{"role": "assistant", "content": "公司在 Jalan 1/99, Bandar Sri Damansara。鲜芋仙昨天开业。"}]
        reply = self.ask("帮我找公司附近新开的小吃店")
        self.assertIn("城市或街区", reply)
        self.run.assert_not_called()
        self.assertNotIn("Damansara", reply)

    def test_food_pending_does_not_supply_location_to_a_new_weather_topic(self):
        self.ask("公司附近有什么好吃的？")
        self.ask("或者你帮我看看现在puchong的天气如何")
        self.run.assert_called_once_with({"kind": "weather", "query": "puchong"})

    def test_pending_weather_accepts_city_reply_and_does_not_catch_affection(self):
        self.assertIn("哪个城市", self.ask("现在天气怎么样？"))
        self.ask("Puchong")
        self.run.assert_called_once_with({"kind": "weather", "query": "Puchong"})
        self.assertIsNone(self.ask("宝宝抱抱我"))

    def test_online_and_source_followups_use_actual_receipt_without_new_search(self):
        self.ask("现在Puchong的天气如何？")
        for followup in ("你确定你有上网找了？", "你从哪里找到的啊", "你真的查过了吗？"):
            reply = self.ask(followup)
            self.assertIn("open-meteo.com", reply)
        self.assertEqual(self.run.call_count, 1)

    def test_failed_attempt_cannot_claim_a_verified_weather_result(self):
        self.run.return_value = {"status": "failed", "performed": True, "message": "页面受限，未取得结果"}
        self.assertIn("未取得结果", self.ask("Puchong现在天气如何？"))
        reply = self.ask("你确定你有上网找了？")
        self.assertIn("确实发起", reply)
        self.assertIn("未取得结果", reply)
        self.assertNotIn("25°C", reply)

    def test_unexecuted_failure_has_no_success_receipt(self):
        self.run.return_value = {"status": "failed", "performed": False, "message": "服务不可用"}
        self.ask("Puchong天气如何？")
        reply = self.ask("你真的上网查了吗？")
        self.assertIn("不能说已经查到了", reply)

    def test_topic_change_and_unperformed_request_clear_old_receipts(self):
        self.ask("现在Puchong天气如何？")
        self.assertIsNone(self.ask("GPT-SoVITS 的 RTF 0.014 是什么？"))
        self.assertIsNone(self.ask("那来源呢？"))
        self.ask("现在Puchong天气如何？")
        self.ask("公司附近有什么好吃的？")
        self.assertIsNone(self.ask("你真的上网查了吗？"))

    def test_activation_is_host_information_without_button_roleplay(self):
        reply = self.ask("你现在试试看启用上网的功能")
        self.assertIn("查询入口已经接入", reply)
        self.run.assert_not_called()

    def test_concepts_and_personal_statements_preserve_normal_chat(self):
        for text in ("上网搜索的原理是什么？", "地图 API 是什么？", "宝宝早上好", "我饿了",
                     "我公司附近有一家鲜芋仙，我昨天去了", "我今天去店里上班吗？"):
            with self.subTest(text=text):
                self.assertIsNone(live.public_plan(text, [text]))
        self.run.assert_not_called()

    def test_future_weather_is_not_presented_as_current_forecast(self):
        reply = self.ask("Puchong明天天气如何？")
        self.assertIn("不能把当前数据当成未来预报", reply)
        self.run.assert_not_called()

    def test_address_followup_uses_only_requested_name_as_query(self):
        self.run.return_value = {"status": "failed", "performed": True, "message": "未取得结果"}
        self.ask("gastro street是在哪里啊 有具体的地址吗")
        self.run.assert_called_once_with({"kind": "search", "query": "gastro street是在哪里啊 有具体的地址吗"})

    def test_user_provided_webpage_uses_direct_browser_route(self):
        self.assertEqual(live.public_plan("帮我看看 https://example.com/ 是什么", []), {"kind": "page", "query": "https://example.com/"})
        self.run.return_value = {"status": "ok", "kind": "page", "performed": True,
                                "captured_at": "now", "sources": ["https://example.com/"],
                                "results": [{"title": "Example Domain", "url": "https://example.com/", "excerpt": "Public page text"}]}
        reply = self.ask("帮我打开 https://example.com/ 看看")
        self.run.assert_called_once_with({"kind": "page", "query": "https://example.com/"})
        self.assertIn("实际打开", reply)
        self.assertIn("Public page text", reply)
        self.assertNotIn("搜索并打开", reply)

    def test_current_weather_with_what_is_phrase_does_not_fall_through_to_model(self):
        self.ask("Puchong现在天气是什么？")
        self.run.assert_called_once_with({"kind": "weather", "query": "Puchong"})

    def test_disable_and_session_bound(self):
        with patch.dict(os.environ, {"NAHIDA_LIVE_LOOKUP": "0"}):
            self.assertIsNone(self.ask("Puchong天气如何？"))
        for number in range(50):
            live.session_state(number)
        self.assertLessEqual(len(live._SESSIONS), 32)
        self.run.assert_not_called()

    def test_malformed_success_cannot_escape_to_model_prose(self):
        self.run.return_value = {"status": "ok", "kind": "weather", "performed": True, "sources": []}
        self.assertIn("数据不完整", self.ask("Puchong天气如何？"))
        self.assertNotIn("receipt", live.session_state("test"))


class BridgeBoundaryTests(unittest.TestCase):
    def test_fixed_helper_argv_and_utf8_stdin(self):
        payload = weather_result()
        with patch.object(live.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))) as run:
            self.assertEqual(live.run_lookup({"kind": "weather", "query": "Puchong"}), payload)
        self.assertEqual(run.call_args.args[0], [sys.executable, str(live.SCRIPT)])
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), {"kind": "weather", "query": "Puchong"})
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["timeout"], 145)

    def test_timeout_invalid_envelope_and_missing_execution_evidence_fail_closed(self):
        for output in ("bad JSON", "[]", json.dumps({"status": "ok", "kind": "weather", "sources": ["https://example.com"]}),
                       json.dumps({"status": "ok", "kind": "search", "performed": True, "sources": ["https://example.com"]}), "x" * 6001):
            with self.subTest(output=output[:60]), patch.object(live.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)):
                result = live.run_lookup({"kind": "weather", "query": "Puchong"})
                self.assertEqual(result["status"], "failed")
                self.assertFalse(result["performed"])
        with patch.object(live.subprocess, "run", side_effect=subprocess.TimeoutExpired("helper", 145)):
            self.assertFalse(live.run_lookup({"kind": "weather", "query": "Puchong"})["performed"])

    def test_chat_pipeline_does_not_forward_personal_memory_or_call_answer_model(self):
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"NAHIDA_LIVE_LOOKUP": "1"}))
            stack.enter_context(patch.object(live, "_SESSIONS", {}))
            stack.enter_context(patch.object(database, "get_connection", side_effect=AssertionError("Private DB accessed")))
            for name in ("get_global_communication_preferences", "get_core_memories"):
                stack.enter_context(patch.object(chat, name, return_value=[]))
            stack.enter_context(patch.object(chat, "get_memories_by_ids", return_value=[{"category": "work", "content": "SECRET private workplace"}]))
            stack.enter_context(patch.object(chat, "load_persona", return_value="Synthetic persona"))
            text = "或者你帮我看看现在puchong的天气如何"
            stack.enter_context(patch.object(chat, "get_recent_messages", return_value=[{"role": "user", "content": text}]))
            model = stack.enter_context(patch.object(chat, "chat_completion", side_effect=AssertionError("Model called")))
            run = stack.enter_context(patch.object(live, "run_lookup", return_value=weather_result()))
            stack.enter_context(patch("sys.stdout", new_callable=io.StringIO))
            answer = chat.generate_nahida_response("synthetic", relevant_memory_ids=[14], latest_message=text,
                                                  active_context={"topic": "SECRET remembered workplace"})
            self.assertIn("Puchong", answer)
            run.assert_called_once_with({"kind": "weather", "query": "puchong"})
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
