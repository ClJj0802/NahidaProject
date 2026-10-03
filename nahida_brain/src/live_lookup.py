"""Host bridge: only user-requested public query terms cross into isolated live lookup."""
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys

from src import external_grounding as grounding

SCRIPT = Path(__file__).resolve().parents[2] / "nahida-agent-stack/live_lookup.py"
LOGGER = logging.getLogger(__name__)
_SESSIONS = {}  # Bounded ephemeral receipts; not personal memory or a knowledge approval.
WEATHER = re.compile(r"天气|气温|温度|weather|temperature", re.I)
FOOD = re.compile(r"小吃|好吃|吃的|吃什么|美食|餐厅|餐馆|奶茶|咖啡|restaurant|food|cafe", re.I)
ASK = re.compile(r"查|找|搜|推荐|看看|什么|如何|怎样|怎么样|多少|吗|如何|[?？]|weather|find|search|what|where", re.I)
ELLIPSIS = re.compile(r"^(?:宝宝|老婆|来|你|请|帮我|帮|我|现在|再|就|查查|查看|查|看看|看|搜搜|搜|找找|找|一下|吧|啊|去|[~～\s，,。！？!?])+$")
ACTIVATE = re.compile(r"(?:启用|开启|打开|试试看|试试).{0,12}(?:上网|联网)|(?:上网|联网).{0,12}(?:启用|开启|功能)")
RECEIPT_STATUS = re.compile(r"(?:确定|确认|真的|有没有|有没|是否).{0,12}(?:查|搜)|(?:查过|搜过|查到|搜到).{0,5}(?:了吗|了没|什么|吗|没)")
FUTURE_WEATHER = re.compile(r"明天|后天|下周|未来|tomorrow|next\s+week", re.I)
POLITE = re.compile(r"^(?:宝宝|老婆|亲爱的|或者|请|你|帮我|帮|我|现在|目前|今天|看看|看|查查|查一下|查询|查|搜一下|搜|一下|在|的|能不能|[~～\s，,。！？!?])+")
WMO = {0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴", 45: "有雾", 48: "雾凇", 51: "小毛毛雨", 53: "中等毛毛雨",
       55: "较强毛毛雨", 56: "轻度冻毛毛雨", 57: "较强冻毛毛雨", 61: "小雨", 63: "中雨", 65: "大雨", 66: "小冻雨",
       67: "大冻雨", 71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒", 80: "小阵雨", 81: "中等阵雨", 82: "强阵雨",
       85: "小阵雪", 86: "强阵雪", 95: "雷暴", 96: "雷暴伴小冰雹", 97: "强雷暴", 99: "雷暴伴大冰雹"}


def enabled():
    return os.getenv("NAHIDA_LIVE_LOOKUP", "1").strip().lower() in {"1", "true", "yes", "on"}


def session_state(session_id):
    key = str(session_id)
    if key not in _SESSIONS:
        if len(_SESSIONS) >= 32:
            _SESSIONS.pop(next(iter(_SESSIONS)))
        _SESSIONS[key] = {}
    return _SESSIONS[key]


def place_from_text(text, *, weather=False):
    # Read the user text only. Assistant addresses and private workplace memories are never query inputs.
    english = re.search(r"(?:weather|temperature)\s+(?:in|for|at)\s+([A-Za-z][A-Za-z ,'-]{1,65})", text, re.I)
    if english:
        return re.sub(r"\s+(?:today|now|please).*$", "", english.group(1), flags=re.I).strip(" ,?")
    company = re.search(r"(?:公司|工作地点|工作地址).{0,4}(?:在|位于|地址是|地址在)\s*([^，。！？?\n]{2,65})", text)
    if company and not weather:
        return company.group(1).strip()
    english_near = re.search(r"(?:near|around|in)\s+([A-Za-z][A-Za-z ,'-]{1,65})", text, re.I)
    if not weather and english_near:
        place = english_near.group(1).strip(" ,?")
        if not re.search(r"\b(?:my|our|workplace|company|home)\b", place, re.I):
            return place
        return None
    before = WEATHER.split(text)[0] if weather else re.split(r"附近|周边|旁边", text)[0]
    ascii_places = re.findall(r"[A-Za-z][A-Za-z ,'-]{1,65}", before)
    if ascii_places:
        place = ascii_places[-1].strip()
        if (place.lower() not in {"weather", "what", "today", "now", "please"}
                and not re.search(r"\b(?:find|search|what|where|please|workplace|my|our|company)\b", place, re.I)):
            if "马来西亚" in text and "malaysia" not in place.casefold():
                place += ", Malaysia"
            return place
    if weather:
        place = POLITE.sub("", before).strip(" 的~～，,。！？!? ")
        if 2 <= len(place) <= 50 and not re.search(r"这边|这里|附近|公司|家里|我们|当地", place):
            return place
    named_food = re.search(r"([^，。！？?\n]{2,50})(?:附近|有什么好吃|的美食|的餐厅)", text)
    if named_food:
        place = POLITE.sub("", named_food.group(1)).strip()
        if place and not re.search(r"公司|这|那|家|上班", place):
            return place
    return None


