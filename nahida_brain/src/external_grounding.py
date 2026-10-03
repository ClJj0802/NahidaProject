"""Truthful fallback for chat turns without host-provided live evidence."""
import re


CAPABILITY_RULES = """
HOST-VERIFIED EXTERNAL LOOKUP STATUS FOR THIS TURN
live_web_search_performed: false
live_map_lookup_performed: false
live_review_site_lookup_performed: false
Any live lookup is performed by the host before generation and returned separately.
For this normal generation, no live result was supplied. Do not claim an action
was performed just because a live lookup feature is available elsewhere.
An optional reviewed research block is an offline snapshot, not a new search.
Do not claim to have searched, opened maps, read current reviews or checked a website.
Do not roleplay scrolling a device as though that supplied real external evidence.
Current shops, opening dates, nearby recommendations, business hours, prices and
news require actual supporting evidence; a personal workplace memory supplies
location context, not proof of nearby businesses or their current status.
Earlier assistant replies are not search results. If they claimed a lookup without
host evidence, correct that claim instead of inventing names, dates or sources.
The user's follow-up question does not confirm an earlier assistant assertion.
You may use user-provided facts, personal memories and reviewed snapshots within
their stated scope, or discuss general concepts without pretending to browse.
""".strip()

ONLINE = re.compile(r"上网|联网|网上|在线|地图|点评|浏览器|搜索引擎|\b(?:google|baidu|browse|browsing|web|internet|maps?)\b", re.I)
WEB_REQUEST = re.compile(r"(?:上网|联网|网上|在线).{0,12}(?:查|搜|找|看)|"
                         r"(?:查|搜|搜索|查找|查看|打开).{0,8}(?:地图|点评|网页|网站|浏览器)|"
                         r"(?:search|browse|check|look\s+up).{0,15}(?:web|internet|google|maps|reviews)", re.I)
STATUS = re.compile(r"有没有|有没|是否|真的|真有|到底|确实|查过.{0,8}[吗么]|搜过.{0,8}[吗么]|"
                    r"(?:上网|联网).{0,5}(?:了吗|了没|[吗没])|(?:did|have)\s+you|did\s+that", re.I)
REQUEST = re.compile(r"帮|找|查|搜|推荐|看看|有没有|哪里|哪家|哪间|什么|多少|几[点时]|吗|[?？]|"
                     r"search|find|look\s+up|recommend|what|where|how", re.I)
NEARBY = re.compile(r"附近|周边|旁边|楼下|公司附件|nearby|near\s+(?:my|the|our)|around\s+(?:my|the|our)", re.I)
BUSINESS = re.compile(r"小吃|餐厅|餐馆|饭店|奶茶|咖啡|店|营业|开业|商场|restaurant|cafe|food|shops?|business", re.I)
FRESH = re.compile(r"新开|刚开|最新|今天|现在|目前|最近|实时|当下|latest|current|newly|today|right\s+now", re.I)
PUBLIC_FACT = re.compile(r"新店|店铺|天气|气温|价格|优惠|新闻|汇率|股价|航班|班次|营业|开业|开放|公告|"
                         r"weather|prices?|news|exchange\s+rate|flight|opening|hours", re.I)
SOURCE_FOLLOWUP = re.compile(r"名字|叫什么|店名|从哪|哪儿|怎么知道|哪来的|可靠|靠谱|准确|可信|确认|确定|真的吗|"
                            r"继续|详细|多说|介绍一下|哪里.{0,5}(?:找|查|看)|来源|出处|地址|哪家|哪间|"
                            r"source|where.{0,12}(?:find|found|read)|(?:shop|its|the)\s+name", re.I)
CONCEPT = re.compile(r"原理|算法|教程|机制|是什么|什么意思|怎么实现|如何实现|how.{0,30}work|what.{0,20}(?:does|means)", re.I)
EXPLICIT_SEARCH = re.compile(r"(?:帮我|请|去|能不能).{0,6}(?:上网|联网|网上|在线).{0,8}(?:查|搜)|"
                             r"(?:上网|联网|网上|在线).{0,5}(?:查一下|搜一下)|please.{0,10}(?:search|browse)", re.I)
TECHNICAL_SUBJECT = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]+(?:[-_.][A-Za-z0-9]+)+|"
                               r"[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*)(?![A-Za-z0-9])|\d+\.\d+")
