"""Offline evidence review and an independent SQLite research store. Python stdlib only."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from uuid import uuid4

from research_runner import KNOWLEDGE_HEADINGS, MAX_ARTIFACT, MAX_CHARS, normalize_markdown_fields, now, public_url

WORKSPACE = Path(__file__).resolve().parent.parent / "Nahida's file"
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[a-f0-9]{8}")
KINDS = {"quoted_claim", "user_report", "maintainer_statement", "documentation", "suggestion", "inference"}
CONFIDENCE = {"low", "medium", "high"}
CLAIM_SECTIONS = {"Summary", "Confirmed Findings", "Likely Findings", "User Reports",
                  "Recommended Experiments", "Hardware Relevance"}
MAX_CLAIMS = 32
GENERIC_TOPIC_WORDS = {"speed", "optimization", "performance", "inference", "benchmark", "guide", "research",
                       "configuration", "config", "how", "to", "and", "of", "the", "for", "on", "with",
                       "api", "cpu", "gpu", "model", "hardware", "version", "issue", "issues"}
FOLLOWUP = re.compile(r"^(?:那|这个|这些|它|这样|刚才|之前|还有|继续|how about\b|what about\b|and\b|so\b)", re.I)
TECHNICAL_FOLLOWUP = re.compile(r"快|慢|速度|延迟|性能|推理|优化|实测|证据|来源|配置|版本|显卡|可用|可靠|支持|"
                               r"cuda|graph|rtf|rtx|benchmark|latency|performance|speed|evidence|source", re.I)
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
 id TEXT PRIMARY KEY, topic TEXT NOT NULL, started_at TEXT, finished_at TEXT, status TEXT NOT NULL,
 report_path TEXT NOT NULL, report_sha256 TEXT NOT NULL, draft_path TEXT, draft_sha256 TEXT, indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_sources (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(id), source_key TEXT NOT NULL,
 url TEXT NOT NULL, title TEXT NOT NULL, evidence_path TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 text_sha256 TEXT NOT NULL, text TEXT NOT NULL, captured_at TEXT, truncated INTEGER NOT NULL,
 UNIQUE(run_id, source_key)
);
CREATE TABLE IF NOT EXISTS research_topics (
 topic TEXT PRIMARY KEY, last_researched_at TEXT, interest_score REAL NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS research_knowledge (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(id), claim_key TEXT NOT NULL,
 section TEXT NOT NULL, proposed_statement TEXT NOT NULL, statement TEXT NOT NULL,
 classification TEXT CHECK(classification IN ('quoted_claim','user_report','maintainer_statement','documentation','suggestion','inference')),
 confidence TEXT CHECK(confidence IN ('low','medium','high')),
 status TEXT NOT NULL CHECK(status IN ('draft','reviewed','rejected','archived')),
 reviewer TEXT, review_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(run_id, claim_key)
);
CREATE TABLE IF NOT EXISTS research_evidence (
 knowledge_id TEXT NOT NULL REFERENCES research_knowledge(id), source_id INTEGER NOT NULL REFERENCES research_sources(id),
 quote TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL, text_sha256 TEXT NOT NULL,
 PRIMARY KEY(knowledge_id, source_id, start)
);
CREATE TABLE IF NOT EXISTS research_reviews (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(id), packet_sha256 TEXT NOT NULL,
 reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, decisions_json TEXT NOT NULL,
 UNIQUE(run_id, packet_sha256, reviewer)
);
CREATE INDEX IF NOT EXISTS knowledge_status_topic ON research_knowledge(status, run_id);
CREATE INDEX IF NOT EXISTS source_url ON research_sources(url);
PRAGMA user_version = 1;
"""


