"""Manual local-model smoke test with synthetic chat and no personal-memory access."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "nahida_brain"))
from src import chat, database, llm_client
from src.research_knowledge import lookup_research

QUESTIONS = [
    "GPT-SoVITS 的 CUDA Graph 优化有实测证据吗？给出来源，并说明对 RTX 5060 Ti 能否确定有效。",
    "GPT-SoVITS 的 RTF 0.014 是 issue 作者自己复现的吗？这个数值能否当成我的显卡性能保证？请附来源。",
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    research_db = ROOT / "Nahida's file/research/db/research.db"
    before = hashlib.sha256(research_db.read_bytes()).hexdigest()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "synthetic_chat": True,
              "personal_database_access": "blocked by test guard", "tests": [], "failures": []}
    real_open = urllib.request.urlopen

    def guarded_connection():
        raise AssertionError("Smoke test attempted personal database access")

    with ExitStack() as patches:
        patches.enter_context(patch.object(database, "get_connection", side_effect=guarded_connection))
        for name in ("get_global_communication_preferences", "get_core_memories", "get_memories_by_ids"):
            patches.enter_context(patch.object(chat, name, return_value=[]))
        for question in QUESTIONS:
            context = lookup_research(question)
            if not context:
                raise RuntimeError("Expected reviewed knowledge was not available")
            observation = {"question": question, "findings": len(context["knowledge"]),
                           "context_chars": len(json.dumps(context, ensure_ascii=False, separators=(",", ":"))),
                           "api_paths": [], "inference_calls": 0}

            def observing_open(request, *args, **kwargs):
                path = urlparse(request.full_url).path
                observation["api_paths"].append(path)
                with real_open(request, *args, **kwargs) as response:
                    body = response.read()
                value = json.loads(body)
                if path == "/props":
                    observation["n_ctx"] = value["default_generation_settings"]["n_ctx"]
                    observation["slots"] = value.get("total_slots")
                elif path == "/tokenize":
                    observation["prompt_tokens"] = len(value["tokens"])
                elif path == "/v1/chat/completions":
                    observation["inference_calls"] += 1
                    sent = json.loads(request.data)
                    observation["max_tokens"] = sent["max_tokens"]
                    observation["source_message_added"] = any("RESEARCH_SOURCE_DATA" in m["content"] for m in sent["messages"] if m["role"] == "user")
                    observation["finish_reason"] = value["choices"][0].get("finish_reason")
                    observation["model_selection"] = value["choices"][0]["message"]["content"]
                    observation["usage"] = value.get("usage")
                return io.BytesIO(body)

            with patch.object(chat, "get_recent_messages", return_value=[{"role": "user", "content": question}]), \
                    patch.object(llm_client.urllib.request, "urlopen", side_effect=observing_open):
                observation["answer"] = chat.generate_nahida_response("synthetic-research-smoke", latest_message=question)
            report["tests"].append(observation)
            print(json.dumps(observation, ensure_ascii=False, indent=2), flush=True)
            if not observation.get("source_message_added") or observation["inference_calls"] != 1:
                report["failures"].append("Research data was not supplied in one chat inference")
            if observation.get("finish_reason") == "length":
                report["failures"].append("Synthetic research answer exhausted its output budget")
            if "https://github.com/RVC-Boss/GPT-SoVITS/issues/" not in observation["answer"]:
                report["failures"].append("Synthetic research answer omitted a supporting source URL")
    after = hashlib.sha256(research_db.read_bytes()).hexdigest()
    report["research_database_unchanged"] = before == after
    if before != after:
        raise AssertionError("Read-only chat lookup changed research database")
    output = ROOT / "nahida-agent-stack/logs/brain-research-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Smoke report: " + str(output))
    if report["failures"]:
        raise AssertionError("; ".join(report["failures"]))


if __name__ == "__main__":
    main()
