"""Regression for invented map lookups; no private databases or network calls."""
from contextlib import ExitStack
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import chat, database, external_grounding as grounding

REQUEST = "宝宝你帮我找找我的公司附件有没有新开的小吃店"
FOLLOWUP = "名字叫什么啊 你从哪里找到的啊"
STATUS = "你有没有上网去查啊"
FALSE_FIRST = "好像有一家新开的奶茶店在 Maistorage 旁边呢。"
FALSE_SECOND = "叫鲜芋仙，就在你公司楼下。是我刚才用地图软件查的，显示他们昨天刚开业。"


class GroundingTests(unittest.TestCase):
    def test_current_nearby_requests_do_not_need_a_model_or_address_to_admit_no_lookup(self):
        for text in (REQUEST, REQUEST.replace("附件", "附近"), "帮我推荐公司附近的小吃店", "附近哪家店今天营业？",
                     "Find newly opened food shops near my workplace", "帮我上网查一下", "查查地图上的店"):
            with self.subTest(text=text):
                reply = grounding.reply_without_live_lookup(text, [{"role": "user", "content": text}])
                self.assertIsNotNone(reply)
                self.assertIn("没有", reply)
                self.assertNotIn("鲜芋仙", reply)

    def test_user_three_turn_example_cannot_repeat_or_defend_a_fabricated_shop(self):
        history = [{"role": "user", "content": REQUEST}, {"role": "assistant", "content": FALSE_FIRST},
                   {"role": "user", "content": FOLLOWUP}]
        reply = grounding.reply_without_live_lookup(FOLLOWUP, history)
        self.assertIn("不能当作事实", reply)
        self.assertNotIn("鲜芋仙", reply)
        history += [{"role": "assistant", "content": FALSE_SECOND}, {"role": "user", "content": STATUS}]
        reply = grounding.reply_without_live_lookup(STATUS, history)
        self.assertTrue(reply.startswith("没有"))
        self.assertIn("是我说错了", reply)

    def test_repeated_name_and_source_followups_remain_honest(self):
        history = []
        for text in (REQUEST, FOLLOWUP, "店名是什么？", "你从哪查到的？", STATUS):
            history.append({"role": "user", "content": text})
            reply = grounding.reply_without_live_lookup(text, history)
            self.assertIsNotNone(reply)
            self.assertFalse(grounding.claims_unsupported_lookup(reply))
            history.append({"role": "assistant", "content": reply})

    def test_unrelated_chat_own_facts_and_general_explanations_remain_normal(self):
        for text in ("宝宝早上好", "我饿了", "我公司附近有一家鲜芋仙，我昨天去了", "地图 API 是什么？",
                     "上网搜索的原理是什么？", "What does Python map do?", "How does a browser work?",
                     "我今天去店里上班吗？",
                     "GPT-SoVITS 的 CUDA Graph 有实测证据吗？请给出处。"):
            with self.subTest(text=text):
                self.assertIsNone(grounding.reply_without_live_lookup(text, [{"role": "user", "content": text}]))

    def test_topic_change_does_not_let_old_shop_request_block_research_sources(self):
        old_history = [{"role": "user", "content": REQUEST}, {"role": "assistant", "content": FALSE_SECOND}]
        technical = "GPT-SoVITS 的 CUDA Graph 有实测证据吗？请给出处。"
        self.assertIsNone(grounding.reply_without_live_lookup(technical, [*old_history, {"role": "user", "content": technical}]))
        history = [{"role": "user", "content": REQUEST}, {"role": "assistant", "content": "尚未查询。"},
                   {"role": "user", "content": "GPT-SoVITS 的 RTF 0.014 是什么？"},
                   {"role": "assistant", "content": "已审核资料里这是引用声称。"},
                   {"role": "user", "content": "那来源是什么？"}]
        self.assertIsNone(grounding.reply_without_live_lookup(history[-1]["content"], history))

    def test_live_status_distinguishes_offline_research_from_browsing(self):
        history = [{"role": "assistant", "content": "我查了已审核的研究资料，来源是 GitHub 的已保存快照。"},
                   {"role": "user", "content": STATUS}]
        reply = grounding.reply_without_live_lookup(STATUS, history)
        self.assertIn("已审核的本地研究资料", reply)
        self.assertNotIn("是我说错了", reply)

    def test_generated_fake_lookup_is_replaced_but_honest_denials_and_offline_reads_survive(self):
        for reply in (FALSE_FIRST, FALSE_SECOND, "我特意上网搜了附近的点评和地图信息", "I checked Google Maps.",
                      "地图显示这家店没有营业。", "网页写着他们尚未开张。", "好呀，这就帮你看看～（拿出手机搜索）",
                      "刚才试着点那个“上网”的按钮，但好像没反应。", "刚才只顾着帮你查店了。"):
            with self.subTest(reply=reply):
                self.assertTrue(grounding.claims_unsupported_lookup(reply))
                guarded = grounding.guard_chat_reply(reply)
                self.assertNotEqual(guarded, reply)
                self.assertIn("没有联网", guarded)
        for reply in ("我没有上网查询。", "我不能确认这家店昨天刚开业。", "你可以用地图查一下。",
                      "我查了已审核的研究资料。", "我在这里，宝宝～", "I did not browse the internet."):
            with self.subTest(reply=reply):
                self.assertFalse(grounding.claims_unsupported_lookup(reply))
                self.assertEqual(grounding.guard_chat_reply(reply), reply)


