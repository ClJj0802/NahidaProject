"""Bounded host-owned live lookup through the existing disposable Chromium/Squid stack."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from research_runner import Runner, ResearchError, WORKSPACE, confined, now, public_url

LOOKUP_SECONDS = 110
MAX_CALLS = 18
MAX_TEXT = 4000
MAX_OUTPUT = 6000
BLOCKED = re.compile(r"请求存在异常|限制本次访问|verify.{0,30}human|access.{0,25}denied|captcha|complete.{0,30}challenge|"
                     r"just a moment|checking your browser|unusual traffic|enable javascript.{0,30}cookies|verifying.{0,30}bot|drag the slider|"
                     r"403\s*-?\s*Forbidden|network.{0,35}automated queries", re.I)


class LiveLookup(Runner):
    def __init__(self, request):
        if (not isinstance(request, dict) or set(request) != {"kind", "query"}
                or not isinstance(request["kind"], str) or request["kind"] not in {"weather", "search", "page"}
                or not isinstance(request["query"], str) or not 2 <= len(request["query"]) <= 180
                or any(ord(char) < 32 for char in request["query"])):
            raise ResearchError("Invalid bounded live lookup request")
        if request["kind"] == "page":
            public_url(request["query"])
        super().__init__(SimpleNamespace(topic=request["query"], prefix="live", stage="live", discovery_url="https://www.bing.com/search"))
        self.lookup_request = request
        self.directory = confined(WORKSPACE / "research/raw/lookups" / self.run_id)
        self.report.update(kind=request["kind"], query=request["query"], status="running",
                           limits={"browser_calls": MAX_CALLS, "page_chars": MAX_TEXT, "sources": 2,
                                   "run_seconds": LOOKUP_SECONDS, "llm_tool_calls": 0, "model_turns": 0})

    def command(self, args, *, input=None, timeout=25):
        remaining = LOOKUP_SECONDS - (time.monotonic() - self.started)
        if remaining <= 0:
            raise ResearchError("Live lookup deadline exceeded")
        return super().command(args, input=input, timeout=min(timeout, remaining))

    def browser(self, *args):
        if self.calls >= MAX_CALLS:
            raise ResearchError("Live browser budget exhausted")
        return super().browser(*args)

    def request(self, path, query):
        if self.calls >= MAX_CALLS:
            raise ResearchError("Live browser budget exhausted")
        return super().request(path, query)

    def start_llm(self):
        # Live lookup makes no model turns. Do not enter the core's 180-second model startup loop.
        try:
            with urlopen("http://127.0.0.1:8080/v1/models", timeout=3) as response:
                models = json.load(response)["data"]
            configured = self.config["models"]["providers"]["llamacpp"]["models"][0]["id"]
            if not any(model["id"] == configured for model in models):
                raise ResearchError("The existing fixed local model is unavailable")
        except OSError:
            raise ResearchError("The existing local stack is not ready") from None

    def capture(self, url, *, selector="body"):
        url = public_url(url)
        tab = self.browser("open", url)
        target = tab["suggestedTargetId"]
        evidence = self.request("/text", {"targetId": target, "selector": selector, "maxChars": str(MAX_TEXT)})
        if evidence.get("url") != url or not 1 <= len(evidence.get("text", "")) <= MAX_TEXT:
            raise ResearchError("Live page URL/content did not match the requested source")
        evidence.update(captured_at=now(), source_title=tab.get("title", ""))
        self.report["pages_visited"].append(url)
        self.save(self.directory / f"capture-{len(self.report['pages_visited'])}.json", json.dumps(evidence, ensure_ascii=False, indent=2), archive=False)
        return evidence

    def weather(self):
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode(
            {"name": self.lookup_request["query"], "count": 5, "language": "en", "format": "json"})
        geo = json.loads(self.capture(geo_url)["text"])
        locations = geo.get("results", [])
        if not locations:
            return {"status": "not_found", "message": "天气服务未找到这个地点，请补充城市和国家。", "sources": [geo_url]}
        exact = [location for location in locations if location.get("name", "").casefold() == self.lookup_request["query"].split(",")[0].strip().casefold()]
        candidates = exact or locations
        if len(candidates) > 1:
            ranked = sorted(candidates, key=lambda item: item.get("population", 0) or 0, reverse=True)
            if (ranked[0].get("population", 0) or 0) >= 100000 and ranked[0]["population"] >= 10 * max(1, ranked[1].get("population", 0) or 0):
                candidates = ranked[:1]
        if len(candidates) != 1:
            choices = [{key: location.get(key) for key in ("name", "admin1", "country")} for location in candidates[:5]]
            return {"status": "ambiguous", "message": "找到多个地点，请补充国家或州。", "locations": choices, "sources": [geo_url]}
        location = candidates[0]
        lat, lon = location["latitude"], location["longitude"]
        if (not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or isinstance(lat, bool) or isinstance(lon, bool) or not math.isfinite(lat + lon)
                or not -90 <= lat <= 90 or not -180 <= lon <= 180):
            raise ResearchError("Invalid geocoding coordinates")
        weather_url = "https://api.open-meteo.com/v1/forecast?" + urlencode({
            "latitude": lat, "longitude": lon, "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,precipitation,wind_speed_10m",
            "timezone": "auto", "forecast_days": 1})
        data = json.loads(self.capture(weather_url)["text"])
        current, units = data["current"], data["current_units"]
        expected = {"temperature_2m": "°C", "apparent_temperature": "°C", "relative_humidity_2m": "%",
                    "precipitation": "mm", "wind_speed_10m": "km/h", "weather_code": "wmo code"}
        for key, unit in expected.items():
            value = current.get(key)
            if units.get(key) != unit or not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ResearchError("Weather values/units are invalid")
        if not (0 <= current["relative_humidity_2m"] <= 100 and current["precipitation"] >= 0 and current["wind_speed_10m"] >= 0):
            raise ResearchError("Weather values are outside their physical ranges")
        timestamp = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc).timestamp() - data["utc_offset_seconds"]
        if abs(datetime.now(timezone.utc).timestamp() - timestamp) > 3 * 3600:
            return {"status": "stale", "message": "已取得天气数据，但数据时间与现在相差超过三小时，不能作为当前天气。",
                    "data_time": current["time"], "sources": [geo_url, weather_url]}
        return {"status": "ok", "kind": "weather", "location": {key: location.get(key) for key in ("name", "admin1", "country")},
                "current": current, "units": units, "timezone": data["timezone"], "captured_at": now(),
                "evidence_type": "weather_model_estimate", "sources": [geo_url, weather_url]}

    def page(self):
        url = public_url(self.lookup_request["query"])
        capture = self.capture(url)
        if len(capture["text"]) < 80 or BLOCKED.search(capture["text"]):
            raise ResearchError("Requested page is empty or blocked")
        return {"status": "ok", "kind": "page", "captured_at": capture["captured_at"], "sources": [url],
                "results": [{"title": capture["source_title"][:250] or url, "url": url, "excerpt": capture["text"][:1000],
                             "captured_at": capture["captured_at"], "truncated": True}]}

    def search(self):
        stops = {"restaurant", "restaurants", "near", "food", "malaysia", "the", "what", "where", "best", "search", "please"}
        anchors = [word for word in re.findall(r"[A-Za-z0-9_-]{3,}|[\u3400-\u9fff]{2,}", self.lookup_request["query"].casefold()) if word not in stops]
        engines = [("https://www.mojeek.com/search?" + urlencode({"q": self.lookup_request["query"]}), "body"),
                   ("https://www.bing.com/search?" + urlencode({"q": self.lookup_request["query"], "setlang": "en", "mkt": "en-MY", "cc": "MY"}), "#b_results")]
        candidates = []
        for index, (url, selector) in enumerate(engines, 1):
            tab = self.browser("open", url)
            target = tab["suggestedTargetId"]
            self.report["pages_visited"].append(url)
            self.browser("focus", target)
            search_text = self.request("/text", {"targetId": target, "selector": "body", "maxChars": str(MAX_TEXT)})
            self.save(self.directory / f"search-{index}-text.json", json.dumps(search_text, ensure_ascii=False, indent=2), archive=False)
            observed = urlsplit(search_text.get("url", ""))
            if (observed.hostname != urlsplit(url).hostname or parse_qs(observed.query).get("q") != [self.lookup_request["query"]]
                    or not 1 <= len(search_text.get("text", "")) <= MAX_TEXT
                    or BLOCKED.search(search_text.get("text", ""))):
                continue
            snap = self.request("/snapshot", {"targetId": target, "selector": selector, "compact": "true",
                                             "mode": "efficient", "interactive": "true", "maxChars": str(MAX_TEXT)})
            self.save(self.directory / f"search-{index}-snapshot.json", json.dumps(snap, ensure_ascii=False, indent=2), archive=False)
            candidates = [(ref, record["name"]) for ref, record in snap.get("refs", {}).items()
                          if record.get("role") == "link" and 12 <= len(record.get("name", "")) <= 250
                          and any(word in record["name"].casefold() for word in anchors)][:4]
            if candidates:
                break
        if not candidates:
            raise ResearchError("Search page has no usable results or is blocked")
        results = []
        for position, (ref, title) in enumerate(candidates):
            if len(results) == 2 or self.calls > MAX_CALLS - (6 if position else 4):
                break
            if position:
                self.browser("focus", target)
                refreshed = self.request("/snapshot", {"targetId": target, "selector": selector, "compact": "true",
                                                      "mode": "efficient", "interactive": "true", "maxChars": str(MAX_TEXT)})
                matches = [key for key, item in refreshed.get("refs", {}).items() if item.get("name") == title and item.get("role") == "link"]
                if len(matches) != 1:
                    continue
                ref = matches[0]
            before = {item["suggestedTargetId"] for item in self.browser("tabs")["tabs"]}
            self.browser("click", ref, "--target-id", target)
            tabs = self.browser("tabs")["tabs"]
            opened = [item for item in tabs if item["suggestedTargetId"] not in before]
            source = opened[-1] if opened else next(item for item in tabs if item["suggestedTargetId"] == target)
            source_url = public_url(source["url"])
            if urlsplit(source_url).hostname in {"www.bing.com", "bing.com", "www.mojeek.com", "mojeek.com"}:
                raise ResearchError("Search result did not navigate to an external source")
            capture = self.request("/text", {"targetId": source["suggestedTargetId"], "selector": "body", "maxChars": str(MAX_TEXT)})
            if capture.get("url") != source_url or not 80 <= len(capture.get("text", "")) <= MAX_TEXT:
                raise ResearchError("Search source capture is not verified")
            if BLOCKED.search(capture["text"]):
                self.report.setdefault("blocked_sources", []).append(source_url)
                if not opened:
                    break
                continue
            capture.update(captured_at=now(), source_title=source.get("title", title))
            self.report["pages_visited"].append(source_url)
            self.save(self.directory / f"source-{len(results)+1}.json", json.dumps(capture, ensure_ascii=False, indent=2), archive=False)
            results.append({"title": source.get("title", title)[:250], "url": source_url,
                            "excerpt": capture["text"][:1000], "captured_at": capture["captured_at"], "truncated": True})
            if not opened:
                break  # Do not reuse refs after replacing the search document.
        if not results:
            raise ResearchError("No verified source is accessible within the browser budget")
        return {"status": "ok", "kind": "search", "results": results, "captured_at": now(), "sources": [r["url"] for r in results]}

    def run_lookup(self):
        lock = confined(WORKSPACE / "temp/research-runner.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return {"status": "busy", "message": "另一个研究或查询正在使用浏览器，请稍后重试。"}
        with os.fdopen(fd, "w") as output:
            json.dump({"pid": os.getpid(), "run_id": self.run_id, "kind": "live_lookup"}, output)
        result = {"status": "failed", "message": "联网查询未完成，不能提供未经核实的结果。"}
        try:
            self.directory.mkdir(parents=True)
            self.start_infrastructure()
            self.fresh_browser()
            handler = {"weather": self.weather, "page": self.page, "search": self.search}[self.lookup_request["kind"]]
            result = handler()
            self.report["status"] = result["status"]
        except (ResearchError, OSError, ValueError, KeyError, TypeError) as error:
            self.report.update(status="failed", error=str(error) if isinstance(error, ResearchError) else type(error).__name__)
            result["message"] = "已尝试联网，但页面受限、没有相关结果或服务不可用，未取得可核实的内容。"
        finally:
            cleanup = []
            if self.browser_owned and not self.remove_container("nahida-browser"):
                cleanup.append("nahida-browser")
                result = {"status": "failed", "message": "查询后的浏览器清理失败，结果暂不可用。"}
                self.report["status"] = "cleanup_failed"
            self.report.update(finished_at=now(), browser_calls=self.calls, cleanup_failed=cleanup)
            result.update(lookup_id=self.run_id, performed=bool(self.report["pages_visited"]),
                          record=f"research/raw/lookups/{self.run_id}/lookup.json")
            if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) > MAX_OUTPUT:
                result = {"status": "failed", "message": "查询结果超过容量限制。", "lookup_id": self.run_id, "performed": result["performed"], "record": result["record"]}
                self.report["status"] = "failed"
            self.report["result"] = result
            try:
                self.save(self.directory / "lookup.json", json.dumps(self.report, ensure_ascii=False, indent=2), archive=False)
            finally:
                lock.unlink()
        return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ResearchError("Lookup input exceeds its budget")
        request = json.loads(raw.decode("utf-8"))
        # Core readiness may print status; stdout is exclusively the bounded result envelope.
        from contextlib import redirect_stdout
        with redirect_stdout(sys.stderr):
            result = LiveLookup(request).run_lookup()
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (ResearchError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "failed", "message": "查询服务不可用，未取得可核实的结果。"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