LIVE_CLAIM = re.compile(
    r"(?:刚才|刚刚|已经|特意).{0,16}(?:帮你|帮宝宝).{0,5}(?:查|搜|找).{0,6}(?:店|餐厅|天气|消息|信息)|"
    r"(?:拿出|掏出|拿起).{0,8}手机.{0,8}(?:搜|查|打开)|"
    r"(?:点|按|点击).{0,10}(?:上网|联网).{0,10}按钮|"
    r"(?:上网|联网|在线).{0,6}(?:查|搜|找|看)|"
    r"(?:查了|查过|查看了|看了|搜了|搜过|找到).{0,6}(?:地图|点评|网页|网站|网上)|"
    r"(?:我|刚才|刚刚|已经|特意).{0,10}(?:用|通过|打开|查看).{0,8}(?:地图|浏览器|google|百度|点评)|"
    r"(?:地图|点评|网页|网站|搜索结果).{0,8}(?:显示|写着|写了|看到|查到)|"
    r"\b(?:I|I've|I have|just)\b.{0,25}(?:searched|browsed|looked (?:it )?up|checked (?:the )?maps?|checked Google)", re.I)
NEW_BUSINESS_CLAIM = re.compile(r"昨天.{0,5}(?:开业|开张)|刚(?:刚)?开(?:业|张)|新开(?:的)?(?:小吃店|奶茶店|餐厅|店)")
NEGATION = re.compile(r"没有|还没|没(?:有)?查|没(?:有)?搜|未|不能|无法|尚未|不准确|说错|不应|不代表|不确定|不等于|不是|并非|不知道|不清楚|"
                      r"你可以|建议你|需要.{0,5}(?:查|核实)|如果|假如|\b(?:not|never|haven't|didn't|can't|cannot)\b", re.I)


def claims_unsupported_lookup(reply):
    """A narrow output guard complements explicit routing and the trusted capability prompt."""
    for clause in re.split(r"[，,。！？!?；;\n]", reply):
        for pattern in (LIVE_CLAIM, NEW_BUSINESS_CLAIM):
            for match in pattern.finditer(clause):
                if not NEGATION.search(clause[:match.end()]):
                    return True
    return False


def needs_live_lookup(text):
    if not isinstance(text, str) or not REQUEST.search(text):
        return False
    if CONCEPT.search(text) and not EXPLICIT_SEARCH.search(text):
        return False
    return bool(WEB_REQUEST.search(text) or NEARBY.search(text) and BUSINESS.search(text)
                or FRESH.search(text) and PUBLIC_FACT.search(text))


def reply_without_live_lookup(latest_message, conversation):
    """Return a truthful host reply for unsupported requests, or None for ordinary chat."""
    if not isinstance(latest_message, str):
        return None
    prior = conversation[:-1] if conversation and conversation[-1]["role"] == "user" else conversation
    prior = prior[-8:]
    last_assistant = next((m["content"] for m in reversed(prior) if m["role"] == "assistant"), "")
    false_claim = claims_unsupported_lookup(last_assistant)
    live_request_before = False
    for message in reversed(prior):
        if message["role"] != "user":
            continue
        text = message["content"]
        if needs_live_lookup(text):
            live_request_before = True
            break
        if SOURCE_FOLLOWUP.search(text) or ONLINE.search(text) and STATUS.search(text):
            continue
        break
    if ONLINE.search(latest_message) and STATUS.search(latest_message):
        if false_claim:
            return "没有，这次我没有联网查询，也没有查看地图或点评。刚才把未核实的信息说成查询结果，是我说错了；那些店名、地点或开业时间不能当作事实。"
        return "这次我没有实时联网查询，也没有打开地图或点评。我可以读取之前已审核的本地研究资料，但那不等于刚刚上网搜索。"
    if (SOURCE_FOLLOWUP.search(latest_message) and not TECHNICAL_SUBJECT.search(latest_message)
            and (false_claim or live_request_before)):
        if false_claim:
            return "刚才的店名、地点或开业时间没有可靠查询来源，不能当作事实。这次我没有联网查找，也没有使用地图或点评，需要先核实再告诉你。"
        return "这次还没有进行实时查询，所以我没有查到可核实的店名、地址或开业时间，也没有新的网页来源。"
    if needs_live_lookup(latest_message):
        if false_claim:
            return "这次我没有联网查询。刚才把未核实的信息说成查询结果是不准确的；具体的新店、地址或开业时间需要可靠来源才能确认。"
        if NEARBY.search(latest_message) and BUSINESS.search(latest_message):
            return "这次我没有联网查找，也没有查看地图或点评，暂时不能确认附近有哪些新店。店名、地址和开业时间需要可靠来源核实后才能告诉你。"
        return "这次我没有进行实时联网查询，暂时无法核实这条最新信息。已有知识或之前保存的资料不能代替当前的查询结果。"
    return None


def guard_chat_reply(reply):
    if claims_unsupported_lookup(reply):
        return "这次我没有联网查询，也没有查看地图或点评，不能把未经核实的信息说成查询结果。需要可靠来源才能确认这些信息。"
    return reply
