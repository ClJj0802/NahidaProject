import json
import urllib.request
import urllib.error


LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"


def chat_completion(
    messages,
    temperature=0.1,
    max_tokens=256,
):
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

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