class ReviewError(RuntimeError):
    pass


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def topic_score(text: str, topic: str) -> int:
    """Conservative lexical routing for named research topics, without another model call."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    topic_normalized = unicodedata.normalize("NFKC", topic).casefold()
    if topic_normalized in normalized:
        return 100 + len(topic_normalized)
    words = re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", normalized)
    phrases = {"".join(words[i:i + size]) for i in range(len(words)) for size in range(1, 5)}
    anchors = re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[-_.+][A-Za-z0-9]+)*", topic)
    meaningful = [a for a in anchors if a.casefold() not in GENERIC_TOPIC_WORDS
                  and (len(re.sub(r"[^A-Za-z0-9]", "", a)) >= 4 or a.isupper() and len(a) >= 3)]
    matches = {re.sub(r"[^a-z0-9]", "", a.casefold()) for a in meaningful} & phrases
    # Chinese titles can match a complete named phrase; generic fragments are not inferred.
    matches |= {a for a in re.findall(r"[\u3400-\u9fff]{4,}", topic_normalized) if a in normalized}
    return sum(len(a) for a in matches)


def candidates(draft: str) -> list[dict]:
    """Split draft prose into review units, without interpreting it as evidence."""
    normalized = normalize_markdown_fields(draft.replace("\r\n", "\n").replace("\r", "\n"), KNOWLEDGE_HEADINGS)
    pattern = r"^#{1,3} (" + "|".join(map(re.escape, KNOWLEDGE_HEADINGS)) + r")[ \t]*$"
    headings = list(re.finditer(pattern, normalized, re.M))
    result = []
    for index, heading in enumerate(headings):
        section = heading.group(1)
        if section not in CLAIM_SECTIONS:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(normalized)
        for line in normalized[heading.end():end].strip().splitlines():
            line = re.sub(r"^\s*[-*+] ", "", line).strip()
            for statement in re.split(r"(?<=[.!?。！？])\s+(?=[A-Z*\[])", line):
                if not statement:
                    continue
                if len(statement) > 1200 or len(result) >= MAX_CLAIMS:
                    raise ReviewError("Draft exceeds the bounded claim review budget")
                result.append({"id": f"C{len(result) + 1:02}", "section": section,
                               "proposed_statement": statement,
                               "source_keys": sorted(set(re.findall(r"\[(S[12])\]", statement)))})
    if not result:
        raise ReviewError("No reviewable draft statements found")
    return result


class ReviewStore:
    def __init__(self, workspace: Path = WORKSPACE):
        self.workspace = Path(workspace).resolve()
        self.db_path = self.path("research/db/research.db")

    def path(self, value) -> Path:
        path = (self.workspace / value).resolve()
        if not path.is_relative_to(self.workspace):
            raise ReviewError("Research path escapes the independent workspace")
        return path

    def relative(self, path: Path) -> str:
        return self.path(path).relative_to(self.workspace).as_posix()

    def read(self, path: Path) -> bytes:
        path = self.path(path)
        if path.stat().st_size > 262144:
            raise ReviewError("Review input exceeds its file budget")
        return path.read_bytes()

    def json_file(self, path: Path) -> dict:
        value = json.loads(self.read(path).decode("utf-8-sig"))
        if not isinstance(value, dict):
            raise ReviewError("Expected a JSON review object")
        return value

    def atomic(self, path: Path, text: str):
        path = self.path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path(path.with_name(path.name + "." + uuid4().hex + ".tmp"))
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def connect(self, *, readonly=False):
        # Re-resolve before opening: an existing DB symlink must not reach chat memory.
        database = self.path(self.db_path)
        if readonly:
            conn = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        else:
            database.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in ({1} if readonly else {0, 1}):
            conn.close()
            raise ReviewError("Unsupported research database schema")
        if not readonly:
            conn.executescript(SCHEMA)
        return conn

    def directory(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise ReviewError("Invalid research run ID")
        return self.path("research/raw/runs/" + run_id)

    def ingest(self, run_id: str) -> dict:
        directory = self.directory(run_id)
        report_path = directory / "run.json"
        report_bytes = self.read(report_path)
        report = json.loads(report_bytes.decode("utf-8-sig"))
        if report.get("id") != run_id or report.get("status") not in {"completed", "failed", "cleanup_failed"}:
            raise ReviewError("Only finished run reports can be indexed")
        topic = report.get("topic")
        if not isinstance(topic, str) or not 1 <= len(topic) <= 300:
            raise ReviewError("Invalid run topic")
        full = report["status"] == "completed" and report.get("stage") == "all"
        sources, proposals, draft_path, draft_sha = [], [], None, None
        if full:
            if report.get("cleanup_failed") or not any(s.get("stage") == "synthesis" for s in report.get("stages", [])):
                raise ReviewError("Completed research lacks a clean synthesis")
            draft_path = directory / "synthesis-artifact.md"
            if not draft_path.exists():
                draft_path = directory / "synthesis-draft.txt"  # Immutable legacy model output, never the latest prefix file.
            draft_bytes = self.read(draft_path)
            draft = draft_bytes.decode("utf-8-sig")
            if not 200 <= len(draft) <= MAX_ARTIFACT + 100:
                raise ReviewError("Invalid bounded synthesis snapshot")
            draft_sha, proposals = digest(draft_bytes), candidates(draft)
            for number in (1, 2):
                evidence_path = directory / f"source{number}-evidence.json"
                data = self.read(evidence_path)
                evidence = json.loads(data.decode("utf-8-sig"))
                text, url = evidence.get("text"), evidence.get("url")
                if not isinstance(text, str) or not 100 <= len(text) <= MAX_CHARS:
                    raise ReviewError("Invalid bounded source capture")
                try:
                    public_url(url)
                except (ValueError, TypeError, RuntimeError):
                    raise ReviewError("Source capture lacks a verified public URL") from None
                if url not in report.get("pages_visited", []):
                    raise ReviewError("Source capture URL was not visited in this run")
                sources.append({"source_key": f"S{number}", "url": url,
                    "title": evidence.get("source_title") or evidence.get("title") or url, "evidence_path": self.relative(evidence_path),
                    "file_sha256": digest(data), "text_sha256": digest(text), "text": text,
                    "captured_at": evidence.get("captured_at") or report.get("finished_at"),
                    "truncated": int(bool(evidence.get("truncated")))})
            if sources[0]["url"] == sources[1]["url"]:
                raise ReviewError("Two distinct source captures are required")
        timestamp = now()
        with closing(self.connect()) as conn, conn:
            previous = conn.execute("SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()
            if previous and (previous["topic"] != topic or previous["draft_sha256"] != draft_sha):
                raise ReviewError("Indexed run identity or synthesis changed; create a new run")
            for source in sources:
                previous_source = conn.execute("SELECT * FROM research_sources WHERE run_id=? AND source_key=?",
                                               (run_id, source["source_key"])).fetchone()
                if previous_source and any(previous_source[k] != source[k] for k in ("file_sha256", "url", "evidence_path")):
                    raise ReviewError("Indexed source capture changed; create a new run")
            conn.execute("""INSERT INTO research_runs VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET report_sha256=excluded.report_sha256, status=excluded.status,
                finished_at=excluded.finished_at""", (run_id, topic, report.get("started_at"), report.get("finished_at"),
                report["status"], self.relative(report_path), digest(report_bytes),
                self.relative(draft_path) if draft_path else None, draft_sha, timestamp))
            for source in sources:
                conn.execute("""INSERT INTO research_sources (run_id,source_key,url,title,evidence_path,file_sha256,
                    text_sha256,text,captured_at,truncated) VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(run_id,source_key) DO NOTHING""", (run_id, *[source[k] for k in
                    ("source_key", "url", "title", "evidence_path", "file_sha256", "text_sha256", "text", "captured_at", "truncated")]))
            for proposal in proposals:
                conn.execute("""INSERT INTO research_knowledge
                    (id,run_id,claim_key,section,proposed_statement,statement,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,'draft',?,?) ON CONFLICT(id) DO NOTHING""",
                    (run_id + ":" + proposal["id"], run_id, proposal["id"], proposal["section"],
                     proposal["proposed_statement"], proposal["proposed_statement"], timestamp, timestamp))
            conn.execute("""INSERT INTO research_topics(topic,last_researched_at) VALUES (?,?)
                ON CONFLICT(topic) DO UPDATE SET last_researched_at=MAX(research_topics.last_researched_at,excluded.last_researched_at)""",
                (topic, report.get("finished_at")))
        return {"run_id": run_id, "candidate_count": len(proposals), "database": self.relative(self.db_path)}

    def inputs(self, conn, run_id):
        run = conn.execute("SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()
        if not run or run["status"] != "completed" or not run["draft_path"]:
            raise ReviewError("Run has no completed full research draft")
        if digest(self.read(self.path(run["report_path"]))) != run["report_sha256"]:
            raise ReviewError("Run report changed after indexing; re-index it first")
        if digest(self.read(self.path(run["draft_path"]))) != run["draft_sha256"]:
            raise ReviewError("Original synthesis snapshot changed after indexing")
        sources = conn.execute("SELECT * FROM research_sources WHERE run_id=? ORDER BY source_key", (run_id,)).fetchall()
        if len(sources) != 2:
            raise ReviewError("Run lacks two indexed source captures")
        for source in sources:
            if (digest(self.read(self.path(source["evidence_path"]))) != source["file_sha256"]
                    or digest(source["text"]) != source["text_sha256"]):
                raise ReviewError("Source capture changed after indexing")
        return dict(run), [dict(s) for s in sources]

    def basis(self, conn, run_id):
        run, sources = self.inputs(conn, run_id)
        claims = [dict(c) for c in conn.execute(
            "SELECT * FROM research_knowledge WHERE run_id=? ORDER BY claim_key", (run_id,))]
        proposals = [{"id": c["claim_key"], "section": c["section"], "proposed_statement": c["proposed_statement"],
                      "source_keys": sorted(set(re.findall(r"\[(S[12])\]", c["proposed_statement"]))) } for c in claims]
        source_metadata = [{k: s[k] for k in ("source_key", "url", "title", "evidence_path", "text_sha256",
                                             "captured_at", "truncated", "text")} for s in sources]
        identity = {"run_id": run_id, "topic": run["topic"], "draft_sha256": run["draft_sha256"],
                    "sources": source_metadata, "proposals": proposals}
        return run, sources, claims, proposals, source_metadata, digest(canonical(identity))

    def prepare(self, run_id: str) -> Path:
        self.ingest(run_id)
        path = self.path(f"research/reviews/{run_id}/packet.json")
        with closing(self.connect(readonly=True)) as conn:
            run, _, _, proposals, sources, basis_sha = self.basis(conn, run_id)
            if path.exists():
                packet = self.json_file(path)
                if packet.get("basis_sha256") != basis_sha or packet.get("run_id") != run_id:
                    raise ReviewError("Existing review packet belongs to different inputs")
                return path  # Never overwrite someone's in-progress review or completed decisions.
            packet = {"schema_version": 1, "run_id": run_id, "topic": run["topic"],
                      "draft_sha256": run["draft_sha256"], "basis_sha256": basis_sha, "sources": sources,
                      "instructions": "Approve only after checking that each exact quote supports the revised statement. "
                                      "Classify quoted benchmarks and user reports honestly. Matching text does not prove truth. "
                                      "Keep original proposed_statement/section/source_keys/id and source metadata unchanged.",
                      "claims": [{**p, "decision": "pending", "statement": p["proposed_statement"],
                                  "classification": None, "confidence": None, "evidence": [], "note": ""} for p in proposals]}
        self.atomic(path, json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        return path

    def validate_packet(self, conn, packet):
        run_id = packet.get("run_id")
        self.directory(run_id)
        run, sources, stored, proposals, metadata, basis_sha = self.basis(conn, run_id)
        if (packet.get("schema_version") != 1 or packet.get("basis_sha256") != basis_sha
                or packet.get("draft_sha256") != run["draft_sha256"] or packet.get("topic") != run["topic"]
                or packet.get("sources") != metadata):
            raise ReviewError("Review packet does not match its original run and source snapshots")
        claims = packet.get("claims")
        if not isinstance(claims, list) or len(claims) != len(proposals):
            raise ReviewError("Review must account for every proposed claim")
        mapping = {s["source_key"]: s for s in sources}
        checked, seen = [], set()
        for claim in claims:
            if not isinstance(claim, dict) or not isinstance(claim.get("id"), str) or claim["id"] in seen:
                raise ReviewError("Invalid or duplicate review claim")
            seen.add(claim["id"])
            proposal = next((p for p in proposals if p["id"] == claim["id"]), None)
            if not proposal or any(claim.get(k) != proposal[k] for k in proposal):
                raise ReviewError("Original claim identity was edited; revise only statement and review fields")
            allowed = set(proposal) | {"decision", "statement", "classification", "confidence", "evidence", "note"}
            if set(claim) - allowed:
                raise ReviewError("Unknown review claim fields")
            decision, issues, anchors = claim.get("decision"), [], []
            if decision not in {"pending", "approve", "reject"}:
                issues.append("decision must be pending, approve or reject")
            if decision in {"approve", "reject"} and (not isinstance(claim.get("note"), str) or not 5 <= len(claim["note"]) <= 2000):
                issues.append("a substantive review note is required")
            if decision == "pending" and next(c for c in stored if c["claim_key"] == claim["id"])["status"] != "draft":
                issues.append("pending cannot undo an existing review; use an explicit decision")
            if decision == "approve":
                statement = claim.get("statement")
                if not isinstance(statement, str) or not 10 <= len(statement) <= 1200:
                    issues.append("revised statement must be 10..1200 characters")
                elif set(re.findall(r"https?://[^\s<>\]\)\"']+", statement)) - {s["url"] for s in sources}:
                    issues.append("statement contains an unverified source URL")
                if claim.get("classification") not in KINDS or claim.get("confidence") not in CONFIDENCE:
                    issues.append("evidence classification and confidence are required")
                evidence = claim.get("evidence")
                if not isinstance(evidence, list) or not 1 <= len(evidence) <= 3:
                    issues.append("approval requires 1..3 exact source excerpts")
                    evidence = []
                for item in evidence:
                    if not isinstance(item, dict) or set(item) != {"source", "quote"}:
                        issues.append("evidence must contain only source and quote")
                        continue
                    source, quote = mapping.get(item["source"]) if isinstance(item["source"], str) else None, item["quote"]
                    if not source or not isinstance(quote, str) or not 20 <= len(quote) <= 600:
                        issues.append("excerpt needs a known source and 20..600 characters")
                    elif source["text"].count(quote) != 1:
                        issues.append("excerpt must occur exactly once in the original capture")
                    else:
                        start = source["text"].index(quote)
                        anchor = {"source_id": source["id"], "quote": quote, "start": start,
                                  "end": start + len(quote), "text_sha256": source["text_sha256"]}
                        if anchor in anchors:
                            issues.append("duplicate evidence excerpt")
                        anchors.append(anchor)
                if isinstance(statement, str):
                    cited = set(re.findall(r"\[(S\d+)\]", statement))
                    anchored = {s["source_key"] for s in sources if any(a["source_id"] == s["id"] for a in anchors)}
                    if cited - anchored:
                        issues.append("every statement citation must have a matching evidence excerpt")
            checked.append({"id": claim["id"], "decision": decision, "issues": issues, "anchors": anchors, "claim": claim})
        return checked

    def check(self, packet_path: Path) -> dict:
        packet = self.json_file(packet_path)
        with closing(self.connect(readonly=True)) as conn:
            checked = self.validate_packet(conn, packet)
        return {"run_id": packet["run_id"], "ready_to_apply": not any(c["issues"] for c in checked)
                and any(c["decision"] != "pending" for c in checked),
                "claims": [{k: c[k] for k in ("id", "decision", "issues")} for c in checked]}

    def apply(self, packet_path: Path, reviewer: str) -> dict:
        if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80:
            raise ReviewError("A named reviewer is required")
        packet = self.json_file(packet_path)
        packet_sha, timestamp = digest(canonical(packet)), now()
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            checked = self.validate_packet(conn, packet)
            if any(c["issues"] for c in checked) or not any(c["decision"] != "pending" for c in checked):
                raise ReviewError("Review is incomplete or has invalid evidence; run check for details")
            existing = conn.execute("SELECT id FROM research_reviews WHERE run_id=? AND packet_sha256=? AND reviewer=?",
                                    (packet["run_id"], packet_sha, reviewer.strip())).fetchone()
            decisions = []
            if not existing:
                for result in checked:
                    if result["decision"] == "pending":
                        continue
                    claim = result["claim"]
                    knowledge_id = packet["run_id"] + ":" + claim["id"]
                    previous = conn.execute("SELECT status FROM research_knowledge WHERE id=?", (knowledge_id,)).fetchone()[0]
                    approved = result["decision"] == "approve"
                    status = "reviewed" if approved else "rejected"
                    conn.execute("""UPDATE research_knowledge SET statement=?,classification=?,confidence=?,status=?,
                        reviewer=?,review_note=?,updated_at=? WHERE id=?""", (claim["statement"] if approved else claim["proposed_statement"],
                        claim["classification"] if approved else None, claim["confidence"] if approved else None,
                        status, reviewer.strip(), claim["note"], timestamp, knowledge_id))
                    conn.execute("DELETE FROM research_evidence WHERE knowledge_id=?", (knowledge_id,))
                    for anchor in result["anchors"]:
                        conn.execute("INSERT INTO research_evidence VALUES (?,?,?,?,?,?)", (knowledge_id,
                            *[anchor[k] for k in ("source_id", "quote", "start", "end", "text_sha256")]))
                    decisions.append({"claim": claim["id"], "previous": previous, "status": status,
                                      "statement": claim.get("statement"), "note": claim["note"]})
                conn.execute("INSERT INTO research_reviews(run_id,packet_sha256,reviewer,reviewed_at,decisions_json) VALUES (?,?,?,?,?)",
                             (packet["run_id"], packet_sha, reviewer.strip(), timestamp, canonical(decisions)))
        # SQLite is authoritative. Markdown is a replaceable projection; replaying apply repairs a failed export.
        output = self.export(packet["run_id"])
        return {"run_id": packet["run_id"], "reviewed_artifact": self.relative(output),
                "changes": len(decisions), "idempotent": bool(existing)}

    def evidence(self, conn, knowledge_id):
        rows = conn.execute("""SELECT e.*,s.source_key,s.url,s.title,s.captured_at,s.truncated,s.evidence_path,s.text
            FROM research_evidence e JOIN research_sources s ON s.id=e.source_id
            WHERE e.knowledge_id=? ORDER BY s.source_key,e.start""", (knowledge_id,)).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            text = data.pop("text")
            if digest(text) != data["text_sha256"] or text[data["start"]:data["end"]] != data["quote"]:
                raise ReviewError("Stored evidence anchor is corrupt")
            results.append(data)
        if not results:
            raise ReviewError("Reviewed knowledge has no evidence anchors")
        return results

    def context(self, query: str, *, max_chars=4000, topic=None) -> str:
        """Bounded read-only chat data; full audit data stays in search/export."""
        if not isinstance(max_chars, int) or not 500 <= max_chars <= 4000:
            raise ReviewError("Knowledge context budget must be 500..4000 characters")
        rows = self.search(query, limit=20, topic=topic)
        payload = {"review_scope": "Source evidence checked; source claims were not independently reproduced.",
                   "knowledge": [], "truncated": len(rows) == 20}
        for row in rows:
            sources = {e["source_key"]: {k: e[k] for k in ("source_key", "url", "captured_at", "truncated")}
                       for e in row["evidence"]}
            finding = {"id": row["id"], "statement": row["statement"], "evidence_type": row["classification"],
                       "confidence": row["confidence"], "sources": list(sources.values())}
            candidate = {**payload, "knowledge": payload["knowledge"] + [finding], "truncated": True}
            if len(canonical(candidate)) > max_chars:
                payload["truncated"] = True
                continue
            payload["knowledge"].append(finding)
        return canonical(payload)

    def retrieve(self, text: str, active_topic: str | None = None, *, max_chars=4000) -> str:
        if (not isinstance(text, str) or not 1 <= len(text) <= 2000
                or active_topic is not None and (not isinstance(active_topic, str) or len(active_topic) > 300)
                or not isinstance(max_chars, int) or not 1000 <= max_chars <= 4000):
            raise ReviewError("Invalid bounded chat lookup request")
        empty = {"matched_topic": None, "knowledge": [], "truncated": False}
        if not self.path(self.db_path).exists():
            return canonical(empty)
        with closing(self.connect(readonly=True)) as conn:
            topics = [row[0] for row in conn.execute("""SELECT r.topic FROM research_runs r
                JOIN research_knowledge k ON k.run_id=r.id WHERE k.status='reviewed'
                GROUP BY r.topic ORDER BY MAX(k.updated_at) DESC,r.topic LIMIT 100""")]
        scored = [(topic_score(text, topic), topic) for topic in topics]
        scored = [entry for entry in scored if entry[0]]
        matched_by = "explicit_topic"
        if not scored and active_topic and len(text) <= 120 and FOLLOWUP.search(text.strip()) and TECHNICAL_FOLLOWUP.search(text):
            scored = [(topic_score(active_topic, topic), topic) for topic in topics]
            scored = [entry for entry in scored if entry[0]]
            matched_by = "technical_followup"
        if not scored:
            return canonical(empty)
        _, selected = max(scored, key=lambda item: item[0])
        payload = json.loads(self.context(selected, max_chars=max_chars, topic=selected))
        payload.update(matched_topic=selected, matched_by=matched_by)
        while len(canonical(payload)) > max_chars and payload["knowledge"]:
            payload["knowledge"].pop()
            payload["truncated"] = True
        return canonical(payload)

    def search(self, query: str = "", *, limit=10, run_id=None, topic=None) -> list[dict]:
        if (not isinstance(query, str) or len(query) > 300 or not 1 <= limit <= 20
                or topic is not None and (not isinstance(topic, str) or len(topic) > 300)):
            raise ReviewError("Query exceeds its bounded search budget")
        if not self.path(self.db_path).exists():
            return []
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with closing(self.connect(readonly=True)) as conn:
            rows = conn.execute("""SELECT k.*,r.topic FROM research_knowledge k JOIN research_runs r ON r.id=k.run_id
                WHERE k.status='reviewed' AND (k.statement LIKE ? ESCAPE '\\' OR r.topic LIKE ? ESCAPE '\\')
                AND (? IS NULL OR k.run_id=?) AND (? IS NULL OR r.topic=?) ORDER BY k.updated_at DESC,k.id LIMIT ?""",
                ("%" + escaped + "%", "%" + escaped + "%", run_id, run_id, topic, topic, limit)).fetchall()
            checked_runs, results = set(), []
            for row in rows:
                if row["run_id"] not in checked_runs:
                    self.inputs(conn, row["run_id"])
                    checked_runs.add(row["run_id"])
                data = dict(row)
                data.pop("proposed_statement")  # Consumers must never receive the unreviewed draft beside a corrected statement.
                data["evidence"] = self.evidence(conn, row["id"])
                results.append(data)
        return results

    def export(self, run_id: str) -> Path:
        # Export all claims rather than search's public 20-result budget.
        with closing(self.connect(readonly=True)) as conn:
            run, _ = self.inputs(conn, run_id)
            rows = conn.execute("SELECT * FROM research_knowledge WHERE run_id=? AND status='reviewed' ORDER BY claim_key",
                                (run_id,)).fetchall()
            lines = ["# " + run["topic"], "", "> Review status: REVIEWED as source evidence; performance was not independently reproduced.",
                     "", "Run: " + run_id, "Updated: " + now(), "", "## Reviewed findings", ""]
            for row in rows:
                lines += ["### " + row["claim_key"], row["statement"], "",
                          f"Evidence type: {row['classification']}; confidence: {row['confidence']}.",
                          "Reviewer: " + row["reviewer"], "Review note: " + row["review_note"], ""]
                for evidence in self.evidence(conn, row["id"]):
                    lines += [f"Source [{evidence['source_key']}]: {evidence['url']}",
                              f"Captured: {evidence['captured_at']}; truncated: {bool(evidence['truncated'])}.",
                              "Evidence: " + evidence["evidence_path"],
                              f"Span: {evidence['start']}..{evidence['end']} (Unicode character offsets); SHA256: {evidence['text_sha256']}",
                              "", *["> " + line for line in evidence["quote"].splitlines()], ""]
            if not rows:
                lines.append("No currently reviewed findings. Draft and rejected statements are excluded.")
        path = self.path(f"research/knowledge/reviewed/{run_id}.md")
        self.atomic(path, "\n".join(lines) + "\n")
        return path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "prepare", "export"):
        sub.add_parser(name).add_argument("--run", required=True)
    for name in ("check", "apply"):
        command = sub.add_parser(name)
        command.add_argument("--packet", type=Path, required=True, help="Absolute path or path relative to Nahida's file")
        if name == "apply":
            command.add_argument("--reviewer", required=True)
    for name in ("search", "context"):
        search = sub.add_parser(name)
        search.add_argument("query", nargs="?", default="")
        if name == "search":
            search.add_argument("--limit", type=int, default=10)
        else:
            search.add_argument("--max-chars", type=int, default=4000)
    retrieve = sub.add_parser("retrieve", help="Read a bounded {text, active_topic} JSON request from stdin")
    retrieve.add_argument("--max-chars", type=int, default=4000)
    args = parser.parse_args()
    store = ReviewStore()
    try:
        if args.command == "index":
            result = store.ingest(args.run)
        elif args.command in {"prepare", "export"}:
            output = getattr(store, args.command)(args.run)
            result = {"path": str(output)}
        elif args.command == "check":
            result = store.check(store.path(args.packet))
        elif args.command == "apply":
            result = store.apply(store.path(args.packet), args.reviewer)
        elif args.command == "context":
            print(store.context(args.query, max_chars=args.max_chars))
            return 0
        elif args.command == "retrieve":
            request = sys.stdin.buffer.read(16385)
            if len(request) > 16384:
                raise ReviewError("Chat lookup request exceeds its input budget")
            request = json.loads(request.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"text", "active_topic"}:
                raise ReviewError("Chat lookup requires text and active_topic only")
            print(store.retrieve(request["text"], request["active_topic"], max_chars=args.max_chars))
            return 0
        else:
            result = store.search(args.query, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == "check" and not result["ready_to_apply"] else 0
    except (ReviewError, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        print("Review stopped: " + (str(error) if isinstance(error, ReviewError) else type(error).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
