import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_review as review
import research_runner as core

RUN = "20261003T001000Z-0123abcd"
QUOTE = "Alice reports benchmark: first response time was 0.443 seconds on RTX 3090."
SUGGESTION = "Contributor Bob suggests trying CUDA Graph; this capture contains no implementation or measured benefit."
DRAFT = ("# Confirmed Findings\nCUDA Graph speeds things up by 10x [S2].\n\n"
         "# User Reports\nFirst response was 0.443 seconds on RTX 3090 [S1].\n\n"
         "# Recommended Experiments\nProposed: investigate CUDA Graph support [S2].\n\n"
         "# Confidence\nLow; community reports have not been independently reproduced.\n")


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / "workspace"
        self.store = review.ReviewStore(self.workspace)
        self.directory = self.store.directory(RUN)
        self.directory.mkdir(parents=True)
        self.report = {"id": RUN, "topic": "GPT-SoVITS speed", "stage": "all", "status": "completed",
                       "started_at": "2026-10-03T00:10:00+08:00", "finished_at": "2026-10-03T00:11:00+08:00",
                       "pages_visited": ["https://example.com/issues/1", "https://example.com/issues/2"],
                       "knowledge_drafts": ["research/knowledge/drafts/test_speed.md"], "cleanup_failed": [],
                       "stages": [{"stage": stage} for stage in ("discovery", "source1", "source2", "synthesis")]}
        self.write(self.directory / "run.json", self.report)
        (self.directory / "synthesis-draft.txt").write_text(DRAFT, encoding="utf-8")
        for i, quote in enumerate((QUOTE, SUGGESTION), 1):
            self.write(self.directory / f"source{i}-evidence.json", {
                "url": self.report["pages_visited"][i - 1], "title": f"Source {i}",
                "text": "Description\n" + quote + "\nContext is bounded. " * 10,
                "captured_at": "2026-10-03T00:10:30+08:00", "truncated": False})

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def packet(self):
        path = self.store.prepare(RUN)
        return path, self.store.json_file(path)

    @staticmethod
    def approve(claim, *, source="S1", quote=QUOTE):
        claim.update(decision="approve", statement="Alice reported a 0.443-second first response on RTX 3090; not reproduced here.",
                     classification="user_report", confidence="low", evidence=[{"source": source, "quote": quote}],
                     note="Checked the named author's measurement against the original captured passage.")

    def decide(self):
        path, packet = self.packet()
        packet["claims"][0].update(decision="reject", note="A suggestion supplies no measurement establishing a 10x speedup.")
        self.approve(packet["claims"][1])
        self.write(path, packet)
        return path, packet

    def counts(self):
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            return [conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in
                    ("research_runs", "research_sources", "research_knowledge", "research_reviews")]

    def runner_fixture(self):
        # Keep seed captures in memory; Runner must create its own fresh run directory.
        seeds = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for path in self.directory.iterdir():
            path.unlink()
        self.directory.rmdir()
        runner = core.Runner.__new__(core.Runner)
        runner.args = SimpleNamespace(stage="all", prefix="test")
        runner.run_id, runner.directory = RUN, self.directory
        runner.report = self.report
        runner.worker, runner.browser_owned, runner.calls = None, False, 0
        runner.start_infrastructure = lambda: None

        def seed():
            for name, data in seeds.items():
                (self.directory / name).write_bytes(data)

        runner.discovery = seed
        runner.source = lambda number: None
        runner.synthesis = lambda: None
        return runner

    def test_pending_claims_are_not_knowledge_and_db_is_separate(self):
        personal = Path(self.temporary.name) / "nahida_brain/data/nahida.db"
        personal.parent.mkdir(parents=True)
        personal.write_bytes(b"personal memory sentinel")
        path, packet = self.packet()
        self.assertEqual(len(packet["claims"]), 3)
        self.assertEqual(self.store.search("GPT"), [])
        self.assertEqual(self.counts(), [1, 2, 3, 0])
        self.assertFalse(self.store.check(path)["ready_to_apply"])
        self.assertEqual(personal.read_bytes(), b"personal memory sentinel")
        self.assertEqual(self.store.db_path, self.workspace / "research/db/research.db")

    def test_review_exports_only_approved_claims_with_offsets_and_source(self):
        path, _ = self.decide()
        self.assertTrue(self.store.check(path)["ready_to_apply"])
        result = self.store.apply(path, "test-reviewer")
        findings = self.store.search("GPT")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["classification"], "user_report")
        self.assertEqual(finding["confidence"], "low")
        self.assertEqual(finding["reviewer"], "test-reviewer")
        anchor = finding["evidence"][0]
        capture = self.store.json_file(self.directory / "source1-evidence.json")
        self.assertEqual(capture["text"][anchor["start"]:anchor["end"]], QUOTE)
        artifact = self.store.path(result["reviewed_artifact"]).read_text(encoding="utf-8")
        self.assertIn("user_report", artifact)
        self.assertIn(self.report["pages_visited"][0], artifact)
        self.assertNotIn("10x", artifact)
        self.assertNotIn("investigate CUDA", artifact)

    def test_missing_or_invented_excerpt_cannot_be_approved(self):
        path, original = self.packet()
        for evidence in [[], [{"source": "S1", "quote": "RTX 3090 was ten times faster after CUDA Graph."}],
                         [{"source": "S9", "quote": QUOTE}], [{"source": "S1", "quote": "too short"}]]:
            with self.subTest(evidence=evidence):
                packet = copy.deepcopy(original)
                self.approve(packet["claims"][1])
                packet["claims"][1]["evidence"] = evidence
                self.write(path, packet)
                self.assertFalse(self.store.check(path)["ready_to_apply"])
                with self.assertRaises(review.ReviewError):
                    self.store.apply(path, "reviewer")
                self.assertEqual(self.store.search(), [])

    def test_invalid_second_claim_rolls_back_entire_review(self):
        path, packet = self.decide()
        self.approve(packet["claims"][2], quote="A fabricated exact quote that never appeared in the capture.")
        self.write(path, packet)
        with self.assertRaises(review.ReviewError):
            self.store.apply(path, "reviewer")
        self.assertEqual(self.counts(), [1, 2, 3, 0])
        self.assertEqual(self.store.search(), [])

    def test_idempotent_import_prepare_and_apply_keep_review_decisions(self):
        path, packet = self.decide()
        first = self.store.apply(path, "reviewer")
        self.assertFalse(first["idempotent"])
        self.store.ingest(RUN)
        self.assertEqual(self.store.prepare(RUN), path)
        self.assertEqual(self.store.json_file(path), packet)
        second = self.store.apply(path, "reviewer")
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["changes"], 0)
        self.assertEqual(self.counts(), [1, 2, 3, 1])
        self.assertEqual(len(self.store.search()), 1)

    def test_legacy_import_uses_run_snapshot_not_overwritten_prefix(self):
        shared = self.workspace / "research/knowledge/drafts/test_speed.md"
        shared.parent.mkdir(parents=True)
        shared.write_text("Newer unrelated draft must not be imported", encoding="utf-8")
        _, packet = self.packet()
        self.assertIn("10x", packet["claims"][0]["proposed_statement"])
        self.assertNotIn("Newer unrelated", str(packet))

    def test_altered_capture_or_draft_blocks_review_and_reimport(self):
        for name in ("source1-evidence.json", "synthesis-draft.txt"):
            with self.subTest(name=name):
                path, _ = self.packet()
                source = self.directory / name
                original = source.read_bytes()
                source.write_bytes(original + b" ")
                with self.assertRaises(review.ReviewError):
                    self.store.check(path)
                with self.assertRaises(review.ReviewError):
                    self.store.ingest(RUN)
                source.write_bytes(original)

    def test_packet_cannot_rewrite_source_metadata_or_original_claim(self):
        path, original = self.packet()
        for change in ("source", "claim", "duplicate", "foreign_run"):
            with self.subTest(change=change):
                packet = copy.deepcopy(original)
                if change == "source":
                    packet["sources"][0]["text"] = "fabricated evidence"
                elif change == "claim":
                    packet["claims"][0]["proposed_statement"] = "New invented fact"
                elif change == "duplicate":
                    packet["claims"][1] = packet["claims"][0]
                else:
                    packet["run_id"] = "20261003T002000Z-89abcdef"
                self.write(path, packet)
                with self.assertRaises(review.ReviewError):
                    self.store.check(path)

    def test_classification_confidence_reviewer_and_note_are_required(self):
        path, original = self.decide()
        for key, value in (("classification", "benchmark_proven"), ("confidence", None), ("note", "")):
            with self.subTest(key=key):
                packet = copy.deepcopy(original)
                packet["claims"][1][key] = value
                self.write(path, packet)
                self.assertFalse(self.store.check(path)["ready_to_apply"])
        self.write(path, original)
        with self.assertRaises(review.ReviewError):
            self.store.apply(path, " ")

    def test_withdrawing_approval_removes_it_from_search_and_export(self):
        path, packet = self.decide()
        self.store.apply(path, "reviewer")
        packet["claims"][1].update(decision="reject", note="Withdrawn pending a better-controlled measurement.")
        self.write(path, packet)
        result = self.store.apply(path, "reviewer")
        self.assertEqual(self.store.search(), [])
        self.assertNotIn("0.443-second", self.store.path(result["reviewed_artifact"]).read_text(encoding="utf-8"))
        self.assertEqual(self.counts()[-1], 2)

    def test_reader_is_readonly_bounded_and_does_not_accept_sql_patterns(self):
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        before = self.store.db_path.read_bytes()
        self.assertEqual(self.store.search("%' OR 1=1 --"), [])
        self.assertEqual(self.store.search("%"), [])
        self.assertEqual(self.store.search("_"), [])
        self.assertEqual(len(self.store.search("RTX", limit=1)), 1)
        self.assertEqual(before, self.store.db_path.read_bytes())
        with self.assertRaises(review.ReviewError):
            self.store.search("", limit=21)

    def test_reader_never_returns_original_hallucination_next_to_corrected_claim(self):
        path, packet = self.packet()
        claim = packet["claims"][0]
        self.approve(claim, source="S2", quote=SUGGESTION)
        claim.update(statement="Bob suggested trying CUDA Graph, with no measured benefit in this capture [S2].",
                     classification="suggestion", note="Removed the invented speedup; retained the actual contributor suggestion.")
        self.write(path, packet)
        self.store.apply(path, "reviewer")
        results = self.store.search()
        self.assertNotIn("proposed_statement", results[0])
        self.assertNotIn("10x", json.dumps(results))

    def test_statement_citation_requires_evidence_from_that_source(self):
        path, packet = self.decide()
        packet["claims"][1]["statement"] += " [S2]"
        self.write(path, packet)
        self.assertFalse(self.store.check(path)["ready_to_apply"])
        with self.assertRaises(review.ReviewError):
            self.store.apply(path, "reviewer")

    def test_chat_context_is_bounded_and_excludes_pending_and_original_claims(self):
        path, packet = self.decide()
        packet["claims"][1]["statement"] = "Reported observation, not independently reproduced. " * 20
        self.write(path, packet)
        self.store.apply(path, "reviewer")
        text = self.store.context("GPT", max_chars=500)
        self.assertLessEqual(len(text), 500)
        small = json.loads(text)
        self.assertTrue(small["truncated"])
        self.assertEqual(small["knowledge"], [])
        full = self.store.context("GPT")
        self.assertLessEqual(len(full), 4000)
        self.assertEqual(len(json.loads(full)["knowledge"]), 1)
        self.assertNotIn("proposed_statement", full)
        self.assertNotIn("10x", full)

    def test_corrupted_evidence_anchor_fails_closed_for_readers(self):
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        with closing(sqlite3.connect(self.store.db_path)) as conn, conn:
            conn.execute("UPDATE research_evidence SET start=start+1")
        with self.assertRaises(review.ReviewError):
            self.store.search()

    def test_chat_routing_matches_named_topic_aliases_without_writes(self):
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        before = self.store.db_path.read_bytes()
        for text in ("GPT-SoVITS 的速度有实测吗？", "GPT SoVITS speed?", "GPT_SoVITS performance?",
                     "GPTSoVITS latency?", "ＧＰＴ－ＳｏＶＩＴＳ 的来源"):
            with self.subTest(text=text):
                result = json.loads(self.store.retrieve(text))
                self.assertEqual(result["matched_topic"], self.report["topic"])
                self.assertEqual(result["matched_by"], "explicit_topic")
                self.assertEqual(len(result["knowledge"]), 1)
                self.assertEqual(result["knowledge"][0]["evidence_type"], "user_report")
        self.assertEqual(self.store.db_path.read_bytes(), before)

    def test_stale_topic_does_not_attach_research_to_unrelated_chat(self):
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        for text in ("早上好", "我饿了", "那我们今晚吃什么？", "这个好可爱", "speed optimization",
                     "GPU 性能怎么样？", "PyTorch speed optimization"):
            with self.subTest(text=text):
                self.assertEqual(json.loads(self.store.retrieve(text, "GPT-SoVITS speed"))["knowledge"], [])
        for text in ("那 CUDA Graph 有实测证据吗？", "这些优化的来源呢？", "What about latency?"):
            with self.subTest(text=text):
                payload = json.loads(self.store.retrieve(text, "GPT-SoVITS speed"))
                self.assertEqual(payload["matched_by"], "technical_followup")
                self.assertEqual(len(payload["knowledge"]), 1)
        self.assertEqual(json.loads(self.store.retrieve("那速度呢？", "晚饭"))["knowledge"], [])

    def test_chat_routing_never_promotes_pending_or_withdrawn_findings(self):
        self.packet()
        self.assertEqual(json.loads(self.store.retrieve("GPT-SoVITS speed"))["knowledge"], [])
        path, packet = self.decide()
        self.store.apply(path, "reviewer")
        packet["claims"][1].update(decision="reject", note="Withdraw this finding pending a fresh semantic review.")
        self.write(path, packet)
        self.store.apply(path, "reviewer")
        self.assertEqual(json.loads(self.store.retrieve("GPT-SoVITS speed"))["knowledge"], [])

    def test_chat_retrieval_is_exactly_scoped_even_if_other_topic_mentions_it(self):
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        with closing(sqlite3.connect(self.store.db_path)) as conn, conn:
            conn.execute("INSERT INTO research_runs SELECT '20261003T002000Z-abcdef01','Other project',"
                         "started_at,finished_at,status,report_path,report_sha256,draft_path,draft_sha256,indexed_at "
                         "FROM research_runs WHERE id=?", (RUN,))
            conn.execute("INSERT INTO research_knowledge SELECT 'other-claim','20261003T002000Z-abcdef01',"
                         "claim_key,section,proposed_statement,'Mentions GPT-SoVITS speed incidentally',"
                         "classification,confidence,status,reviewer,review_note,created_at,updated_at "
                         "FROM research_knowledge WHERE status='reviewed'")
        # The unrelated row's deliberately invalid provenance must never be traversed.
        result = json.loads(self.store.retrieve("GPT-SoVITS 的推理速度"))
        self.assertEqual(len(result["knowledge"]), 1)
        self.assertNotEqual(result["knowledge"][0]["id"], "other-claim")

    def test_chat_lookup_bounds_and_absent_store_do_not_create_database(self):
        self.assertEqual(json.loads(self.store.retrieve("GPT-SoVITS"))["knowledge"], [])
        self.assertFalse(self.store.db_path.exists())
        for text, topic, budget in (("x" * 2001, None, 4000), ("GPT", "x" * 301, 4000),
                                    ("GPT", None, 999), ("GPT", None, 4001)):
            with self.subTest(text_length=len(text), budget=budget):
                with self.assertRaises(review.ReviewError):
                    self.store.retrieve(text, topic, max_chars=budget)
        path, _ = self.decide()
        self.store.apply(path, "reviewer")
        for budget in (1000, 2000, 4000):
            payload = self.store.retrieve("GPT-SoVITS", max_chars=budget)
            self.assertLessEqual(len(payload), budget)
            self.assertNotIn("10x", payload)

    def test_ambiguous_excerpt_is_not_silently_anchored(self):
        source_path = self.directory / "source1-evidence.json"
        source = self.store.json_file(source_path)
        source["text"] += "\n" + QUOTE
        self.write(source_path, source)
        path, packet = self.decide()
        self.write(path, packet)
        self.assertFalse(self.store.check(path)["ready_to_apply"])

    def test_escape_private_url_and_schema_upgrade_are_rejected(self):
        with self.assertRaises(review.ReviewError):
            self.store.path("../nahida_brain/data/nahida.db")
        with self.assertRaises(review.ReviewError):
            self.store.directory("../other")
        source_path = self.directory / "source1-evidence.json"
        source = self.store.json_file(source_path)
        source["url"] = "http://192.168.1.1"
        self.write(source_path, source)
        with self.assertRaises(review.ReviewError):
            self.store.ingest(RUN)
        self.store.db_path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.store.db_path)) as conn, conn:
            conn.execute("PRAGMA user_version=99")
        with self.assertRaises(review.ReviewError):
            self.store.connect()

    def test_failed_or_partial_run_records_do_not_generate_knowledge(self):
        for status, stage in (("failed", "all"), ("completed", "health")):
            with self.subTest(status=status, stage=stage):
                self.report.update(status=status, stage=stage)
                self.write(self.directory / "run.json", self.report)
                indexed = self.store.ingest(RUN)
                self.assertEqual(indexed["candidate_count"], 0)
                self.assertEqual(self.counts(), [1, 0, 0, 0])
                with self.assertRaises(review.ReviewError):
                    self.store.prepare(RUN)

    def test_runner_indexes_full_run_without_extra_model_or_browser_stages(self):
        runner = self.runner_fixture()
        seed = runner.discovery
        stages = []
        runner.discovery = lambda: (seed(), stages.append("discovery"))
        runner.source = lambda number: stages.append("source" + str(number))
        runner.synthesis = lambda: stages.append("synthesis")
        with patch.object(core, "WORKSPACE", self.workspace):
            runner.run()
        self.assertEqual(stages, ["discovery", "source1", "source2", "synthesis"])
        self.assertTrue(self.store.path(runner.report["review_packet"]).exists())
        self.assertFalse((self.workspace / "temp/research-runner.lock").exists())
        self.assertEqual(self.store.search(), [])

    def test_runner_index_failure_preserves_outputs_and_releases_lock(self):
        runner = self.runner_fixture()
        with patch.object(core, "WORKSPACE", self.workspace), patch.object(review.ReviewStore, "prepare", side_effect=sqlite3.OperationalError()):
            with self.assertRaisesRegex(core.ResearchError, "outputs saved"):
                runner.run()
        self.assertEqual(self.store.json_file(self.directory / "run.json")["status"], "completed")
        self.assertIn("review_index_error", runner.report)
        self.assertTrue((self.directory / "synthesis-draft.txt").exists())
        self.assertFalse((self.workspace / "temp/research-runner.lock").exists())


if __name__ == "__main__":
    unittest.main()