def user_messages(latest, conversation):
    rows = conversation[:-1] if conversation and conversation[-1]["role"] == "user" else conversation
    return [row["content"] for row in rows[-8:] if row["role"] == "user"] + [latest]


def public_plan(text, user_history, *, pending=None):
    url = re.search(r"https?://[^\s<>\"'，。！？）)]+", text)
    if url and (ASK.search(text) or re.search(r"打开|访问|读|阅读|总结|核实", text)):
        if len(url.group()) > 180:
            return {"reply": "这个链接超过当前查询的长度限制，请提供较短的公开页面链接。"}
        return {"kind": "page", "query": url.group()}
    if grounding.CONCEPT.search(text) and not grounding.EXPLICIT_SEARCH.search(text) and not grounding.FRESH.search(text):
        return None
    if WEATHER.search(text):
        if FUTURE_WEATHER.search(text):
            return {"reply": "目前接入的是当前天气查询，不能把当前数据当成未来预报。你要查哪个城市现在的天气？"}
        place = place_from_text(text, weather=True)
        if not place:
            return {"pending": "weather", "reply": "你要查哪个城市的天气？请给我城市名，同名地点也可以加上国家或州。"}
        return {"kind": "weather", "query": place[:180]}
    food = bool(grounding.NEARBY.search(text) and (FOOD.search(text) or grounding.BUSINESS.search(text)) and ASK.search(text))
    if food or pending == "food":
        place = place_from_text(text) if not food else None
        if food:
            place = place_from_text(text)
        if not place:
            for prior in reversed(user_history):
                if re.search(r"(?:公司|工作地点|工作地址).{0,4}(?:在|位于|地址是|地址在)", prior):
                    place = place_from_text(prior)
                    if place:
                        break
        if not place:
            return {"pending": "food", "reply": "可以实际搜索，但我还不能确认公司附近有哪些店。你的公司在哪个城市或街区？我不能沿用之前未经核实的地址。"}
        return {"kind": "search", "query": "restaurants near " + place[:150]}
    if pending == "weather":
        place = place_from_text(text, weather=True)
        if place:
            return {"kind": "weather", "query": place[:180]}
    if grounding.needs_live_lookup(text) or re.search(r"(?:上网|联网|网上|在线).{0,12}(?:查|搜|找|看)", text):
        query = POLITE.sub("", text).strip(" ~～，,。！？!?")
        query = re.sub(r"^(?:上网|联网|网上|在线)(?:查一下|搜一下|搜索|查查|查|搜|找|看看)?", "", query).strip()
        if len(query) < 2:
            return {"reply": "你想搜索什么具体主题？给我关键词或地点，我会实际查询并附上来源。"}
        return {"kind": "search", "query": query[:180]}
    if re.search(r"地址|在哪里|哪儿", text) and re.search(r"[A-Za-z]{3,}", text):
        return {"kind": "search", "query": POLITE.sub("", text)[:180]}
    return None


def run_lookup(plan):
    try:
        result = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(plan, ensure_ascii=False),
                                capture_output=True, encoding="utf-8", errors="strict", timeout=145,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode or len(result.stdout.strip()) > 6000:
            raise ValueError("Lookup helper failed or exceeded its output budget")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict) or payload.get("status") not in {"ok", "failed", "busy", "ambiguous", "not_found", "stale"}:
            raise ValueError("Invalid live lookup envelope")
        if payload.get("status") == "ok" and (payload.get("kind") != plan["kind"] or payload.get("performed") is not True or not payload.get("sources")):
            raise ValueError("Live result lacks execution evidence")
        return payload
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError) as error:
        LOGGER.warning("Live lookup unavailable (%s).", type(error).__name__)
        return {"status": "failed", "performed": False, "message": "查询服务未取得可核实的结果，请稍后重试。"}