class ChatGroundingTests(unittest.TestCase):
    def setUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(database, "get_connection", side_effect=AssertionError("Personal DB accessed")))
        for name in ("get_global_communication_preferences", "get_core_memories"):
            self.patches.enter_context(patch.object(chat, name, return_value=[]))
        self.patches.enter_context(patch.object(chat, "get_memories_by_ids", return_value=[
            {"category": "work", "content": "The user works at Maistorage."}]))
        self.patches.enter_context(patch.object(chat, "load_persona", return_value="Speak affectionately in Chinese."))
        self.patches.enter_context(patch.object(chat, "try_live_reply", return_value=None))
        self.history = self.patches.enter_context(patch.object(chat, "get_recent_messages", return_value=[]))
        self.lookup = self.patches.enter_context(patch.object(chat, "lookup_research", return_value=None))
        self.completion = self.patches.enter_context(patch.object(chat, "chat_completion", return_value=FALSE_SECOND))

    def test_workplace_memory_cannot_supply_shop_details_or_start_fake_search(self):
        self.history.return_value = [{"role": "user", "content": REQUEST}]
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            reply = chat.generate_nahida_response(999, relevant_memory_ids=[14], latest_message=REQUEST)
        self.assertIn("Live web/maps not called", output.getvalue())
        self.assertIn("不能确认附近", reply)
        self.assertNotIn("鲜芋仙", reply)
        self.lookup.assert_not_called()
        self.completion.assert_not_called()

    def test_existing_fabricated_history_is_corrected_without_deleting_it(self):
        rows = [{"role": "user", "content": REQUEST}, {"role": "assistant", "content": FALSE_FIRST},
                {"role": "user", "content": FOLLOWUP}, {"role": "assistant", "content": FALSE_SECOND},
                {"role": "user", "content": STATUS}]
        self.history.return_value = rows
        with patch("sys.stdout", new_callable=io.StringIO):
            reply = chat.generate_nahida_response(999, latest_message=STATUS)
        self.assertIn("是我说错了", reply)
        self.assertEqual(rows[-2]["content"], FALSE_SECOND)
        self.completion.assert_not_called()

    def test_every_normal_chat_prompt_has_host_capability_status_and_output_guard(self):
        self.history.return_value = [{"role": "user", "content": "宝宝早上好"}]
        reply = chat.generate_nahida_response(999, latest_message="宝宝早上好")
        self.completion.assert_called_once()
        self.assertNotIn("鲜芋仙", reply)
        self.assertIn("没有联网", reply)
        prompt = self.completion.call_args.kwargs["messages"][0]["content"]
        self.assertIn("live_web_search_performed: false", prompt)
        self.assertIn("Earlier assistant replies are not search results", prompt)


if __name__ == "__main__":
    unittest.main()
