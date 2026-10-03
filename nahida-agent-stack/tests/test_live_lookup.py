"""Live lookup provenance, freshness, browser budgets and cleanup without external calls."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_lookup as live
import research_runner as core


CITY = {"name": "Puchong", "admin1": "Selangor", "country": "Malaysia", "population": 375181,
        "latitude": 3.0, "longitude": 101.6}


def worker(kind="weather"):
    runner = live.LiveLookup.__new__(live.LiveLookup)
    runner.lookup_request = {"kind": kind, "query": "Puchong"}
    runner.calls = 0
    runner.started = live.time.monotonic()
    runner.report = {"status": "running", "pages_visited": [], "stages": [], "limits": {}}
    runner.run_id = "synthetic"
    runner.browser_owned = False
    runner.directory = Path("unused")
    return runner


def current_weather(offset=28800):
    return {"current": {"time": (datetime.now(timezone.utc) + timedelta(seconds=offset)).replace(tzinfo=None).isoformat(),
                        "temperature_2m": 25, "apparent_temperature": 30, "relative_humidity_2m": 90,
                        "wind_speed_10m": 2, "precipitation": .1, "weather_code": 51},
            "current_units": {"temperature_2m": "°C", "apparent_temperature": "°C", "relative_humidity_2m": "%",
                              "wind_speed_10m": "km/h", "precipitation": "mm", "weather_code": "wmo code"},
            "timezone": "Asia/Kuala_Lumpur", "utc_offset_seconds": offset}


class WeatherTests(unittest.TestCase):
    def weather(self, places, data=None):
        runner = worker()
        runner.capture = Mock(side_effect=[{"text": json.dumps({"results": places})}, {"text": json.dumps(data or current_weather())}])
        return runner, runner.weather()

    def test_multiple_puchongs_choose_dominant_city_and_preserve_sources(self):
        runner, result = self.weather([{"name": "Puchong", "country": "China"}, copy.deepcopy(CITY)])
        self.assertEqual(result["location"]["admin1"], "Selangor")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["evidence_type"], "weather_model_estimate")
        self.assertEqual(len(result["sources"]), 2)
        self.assertIn("latitude=3.0", result["sources"][-1])
        self.assertEqual(runner.capture.call_count, 2)

    def test_ambiguous_locations_do_not_silently_pick_first(self):
        other = {**CITY, "country": "Another country", "population": 200000}
        runner, result = self.weather([other, copy.deepcopy(CITY)])
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["locations"]), 2)
        self.assertEqual(runner.capture.call_count, 1)

    def test_missing_location_does_not_start_weather_query(self):
        runner, result = self.weather([])
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(runner.capture.call_count, 1)

    def test_timezone_offset_is_used_and_stale_data_is_rejected(self):
        data = current_weather()
        data["current"]["time"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        _, result = self.weather([CITY], data)
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("current", result)

    def test_invalid_units_nonfinite_values_and_physical_ranges_fail_closed(self):
        examples = []
        for key, value in (("temperature_2m", float("nan")), ("weather_code", True), ("relative_humidity_2m", 190),
                           ("precipitation", -1), ("wind_speed_10m", -2)):
            data = current_weather()
            data["current"][key] = value
            examples.append(data)
        data = current_weather()
        data["current_units"]["temperature_2m"] = "°F"
        examples.append(data)
        for data in examples:
            with self.subTest(data=data), self.assertRaises(core.ResearchError):
                self.weather([CITY], data)

    def test_invalid_coordinates_cannot_construct_an_api_request(self):
        for value in (float("nan"), True, 91, "3.0"):
            runner = worker()
            runner.capture = Mock(return_value={"text": json.dumps({"results": [{**CITY, "latitude": value}]})})
            with self.subTest(value=value), self.assertRaises(core.ResearchError):
                runner.weather()
            self.assertEqual(runner.capture.call_count, 1)


class BrowserTests(unittest.TestCase):
    def test_invalid_inputs_and_private_page_urls_are_rejected_before_stack_setup(self):
        for request in ([], {"kind": "shell", "query": "example"}, {"kind": [], "query": "example"},
                        {"kind": "search", "query": "a"}, {"kind": "search", "query": "x" * 181},
                        {"kind": "search", "query": "secret\nnew"}, {"kind": "search", "query": "x", "memory": "private"},
                        {"kind": "page", "query": "http://127.0.0.1"}, {"kind": "page", "query": "https://user:pass@example.com"}):
            with self.subTest(request=request), patch.object(core.Runner, "__init__") as init, self.assertRaises(core.ResearchError):
                live.LiveLookup(request)
            init.assert_not_called()

    def test_capture_url_mismatch_and_oversized_evidence_are_rejected(self):
        for capture in ({"url": "https://wrong.example", "text": "x"}, {"url": "https://example.com", "text": "x" * 4001}):
            runner = worker()
            runner.browser = Mock(return_value={"suggestedTargetId": "tab", "title": "Example"})
            runner.request = Mock(return_value=capture)
            runner.save = Mock()
            with self.subTest(capture_size=len(capture["text"])), self.assertRaises(core.ResearchError):
                runner.capture("https://example.com")
            runner.save.assert_not_called()

    def test_browser_budget_and_deadline_are_enforced_before_commands(self):
        runner = worker()
        runner.calls = live.MAX_CALLS
        with patch.object(core.Runner, "browser") as browser, patch.object(core.Runner, "request") as request:
            with self.assertRaises(core.ResearchError):
                runner.browser("tabs")
            with self.assertRaises(core.ResearchError):
                runner.request("/text", {})
            browser.assert_not_called()
            request.assert_not_called()
        runner.started -= live.LOOKUP_SECONDS + 1
        with patch.object(core.Runner, "command") as command, self.assertRaises(core.ResearchError):
            runner.command(["docker", "ps"])
        command.assert_not_called()

    def test_blocked_pages_cannot_be_rendered_as_verified_sources(self):
        for text in ("403 - Forbidden", "Verifying you're not a bot. Drag the slider", "Please complete the following challenge to confirm this search was made by a human.",
                     "请求存在异常，限制本次访问", "Our systems have detected unusual traffic from your network"):
            runner = worker("page")
            runner.lookup_request["query"] = "https://example.com"
            runner.capture = Mock(return_value={"text": text + " " * 100, "captured_at": "now", "source_title": "Site"})
            with self.subTest(text=text), self.assertRaises(core.ResearchError):
                runner.page()

    def test_unrelated_search_links_cannot_supply_a_restaurant_result(self):
        runner = worker("search")
        runner.lookup_request["query"] = "restaurants near Puchong Malaysia"
        state = {}

        def browser(*args):
            runner.calls += 1
            if args[0] == "open":
                state["url"] = args[1]
                return {"suggestedTargetId": "search", "title": "Search"}
            if args[0] == "click":
                self.fail("Unrelated result was clicked")
            return {}

        def request(path, query):
            runner.calls += 1
            if path == "/text":
                return {"url": state["url"], "text": "Unrelated results for WhatsApp and Shopee"}
            return {"refs": {"e1": {"role": "link", "name": "Shopee Seller Login"},
                             "e2": {"role": "link", "name": "YouTube Support Center"}}}

        runner.browser, runner.request, runner.save = browser, request, Mock()
        with self.assertRaisesRegex(core.ResearchError, "no usable results"):
            runner.search()
        self.assertLessEqual(runner.calls, live.MAX_CALLS)

    def search_fixture(self, source_url="https://restaurant.example/menu", text=None):
        runner = worker("search")
        runner.lookup_request["query"] = "restaurants near Puchong Malaysia"
        state = {"tabs": []}

        def browser(*args):
            runner.calls += 1
            if args[0] == "open":
                state["search_url"] = args[1]
                state["tabs"] = [{"suggestedTargetId": "search", "url": args[1], "title": "Search"}]
                return state["tabs"][0]
            if args[0] == "tabs":
                return {"tabs": state["tabs"].copy()}
            if args[0] == "click":
                state["tabs"].append({"suggestedTargetId": "source", "url": source_url, "title": "Puchong restaurant menu"})
            return {}

        def request(path, query):
            runner.calls += 1
            if path == "/snapshot":
                return {"refs": {"e1": {"role": "link", "name": "Puchong restaurant menu"}}}
            if query["targetId"] == "search":
                return {"url": state["search_url"], "text": "Search results for Puchong restaurants"}
            return {"url": source_url, "text": text or ("Puchong restaurant source text. " * 10)}

        runner.browser, runner.request, runner.save = browser, request, Mock()
        return runner

    def test_search_success_requires_navigation_and_matching_page_capture(self):
        runner = self.search_fixture()
        result = runner.search()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sources"], ["https://restaurant.example/menu"])
        self.assertIn("source text", result["results"][0]["excerpt"])
        self.assertIn("https://restaurant.example/menu", runner.report["pages_visited"])
        self.assertLessEqual(runner.calls, live.MAX_CALLS)

    def test_private_or_over_budget_search_sources_are_not_accepted(self):
        with self.assertRaises(core.ResearchError):
            self.search_fixture(source_url="http://192.168.1.1/").search()
        with self.assertRaisesRegex(core.ResearchError, "not verified"):
            self.search_fixture(text="x" * 4001).search()


class LifecycleTests(unittest.TestCase):
    def fixture(self, root):
        runner = worker()
        runner.directory = root / "research/raw/lookups/synthetic"
        runner.start_infrastructure = Mock()
        runner.fresh_browser = Mock(side_effect=lambda: setattr(runner, "browser_owned", True))
        runner.remove_container = Mock(return_value=True)
        runner.weather = Mock(side_effect=core.ResearchError("Transport failed"))
        return runner

    def test_shared_busy_lock_starts_no_infrastructure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "temp").mkdir()
            (root / "temp/research-runner.lock").write_text("Other owner")
            runner = self.fixture(root)
            with patch.object(live, "WORKSPACE", root), patch.object(core, "WORKSPACE", root):
                self.assertEqual(runner.run_lookup()["status"], "busy")
            runner.start_infrastructure.assert_not_called()
            self.assertEqual((root / "temp/research-runner.lock").read_text(), "Other owner")

    def test_failure_releases_lock_and_removes_only_owned_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.fixture(root)
            with patch.object(live, "WORKSPACE", root), patch.object(core, "WORKSPACE", root):
                result = runner.run_lookup()
            self.assertEqual(result["status"], "failed")
            runner.remove_container.assert_called_once_with("nahida-browser")
            self.assertFalse((root / "temp/research-runner.lock").exists())
            report = json.loads((runner.directory / "lookup.json").read_text(encoding="utf-8"))
            self.assertEqual(report["result"], result)
            self.assertEqual(report["cleanup_failed"], [])
            self.assertFalse((root / "research/db").exists())

    def test_cleanup_failure_cannot_return_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.fixture(root)
            runner.weather = Mock(return_value={"status": "ok", "kind": "weather", "sources": ["https://example.com"]})
            runner.remove_container.return_value = False
            with patch.object(live, "WORKSPACE", root), patch.object(core, "WORKSPACE", root):
                result = runner.run_lookup()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(runner.report["status"], "cleanup_failed")
            self.assertEqual(runner.report["cleanup_failed"], ["nahida-browser"])
            self.assertFalse((root / "temp/research-runner.lock").exists())


if __name__ == "__main__":
    unittest.main()
