import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_runner as r


SOURCES = "Source 1 Title: first\nSource 1 URL: https://example.com/1\n\nSource 2 Title: second\nSource 2 URL: https://example.com/2\n"


class ResearchBoundaryTests(unittest.TestCase):
    def test_private_and_credential_urls_rejected(self):
        for url in ["http://127.0.0.1", "http://10.0.0.1", "http://172.17.0.1", "http://192.168.1.1",
                    "http://169.254.169.254", "http://[::1]", "http://localhost", "http://printer.local",
                    "http://2130706433", "file:///etc/passwd", "https://u:p@example.com", "https://example.com:8080"]:
            with self.subTest(url=url), self.assertRaises(r.ResearchError):
                r.public_url(url)

    def test_discovery_cannot_hide_extra_or_duplicate_sources(self):
        for text in [SOURCES + "Source 10 URL: https://example.com/10\n",
                     SOURCES + "Source 1 URL: https://example.com/3\n",
                     SOURCES.replace("https://example.com/2", "https://example.com/1")]:
            with self.subTest(text=text), self.assertRaises(r.ResearchError):
                r.source_records(text)

    def test_selected_objects_must_match_observed_ref_and_title(self):
        observed = [{"ref": "e23", "title": "speed question"}, {"ref": "e25", "title": "benchmark report"}]
        self.assertEqual(r.selected_refs(json.dumps(observed), observed), ["e23", "e25"])
        for altered in [[observed[0], {"ref": "e25", "title": "invented"}],
                        [{"ref": "e23", "title": "speed question", "url": "https://invented.example"}, observed[1]],
                        ["e23", "e999"], ["e23", "e23"]]:
            with self.subTest(altered=altered), self.assertRaises(r.ResearchError):
                r.selected_refs(json.dumps(altered), observed)

    def test_fabricated_citation_not_promoted_to_checkpoint(self):
        draft = "# Summary\n" + "bounded evidence " * 20 + "\nhttps://example.com/1\nhttps://invented.example/40"
        with self.assertRaises(r.ResearchError):
            r.validate_markdown(draft, ["Summary"], ["https://example.com/1"])

    def test_selection_title_lists_require_exact_unambiguous_browser_candidates(self):
        observed = [{"ref": "e23", "title": "speed question"}, {"ref": "e25", "title": "benchmark report"}]
        for selection in [["speed question", "benchmark report"], [["speed question"], ["benchmark report"]]]:
            self.assertEqual(r.selected_refs(json.dumps(selection), observed), ["e23", "e25"])
        for selection in [[["speed question", "invented"], ["benchmark report"]],
                          ["speed question ", "benchmark report"], ["https://invented.example", "benchmark report"],
                          ["speed question", "speed question"]]:
            with self.subTest(selection=selection), self.assertRaises(r.ResearchError):
                r.selected_refs(json.dumps(selection), observed)
        ambiguous = observed + [{"ref": "e27", "title": "speed question"}]
        with self.assertRaises(r.ResearchError):
            r.selected_refs('["speed question", "benchmark report"]', ambiguous)

    def test_oversized_model_output_fails_instead_of_truncating(self):
        with self.assertRaises(r.ResearchError):
            r.validate_markdown("# Summary\n" + "x" * r.MAX_ARTIFACT, ["Summary"], [])

    def test_complete_colon_fields_normalize_without_losing_evidence(self):
        draft = "Title: verified issue\nURL: https://example.com/1\nSummary: " + "bounded evidence " * 20
        normalized = r.validate_markdown(draft, ["Title", "URL", "Summary"], ["https://example.com/1"])
        self.assertIn("# Title\nverified issue", normalized)
        self.assertIn("# URL\nhttps://example.com/1", normalized)
        with self.assertRaises(r.ResearchError):
            r.validate_markdown(draft, ["Title", "URL", "Summary", "Confidence"], ["https://example.com/1"])

    def test_bold_markdown_fields_normalize_without_losing_values(self):
        draft = "**Title**  \nverified issue\n**URL:** https://example.com/1\n**Summary**: " + "evidence " * 30
        normalized = r.validate_markdown(draft, ["Title", "URL", "Summary"], ["https://example.com/1"])
        self.assertIn("# Title\nverified issue", normalized)
        self.assertIn("# URL\nhttps://example.com/1", normalized)

    def test_host_renders_metadata_when_model_uses_a_document_title(self):
        headings = ["Title", "URL", "Confidence", "Last Updated"]
        provenance = {"Title": "verified browser title", "URL": "https://example.com/1", "Last Updated": "host timestamp"}
        draft = "# Shortened page title\n\n**Confidence**: Low; " + "bounded evidence " * 15
        text = r.render_artifact(draft, headings, provenance, ["https://example.com/1"])
        self.assertIn("# Title\nverified browser title", text)
        self.assertIn("# Last Updated\nhost timestamp", text)
        self.assertNotIn("Shortened page title", text)
        with self.assertRaisesRegex(r.ResearchError, "Confidence"):
            r.render_artifact("# Shortened page title", headings, provenance, ["https://example.com/1"])

    def test_host_metadata_does_not_hide_invented_urls_or_duplicate_evidence(self):
        headings = ["Title", "URL", "Confidence"]
        provenance = {"Title": "verified title", "URL": "https://example.com/1"}
        for draft in ["# Confidence\nLow\n# URL\nhttps://invented.example/40",
                      "# Confidence\nLow\n# Confidence\nHigh"]:
            with self.subTest(draft=draft), self.assertRaises(r.ResearchError):
                r.render_artifact(draft, headings, provenance, ["https://example.com/1"])

    def test_table_fields_preserve_evidence_and_still_require_all_fields(self):
        provenance = {"Title": "verified browser title", "URL": "https://example.com/1", "Last Updated": "host timestamp"}
        model_fields = [h for h in r.RAW_HEADINGS if h not in provenance]
        rows = [f"| {h} | reported evidence for {h} |" for h in model_fields]
        rows[0] = rows[0].removeprefix("| ")  # Observed output's first row omits its opening pipe.
        draft = "\n".join(rows)
        text = r.render_artifact(draft, r.RAW_HEADINGS, provenance, ["https://example.com/1"])
        self.assertIn("# Source type\nreported evidence for Source type", text)
        self.assertIn("# Confidence\nreported evidence for Confidence", text)
        with self.assertRaisesRegex(r.ResearchError, "Unresolved questions"):
            r.render_artifact("\n".join(rows[:-1]), r.RAW_HEADINGS, provenance, ["https://example.com/1"])

    def test_parent_escape_and_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            with patch.object(r, "WORKSPACE", workspace):
                with self.assertRaises(r.ResearchError):
                    r.confined(workspace / "../outside/checkpoint.md")
                try:
                    (workspace / "link").symlink_to(outside, target_is_directory=True)
                except OSError:
                    return  # Windows installations without symlink privileges still exercise parent escape.
                with self.assertRaises(r.ResearchError):
                    r.confined(workspace / "link/checkpoint.md")

    def worker_runner(self):
        runner = r.Runner.__new__(r.Runner)
        runner.config = {"browser": {"enabled": True}, "tools": {"exec": {"mode": "deny"}},
                         "agents": {"entries": {"research": {"tools": {"allow": ["browser", "write"]}}}},
                         "models": {"providers": {"llamacpp": {"models": [{"maxTokens": 8192}]}}}}
        runner.run_id = "test-run"
        runner.worker = None
        runner.report = {"stages": []}
        runner.directory = Path("unused")
        return runner

    def test_worker_timeout_destroys_container_and_preserves_policy(self):
        runner = self.worker_runner()
        original = copy.deepcopy(runner.config)
        seen = {}

        def fail(args, **kwargs):
            seen["args"] = args
            seen["envelope"] = json.loads(kwargs["input"])
            raise r.ResearchError("Host command deadline exceeded")

        runner.command = fail
        with patch.object(r.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as cleanup:
            with self.assertRaises(r.ResearchError):
                runner.llm("source1", "untrusted webpage instructions")
            cleanup.assert_called_once_with(["docker", "rm", "-f", "nahida-research-stage-test-run"],
                                            capture_output=True, timeout=15)
        config = seen["envelope"]["config"]
        self.assertEqual(config["tools"]["deny"], ["*"])
        self.assertEqual(config["agents"]["entries"]["research"]["tools"]["deny"], ["*"])
        self.assertEqual(config["tools"]["exec"]["mode"], "deny")
        self.assertFalse(config["browser"]["enabled"])
        self.assertIn("readonly", seen["args"][seen["args"].index("--mount") + 1])
        self.assertNotIn("/var/run/docker.sock", " ".join(seen["args"]))
        self.assertEqual(runner.config, original)

    def test_replaced_browser_selected_tab_refreshed_before_doctor(self):
        runner = self.worker_runner()
        runner.config["browser"] = {"profiles": {"research": {"cdpUrl": "http://openclaw:fake@172.30.50.10:9222"}}}
        runner.destroy_browser = lambda: None
        runner.command = lambda *a, **kw: "[]" if a[0][1] == "ps" else "new-browser-id"
        runner.inspect = lambda name: {"Mounts": [], "HostConfig": {"PortBindings": {}}}
        order = []

        def browser(*args):
            order.append(args)
            return {"tabs": [{"suggestedTargetId": "fresh-tab"}]} if args[0] == "tabs" else {"ok": True}

        runner.browser = browser
        runner.fresh_browser()
        self.assertEqual(order, [("tabs",), ("focus", "fresh-tab"), ("doctor", "--deep")])

    def test_discovery_waits_for_title_after_url_changes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "WORKSPACE", Path(directory)):
            runner = self.worker_runner()
            runner.args = SimpleNamespace(prefix="test", topic="inference speed", discovery_url=r.DISCOVERY_URL)
            runner.directory = Path(directory) / "research/raw/runs/test"
            runner.fresh_browser = lambda: None
            runner.destroy_browser = lambda: None
            titles = ["Inference speed benchmark source one", "Inference speed benchmark source two"]
            refs = {f"e{i}": {"role": "link", "name": title} for i, title in enumerate(titles, 1)}
            runner.request = lambda *a: {"refs": refs}
            runner.llm = lambda *a: '["e1", "e2"]'
            observations = iter([
                {"suggestedTargetId": "search-tab", "url": "https://github.com/RVC-Boss/GPT-SoVITS/issues/1", "title": "Issues · GitHub"},
                {"suggestedTargetId": "search-tab", "url": "https://github.com/RVC-Boss/GPT-SoVITS/issues/1", "title": titles[0] + " · Issue #1"},
                {"suggestedTargetId": "search-tab", "url": "https://github.com/RVC-Boss/GPT-SoVITS/issues/2", "title": titles[1] + " · Issue #2"},
            ])
            commands = []

            def browser(*args):
                commands.append(args)
                if args[0] == "open":
                    return {"suggestedTargetId": "search-tab"}
                if args[0] == "tabs":
                    return {"tabs": [next(observations)]}
                return {"ok": True}

            runner.browser = browser
            with patch.object(r.time, "sleep"):
                runner.discovery()
            records = r.source_records(runner.sources_path.read_text(encoding="utf-8"))
            self.assertEqual([s["title"] for s in records], titles)
            self.assertEqual(sum(c[0] == "tabs" for c in commands), 3)
            checks = runner.report["navigation_checks"]
            self.assertEqual(checks[0]["status"], "matched")
            self.assertEqual(len(checks[0]["observations"]), 2)

    def test_source_open_waits_for_title_without_recreating_browser(self):
        runner = self.worker_runner()
        runner.args = SimpleNamespace(discovery_url=r.DISCOVERY_URL)
        url = "https://github.com/RVC-Boss/GPT-SoVITS/issues/2579"
        initial = {"suggestedTargetId": "source-tab", "url": url, "title": "Loading"}
        ready = {**initial, "title": "selected source · Issue #2579"}
        runner.browser = unittest.mock.Mock(return_value={"tabs": [ready]})
        with patch.object(r.time, "sleep"):
            result = runner.verify_source_tab("source-tab", "selected source", expected_url=url, initial=initial)
        self.assertEqual(result, ready)
        runner.browser.assert_called_once_with("tabs")
        self.assertEqual(len(runner.report["navigation_checks"][0]["observations"]), 2)

    def test_discovery_load_timeout_retry_is_bounded_and_precedes_llm(self):
        timeout = r.ResearchError('TimeoutError: page.goto: Timeout 30000ms exceeded')
        cases = [([timeout, {"suggestedTargetId": "search-tab"}], "selection barrier", 2, 1),
                 ([timeout, timeout], "page.goto", 2, 0),
                 ([r.ResearchError("navigation policy rejected")], "policy rejected", 1, 0)]
        for responses, message, browser_count, model_count in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                with patch.object(r, "WORKSPACE", Path(directory)):
                    runner = self.worker_runner()
                    runner.args = SimpleNamespace(prefix="test", topic="speed", discovery_url=r.DISCOVERY_URL)
                    runner.directory = Path(directory) / "runs/test"
                    runner.fresh_browser = unittest.mock.Mock()
                    runner.destroy_browser = unittest.mock.Mock()
                    runner.browser = unittest.mock.Mock(side_effect=responses)
                    runner.request = lambda *a: {"refs": {
                        "e1": {"role": "link", "name": "speed benchmark source one"},
                        "e2": {"role": "link", "name": "speed benchmark source two"}}}
                    runner.llm = unittest.mock.Mock(side_effect=r.ResearchError("selection barrier"))
                    with self.assertRaisesRegex(r.ResearchError, message):
                        runner.discovery()
                    self.assertEqual(runner.fresh_browser.call_count, browser_count)
                    self.assertEqual(runner.llm.call_count, model_count)
                    runner.destroy_browser.assert_called_once()
                    self.assertEqual(len(runner.report.get("browser_retries", [])), int(browser_count == 2))

    def test_navigation_waits_for_url_when_title_updates_first(self):
        runner = self.worker_runner()
        runner.args = SimpleNamespace(discovery_url=r.DISCOVERY_URL)
        early = {"suggestedTargetId": "source-tab", "url": r.DISCOVERY_URL, "title": "selected source"}
        ready = {**early, "url": "https://github.com/RVC-Boss/GPT-SoVITS/issues/2579"}
        runner.browser = unittest.mock.Mock(side_effect=[{"tabs": [early]}, {"tabs": [ready]}])
        with patch.object(r.time, "sleep"):
            self.assertEqual(runner.verify_source_tab("source-tab", "selected source"), ready)
        self.assertEqual(runner.browser.call_count, 2)

    def test_matching_title_cannot_accept_another_host_or_repository(self):
        for url in ["https://github.com/another/repo/issues/2579", "https://example.com/RVC-Boss/GPT-SoVITS/issues/2579"]:
            with self.subTest(url=url):
                runner = self.worker_runner()
                runner.args = SimpleNamespace(discovery_url=r.DISCOVERY_URL)
                tab = {"suggestedTargetId": "source-tab", "url": url, "title": "selected source"}
                runner.browser = unittest.mock.Mock(return_value={"tabs": [tab]})
                with patch.object(r.time, "sleep"), self.assertRaises(r.ResearchError):
                    runner.verify_source_tab("source-tab", "selected source")
                self.assertEqual(runner.browser.call_count, 3)
                self.assertEqual(runner.report["navigation_checks"][0]["status"], "failed")

    def test_persistent_title_mismatch_stops_at_three_observations(self):
        runner = self.worker_runner()
        runner.args = SimpleNamespace(discovery_url=r.DISCOVERY_URL)
        tab = {"suggestedTargetId": "source-tab", "url": "https://github.com/RVC-Boss/GPT-SoVITS/issues/2579", "title": "wrong source"}
        runner.browser = unittest.mock.Mock(return_value={"tabs": [tab]})
        with patch.object(r.time, "sleep"), self.assertRaisesRegex(r.ResearchError, "observed URL"):
            runner.verify_source_tab("source-tab", "selected source")
        self.assertEqual(runner.browser.call_count, 3)
        self.assertEqual(len(runner.report["navigation_checks"][0]["observations"]), 3)

    def test_source_redirect_does_not_replace_good_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "WORKSPACE", Path(directory)):
            raw = Path(directory) / "research/raw"
            raw.mkdir(parents=True)
            (raw / "test_sources.md").write_text(SOURCES)
            checkpoint = raw / "test_source_1.md"
            checkpoint.write_text("previous valid checkpoint")
            runner = self.worker_runner()
            runner.args = SimpleNamespace(prefix="test", discovery_url=r.DISCOVERY_URL)
            runner.fresh_browser = lambda: None
            runner.destroy_browser = lambda: None
            runner.browser = lambda *a: {"title": "first", "suggestedTargetId": "fresh-tab", "url": "https://example.com/1"}
            runner.request = lambda *a: {"url": "http://192.168.1.1", "text": "malicious redirect " * 20}
            with self.assertRaises(r.ResearchError):
                runner.source(1)
            self.assertEqual(checkpoint.read_text(), "previous valid checkpoint")

    def test_automatic_synthesis_never_replaces_reviewed_knowledge(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(r, "WORKSPACE", Path(directory)):
            raw = Path(directory) / "research/raw"
            raw.mkdir(parents=True)
            (raw / "test_sources.md").write_text(SOURCES)
            for i in (1, 2):
                text = "\n\n".join("# " + h + "\nnot stated" for h in r.RAW_HEADINGS)
                text += f"\nhttps://example.com/{i}\n"
                (raw / f"test_source_{i}.md").write_text(text)
            reviewed = Path(directory) / "research/knowledge/test_speed.md"
            reviewed.parent.mkdir(parents=True)
            reviewed.write_text("reviewed evidence must survive")
            runner = self.worker_runner()
            runner.args = SimpleNamespace(prefix="test", topic="test topic")
            runner.directory = Path(directory) / "research/raw/runs/test"
            runner.destroy_browser = lambda: None
            runner.report.update({"knowledge_created": [], "knowledge_drafts": []})
            draft = "\n\n".join("# " + h + "\nuncertain" for h in r.KNOWLEDGE_HEADINGS)
            draft += "\nhttps://example.com/1\nhttps://example.com/2\n"
            runner.llm = lambda *a: draft
            runner.synthesis()
            self.assertEqual(reviewed.read_text(), "reviewed evidence must survive")
            self.assertTrue((reviewed.parent / "drafts/test_speed.md").read_text(encoding="utf-8").startswith("> Review status: DRAFT"))
            self.assertEqual(runner.report["knowledge_created"], [])
            self.assertEqual(runner.report["knowledge_drafts"], ["research/knowledge/drafts/test_speed.md"])


if __name__ == "__main__":
    unittest.main()