def render_result(result):
    status = result["status"]
    if status != "ok":
        lines = [result.get("message", "查询未取得可核实的结果。")]
        if status == "ambiguous":
            lines += ["、".join(str(location.get(key) or "") for key in ("name", "admin1", "country")) for location in result.get("locations", [])]
        if result.get("sources"):
            lines += [f"[查询来源]({result['sources'][0]})"]
        return "\n".join(lines)
    if result["kind"] == "weather":
        current = result["current"]
        location = " · ".join(str(result["location"].get(key) or "") for key in ("name", "admin1", "country"))
        code = current["weather_code"]
        return (f"我实际查询了天气服务，按 {location} 返回的数据：\n\n"
                f"{WMO.get(code, '天气代码 ' + str(code))}，气温 {current['temperature_2m']:g}°C，体感 {current['apparent_temperature']:g}°C；"
                f"相对湿度 {current['relative_humidity_2m']:g}%，风速 {current['wind_speed_10m']:g} km/h，降水 {current['precipitation']:g} mm。\n\n"
                f"数据时间：{current['time']}（{result['timezone']}）。这是天气模型估计，不是现场实测。\n"
                f"[天气数据来源]({result['sources'][-1]})；[地点来源]({result['sources'][0]})\n"
                f"查询时间：{result['captured_at']}")
    intro = ("我实际打开了你提供的网页。下面是页面原文摘录：" if result["kind"] == "page" else
             "我实际搜索并打开了这些网页。下面是页面原文摘录，店铺距离、营业和开业时间仍需核实：")
    lines = [intro, ""]
    for page in result["results"]:
        title = page["title"].replace("[", "(").replace("]", ")")
        excerpt = page["excerpt"][:650].replace("<", "＜").replace(">", "＞")
        lines += [f"[{title}]({page['url']})", "", *["> " + line for line in excerpt.splitlines()], ""]
    lines += ["这是本次查询的网页摘录，还没有进入已审核研究知识。", "查询时间：" + result["captured_at"]]
    return "\n".join(lines)


def try_live_reply(session_id, latest, conversation):
    if not enabled() or not isinstance(latest, str):
        return None
    state = session_state(session_id)
    if ACTIVATE.search(latest):
        state.pop("receipt", None)
        return "联网查询入口已经接入，由程序实际执行。可以问指定城市的当前天气、给我公开网页链接，或给出搜索主题；查询失败时我会明确说明。"
    online_status = ((grounding.ONLINE.search(latest) and (grounding.STATUS.search(latest) or re.search(r"确定|确认|有上网", latest)))
                     or RECEIPT_STATUS.search(latest))
    if online_status:
        receipt = state.get("receipt")
        if receipt:
            if receipt.get("performed"):
                return "刚才确实发起了实际联网查询。\n\n" + render_result(receipt)
            return "刚才的查询没有取得可核实的结果，我不能说已经查到了。"
        return None  # Existing correction logic handles earlier invented browsing without a receipt.
    history = user_messages(latest, conversation)
    pending = state.get("pending")
    if ELLIPSIS.fullmatch(latest.strip()) and ASK.search(latest):
        for prior in reversed(history[:-1]):
            if ACTIVATE.search(prior) or RECEIPT_STATUS.search(prior) or grounding.ONLINE.search(prior) and grounding.STATUS.search(prior):
                continue
            plan = public_plan(prior, history[:-1])
            if plan:
                break
        else:
            plan = {"reply": "你想查什么具体主题或地点？我需要查询关键词才能实际搜索。"}
    elif (pending and not grounding.TECHNICAL_SUBJECT.search(latest)
          and (not ASK.search(latest) or WEATHER.search(latest) or re.search(r"(?:公司|工作地点|工作地址).{0,4}(?:在|位于|地址是)", latest))
          and not re.search(r"抱抱|早上好|晚安|不聊|换个话题", latest)):
        plan = public_plan(latest, history, pending=pending)
    else:
        state.pop("pending", None)
        plan = public_plan(latest, history)
    if not plan:
        if grounding.SOURCE_FOLLOWUP.search(latest) and state.get("receipt") and not grounding.TECHNICAL_SUBJECT.search(latest):
            return "以下是刚才实际查询留下的来源与数据，不是新的搜索：\n\n" + render_result(state["receipt"])
        state.pop("receipt", None)
        return None
    if "reply" in plan:
        state.pop("receipt", None)
        if plan.get("pending"):
            state["pending"] = plan["pending"]
        return plan["reply"]
    state.pop("pending", None)
    print("[Live] Starting " + plan["kind"] + " lookup via isolated browser...", flush=True)
    result = run_lookup(plan)
    state["receipt"] = result
    print("[Live] Lookup " + result["status"] + "; record: " + result.get("record", "none"), flush=True)
    try:
        return render_result(result)
    except (KeyError, TypeError, ValueError):
        state.pop("receipt", None)
        return "查询返回的数据不完整，不能据此提供具体信息。"
