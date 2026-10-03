import json
import urllib.request
import urllib.error


LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
RESEARCH_CONTEXT_LIMIT = 16384


def research_prompt_fits(messages, max_tokens):
    """Check the live local template/tokenizer before adding optional research data."""
    base = LLM_URL.removesuffix("/v1/chat/completions")

    def request(path, body=None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.load(response)

    try:
        props = request("/props")
        capacity = props["default_generation_settings"]["n_ctx"]
        if not isinstance(capacity, int) or capacity <= 0:
            return False
        prompt = request("/apply-template", {"messages": messages, "add_generation_prompt": True})["prompt"]
        if not isinstance(prompt, str):
            return False
        tokens = request("/tokenize", {"content": prompt})["tokens"]
        return isinstance(tokens, list) and len(tokens) + max_tokens + 256 <= min(capacity, RESEARCH_CONTEXT_LIMIT)
    except (OSError, ValueError, KeyError, TypeError):
        return False  # Normal chat remains available when optional budget verification fails.


def chat_completion(
    messages,
    temperature=0.1,
    max_tokens=256,
    response_format=None,
):
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        LLM_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:
            body = response.read().decode("utf-8")

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot connect to llama.cpp server: {exc}"
        ) from exc

    result = json.loads(body)

    return result["choices"][0]["message"]["content"]
