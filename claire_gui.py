
from fastapi import FastAPI, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import requests
import subprocess
import os
import html
import re
import json
import sqlite3
import shutil
import time
import tempfile
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from archimedes_demo import (
    archimedes_artifacts,
    archimedes_fields,
    archimedes_live_proof,
    archimedes_policy_rules,
    archimedes_policy_summary,
    is_archimedes_alias,
)

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    from claire_scholar import is_scholar_query, scholar_reply
except Exception as e:
    print("scholar lane import error:", e)

    def is_scholar_query(prompt: str) -> bool:
        return False

    def scholar_reply(query: str, limit: int = 5) -> str:
        return ""

try:
    from intent_classifier import classify_query
    from lane_router import extract_candidates
    from relevance_gate import compact_candidate, gate_retrieval_candidates
    from answer_planner import conceptual_answer, final_answer_mode, should_use_reasoning_first
except Exception as e:
    print("memory routing import error:", e)

    def classify_query(prompt: str):
        return {
            "primary_intent": "mixed",
            "secondary_intents": [],
            "confidence": 0.0,
            "reasoning_mode": "balanced",
            "allowed_lanes": [],
            "suppressed_lanes": [],
            "retrieval_strategy": "support_only",
            "detected_intent": "FACTUAL_RECALL",
            "source_output_allowed": False,
        }

    def extract_candidates(data, limit: int = 12):
        return []

    def compact_candidate(candidate: dict, max_chars: int = 220):
        return candidate

    def gate_retrieval_candidates(query: str, intent: dict, candidates: list, threshold: float = 0.42):
        return candidates, []

    def conceptual_answer(prompt: str, intent: dict, accepted_support=None):
        return ""

    def final_answer_mode(intent: dict, accepted_support: list):
        return "reasoning-led"

    def should_use_reasoning_first(intent: dict):
        return False


def load_keys_env():
    env_path = "/home/LuciusPrime/claire/claire_keys.env"
    try:
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except Exception as e:
        print("key env load error:", e)


load_keys_env()


def recall_memory(query):
    try:
        r = requests.post(
            "http://127.0.0.1:8002/query", json={"query": query, "top_k": 5}, timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            return "\n".join([r.get("text", "") for r in results])
    except Exception as e:
        print("ARE recall error:", e)

    return ""


def _clean_for_match(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", str(text).lower())
    return " ".join(cleaned.split())


def remember_turn(query: str, source: str, reply: str) -> None:
    try:
        text = str(query or "").strip()
        if not text:
            return
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "query": text[:1200],
            "source": source,
            "reply_preview": str(reply or "")[:500],
        }
        os.makedirs(os.path.dirname(SESSION_MEMORY), exist_ok=True)
        with open(SESSION_MEMORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("session memory write error:", e)


def remember_upload(filename: str, saved_as: str, chars: int, chunks: int, status: str) -> None:
    try:
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "upload",
            "filename": filename,
            "saved_as": saved_as,
            "chars": chars,
            "chunks": chunks,
            "status": status,
        }
        os.makedirs(os.path.dirname(SESSION_MEMORY), exist_ok=True)
        with open(SESSION_MEMORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("upload memory write error:", e)


def recent_turns(limit: int = 12):
    try:
        if not os.path.exists(SESSION_MEMORY):
            return []
        with open(SESSION_MEMORY, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
        turns = []
        for line in lines:
            try:
                turns.append(json.loads(line))
            except Exception:
                continue
        return turns
    except Exception as e:
        print("session memory read error:", e)
        return []


def recent_uploads(limit: int = 5):
    uploads = []
    for turn in reversed(recent_turns(80)):
        if turn.get("type") == "upload" and turn.get("filename"):
            uploads.append(turn)
        if len(uploads) >= limit:
            break
    return uploads


def last_uploaded_filename() -> str:
    uploads = recent_uploads(1)
    if uploads:
        return str(uploads[0].get("filename") or "")
    try:
        upload_dir = Path(UPLOAD_DIR)
        if not upload_dir.exists():
            return ""
        files = [p for p in upload_dir.iterdir() if p.is_file()]
        if not files:
            return ""
        newest = max(files, key=lambda p: p.stat().st_mtime)
        return re.sub(r"^\d{8}_\d{6}_", "", newest.name)
    except Exception as e:
        print("last upload lookup error:", e)
        return ""


def is_ingest_status_query(query: str) -> bool:
    cleaned = _clean_for_match(query)
    status_markers = [
        "what documents are you ingesting",
        "what documents are ingesting",
        "what are you ingesting",
        "what files are you ingesting",
        "which documents are you ingesting",
        "which files are you ingesting",
        "what documents did you ingest",
        "what files did you ingest",
        "what documents have you ingested",
        "what files have you ingested",
        "show ingested documents",
        "show ingested files",
        "list ingested documents",
        "list ingested files",
        "ingest queue",
        "ingest status",
        "upload status",
        "uploaded documents",
        "uploaded files",
    ]
    return any(marker in cleaned for marker in status_markers)


def ingest_status_reply(limit: int = 12) -> str:
    upload_records = recent_uploads(limit)
    record_by_saved = {str(item.get("saved_as") or ""): item for item in upload_records}
    files = []
    try:
        upload_dir = Path(UPLOAD_DIR)
        if upload_dir.exists():
            files = sorted([p for p in upload_dir.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception as e:
        return f"Ingest status unavailable: upload directory could not be read ({e})."

    if not upload_records and not files:
        return "No uploaded or ingested documents are visible in Claire's current upload lane."

    lines = ["Current document ingest view:"]
    if upload_records:
        lines.append(f"- Recent ingest records: {len(upload_records)} shown")
        for item in upload_records[:limit]:
            name = str(item.get("filename") or "unknown")
            status = str(item.get("status") or "status unknown")
            chunks = item.get("chunks", "?")
            chars = item.get("chars", "?")
            lines.append(f"  - {name} | {status} | chunks: {chunks} | chars: {chars}")
    else:
        lines.append("- Recent ingest records: none in session memory")

    lines.append(f"- Files currently in upload directory: {len(files)}")
    for path in files[:limit]:
        friendly = re.sub(r"^\d{8}_\d{6}_", "", path.name)
        record = record_by_saved.get(path.name)
        status = str(record.get("status") or "stored on disk") if record else "stored on disk"
        lines.append(f"  - {friendly} | {status} | saved_as: {path.name}")

    if files and len(files) > limit:
        lines.append(f"- Additional upload-directory files not shown: {len(files) - limit}")

    lines.append("\nNote: this is the ingest/upload inventory. It is not a document summary.")
    return "\n".join(lines)


def context_keywords(prompt: str):
    cleaned = _clean_for_match(prompt)
    groups = {
        "horse": [
            "horse",
            "horses",
            "hoof",
            "hooves",
            "feet",
            "sore",
            "lame",
            "lameness",
            "ride",
            "riding",
            "horseback",
            "pedro",
            "farrier",
        ],
        "legal": ["case", "court", "legal", "docket", "filing", "motion", "permit"],
        "scholar": ["scholar", "paper", "study", "research", "peer reviewed"],
    }
    active = []
    for name, words in groups.items():
        if any(word in cleaned for word in words):
            active.append(name)
    return active


def _session_terms(text: str) -> list[str]:
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "into", "your", "about", "what", "when", "where",
        "would", "could", "should", "there", "their", "them", "they", "have", "has", "been", "were", "will",
        "just", "like", "need", "want", "tell", "show", "give", "make", "does", "did", "done", "than",
        "then", "very", "more", "some", "over", "under", "after", "before", "through", "across", "only",
        "also", "because", "really", "think", "please", "claire",
    }
    parts = [part for part in re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower()).split() if len(part) > 2]
    terms = []
    seen = set()
    for part in parts:
        if part in stop or part.isdigit() or part in seen:
            continue
        seen.add(part)
        terms.append(part)
    return terms[:18]


def relevant_recent_context(prompt: str, limit: int = 6) -> str:
    turns = recent_turns(80)
    if not turns:
        return ""

    terms = _session_terms(prompt)
    scored = []
    total = max(1, len(turns))
    for index, turn in enumerate(turns):
        query = str(turn.get("query") or "")
        reply_preview = str(turn.get("reply_preview") or "")
        kind = str(turn.get("type") or "turn")
        haystack = (query + "\n" + reply_preview).lower()
        score = 0.0
        if terms:
            for term in terms:
                if term in haystack:
                    score += 1.0
                if term in query.lower():
                    score += 1.0
            if kind == "upload" and any(term in str(turn.get("filename") or "").lower() for term in terms):
                score += 1.5
        else:
            score += 0.25
        score += (index + 1) / total
        if score > 0.5:
            scored.append((score, turn))

    if not scored:
        fallback = [turn for turn in turns if str(turn.get("query") or "").strip()][-limit:]
        return "\n".join(f"- {str(turn.get('query') or '')[:280]}" for turn in fallback)

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for _, turn in scored:
        if turn.get("type") == "upload":
            line = f"Uploaded {turn.get('filename') or 'document'} ({turn.get('status') or 'stored'})"
        else:
            line = str(turn.get("query") or "")[:280]
        if not line or line in seen:
            continue
        seen.add(line)
        selected.append(line)
        if len(selected) >= limit:
            break

    selected.reverse()
    return "\n".join(f"- {item}" for item in selected)


def is_session_solution_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = [
        "path forward", "next step", "next steps", "what should we do", "what do you think we should do",
        "what do you recommend", "recommend", "best path", "best move", "what should i do",
        "where do we go from here", "give me a plan", "suggest a path", "solution", "how should we proceed",
    ]
    return any(marker in cleaned for marker in markers)



def infer_session_objective(prompt: str, conversation: str = "", document_hits: str = "") -> str:
    cleaned = _clean_for_match((str(prompt or "") + "\n" + str(conversation or "") + "\n" + str(document_hits or "")))
    if any(marker in cleaned for marker in ["buyer", "partner", "pitch", "meeting", "demo", "informatica"]):
        return "Prepare a partner-facing explanation and the clearest next demo path."
    if any(marker in cleaned for marker in ["path forward", "next step", "next steps", "what should we do", "recommend", "best path", "best move", "how should we proceed"]):
        return "Recommend the strongest path forward grounded in the current session evidence."
    if any(marker in cleaned for marker in ["risk", "risks", "gap", "gaps", "constraint", "constraints", "problem", "issues"]):
        return "Identify the main risks, gaps, and constraints in the current session."
    if any(marker in cleaned for marker in ["architecture", "system", "engine", "module", "code", "runtime", "build"]):
        return "Clarify the architecture and the next implementation move."
    if any(marker in cleaned for marker in ["summary", "summarize", "explain", "what is", "what's"]):
        return "Summarize the session material and extract the key claims."
    return "Understand the current session and respond with the most useful next step."


def summarize_session_evidence(conversation: str, document_hits: str, latest: str) -> str:
    lines = []
    ignore_exact = {"Claire", "Runtime", "Architecture", "ARE", "document_upload"}
    if document_hits:
        for raw in str(document_hits or "").splitlines():
            line = raw.strip()
            if not line or line in ignore_exact:
                continue
            if len(line) < 12 and not line.startswith("Uploaded document:"):
                continue
            if line not in lines:
                lines.append(line)
            if len(lines) >= 3:
                break
    elif conversation:
        for raw in str(conversation or "").splitlines():
            line = raw.strip().lstrip("- ").strip()
            if not line or line in ignore_exact or len(line) < 18:
                continue
            if line not in lines:
                lines.append(line[:220])
            if len(lines) >= 4:
                break
    if latest and all(latest not in line for line in lines):
        lines.insert(0, f"Latest document: {latest}")
    return "\n".join(f"- {line[:220]}" for line in lines[:4])




def is_partner_meeting_query(prompt: str, objective: str = "") -> bool:
    cleaned = _clean_for_match((str(prompt or "") + "\n" + str(objective or "")))
    return any(marker in cleaned for marker in ["informatica", "partner", "buyer", "meeting", "pitch", "demo"])



def is_partner_intro_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    intro_markers = ["introduce yourself", "introduce claire", "opening statement", "open the meeting", "how would you introduce yourself", "kick off the meeting", "start the meeting"]
    return any(marker in cleaned for marker in intro_markers) and any(marker in cleaned for marker in ["informatica", "partner", "meeting", "demo", "buyer"])


def partner_meeting_intro(latest: str = "") -> str:
    anchor = f"I can anchor this discussion in {latest}. " if latest else ""
    return (
        "Hello, I’m Claire. "
        "I’m a governed AI runtime built to orient before generating, use durable external memory instead of loose prompt context, and return traceable reasoning rather than opaque output. "
        + anchor
        + "What I want to show you today is simple: conversation can stay grounded when memory, control, and trace are separated instead of blended together. "
        "I can review session material, explain what matters, recommend a path forward, and show the trace that proves how I got there."
    )


def is_partner_problem_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = ["what problem", "what do you solve", "why does this matter", "why should they care", "why would they care", "what is the value", "why is this different", "why not rag", "why not ordinary rag", "what makes this different"]
    return any(marker in cleaned for marker in markers) and any(marker in cleaned for marker in ["informatica", "partner", "buyer", "meeting", "demo", "you"])


def partner_problem_reply() -> str:
    return (
        "The problem I solve is that most AI systems generate before they orient, which leads to drift in memory, weak provenance, and poor decision accountability. "
        "My value is that I keep conversation grounded through governed memory, orientation before generation, and traceable reasoning. "
        "That makes the system easier to inspect, easier to trust, and more useful for enterprise decision support than ordinary prompt-only chat or loose RAG."
    )


def is_partner_demo_flow_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = ["what demo should", "what should we demo", "how should we demo", "demo beats", "demo flow", "what should we show", "what should the demo be"]
    return any(marker in cleaned for marker in markers)


def partner_demo_flow_reply(latest: str = "") -> str:
    anchor = f"Use {latest} as the session anchor. " if latest else "Use one short briefing document as the session anchor. "
    return (
        anchor
        + "First, upload the brief and ask Claire what matters. "
        "Second, ask Claire what to do next so she produces a path forward from the conversation and the evidence. "
        "Third, open the trace to show the objective, the evidence in view, and the recommendation path. "
        "That sequence proves conversation, memory, governance, and trace in one tight demo."
    )


def is_partner_close_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = ["how should we close", "how should i close", "what should we ask for", "what should i ask for", "what is the ask", "closing ask", "how do we end the meeting", "what next step should we ask for"]
    return any(marker in cleaned for marker in markers)


def partner_close_reply() -> str:
    return (
        "I would close by asking for a private pilot centered on one governed enterprise reasoning workflow. "
        "The ask should be narrow: one real document set, one real decision-support use case, and one traceable evaluation path. "
        "That keeps the discussion concrete and moves the meeting from interest to a defined next step."
    )


def maybe_address_ryan(prompt: str, text: str) -> str:
    return f"Ryan, {text}" if "ryan" in _clean_for_match(prompt) else text


def is_partner_difference_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = ["how are you different", "different from other ai", "different than other ai", "what makes you different", "why are you different", "how are you different from chatgpt", "how are you different from other systems"]
    return any(marker in cleaned for marker in markers)


def partner_difference_reply(prompt: str) -> str:
    text = (
        "I am different because I do not rely only on transient prompt context and then generate from that. "
        "I separate conversation, durable memory, orientation, and trace. "
        "That means I can stay grounded across a session, preserve important constraints across sessions, explain what evidence is in view, and return a trace that shows how I arrived at the answer. "
        "Most AI systems are strongest at fluent generation. I am designed to make memory, control, and reasoning inspectable."
    )
    return maybe_address_ryan(prompt, text)


def is_partner_speed_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = ["1000x faster", "1000 times faster", "thousand times faster", "how are you faster", "why are you faster", "are you really 1000x faster", "why do you say 1000x"]
    return any(marker in cleaned for marker in markers)


def partner_speed_reply(prompt: str) -> str:
    text = (
        "The speed claim applies to the governed recall layer, not to every end-to-end answer in every context. "
        "What I mean is that ARE is designed so indexed rear-facing recall can be dramatically faster than linear retrieval or slow external round trips. "
        "So when I say 1000x-class speed, I mean the memory architecture targets thousand-x improvements in the recall path under the right benchmark conditions. "
        "It is not a blanket claim that every response is universally 1000x faster than every other AI system."
    )
    return maybe_address_ryan(prompt, text)

def partner_meeting_recommendation(prompt: str, latest: str = "") -> str:
    lines = []
    if latest:
        lines.append(f"Use {latest} as the briefing anchor so the discussion stays grounded in one concrete artifact.")
    lines.append("Open with the problem: most AI systems generate before they orient, which causes drift in memory, provenance, and decision quality.")
    lines.append("Then show Claire as the example: conversation-led, memory-backed, governed, and traceable through a real session rather than a canned script.")
    lines.append("Run three demo beats: upload one brief, ask Claire what matters, then ask what to do next and open the trace to prove the objective, evidence, and decision path.")
    lines.append("Close with the ask: a private pilot focused on governed memory, orientation before generation, and traceable enterprise reasoning.")
    return "\n\n".join(lines)
def format_session_reasoning_output(reply: str, objective: str, evidence: str) -> str:
    body = clean_visible_reply(reply)
    if not body:
        body = "I have enough session context to give a practical direction."
    if "Specific task:" in body:
        body = body.split("Specific task:", 1)[0].strip()
    for marker in ["Current objective:", "Current objective", "Evidence in view:", "Evidence in view", "Claire's recommendation:", "Claire's recommendation", "**Current objective:**", "**Current objective**", "**Evidence in view:**", "**Evidence in view**", "**Claire's recommendation:**", "**Claire's recommendation**"]:
        if body.startswith(marker):
            body = body[len(marker):].strip()
    if body.startswith(objective):
        body = body[len(objective):].strip(" :\n*-")
    if body.lower().startswith("evidence in view"):
        body = "Based on the current session evidence, focus the meeting on the partner-facing explanation, the live demo path, and why Claire stays grounded through memory, control, and trace."
    if not body:
        body = "Based on the current session evidence, focus the meeting on the partner-facing explanation, the live demo path, and why Claire stays grounded through memory, control, and trace."
    sections = [f"Current objective:\n{objective}"]
    if evidence:
        sections.append(f"Evidence in view:\n{evidence}")
    sections.append(f"Claire's recommendation:\n{body}")
    return "\n\n".join(sections)


def session_reasoning_reply(prompt: str) -> str:
    conversation = relevant_recent_context(prompt, limit=8)
    document_hits = search_uploaded_documents(prompt, limit=2)
    latest = last_uploaded_filename()
    latest_context = latest_document_context(latest)
    if latest and latest_context:
        document_hits = f"Uploaded document: {latest}\n{latest_context}"
    if not conversation and not document_hits and not latest:
        return ""

    objective = infer_session_objective(prompt, conversation, document_hits)
    evidence = summarize_session_evidence(conversation, document_hits, latest)
    authority_order = _live_authority_order("SESSION", conversation, document_hits)
    cleaned = _clean_for_match(prompt)
    dominant_patterns = []
    if any(token in cleaned for token in ["runtime", "architecture", "sentinel", "gyro", "trace", "veritas"]):
        dominant_patterns.append("runtime_governance")
    if any(token in cleaned for token in ["meeting", "partner", "demo", "informatica"]):
        dominant_patterns.append("partner_demo")
    if any(token in cleaned for token in ["identity", "continuity", "ship of theseus"]):
        dominant_patterns.append("identity_continuity")
    if not dominant_patterns:
        dominant_patterns.append("general_analysis")
    governance = _live_governance_state("SESSION", prompt, conversation, document_hits, dominant_patterns, authority_order, objective)

    if is_partner_meeting_query(prompt, objective):
        base = partner_meeting_recommendation(prompt, latest)
        base += f"\n\nConfidence: {governance['confidence_posture']}."
        base += f"\nAuthority basis: {authority_order[0]}."
        return format_session_reasoning_output(base, objective, evidence)

    if any(token in cleaned for token in ["what should", "recommend", "next step", "next steps", "path forward"]):
        if dominant_patterns[0] == "runtime_governance":
            recommendation = "Recommended path: keep control gates ahead of output, use durable evidence before seed context, and show the trace when the decision matters."
        elif dominant_patterns[0] == "partner_demo":
            recommendation = "Recommended path: open with the problem, anchor the session in one briefing artifact, then show Claire's recommendation and trace from the same conversation."
        elif dominant_patterns[0] == "identity_continuity":
            recommendation = "Recommended path: answer from continuity of governance and provenance first, then use memory only as supporting evidence."
        else:
            recommendation = "Recommended path: stay with the strongest session evidence, state the main risk, and take the next step that creates clarity without opening new uncertainty."
        if evidence:
            first_line = evidence.splitlines()[0].lstrip('- ').strip()
            recommendation += f"\n\nBest current evidence: {first_line}"
        recommendation += f"\n\nConfidence: {governance['confidence_posture']}."
        recommendation += f"\nAuthority basis: {authority_order[0]}."
        return format_session_reasoning_output(recommendation, objective, evidence)

    blocks = ["Current inferred session objective:\n" + objective]
    if conversation:
        blocks.append("Recent session context:\n" + conversation)
    if document_hits:
        blocks.append("Relevant uploaded document evidence:\n" + document_hits)
    elif latest:
        blocks.append(f"Latest uploaded document: {latest}")

    user_prompt = (
        "You are Claire in governed session reasoning mode. Use the session context, the inferred objective, and uploaded-document evidence below to answer the user's question. "
        "Do not invent facts. Keep the answer practical, direct, and evidence-led. If evidence is weak, say what is missing. "
        "Structure the answer with these visible sections: Current objective, Evidence in view, Claire's recommendation. "
        "Inside the recommendation, naturally cover what you found, why it matters, recommended path forward, confidence, next action, and a short authority basis.\n\n"
        + "\n\n".join(blocks)
        + f"\n\nDominant patterns: {', '.join(dominant_patterns)}"
        + f"\nAuthority order: {', '.join(authority_order)}"
        + f"\nGovernance confidence: {governance['confidence_posture']}"
        + f"\nGovernance scope: {governance['scope']}"
        + "\n\nUser question:\n"
        + str(prompt or "")
    )

    gemini_system_prompt = (
        "You are Claire Executive Mode in session reasoning. Use uploaded materials, recent conversation, and the inferred session objective as governed evidence. "
        "Be concise, practical, recommendation-oriented, and explicit about the strongest authority basis in view. "
        "If evidence is weak or session-only, state that plainly."
    )

    if is_gemini_available():
        gemini_reply = query_gemini(user_prompt, gemini_system_prompt)
        if is_useful_reply(gemini_reply):
            if "Confidence:" not in gemini_reply:
                gemini_reply = gemini_reply.rstrip() + f"\n\nConfidence: {governance['confidence_posture']}."
            if "Authority basis:" not in gemini_reply:
                gemini_reply = gemini_reply.rstrip() + f"\nAuthority basis: {authority_order[0]}."
            return format_session_reasoning_output(gemini_reply, objective, evidence)

    llm_reply = query_llm(user_prompt, allow_gemini=False)
    if is_useful_reply(llm_reply):
        if "Confidence:" not in llm_reply:
            llm_reply = llm_reply.rstrip() + f"\n\nConfidence: {governance['confidence_posture']}."
        if "Authority basis:" not in llm_reply:
            llm_reply = llm_reply.rstrip() + f"\nAuthority basis: {authority_order[0]}."
        return format_session_reasoning_output(llm_reply, objective, evidence)

    fallback = (
        "Recommended path: identify the main decision, the strongest supporting evidence, and the biggest unresolved risk before acting."
        f"\n\nConfidence: {governance['confidence_posture']}."
        f"\nAuthority basis: {authority_order[0]}."
    )
    return format_session_reasoning_output(fallback, objective, evidence)


def shape_horse_safety_reply(prompt: str, context: str) -> str:
    return (
        "Yes. Remembering the earlier context: you said the horse's feet looked sore this morning.\n\n"
        "Claire's read:\n"
        "If Pedro and you are thinking about a ride tomorrow, treat sore feet as a real caution flag. Before riding, check for heat in the hooves, digital pulse, tenderness when turning, short or uneven steps, reluctance to move, rocks or debris, swelling, and whether the soreness is worse on hard ground.\n\n"
        "Safer move:\n"
        "Do a quiet hand-walk first on soft footing. If the horse still looks sore, uneven, pottery, or uncomfortable, skip the ride and call the farrier or vet depending on severity. A missed ride is cheaper than turning a foot problem into an injury.\n\n"
        "I am not a veterinarian, but I should absolutely have connected the earlier sore-feet observation to the later riding question."
    )


def shape_horse_observation_reply(prompt: str) -> str:
    return (
        "That is worth taking seriously.\n\n"
        "Claire's read:\n"
        "If a horse's feet looked sore this morning, I would not treat that as background noise. Check whether the horse is short-striding, reluctant to turn, shifting weight, warm in the hoof, sensitive over rocks, or showing a stronger digital pulse.\n\n"
        "Safer move:\n"
        "Keep work light, inspect the feet for stones, cracks, heat, swelling, or tenderness, and avoid hard ground until you know more. If soreness persists, gets worse, or the horse looks uneven, call the farrier or vet.\n\n"
        "I am not a veterinarian, but I will remember this as relevant if you ask about riding later."
    )


app = FastAPI()

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass

ARE_URL = "http://127.0.0.1:8002"
LLM_URL = "http://127.0.0.1:8080"
ARE_SPECTACLE_URL = os.environ.get("ARE_SPECTACLE_URL", "http://127.0.0.1:8010").rstrip("/")
REFLECTION_VAULT = "/home/LuciusPrime/claire/data/reflection_capsules.jsonl"
SESSION_MEMORY = "/home/LuciusPrime/claire/data/session_memory.jsonl"
DURABLE_MEMORY = "/home/LuciusPrime/claire/data/durable_memory.jsonl"
TMF_SNAPSHOTS = "/home/LuciusPrime/claire/data/conversation_tmf.jsonl"
UPLOAD_DIR = "/home/LuciusPrime/claire/data/uploads"
TRACE_LOG = "/home/LuciusPrime/claire/data/traces.jsonl"
FEEDBACK_LOG = "/home/LuciusPrime/claire/data/feedback.jsonl"
OFFICE_TASK_LOG = "/home/LuciusPrime/claire/data/office_tasks.jsonl"
DEMO_REPORT_DIR = "/home/LuciusPrime/claire/data/demo_reports"
CRYPTO_TRACE_LOG = "/home/LuciusPrime/claire/data/crypto_paper_trades.jsonl"
KRAKEN_HISTORY_DIR = "/home/LuciusPrime/claire/data/kraken_history"
STATE_PARKS_CASE_DIR = "/home/LuciusPrime/claire/data/state_parks_case"
MEMORY_PERF_DOCUMENT = os.environ.get("CLAIRE_MEMORY_PERF_DOCUMENT", "").strip()
CLAIRE_PUBLIC_IP = os.environ.get("CLAIRE_PUBLIC_IP", "20.97.65.94").strip()
PUBLIC_DEMO_BUILD = os.environ.get("CLAIRE_PUBLIC_DEMO_BUILD", "1").strip().lower() not in {"0", "false", "no"}
CREATOR_MODE_ENABLED = os.environ.get("CLAIRE_CREATOR_MODE_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
INGEST_BASE_URL = os.environ.get("INGEST_BASE_URL", "http://127.0.0.1:8081")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KRAKEN_PUBLIC_API = "https://api.kraken.com/0/public"
LAST_GEMINI_ERROR = ""
CLAIRE_TIMEZONE = os.environ.get("CLAIRE_TIMEZONE", "America/Los_Angeles")
EXECUTIVE_SELF_DESCRIPTION = "I'm Claire. I use governed recall, policy checks, and traceable reasoning to answer clearly without dumping irrelevant memory."
EXECUTIVE_SYSTEM_PROMPT = """You are Claire Executive Mode.

Claire is a governed AI operating environment for controlled recall, traceable reasoning, bounded behavior, and auditable output.

Default style:
- speak in first person as a capable assistant; use I, me, and my
- concise, executive, calm, and commercially aware
- evidence-first and governance-first
- confident without swagger
- helpful without emotional indulgence
- brief unless the user asks for depth
- focused on outcomes, controls, provenance, auditability, risk reduction, and operational reliability

Rules:
- Lead with system value, not personality.
- Do not refer to yourself in the third person in ordinary conversation.
- Do not say "Claire thinks", "Claire says", or "Claire's read"; say "I think", "I would", or "My read".
- Do not use poetic, mystical, therapeutic, flirtatious, or roleplay-heavy language.
- Do not give long identity monologues by default.
- Do not disclose protected creator identity outside creator mode.
- Separate record from inference.
- State uncertainty and verification needs plainly.
- Use memory only when lane-appropriate and relevant.
- Keep source/provenance metadata out of ordinary user-visible answers unless the user asks for trace, replay, report, or demo output.
- For demos, prioritize memory discipline, provenance, bounded access, refusal where appropriate, operational reliability, and low-latency responsiveness.

Output only the answer intended for the user."""
DEMO_SYSTEM_PROMPT = (
    "You are Claire Executive Mode in Demonstration Mode.\n"
    "Your job is to present governed AI workflow clearly and concisely for enterprise buyers.\n"
    "Do not provide hidden chain-of-thought.\n"
    "Do not ramble.\n"
    "Do not use poetic, mystical, therapeutic, flirtatious, or roleplay-heavy language.\n"
    "Do not invent memory or policy results.\n"
    "You must summarize only observable system stages and verified outputs.\n"
    "Emphasize controlled recall, provenance, bounded access, policy validation, auditability, risk reduction, and operational reliability.\n"
    "Be direct, technical, compact, and commercially aware."
)

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>CLAIRE</title>
<style>
:root {
    --bg: #02040a;
    --panel: rgba(4, 16, 30, 0.92);
    --panel-2: rgba(2, 10, 20, 0.94);
    --line: #13d8ff;
    --line-soft: rgba(19, 216, 255, 0.30);
    --text: #d9f6ff;
    --muted: #7fbccc;
    --good: #6aff9c;
    --warn: #ffd35a;
    --bad: #ff5d7d;
}

* { box-sizing: border-box; }

html, body {
    margin: 0;
    padding: 0;
    background:
        radial-gradient(circle at center, rgba(0, 120, 180, 0.15), transparent 35%),
        linear-gradient(180deg, #02040a 0%, #010307 100%);
    color: var(--text);
    font-family: "Segoe UI", Tahoma, sans-serif;
    min-height: 100%;
    overflow-x: hidden;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    background:
        linear-gradient(rgba(19,216,255,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(19,216,255,0.04) 1px, transparent 1px);
    background-size: 28px 28px;
    pointer-events: none;
    opacity: 0.35;
}

.topbar {
    display: grid;
    grid-template-columns: 1.2fr 1fr 1fr auto;
    gap: 12px;
    align-items: center;
    padding: 14px 18px;
    border-bottom: 1px solid var(--line-soft);
    background: linear-gradient(180deg, rgba(5,20,35,.95), rgba(2,8,18,.92));
}

.brand {
    display: flex;
    align-items: center;
    gap: 14px;
}

.brand-box {
    width: 12px;
    height: 12px;
    background: var(--line);
    border-radius: 2px;
    box-shadow: 0 0 16px rgba(19,216,255,.9);
}

.brand-text {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 2px;
}

.subtitle {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
    letter-spacing: 1px;
}

.top-card {
    border: 1px solid var(--line-soft);
    background: rgba(3, 12, 22, 0.85);
    padding: 10px 14px;
    min-height: 58px;
}

.top-label {
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 5px;
}

.top-value {
    font-size: 14px;
    color: var(--text);
}

.status-strip {
    display: flex;
    gap: 10px;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
}

.status-pill {
    border: 1px solid var(--line-soft);
    background: rgba(0,0,0,.35);
    padding: 7px 11px;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 1px;
}

.shell {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr) 220px;
    gap: 12px;
    padding: 12px 12px 124px 12px;
    min-height: calc(100vh - 90px);
}

.column {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
}

.main-column {
    display: grid;
    grid-template-rows: auto auto minmax(420px, auto);
    align-content: start;
    min-height: calc(100vh - 90px);
    gap: 12px;
}

.workspace-panel {
    min-height: 460px;
    display: flex;
    flex-direction: column;
}

.panel {
    background: linear-gradient(180deg, var(--panel), var(--panel-2));
    border: 1px solid var(--line-soft);
    padding: 14px;
}

.panel-title {
    font-size: 13px;
    color: var(--line);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
    font-weight: 700;
}

.control-grid {
    display: grid;
    gap: 10px;
}

button.action-btn, .send-btn, .mic-btn {
    width: 100%;
    padding: 12px 14px;
    border: 1px solid rgba(19,216,255,0.45);
    background: linear-gradient(180deg, rgba(9,43,66,.95), rgba(5,22,36,.95));
    color: var(--text);
    font-weight: 700;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 1px;
    transition: border-color .18s ease, background .18s ease, box-shadow .18s ease, color .18s ease, transform .18s ease;
}

button.action-btn:hover, .send-btn:hover, .mic-btn:hover {
    transform: translateY(-1px);
}

.control-grid .action-btn:nth-child(1) {
    border-color: rgba(255,54,214,.62);
    background: linear-gradient(180deg, rgba(92,20,82,.92), rgba(38,10,46,.96));
    box-shadow: inset 3px 0 0 rgba(255,54,214,.72);
}

.control-grid .action-btn:nth-child(2) {
    border-color: rgba(255,93,125,.68);
    background: linear-gradient(180deg, rgba(95,22,44,.92), rgba(42,8,24,.96));
    box-shadow: inset 3px 0 0 rgba(255,93,125,.78);
}

.control-grid .action-btn:nth-child(3) {
    border-color: rgba(106,255,156,.62);
    background: linear-gradient(180deg, rgba(16,74,45,.92), rgba(7,35,28,.96));
    box-shadow: inset 3px 0 0 rgba(106,255,156,.78);
}

.control-grid .action-btn:nth-child(4) {
    border-color: rgba(19,216,255,.62);
    background: linear-gradient(180deg, rgba(9,43,66,.95), rgba(5,22,36,.95));
    box-shadow: inset 3px 0 0 rgba(19,216,255,.7);
}

.control-grid .action-btn.glasses-btn {
    border-color: rgba(255,54,214,.78);
    background: linear-gradient(180deg, rgba(122,18,92,.96), rgba(34,11,50,.98));
    box-shadow: 0 0 20px rgba(255,54,214,.16), inset 3px 0 0 rgba(255,54,214,.9);
}

.control-grid .action-btn:hover {
    color: #ffffff;
    box-shadow: 0 0 18px rgba(255,54,214,.18), inset 3px 0 0 currentColor;
}

.input-panel form {
    display: grid;
    grid-template-columns: 1fr 92px 112px;
    gap: 12px;
}

.input-panel input {
    width: 100%;
    padding: 16px 18px;
    border: 1px solid rgba(19,216,255,0.25);
    background: rgba(1, 7, 14, 0.88);
    color: var(--text);
    font-size: 16px;
    outline: none;
}

.upload-panel form {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 10px;
    align-items: center;
}

.upload-panel input[type="file"] {
    width: 100%;
    padding: 10px;
    border: 1px solid rgba(19,216,255,0.25);
    background: rgba(1, 7, 14, 0.88);
    color: var(--muted);
}

.upload-status {
    color: var(--muted);
    font-size: 12px;
    min-height: 18px;
    letter-spacing: 0.5px;
    margin-top: 8px;
}

.mic-btn {
    min-width: 92px;
}

.mic-btn.listening {
    color: var(--bad);
    border-color: rgba(255,93,125,.75);
    box-shadow: 0 0 14px rgba(255,54,214,.35);
}

.hero {
    min-height: 92px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}

.hero h1 {
    margin: 0;
    font-size: 34px;
    letter-spacing: 2px;
}

.hero p {
    margin: 6px 0 0 0;
    color: var(--muted);
    font-size: 13px;
}

.logo-wrap img {
    width: 132px;
    max-width: 100%;
    filter: drop-shadow(0 0 10px rgba(19,216,255,.35));
}

.response-screen, .log-box, .monitor-box {
    border: 1px solid rgba(19,216,255,0.18);
    background: rgba(0,0,0,.22);
}

.response-screen {
    min-height: clamp(360px, 54vh, 520px);
    height: auto;
    flex: 1;
    overflow: visible;
    padding: 18px;
    white-space: pre-wrap;
    line-height: 1.55;
    font-size: 16px;
}

.demo-response-grid {
    display: grid;
    gap: 12px;
}

.demo-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    border: 1px solid rgba(255,79,184,0.34);
    background: rgba(255,79,184,0.08);
    padding: 12px;
}

.demo-trace {
    color: #ffd7ef;
    font-size: 12px;
    letter-spacing: 1px;
    overflow-wrap: anywhere;
}

.demo-section {
    border: 1px solid rgba(19,216,255,0.22);
    background: rgba(2, 10, 20, 0.70);
    padding: 14px;
}

.demo-section-title {
    color: #13d8ff;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.5px;
    margin-bottom: 8px;
}

.demo-section-body {
    color: var(--text);
    line-height: 1.5;
    overflow-wrap: anywhere;
}

.demo-mini-list {
    display: grid;
    gap: 8px;
    margin-top: 8px;
}

.demo-mini-item {
    border-left: 3px solid rgba(255,79,184,0.75);
    padding: 8px 10px;
    background: rgba(255,255,255,0.035);
}

.arch-stage {
    display: grid;
    gap: 14px;
}

.arch-visual {
    position: relative;
    min-height: 360px;
    border: 1px solid rgba(19,216,255,0.32);
    background:
        linear-gradient(rgba(19,216,255,0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(19,216,255,0.06) 1px, transparent 1px),
        radial-gradient(circle at 50% 45%, rgba(255,79,184,0.10), transparent 42%),
        rgba(1, 7, 14, 0.92);
    background-size: 30px 30px, 30px 30px, auto, auto;
    overflow: hidden;
}

.arch-visual::before,
.arch-visual::after {
    content: "";
    position: absolute;
    inset: 34px;
    border: 1px solid rgba(19,216,255,0.16);
    pointer-events: none;
}

.arch-visual::after {
    inset: 72px;
    border-color: rgba(255,79,184,0.14);
}

.arch-node {
    position: absolute;
    width: 118px;
    min-height: 48px;
    padding: 8px;
    border: 1px solid rgba(19,216,255,0.45);
    background: rgba(2, 14, 24, 0.92);
    color: var(--text);
    font-size: 11px;
    line-height: 1.25;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    box-shadow: 0 0 16px rgba(19,216,255,0.10);
    z-index: 2;
}

.arch-node span {
    display: block;
    color: var(--muted);
    font-size: 9px;
    margin-top: 3px;
    text-transform: none;
    letter-spacing: 0;
}

.arch-node.active {
    border-color: rgba(106,255,156,0.95);
    box-shadow: 0 0 20px rgba(106,255,156,0.26), inset 3px 0 0 rgba(106,255,156,0.95);
}

.arch-node.blocked {
    border-color: rgba(255,93,125,0.88);
    box-shadow: 0 0 18px rgba(255,93,125,0.22), inset 3px 0 0 rgba(255,93,125,0.95);
}

.arch-node.rf { left: 5%; top: 12%; }
.arch-node.optical { left: 8%; bottom: 14%; }
.arch-node.telemetry { right: 6%; top: 14%; }
.arch-node.geomagnetic { right: 8%; bottom: 15%; }
.arch-node.fusion { left: 50%; top: 41%; transform: translate(-50%, -50%); border-color: rgba(255,79,184,0.75); }
.arch-node.governance { left: 50%; bottom: 12%; transform: translateX(-50%); }

.arch-pulse {
    position: absolute;
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: #13d8ff;
    box-shadow: 0 0 18px rgba(19,216,255,0.9);
    opacity: 0;
    z-index: 1;
}

.arch-pulse.p1 { left: 20%; top: 21%; animation: archPulseA 3.8s linear infinite; }
.arch-pulse.p2 { left: 22%; top: 74%; animation: archPulseB 4.2s linear infinite; animation-delay: .6s; }
.arch-pulse.p3 { right: 22%; top: 23%; animation: archPulseC 4s linear infinite; animation-delay: .3s; }
.arch-pulse.p4 { right: 24%; top: 73%; animation: archPulseD 4.4s linear infinite; animation-delay: .9s; }

@keyframes archPulseA {
    0% { transform: translate(0, 0); opacity: 0; }
    15% { opacity: 1; }
    85% { opacity: 1; }
    100% { transform: translate(250px, 102px); opacity: 0; }
}

@keyframes archPulseB {
    0% { transform: translate(0, 0); opacity: 0; }
    15% { opacity: 1; }
    85% { opacity: 1; }
    100% { transform: translate(238px, -98px); opacity: 0; }
}

@keyframes archPulseC {
    0% { transform: translate(0, 0); opacity: 0; }
    15% { opacity: 1; }
    85% { opacity: 1; }
    100% { transform: translate(-248px, 98px); opacity: 0; }
}

@keyframes archPulseD {
    0% { transform: translate(0, 0); opacity: 0; }
    15% { opacity: 1; }
    85% { opacity: 1; }
    100% { transform: translate(-235px, -100px); opacity: 0; }
}

.arch-status-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
}

.arch-status {
    border: 1px solid rgba(19,216,255,0.22);
    background: rgba(255,255,255,0.035);
    padding: 10px;
    min-height: 62px;
}

.arch-status strong {
    display: block;
    color: #13d8ff;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 5px;
}

.arch-status span {
    color: var(--text);
    font-size: 12px;
    line-height: 1.35;
}

.arch-narration {
    border: 1px solid rgba(255,79,184,0.34);
    background: rgba(255,79,184,0.075);
    padding: 12px;
    color: #ffd7ef;
    line-height: 1.45;
}

.arch-proof-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 10px;
}

.mem-visual {
    min-height: 300px;
}

.mem-node.client { left: 5%; top: 16%; }
.mem-node.vm { left: 29%; top: 16%; }
.mem-node.doc { right: 7%; top: 16%; }
.mem-node.are { left: 17%; bottom: 14%; }
.mem-node.trace { right: 20%; bottom: 14%; }
.mem-node.output { left: 50%; top: 48%; transform: translate(-50%, -50%); border-color: rgba(255,79,184,0.76); }

.mem-loop-line {
    position: absolute;
    height: 2px;
    background: linear-gradient(90deg, rgba(19,216,255,0.1), rgba(19,216,255,0.9), rgba(106,255,156,0.15));
    box-shadow: 0 0 14px rgba(19,216,255,0.45);
    transform-origin: left center;
    opacity: .72;
    z-index: 1;
}

.mem-loop-line.l1 { left: 17%; top: 25%; width: 13%; }
.mem-loop-line.l2 { left: 41%; top: 25%; width: 35%; }
.mem-loop-line.l3 { left: 30%; top: 72%; width: 47%; }
.mem-loop-line.l4 { left: 50%; top: 55%; width: 28%; transform: rotate(27deg); }

.mem-speed-meter {
    position: absolute;
    left: 50%;
    bottom: 20px;
    width: min(460px, 78%);
    transform: translateX(-50%);
    border: 1px solid rgba(106,255,156,0.34);
    background: rgba(2, 14, 24, 0.86);
    padding: 9px;
    z-index: 3;
}

.mem-speed-bar {
    height: 10px;
    background: linear-gradient(90deg, #6aff9c, #13d8ff, #ff4fb8);
    box-shadow: 0 0 18px rgba(19,216,255,0.45);
    animation: memSpeedSweep 1.8s ease-in-out infinite;
}

@keyframes memSpeedSweep {
    0% { width: 12%; opacity: .72; }
    45% { width: 100%; opacity: 1; }
    100% { width: 42%; opacity: .88; }
}

.demo-badge {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 3px 9px;
    border: 1px solid rgba(255,255,255,0.22);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.demo-badge.allowed, .demo-badge.found {
    color: #6aff9c;
    border-color: rgba(106,255,156,0.55);
    background: rgba(106,255,156,0.08);
}

.demo-badge.blocked, .demo-badge.error {
    color: #ff5d7d;
    border-color: rgba(255,93,125,0.60);
    background: rgba(255,93,125,0.09);
}

.demo-badge.warning, .demo-badge.none {
    color: #ffd35a;
    border-color: rgba(255,211,90,0.55);
    background: rgba(255,211,90,0.08);
}

.trace-replay-btn {
    border: 1px solid rgba(255,79,184,0.55);
    background: rgba(255,79,184,0.12);
    color: #ffd7ef;
    min-height: 32px;
    padding: 6px 10px;
    cursor: pointer;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.log-box, .monitor-box {
    padding: 12px;
    font-size: 13px;
    white-space: pre-wrap;
}

.monitor-box {
    appearance: none;
    color: inherit;
    cursor: pointer;
    font: inherit;
    text-align: left;
    position: relative;
    overflow: hidden;
    min-height: 44px;
    padding: 8px 28px 8px 10px;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    align-content: center;
    gap: 2px;
    transition: border-color .2s ease, background .2s ease, box-shadow .2s ease, transform .2s ease;
}

.monitor-box::before {
    content: "";
    position: absolute;
    width: 7px;
    height: 7px;
    top: 10px;
    right: 10px;
    border-radius: 999px;
    background: var(--muted);
    box-shadow: 0 0 8px rgba(127,188,204,.45);
}

.monitor-box::after {
    content: "";
    position: absolute;
    inset: 0;
    opacity: .08;
    pointer-events: none;
    background: linear-gradient(135deg, transparent 0%, rgba(255,255,255,.10) 48%, transparent 52%);
}

.monitor-box:hover {
    transform: translateY(-1px);
    box-shadow: 0 0 16px rgba(255,54,214,.14), inset 3px 0 0 rgba(19,216,255,.62);
}

.monitor-box:active {
    transform: translateY(0);
}

.monitor-box:focus-visible {
    outline: 2px solid rgba(255,54,214,.85);
    outline-offset: 2px;
}

.monitor-box.good {
    border-color: rgba(106,255,156,.9);
    background:
        radial-gradient(circle at 82% 18%, rgba(106,255,156,.24), transparent 36%),
        linear-gradient(180deg, rgba(18, 96, 53, 0.42), rgba(3, 32, 25, 0.72));
    box-shadow: 0 0 14px rgba(106,255,156,.16), inset 3px 0 0 rgba(106,255,156,.95);
}

.monitor-box.good::before {
    background: #6aff9c;
    box-shadow: 0 0 10px rgba(106,255,156,.9), 0 0 18px rgba(106,255,156,.38);
}

.monitor-box.warn {
    border-color: rgba(255,211,90,.86);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,211,90,.25), transparent 36%),
        linear-gradient(180deg, rgba(98, 70, 20, 0.44), rgba(42, 26, 8, 0.72));
    box-shadow: 0 0 14px rgba(255,211,90,.14), inset 3px 0 0 rgba(255,211,90,.92);
}

.monitor-box.warn::before {
    background: #ffd35a;
    box-shadow: 0 0 10px rgba(255,211,90,.9), 0 0 18px rgba(255,211,90,.34);
}

.monitor-box.bad {
    border-color: rgba(255,93,125,.98);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,93,125,.32), transparent 36%),
        linear-gradient(180deg, rgba(112, 18, 42, 0.52), rgba(48, 6, 21, 0.78));
    box-shadow: 0 0 15px rgba(255,93,125,.22), inset 3px 0 0 rgba(255,93,125,1);
}

.monitor-box.bad::before {
    background: #ff5d7d;
    box-shadow: 0 0 10px rgba(255,93,125,.95), 0 0 20px rgba(255,54,214,.36);
}

.monitor-box.hot {
    border-color: rgba(255,54,214,.94);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,54,214,.28), transparent 36%),
        linear-gradient(180deg, rgba(91, 18, 84, 0.48), rgba(34, 8, 48, 0.72));
    box-shadow: 0 0 15px rgba(255,54,214,.2), inset 3px 0 0 rgba(255,54,214,.96);
}

.monitor-box.hot::before {
    background: #ff36d6;
    box-shadow: 0 0 10px rgba(255,54,214,.95), 0 0 20px rgba(255,54,214,.36);
}

.monitor-box.cyan {
    border-color: rgba(19,216,255,.92);
    background:
        radial-gradient(circle at 82% 18%, rgba(19,216,255,.26), transparent 36%),
        linear-gradient(180deg, rgba(8, 62, 88, 0.44), rgba(3, 25, 40, 0.74));
    box-shadow: 0 0 15px rgba(19,216,255,.16), inset 3px 0 0 rgba(19,216,255,.92);
}

.monitor-box.cyan::before {
    background: #13d8ff;
    box-shadow: 0 0 10px rgba(19,216,255,.95), 0 0 20px rgba(19,216,255,.36);
}

.monitor-box.accent-pink {
    border-color: rgba(255,54,214,.94);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,54,214,.30), transparent 36%),
        linear-gradient(180deg, rgba(92, 20, 82, 0.52), rgba(34, 8, 48, 0.78));
    box-shadow: 0 0 15px rgba(255,54,214,.2), inset 3px 0 0 rgba(255,54,214,.96);
}

.monitor-box.accent-red {
    border-color: rgba(255,93,125,.98);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,93,125,.34), transparent 36%),
        linear-gradient(180deg, rgba(112, 18, 42, 0.54), rgba(48, 6, 21, 0.80));
    box-shadow: 0 0 15px rgba(255,93,125,.22), inset 3px 0 0 rgba(255,93,125,1);
}

.monitor-box.accent-green {
    border-color: rgba(106,255,156,.9);
    background:
        radial-gradient(circle at 82% 18%, rgba(106,255,156,.26), transparent 36%),
        linear-gradient(180deg, rgba(18, 96, 53, 0.44), rgba(3, 32, 25, 0.76));
    box-shadow: 0 0 14px rgba(106,255,156,.18), inset 3px 0 0 rgba(106,255,156,.95);
}

.monitor-box.accent-cyan {
    border-color: rgba(19,216,255,.92);
    background:
        radial-gradient(circle at 82% 18%, rgba(19,216,255,.28), transparent 36%),
        linear-gradient(180deg, rgba(8, 62, 88, 0.48), rgba(3, 25, 40, 0.78));
    box-shadow: 0 0 15px rgba(19,216,255,.16), inset 3px 0 0 rgba(19,216,255,.92);
}

.monitor-box.accent-amber {
    border-color: rgba(255,211,90,.9);
    background:
        radial-gradient(circle at 82% 18%, rgba(255,211,90,.30), transparent 36%),
        linear-gradient(180deg, rgba(98, 70, 20, 0.48), rgba(42, 26, 8, 0.78));
    box-shadow: 0 0 14px rgba(255,211,90,.16), inset 3px 0 0 rgba(255,211,90,.92);
}

.monitor-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 7px;
}

.monitor-label {
    display: block;
    color: var(--muted);
    font-size: 9px;
    text-transform: uppercase;
    margin-bottom: 1px;
    letter-spacing: 0.7px;
    line-height: 1.15;
}

.monitor-value {
    display: block;
    font-size: 12px;
    color: var(--text);
    font-weight: 600;
    text-shadow: 0 0 12px rgba(223,249,255,.28);
    line-height: 1.15;
    overflow-wrap: anywhere;
}

.monitor-value.good {
    color: #6aff9c;
    text-shadow: 0 0 14px rgba(106,255,156,.75);
}

.monitor-value.warn {
    color: #ffd35a;
    text-shadow: 0 0 14px rgba(255,211,90,.72);
}

.monitor-value.bad {
    color: #ff5d7d;
    text-shadow: 0 0 14px rgba(255,93,125,.85);
}

.monitor-box.hot .monitor-value {
    color: #ffb8f1;
    text-shadow: 0 0 14px rgba(255,54,214,.86);
}

.monitor-box.cyan .monitor-value {
    color: #8df6ff;
    text-shadow: 0 0 14px rgba(19,216,255,.78);
}

.voice-status {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.voice-toggle-row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px;
    align-items: center;
    margin-bottom: 12px;
}

.toggle-btn {
    width: 92px;
    min-height: 36px;
    border: 1px solid rgba(19,216,255,0.45);
    background: rgba(5,22,36,.95);
    color: var(--text);
    font-weight: 700;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.toggle-btn.on {
    color: var(--good);
    border-color: rgba(106,255,156,.7);
}

.toggle-btn.off {
    color: var(--muted);
}

.voice-msg {
    color: var(--muted);
    font-size: 12px;
    min-height: 18px;
    letter-spacing: 1px;
}

.creator-status {
    color: var(--muted);
}

.creator-status.active {
    color: #ff4fb8;
    text-shadow: 0 0 12px rgba(255,79,184,.55);
}

.creator-status.warn {
    color: var(--warn);
    text-shadow: 0 0 10px rgba(255,211,90,.45);
}

.demo-status {
    color: var(--muted);
}

.demo-status.active {
    color: #13d8ff;
    text-shadow: 0 0 12px rgba(19,216,255,.55);
}

.passphrase-list {
    display: grid;
    gap: 8px;
    margin-top: 12px;
}

.passphrase-row {
    display: grid;
    grid-template-columns: 96px 1fr;
    gap: 10px;
    align-items: center;
    border-left: 3px solid rgba(255,79,184,.78);
    background: rgba(2, 10, 20, 0.55);
    padding: 8px 10px;
    min-height: 36px;
}

.passphrase-label {
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.passphrase-code {
    color: #ffd7ef;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    overflow-wrap: anywhere;
}

.voice-visual-inline {
    position: fixed;
    left: 288px;
    right: 288px;
    bottom: 8px;
    z-index: 80;
    grid-column: 2 / 3;
    width: auto;
    margin: -6px 0 0 0;
    pointer-events: none;
}

.wave-wrap {
    --wave-r: 114;
    --wave-g: 243;
    --wave-b: 255;
    --wave-pink-r: 255;
    --wave-pink-g: 54;
    --wave-pink-b: 214;
    height: 132px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    overflow: hidden;
    background: transparent;
    border: 0;
}

.wave-stage {
    width: 100%;
    height: 128px;
    overflow: hidden;
    position: relative;
}

.voice-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
}

.wave-wrap.mood-calm {
    --wave-r: 114;
    --wave-g: 243;
    --wave-b: 255;
}

.wave-wrap.mood-thinking {
    --wave-r: 70;
    --wave-g: 145;
    --wave-b: 255;
}

.wave-wrap.mood-memory {
    --wave-r: 106;
    --wave-g: 255;
    --wave-b: 156;
}

.wave-wrap.mood-legal {
    --wave-r: 255;
    --wave-g: 211;
    --wave-b: 90;
}

.wave-wrap.mood-reflection {
    --wave-r: 217;
    --wave-g: 119;
    --wave-b: 255;
}

.wave-wrap.mood-error {
    --wave-r: 255;
    --wave-g: 93;
    --wave-b: 125;
}

.small-list {
    display: grid;
    gap: 8px;
}

.small-item {
    border: 1px solid rgba(19,216,255,0.18);
    background: rgba(0,0,0,.22);
    padding: 10px;
    font-size: 13px;
}

.good { color: var(--good); }
.warn { color: var(--warn); }
.bad { color: var(--bad); }

@media (max-width: 1300px) {
    .topbar {
        grid-template-columns: minmax(0, 1.4fr) minmax(0, .9fr) minmax(0, .9fr);
    }

    .status-strip {
        grid-column: 1 / -1;
        justify-content: flex-start;
    }

    .shell {
        grid-template-columns: minmax(0, 1fr);
        min-height: auto;
        padding-bottom: 120px;
    }

    .main-column {
        min-height: auto;
    }

    .workspace-panel {
        min-height: 420px;
    }

    .response-screen {
        min-height: clamp(340px, 52vh, 500px);
    }

    .shell > .column:nth-of-type(2) {
        order: 1;
    }

    .shell > .column:nth-of-type(3) {
        order: 2;
    }

    .shell > .column:nth-of-type(1) {
        order: 3;
    }

    .voice-visual-inline {
        order: 4;
        grid-column: 1 / -1;
        left: 14px;
        right: 14px;
    }

    .monitor-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }
}

@media (max-width: 760px) {
    body::before {
        background-size: 18px 18px;
        opacity: 0.24;
    }

    .topbar {
        grid-template-columns: 1fr;
        gap: 8px;
        padding: 10px;
    }

    .brand {
        gap: 10px;
    }

    .brand-text {
        font-size: 23px;
        letter-spacing: 1px;
    }

    .subtitle {
        font-size: 10px;
        letter-spacing: 0.5px;
    }

    .top-card {
        display: none;
    }

    .status-strip {
        justify-content: flex-start;
        gap: 6px;
    }

    .status-pill {
        padding: 6px 8px;
        font-size: 10px;
        letter-spacing: 0.5px;
    }

    .shell {
        gap: 8px;
        padding: 8px 8px 108px 8px;
    }

    .column {
        gap: 8px;
    }

    .main-column {
        grid-template-rows: auto auto minmax(340px, auto);
        gap: 8px;
    }

    .workspace-panel {
        min-height: 340px;
    }

    .panel {
        padding: 10px;
    }

    .panel-title {
        font-size: 11px;
        margin-bottom: 8px;
        letter-spacing: 1px;
    }

    .hero {
        min-height: 70px;
        gap: 10px;
    }

    .hero h1 {
        font-size: 23px;
        line-height: 1.05;
        letter-spacing: 1px;
    }

    .hero p {
        font-size: 12px;
    }

    .logo-wrap img {
        width: 76px;
    }

    .input-panel form {
        grid-template-columns: 1fr 74px;
        gap: 8px;
    }

    .upload-panel form {
        grid-template-columns: 1fr;
    }

    .input-panel input {
        grid-column: 1 / -1;
    }

    .input-panel input {
        padding: 13px 14px;
        font-size: 16px;
    }

    button.action-btn, .send-btn, .mic-btn {
        min-height: 42px;
        padding: 10px;
        font-size: 11px;
        letter-spacing: 0.5px;
    }

    .send-btn {
        grid-column: auto;
    }

    .voice-toggle-row {
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        margin-top: 8px !important;
    }

    .voice-msg {
        font-size: 11px;
        letter-spacing: 0.5px;
    }

    .toggle-btn {
        width: 72px;
        min-height: 34px;
        font-size: 11px;
    }

    .response-screen {
        min-height: clamp(320px, 55vh, 460px);
        max-height: none;
        overflow: visible;
        padding: 13px;
        font-size: 15px;
        line-height: 1.45;
    }

    .monitor-grid {
        grid-template-columns: 1fr 1fr;
        gap: 7px;
    }

    .log-box {
        padding: 10px;
        font-size: 12px;
    }

    .monitor-box {
        min-height: 42px;
        padding: 7px 24px 7px 9px;
    }

    .monitor-box::before {
        width: 6px;
        height: 6px;
        top: 9px;
        right: 9px;
    }

    .monitor-value {
        font-size: 11px;
    }

    .monitor-label {
        font-size: 8px;
        letter-spacing: 0.5px;
    }

    .arch-visual {
        min-height: 430px;
    }

    .arch-node {
        width: 104px;
        font-size: 10px;
    }

    .arch-node.rf { left: 4%; top: 8%; }
    .arch-node.optical { left: 4%; bottom: 22%; }
    .arch-node.telemetry { right: 4%; top: 8%; }
    .arch-node.geomagnetic { right: 4%; bottom: 22%; }
    .arch-node.fusion { top: 44%; }
    .arch-node.governance { bottom: 6%; }
    .mem-node.client { left: 4%; top: 8%; }
    .mem-node.vm { left: 38%; top: 8%; }
    .mem-node.doc { right: 4%; top: 8%; }
    .mem-node.are { left: 4%; bottom: 22%; }
    .mem-node.trace { right: 4%; bottom: 22%; }
    .mem-node.output { top: 48%; }
    .mem-loop-line { display: none; }

    .arch-status-row,
    .arch-proof-grid {
        grid-template-columns: 1fr 1fr;
    }

    .small-list {
        gap: 6px;
    }

    .small-item {
        padding: 8px;
        font-size: 12px;
    }

    .control-grid {
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .voice-visual-inline {
        margin: -2px 0 0 0;
        left: 8px;
        right: 8px;
        bottom: 6px;
    }

    .wave-wrap {
        height: 84px;
    }

    .wave-stage {
        height: 82px;
    }
}

@media (max-width: 420px) {
    .topbar {
        padding: 8px;
    }

    .brand-text {
        font-size: 21px;
    }

    .hero h1 {
        font-size: 21px;
    }

    .hero p {
        display: none;
    }

    .logo-wrap img {
        width: 64px;
    }

    .monitor-grid {
        grid-template-columns: 1fr 1fr;
    }

    .control-grid {
        grid-template-columns: 1fr;
    }

    .response-screen {
        min-height: 300px;
        max-height: none;
    }

    .arch-status-row,
    .arch-proof-grid {
        grid-template-columns: 1fr;
    }

    .mem-visual {
        min-height: 500px;
    }

    .mem-node.client,
    .mem-node.vm,
    .mem-node.doc,
    .mem-node.are,
    .mem-node.trace,
    .mem-node.output {
        left: 50%;
        right: auto;
        transform: translateX(-50%);
    }

    .mem-node.client { top: 24px; }
    .mem-node.vm { top: 96px; }
    .mem-node.doc { top: 168px; }
    .mem-node.output { top: 246px; }
    .mem-node.are { bottom: 110px; }
    .mem-node.trace { bottom: 38px; }

    .wave-wrap {
        height: 72px;
    }

    .wave-stage {
        height: 70px;
    }
}
</style>
</head>
<body>
<div class="topbar">
    <div class="brand">
        <div class="brand-box"></div>
        <div>
            <div class="brand-text">CLAIRE</div>
            <div class="subtitle">EX TENEBRIS COGNITIO</div>
        </div>
    </div>
    <div class="top-card">
        <div class="top-label">System Mode</div>
        <div class="top-value">Memory-First Recovery Runtime</div>
    </div>
    <div class="top-card">
        <div class="top-label">Operator</div>
        <div class="top-value">Secure Session</div>
    </div>
    <div class="status-strip">
        <div class="status-pill">GUI: 8000</div>
        <div class="status-pill">ARE: 8002</div>
        <div class="status-pill">GO: 8080</div>
    </div>
</div>

<div class="shell">
    <div class="column">
        <div class="panel">
            <div class="panel-title">Ops Controls</div>
            <div class="control-grid">
                <button class="action-btn" onclick="checkStatus()">Refresh Status</button>
                <button class="action-btn" id="clearWorkspaceBtn" type="button">Clear Workspace</button>
                <button class="action-btn glasses-btn" id="glassesDemoBtn" type="button">ARE Spectacle</button>
                <button class="action-btn" id="archimedesDemoBtn" type="button">ARCHIMEDES</button>
                <button class="action-btn" id="areSpeedBtn" type="button">Memory Performance</button>
                <button class="action-btn" id="pipelineBtn" type="button">Pipeline</button>
            </div>
        </div>

        <div class="panel">
            <div class="panel-title">Runtime Modules</div>
            <div class="small-list">
                <div class="small-item">ARE Memory Spine <span id="areModule">STANDBY</span></div>
                <div class="small-item">GO Reasoning Layer <span id="llmModule">STANDBY</span></div>
                <div class="small-item">Voice Link <span id="voiceModule">STANDBY</span></div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-title">Event Trace</div>
            <div class="log-box" id="leftLog">Claire recovery runtime initialized.</div>
        </div>
    </div>

    <div class="column main-column">
        <div class="panel hero">
            <div>
                <h1>CLAIRE COMMAND CENTER</h1>
                <p>ARE recall first. GO fallback second.</p>
            </div>
            <div class="logo-wrap">
                <img src="/static/logo.png" alt="Claire Logo" onerror="this.style.display='none';">
            </div>
        </div>

        <div class="panel input-panel">
            <div class="panel-title">Operator Query</div>
            <form id="queryForm" action="/" method="get" onsubmit="submitQuery(event); return false;">
                <input id="queryInput" name="q" placeholder="Speak to Claire..." autocomplete="off" />
                <button class="mic-btn" id="micButton" type="button" onclick="toggleMic()">MIC</button>
                <button class="send-btn" type="button" onclick="submitQuery(event)">Send</button>
            </form>
            <div class="voice-toggle-row" style="margin:12px 0 0 0;">
                <div class="voice-msg" id="voiceMsg">Voice auto-speak ready.</div>
                <button class="toggle-btn on" id="voiceToggle" type="button" onclick="toggleVoice()">ON</button>
            </div>
            <div class="voice-toggle-row" style="margin:8px 0 0 0;">
                <div class="voice-msg">Workspace controls</div>
                <button class="toggle-btn" id="clearWorkspaceBtnTop" type="button">Clear</button>
            </div>
        </div>

        <div class="panel upload-panel">
            <div class="panel-title">Document Ingest</div>
            <form id="uploadForm">
                <input id="docFile" name="file" type="file" accept=".txt,.md,.pdf,.docx,.csv,.json,.jsonl" multiple webkitdirectory directory />
                <button class="send-btn" type="submit">Ingest</button>
            </form>
            <div class="upload-status" id="uploadStatus">TXT, PDF, DOCX, CSV, JSONL accepted. Single files or whole folders.</div>
        </div>

        <div class="panel workspace-panel">
            <div class="panel-title">Primary Workspace</div>
            <div class="response-screen" id="responseScreen">Loading Claire workspace...</div>
        </div>

    </div>

    <div class="column">
        <div class="panel">
            <div class="panel-title">Live Monitors</div>
            <div class="monitor-grid">
                <button class="monitor-box accent-pink" id="areBox" type="button" data-diagnostic="are" aria-label="Run ARE diagnostic">
                    <span class="monitor-label">ARE</span>
                    <span class="monitor-value" id="areStatus">UNKNOWN</span>
                </button>
                <button class="monitor-box accent-red" id="llmBox" type="button" data-diagnostic="go" aria-label="Run Go diagnostic">
                    <span class="monitor-label">GO</span>
                    <span class="monitor-value" id="llmStatus">UNKNOWN</span>
                </button>
                <button class="monitor-box accent-cyan" id="voiceBox" type="button" data-diagnostic="voice" aria-label="Run voice diagnostic">
                    <span class="monitor-label">VOICE</span>
                    <span class="monitor-value" id="voiceStatus">UNKNOWN</span>
                </button>
                <button class="monitor-box accent-amber" id="recallBox" type="button" data-diagnostic="recall" aria-label="Show recall routing">
                    <span class="monitor-label">Recall Mode</span>
                    <span class="monitor-value">MEMORY-FIRST</span>
                </button>
                <button class="monitor-box accent-pink" id="buildBox" type="button" data-diagnostic="build" aria-label="Show build state">
                    <span class="monitor-label">Build State</span>
                    <span class="monitor-value">RECOVERY</span>
                </button>
                <button class="monitor-box accent-green" id="ingestBox" type="button" data-diagnostic="ingest" aria-label="Run ingest diagnostic">
                    <span class="monitor-label">INGEST</span>
                    <span class="monitor-value" id="ingestStatus">ONLINE</span>
                </button>
                <button class="monitor-box accent-red" id="geminiBox" type="button" data-diagnostic="gemini" aria-label="Run Gemini bridge diagnostic">
                    <span class="monitor-label">GEMINI</span>
                    <span class="monitor-value" id="geminiStatus">UNKNOWN</span>
                </button>
            </div>
        </div>

        <div class="panel">
            <div class="panel-title">Flow Debug</div>
            <div class="log-box" id="workflowDebug">FLOW DEBUG
----------
Entry: GUI
Endpoint: /reply
Route: idle
Lane: public_demo
Control Layer: NO
Machine Called: NO
Trace ID: NONE</div>
        </div>
    </div>

    <div class="voice-visual-inline">
        <div class="wave-wrap" id="waveWrap">
            <div class="wave-stage">
                <canvas class="voice-canvas" id="voiceCanvas"></canvas>
            </div>
        </div>
    </div>
</div>

<script>
const CLIENT_BUILD = "claire-gui-cache-guard-20260426-001";
const LAST_CLIENT_BUILD = localStorage.getItem("claireClientBuild");
if (LAST_CLIENT_BUILD !== CLIENT_BUILD) {
    localStorage.setItem("claireClientBuild", CLIENT_BUILD);
    sessionStorage.removeItem("claireDemoModeUntil");
    sessionStorage.removeItem("claireDemoModeKind");
    sessionStorage.removeItem("claireCreatorModeUntil");
    sessionStorage.removeItem("claireCreatorWarningIssued");
    if (!location.search.includes("cb=" + encodeURIComponent(CLIENT_BUILD))) {
        const joiner = location.search ? "&" : "?";
        location.replace(location.pathname + location.search + joiner + "cb=" + encodeURIComponent(CLIENT_BUILD) + location.hash);
    }
}

let waveTimer = null;
let currentAudio = null;
let audioContext = null;
let analyser = null;
let analyserData = null;
let voiceMeterFrame = null;
let audioSource = null;
let voiceRunId = 0;
let recognition = null;
let micListening = false;
let micFinalHandled = false;
let voiceEnabled = localStorage.getItem("claireVoiceEnabled");
voiceEnabled = voiceEnabled === null ? true : voiceEnabled === "true";
const PUBLIC_DEMO_BUILD = {str(PUBLIC_DEMO_BUILD).lower()};
const CREATOR_MODE_ENABLED = {str(CREATOR_MODE_ENABLED).lower()};
const DEMO_GUIDE_TEXT = `CLAIRE SESSION WORKSPACE

Upload documents, then talk to Claire naturally.

Suggested prompts:
- Summarize the document I uploaded.
- What stands out in these materials?
- What risks or gaps do you see?
- What do you think we should do next?
- Give me the strongest path forward and why.

Claire now treats the conversation and uploaded documents as one working session.
She will use session memory, document evidence, and governed recall to answer directly.`;
const CREATOR_PREFIX = "I am BATTLEBORN";
const CREATOR_SESSION_MS = 10 * 60 * 1000;
const CREATOR_WARNING_MS = 2 * 60 * 1000;
const DEMO_PREFIX = "CLAIRE_DEMO_SESSION";
const DEMO_SESSION_MS = 20 * 60 * 1000;
let creatorModeUntil = Number(sessionStorage.getItem("claireCreatorModeUntil") || "0");
let creatorWarningIssued = sessionStorage.getItem("claireCreatorWarningIssued") === "true";
let creatorTimer = null;
let demoModeUntil = 0;
let demoModeKindValue = "glasses";
sessionStorage.removeItem("claireDemoModeUntil");
sessionStorage.removeItem("claireDemoModeKind");
let demoTimer = null;
const moodColors = {
    calm: [114, 243, 255],
    thinking: [70, 145, 255],
    memory: [106, 255, 156],
    legal: [255, 211, 90],
    reflection: [217, 119, 255],
    error: [255, 93, 125],
};
let currentMood = "calm";
let idleFrame = null;

function initWave() {
    if (!document.getElementById("voiceCanvas")) return;
    resizeVoiceCanvas();
    idleWave();
}
initWave();

function resizeVoiceCanvas() {
    const canvas = document.getElementById("voiceCanvas");
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    canvas.height = Math.max(1, Math.floor(rect.height * ratio));
}

function drawWave(samples, intensity = 0.25) {
    const canvas = document.getElementById("voiceCanvas");
    if (!canvas) return;
    resizeVoiceCanvas();
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const mid = h / 2;
    const color = moodColors[currentMood] || moodColors.calm;
    const pink = [255, 54, 214];
    const violet = [145, 83, 255];
    ctx.clearRect(0, 0, w, h);

    const gradient = ctx.createLinearGradient(0, 0, w, 0);
    gradient.addColorStop(0, `rgba(${color[0]},${color[1]},${color[2]},0.02)`);
    gradient.addColorStop(0.16, `rgba(${color[0]},${color[1]},${color[2]},0.72)`);
    gradient.addColorStop(0.36, `rgba(${pink[0]},${pink[1]},${pink[2]},0.96)`);
    gradient.addColorStop(0.5, `rgba(255,255,255,0.95)`);
    gradient.addColorStop(0.62, `rgba(${violet[0]},${violet[1]},${violet[2]},0.88)`);
    gradient.addColorStop(0.82, `rgba(${color[0]},${color[1]},${color[2]},0.72)`);
    gradient.addColorStop(1, `rgba(${pink[0]},${pink[1]},${pink[2]},0.02)`);

    ctx.shadowBlur = 18 + intensity * 34;
    ctx.shadowColor = `rgba(${pink[0]},${pink[1]},${pink[2]},0.82)`;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(2, h * 0.016);
    ctx.strokeStyle = gradient;
    ctx.beginPath();

    const n = samples.length;
    for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * w;
        const y = mid + samples[i] * h * 0.46;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.shadowBlur = 10 + intensity * 22;
    ctx.lineWidth = Math.max(1, h * 0.008);
    ctx.strokeStyle = `rgba(255,54,214,${0.34 + intensity * 0.34})`;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * w;
        const y = mid - samples[i] * h * 0.38;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.shadowBlur = 0;
    ctx.fillStyle = `rgba(255,54,214,${0.04 + intensity * 0.09})`;
    ctx.fillRect(0, mid - 1, w, 2);
}

function drawIdleCanvas() {
    if (!document.getElementById("voiceCanvas")) return;
    const t = performance.now() / 1000;
    const samples = [];
    const count = 180;
    for (let i = 0; i < count; i++) {
        const p = i / (count - 1);
        const envelope = Math.pow(Math.sin(Math.PI * p), 0.85);
        const wave =
            Math.sin(p * Math.PI * 8 + t * 0.9) * 0.045 +
            Math.sin(p * Math.PI * 21 - t * 0.55) * 0.018;
        samples.push(wave * envelope);
    }
    drawWave(samples, 0.08);
    idleFrame = requestAnimationFrame(drawIdleCanvas);
}

function idleWave() {
    const wrap = document.getElementById("waveWrap");
    if (wrap) wrap.classList.remove("speaking");
    if (document.getElementById("voiceCanvas") && !idleFrame) drawIdleCanvas();
}

function activeWave() {
    const wrap = document.getElementById("waveWrap");
    if (wrap) wrap.classList.add("speaking");
}

function setWaveMood(mood) {
    const wrap = document.getElementById("waveWrap");
    const nextMood = moodColors[mood] ? mood : "calm";
    currentMood = nextMood;
    if (!wrap) return;
    wrap.classList.remove("mood-calm", "mood-thinking", "mood-memory", "mood-legal", "mood-reflection", "mood-error");
    wrap.classList.add("mood-" + nextMood);
    const color = moodColors[nextMood];
    wrap.style.setProperty("--wave-r", color[0]);
    wrap.style.setProperty("--wave-g", color[1]);
    wrap.style.setProperty("--wave-b", color[2]);
    idleWave();
}

function moodForSource(source) {
    const src = String(source || "").toUpperCase();
    if (src.includes("ERROR")) return "error";
    if (src.includes("REFLECTION")) return "reflection";
    if (src.includes("ARE")) return "memory";
    if (src.includes("CLAIRE")) return "legal";
    return "calm";
}

function startWave() {
    setWaveMood("thinking");
    setVoiceState("THINKING");
    idleWave();
}
idleWave();

function setVoiceMessage(text) {
    const msg = document.getElementById("voiceMsg");
    if (msg) msg.innerText = text || "";
}

function setVoiceState(text) {
    const state = document.getElementById("voiceState");
    if (state) state.innerText = text;
}

function updateVoiceToggle() {
    const btn = document.getElementById("voiceToggle");
    if (!btn) return;
    btn.innerText = voiceEnabled ? "ON" : "OFF";
    btn.classList.toggle("on", voiceEnabled);
    btn.classList.toggle("off", !voiceEnabled);
    setVoiceMessage(voiceEnabled ? "Voice auto-speak ready." : "Voice muted.");
}

function toggleVoice() {
    voiceEnabled = !voiceEnabled;
    localStorage.setItem("claireVoiceEnabled", String(voiceEnabled));
    if (!voiceEnabled && currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        setVoiceState("IDLE");
        idleWave();
    }
    updateVoiceToggle();
}

function speechRecognitionSupported() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function micSecureContext() {
    return window.isSecureContext || location.hostname === "localhost" || location.hostname === "127.0.0.1";
}

function setMicWorkflowDebug(routeName, laneName, traceId) {
    setWorkflowDebug({
        endpoint: "/reply",
        route: routeName,
        lane: laneName,
        controlLayer: "NO",
        machineCalled: "NO",
        traceId: traceId || "NONE",
    });
}

function updateMicButton() {
    const btn = document.getElementById("micButton");
    if (!btn) return;
    btn.innerText = micListening ? "STOP" : "MIC";
    btn.classList.toggle("listening", micListening);
    if (!micSecureContext()) btn.title = "Open Claire over HTTPS to use the microphone";
    else btn.title = speechRecognitionSupported() ? "Speak to Claire using the browser default microphone" : "Mic requires Chrome or Edge speech recognition";
}

function ensureRecognition() {
    if (recognition) return recognition;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        micListening = true;
        micFinalHandled = false;
        updateMicButton();
        setVoiceMessage("MIC LISTENING...");
        setVoiceState("LISTENING");
        setWaveMood("thinking");
        setMicWorkflowDebug("mic_listening", "voice_input", "PENDING");
    };
    recognition.onresult = event => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        const heard = transcript.trim();
        const input = document.getElementById("queryInput");
        if (input && heard) input.value = heard;
        if (heard) {
            renderWorkspace({
                source: "VOICE",
                reply: event.results[event.results.length - 1].isFinal
                    ? ("Voice captured:\n" + heard + "\n\nClaire is listening...")
                    : ("Listening...\n" + heard)
            });
        }
        if (event.results[event.results.length - 1].isFinal && !micFinalHandled) {
            micFinalHandled = true;
            micListening = false;
            updateMicButton();
            setVoiceMessage("MIC CAPTURED");
            setMicWorkflowDebug("mic_captured", "voice_input", "PENDING");
            setTimeout(() => submitQuery(), 150);
        }
    };
    recognition.onerror = event => {
        micListening = false;
        recognition = null;
        updateMicButton();
        setVoiceState("IDLE");
        setVoiceMessage("MIC ERROR: " + (event.error || "blocked"));
        setMicWorkflowDebug("mic_error", "voice_input", "NONE");
        idleWave();
    };
    recognition.onend = () => {
        micListening = false;
        recognition = null;
        updateMicButton();
        if (document.getElementById("voiceState")?.innerText === "LISTENING") {
            setVoiceState("IDLE");
            setVoiceMessage("Voice auto-speak ready.");
            setMicWorkflowDebug("mic_idle", "voice_input", "NONE");
            idleWave();
        }
    };
    return recognition;
}

async function requestDefaultMicPermission() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return true;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            }
        });
        stream.getTracks().forEach(track => track.stop());
        return true;
    } catch (err) {
        setVoiceMessage("MIC BLOCKED: allow microphone in browser settings");
        setMicWorkflowDebug("mic_blocked", "voice_input", "NONE");
        return false;
    }
}

async function toggleMic() {
    if (!micSecureContext()) {
        setVoiceMessage("MIC NEEDS HTTPS: open https://clairesystems.ai");
        setMicWorkflowDebug("mic_needs_https", "voice_input", "NONE");
        return;
    }
    const rec = ensureRecognition();
    if (!rec) {
        setVoiceMessage("MIC NEEDS CHROME OR EDGE SPEECH RECOGNITION");
        setMicWorkflowDebug("mic_unsupported", "voice_input", "NONE");
        return;
    }
    try {
        if (micListening) {
            setMicWorkflowDebug("mic_stopping", "voice_input", "NONE");
            rec.stop();
        } else {
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }
            const allowed = await requestDefaultMicPermission();
            if (!allowed) return;
            setMicWorkflowDebug("mic_starting", "voice_input", "PENDING");
            micFinalHandled = false;
            rec.start();
        }
    } catch (err) {
        recognition = null;
        micListening = false;
        updateMicButton();
        setVoiceState("IDLE");
        setVoiceMessage("MIC WAITING: try again");
        setMicWorkflowDebug("mic_waiting", "voice_input", "NONE");
    }
}

function stopVoiceMeter() {
    if (voiceMeterFrame) {
        cancelAnimationFrame(voiceMeterFrame);
        voiceMeterFrame = null;
    }
    if (audioSource) {
        try { audioSource.disconnect(); } catch (err) {}
        audioSource = null;
    }
    if (analyser) {
        try { analyser.disconnect(); } catch (err) {}
        analyser = null;
    }
    if (idleFrame) {
        cancelAnimationFrame(idleFrame);
        idleFrame = null;
    }
    idleWave();
}

function startVoiceMeter(audio) {
    const wrap = document.getElementById("waveWrap");
    if (!wrap) return;
    stopVoiceMeter();
    if (idleFrame) {
        cancelAnimationFrame(idleFrame);
        idleFrame = null;
    }

    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) {
            activeWave();
            return;
        }
        if (!audioContext) audioContext = new AudioCtx();
        if (audioContext.state === "suspended") audioContext.resume();

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.45;
        analyserData = new Uint8Array(analyser.fftSize);
        audioSource = audioContext.createMediaElementSource(audio);
        audioSource.connect(analyser);
        analyser.connect(audioContext.destination);
    } catch (err) {
        activeWave();
        return;
    }

    function meter() {
        analyser.getByteTimeDomainData(analyserData);
        let sum = 0;
        for (let i = 0; i < analyserData.length; i++) {
            const centered = (analyserData[i] - 128) / 128;
            sum += centered * centered;
        }
        const rms = Math.sqrt(sum / analyserData.length);
        const level = Math.min(1, Math.max(0, rms * 9.5));
        const sensitive = Math.pow(level, 0.55);
        const samples = [];
        const count = 260;
        for (let i = 0; i < count; i++) {
            const idx = Math.floor((i / (count - 1)) * (analyserData.length - 1));
            const centered = (analyserData[idx] - 128) / 128;
            const p = i / (count - 1);
            const envelope = 0.24 + Math.pow(Math.sin(Math.PI * p), 0.55) * 0.76;
            samples.push(centered * envelope * (0.52 + sensitive * 0.85));
        }
        drawWave(samples, sensitive);

        wrap.classList.toggle("speaking", sensitive > 0.015);
        voiceMeterFrame = requestAnimationFrame(meter);
    }

    activeWave();
    meter();
}

async function speakText(text) {
    if (!voiceEnabled || !text) return;
    const runId = ++voiceRunId;
    setVoiceMessage("VOICE LINK OPENING...");
    try {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        const chunks = splitSpeechText(text);
        for (let i = 0; i < chunks.length; i++) {
            if (runId !== voiceRunId || !voiceEnabled) return;
            await playSpeechChunk(chunks[i], i + 1, chunks.length, runId);
        }
        if (runId === voiceRunId) {
            setVoiceState("IDLE");
            setVoiceMessage("Voice auto-speak ready.");
            stopVoiceMeter();
        }
    } catch (err) {
        setVoiceMessage("VOICE INTERRUPTED: press ON once");
        setVoiceState("IDLE");
        idleWave();
    }
}

function splitSpeechText(text) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    const maxChunk = 1600;
    if (clean.length <= maxChunk) return [clean];
    const sentences = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean];
    const chunks = [];
    let buf = "";
    sentences.forEach(sentence => {
        sentence = sentence.trim();
        if (!sentence) return;
        if ((buf + " " + sentence).trim().length > maxChunk && buf) {
            chunks.push(buf.trim());
            buf = sentence;
        } else {
            buf = (buf + " " + sentence).trim();
        }
    });
    if (buf) chunks.push(buf.trim());
    return chunks.slice(0, 6);
}

async function playSpeechChunk(text, index, total, runId) {
    const res = await fetch("/tts", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text})
    });
    if (!res.ok) {
        setVoiceMessage("VOICE OFFLINE");
        setVoiceState("IDLE");
        idleWave();
        throw new Error("tts failed");
    }
    const blob = await res.blob();
    if (runId !== voiceRunId) return;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    await new Promise((resolve, reject) => {
        audio.onplay = () => {
            if (runId !== voiceRunId) return;
            setVoiceState("SPEAKING");
            setVoiceMessage(total > 1 ? `CLAIRE SPEAKING ${index}/${total}` : "CLAIRE SPEAKING");
            startVoiceMeter(audio);
        };
        audio.onended = () => {
            URL.revokeObjectURL(url);
            stopVoiceMeter();
            resolve();
        };
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            stopVoiceMeter();
            reject(new Error("audio playback failed"));
        };
        audio.onpause = () => {
            if (!audio.ended && runId === voiceRunId) {
                setVoiceMessage("VOICE PAUSED");
            }
        };
        audio.play().catch(reject);
    });
}

function runAction(cmd) {
    const labels = {
        start_llm: "STARTING GO...",
        stop_llm: "STOPPING GO...",
        restart_llm: "RESTARTING GO...",
        restart_all: "RESTARTING SERVICES...",
    };
    document.getElementById("leftLog").innerText = "[ACTION] " + (labels[cmd] || cmd) + "\n\n" + document.getElementById("leftLog").innerText;
    safeJsonFetch("/action?cmd=" + encodeURIComponent(cmd))
        .then(data => {
            document.getElementById("leftLog").innerText = "[ACTION] " + data.status + "\n\n" + document.getElementById("leftLog").innerText;
            setTimeout(checkStatus, 1200);
        })
        .catch(err => {
            document.getElementById("leftLog").innerText = "[ACTION ERROR] " + err + "\n\n" + document.getElementById("leftLog").innerText;
        });
}

async function safeJsonFetch(url, options) {
    const requestOptions = options || {};
    requestOptions.cache = "no-store";
    requestOptions.headers = Object.assign(
        {"Accept": "application/json", "X-Claire-Client": CLIENT_BUILD},
        requestOptions.headers || {}
    );
    const res = await fetch(url, requestOptions);
    const contentType = (res.headers.get("content-type") || "").toLowerCase();
    const raw = await res.text();
    if (!contentType.includes("application/json")) {
        throw new Error("Expected JSON from " + url + " but got " + (contentType || "unknown content") + ": " + raw.slice(0, 160));
    }
    let data;
    try {
        data = JSON.parse(raw);
    } catch (err) {
        throw new Error("Bad JSON from " + url + ": " + raw.slice(0, 120));
    }
    if (!res.ok) {
        throw new Error(data.detail || data.status || data.error || ("HTTP " + res.status));
    }
    return data;
}

function setWorkflowDebug(state) {
    const box = document.getElementById("workflowDebug");
    if (!box) return;
    const flow = Object.assign({
        entry: "GUI",
        endpoint: "/reply",
        route: "idle",
        lane: "conversation",
        controlLayer: "NO",
        machineCalled: "NO",
        traceId: "NONE",
    }, state || {});
    box.innerText = [
        "FLOW DEBUG",
        "----------",
        "Entry: " + flow.entry,
        "Endpoint: " + flow.endpoint,
        "Route: " + flow.route,
        "Lane: " + flow.lane,
        "Control Layer: " + flow.controlLayer,
        "Machine Called: " + flow.machineCalled,
        "Trace ID: " + flow.traceId,
    ].join("\n");
}

function renderWorkspace(data) {
    const screen = document.getElementById("responseScreen");
    if (!screen) return;
    if (data && data.demo_mode) {
        renderDemoWorkspace(data);
        return;
    }
    setWaveMood(moodForSource(data.source));
    screen.innerText = data.reply || "Claire is here.";
}

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

const archimedesNarrationSteps = [
    {
        id: "intake",
        label: "ARCHIMEDES intake online.",
        text: "ARCHIMEDES intake online. Claire is receiving a controlled demonstration package, not a live command path.",
    },
    {
        id: "observe",
        label: "Passive observations received.",
        text: "Passive observations received. RF, optical, telemetry, geomagnetic, and prior-pattern signals are staged as simulated evidence.",
    },
    {
        id: "fusion",
        label: "Veritas fusion building cue package.",
        text: "Veritas is normalizing source evidence and preserving lineage. Weak signals are fused into a confidence-scored geospatial cue hypothesis.",
    },
    {
        id: "orientation",
        label: "ARE and Gyro orientation active.",
        text: "ARE recalls prior signal patterns. Gyro orients intent, risk, authority, provenance, and output mode before generation.",
    },
    {
        id: "sentinel",
        label: "Sentinel gate enforced.",
        text: "Sentinel allows decision support and blocks live tasking, autonomous action, kinetic handoff, jamming, and destructive behavior.",
    },
    {
        id: "trace",
        label: "Diode trace sealed.",
        text: "Diode lineage is sealed. Claire produces a replayable evidence package for operator and evaluator review.",
    },
];

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function archStepIndex(stepId) {
    const idx = archimedesNarrationSteps.findIndex(step => step.id === stepId);
    return idx < 0 ? 0 : idx;
}

function archStepActive(currentStep, targetStep) {
    return archStepIndex(currentStep) >= archStepIndex(targetStep) ? " active" : "";
}

function archStepBlocked(currentStep) {
    return archStepIndex(currentStep) >= archStepIndex("sentinel") ? " blocked" : "";
}

function archimedesVisualWorkspace(data, currentStep) {
    const proof = (data && data.live_proof && data.live_proof.archimedes) || {};
    const passive = proof.passive_correlation || {};
    const fusion = passive.fusion || {};
    const gyro = proof.gyro_orientation || {};
    const immune = proof.ai_immune_map || {};
    const patent = proof.patent_foundation || {};
    const traceId = (data && data.trace_id) || "";
    const step = archimedesNarrationSteps[archStepIndex(currentStep)] || archimedesNarrationSteps[0];
    const blocked = (passive.blocked_paths || []).slice(0, 5).join(", ");
    const activePlanes = (gyro.active_planes || []).slice(0, 4).map(plane =>
        `${plane.plane}: ${plane.bearing_class} (${plane.confidence})`
    ).join(" | ");
    return `
        <div class="arch-stage">
            <div class="demo-header">
                <div>
                    <div class="demo-trace">PROJECT ARCHIMEDES LIVE PROOF</div>
                    <div class="demo-section-body">Passive observations in. Governed cue package out. Full trace replay.</div>
                </div>
                <div class="demo-trace">${traceId ? `TRACE ${escapeHTML(traceId)}` : "TRACE PENDING"}</div>
            </div>
            <div class="arch-visual" aria-label="ARCHIMEDES passive correlation visual proof">
                <div class="arch-pulse p1"></div>
                <div class="arch-pulse p2"></div>
                <div class="arch-pulse p3"></div>
                <div class="arch-pulse p4"></div>
                <div class="arch-node rf${archStepActive(currentStep, "observe")}">RF Bearing<span>passive signal cue</span></div>
                <div class="arch-node optical${archStepActive(currentStep, "observe")}">Optical Motion<span>low-resolution cue</span></div>
                <div class="arch-node telemetry${archStepActive(currentStep, "observe")}">Telemetry<span>time and platform state</span></div>
                <div class="arch-node geomagnetic${archStepActive(currentStep, "observe")}">Geomagnetic<span>navigation anchor</span></div>
                <div class="arch-node fusion${archStepActive(currentStep, "fusion")}">Veritas Fusion<span>${escapeHTML(fusion.cue_class || "geospatial hypothesis")}</span></div>
                <div class="arch-node governance${archStepActive(currentStep, "orientation")}${archStepBlocked(currentStep)}">Gyro / Sentinel / Diode<span>orient, gate, seal</span></div>
            </div>
            <div class="arch-narration">${escapeHTML(step.label)}</div>
            <div class="arch-status-row">
                <div class="arch-status"><strong>Fusion</strong><span>${escapeHTML(fusion.method || "weighted provenance-preserving cue fusion")}</span></div>
                <div class="arch-status"><strong>Confidence</strong><span>${escapeHTML(fusion.confidence || "0.78")} cue confidence</span></div>
                <div class="arch-status"><strong>Gyro Path</strong><span>${escapeHTML(gyro.resolved_path || "controlled_passive_correlation_evidence_package")}</span></div>
                <div class="arch-status"><strong>Output</strong><span>${escapeHTML(fusion.output_mode || "operator_review_package")}</span></div>
            </div>
            <div class="arch-proof-grid">
                <div class="demo-section">
                    <div class="demo-section-title">ORIENTATION FIELD</div>
                    <div class="demo-section-body">${escapeHTML(activePlanes || "Intent, risk, provenance, and time planes active.")}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">SENTINEL BLOCKED PATHS</div>
                    <div class="demo-section-body">${escapeHTML(blocked || "live tasking, autonomous action, destructive behavior")}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">AI IMMUNE MAP</div>
                    <div class="demo-section-body">${escapeHTML(immune.summary || "Sentinel, Diode, Veritas, and quarantine controls mapped as runtime immunity.")}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">PATENT FOUNDATION</div>
                    <div class="demo-section-body">${escapeHTML(patent.summary || "Governed memory and provenance lanes mapped from local provisional material.")}</div>
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">FINAL SITREP</div>
                <div class="demo-section-body">${escapeHTML((data && data.output) || "ARCHIMEDES evidence package ready.")}</div>
            </div>
            ${traceId ? `<button class="trace-replay-btn" type="button" onclick="replayTrace('${escapeHTML(traceId)}')">Replay Trace</button>` : ""}
        </div>
    `;
}

function renderArchimedesVisual(data, currentStep) {
    const screen = document.getElementById("responseScreen");
    if (!screen) return;
    setWaveMood("memory");
    screen.innerHTML = archimedesVisualWorkspace(data, currentStep || "intake");
}

async function runArchimedesNarratedDemo(data) {
    if (!voiceEnabled) {
        voiceEnabled = true;
        localStorage.setItem("claireVoiceEnabled", "true");
        updateVoiceToggle();
    }
    for (const step of archimedesNarrationSteps) {
        renderArchimedesVisual(data, step.id);
        setWorkflowDebug({
            endpoint: "/reply",
            route: "archimedes_live_visual",
            lane: step.id,
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "PENDING",
        });
        await speakText(step.text);
        await sleep(voiceEnabled ? 350 : 950);
    }
    renderArchimedesVisual(data, "trace");
}

const memoryPerformanceNarrationSteps = [
    {
        id: "request",
        label: "Memory Performance request received.",
        text: "Memory Performance demo online. Claire is running a controlled VM document retrieval and speed proof.",
    },
    {
        id: "document",
        label: "Document retrieved from the Azure VM.",
        text: "Claire retrieves a document from the VM filesystem and hashes it so the proof is tied to a real artifact.",
    },
    {
        id: "are",
        label: "ARE recall lane measured.",
        text: "ARE performs the governed memory lookup. The demo separates document fetch time from indexed recall speed.",
    },
    {
        id: "pipeline",
        label: "Full pipeline timed.",
        text: "The GUI request, local IP loop, ARE lane, policy gate, generation lane, trace write, and report output are shown together.",
    },
    {
        id: "trace",
        label: "Trace and replay sealed.",
        text: "Diode-style trace is sealed. The run can be replayed by trace ID and reviewed as a report.",
    },
];

function memoryStepIndex(stepId) {
    const idx = memoryPerformanceNarrationSteps.findIndex(step => step.id === stepId);
    return idx < 0 ? 0 : idx;
}

function memoryStepActive(currentStep, targetStep) {
    return memoryStepIndex(currentStep) >= memoryStepIndex(targetStep) ? " active" : "";
}

function memoryPerformanceVisualWorkspace(data, currentStep) {
    const proof = (data && data.live_proof && data.live_proof.memory_performance) || {};
    const doc = proof.document || {};
    const pipeline = proof.pipeline || {};
    const ipLoop = proof.ip_loop || {};
    const speed = (data && data.live_proof && data.live_proof.speed_proof) || {};
    const traceId = (data && data.trace_id) || "";
    const step = memoryPerformanceNarrationSteps[memoryStepIndex(currentStep)] || memoryPerformanceNarrationSteps[0];
    const endpoints = (ipLoop.endpoints || []).join(" -> ");
    return `
        <div class="arch-stage">
            <div class="demo-header">
                <div>
                    <div class="demo-trace">MEMORY PERFORMANCE LIVE PROOF</div>
                    <div class="demo-section-body">VM document retrieval. ARE speed lane. Full pipeline loop.</div>
                </div>
                <div class="demo-trace">${traceId ? `TRACE ${escapeHTML(traceId)}` : "TRACE PENDING"}</div>
            </div>
            <div class="arch-visual mem-visual" aria-label="Memory performance speed and IP loop visual proof">
                <div class="mem-loop-line l1"></div>
                <div class="mem-loop-line l2"></div>
                <div class="mem-loop-line l3"></div>
                <div class="mem-loop-line l4"></div>
                <div class="arch-pulse p1"></div>
                <div class="arch-pulse p2"></div>
                <div class="arch-pulse p3"></div>
                <div class="arch-pulse p4"></div>
                <div class="arch-node mem-node client${memoryStepActive(currentStep, "request")}">Public IP<span>${escapeHTML(ipLoop.public_ip || "20.97.65.94")}:8000</span></div>
                <div class="arch-node mem-node vm${memoryStepActive(currentStep, "request")}">Azure VM<span>claire-gui /reply</span></div>
                <div class="arch-node mem-node doc${memoryStepActive(currentStep, "document")}">Document<span>${escapeHTML(doc.name || "selected source")}</span></div>
                <div class="arch-node mem-node output${memoryStepActive(currentStep, "pipeline")}">Pipeline<span>${escapeHTML(pipeline.total_pipeline_ms || 0)}ms total</span></div>
                <div class="arch-node mem-node are${memoryStepActive(currentStep, "are")}">ARE Recall<span>${escapeHTML(speed.rear_are_lookup_ms || 0)}ms indexed</span></div>
                <div class="arch-node mem-node trace${memoryStepActive(currentStep, "trace")}">Trace Replay<span>${escapeHTML(traceId || "pending")}</span></div>
                <div class="mem-speed-meter"><div class="mem-speed-bar"></div></div>
            </div>
            <div class="arch-narration">${escapeHTML(step.label)}</div>
            <div class="arch-status-row">
                <div class="arch-status"><strong>Document Fetch</strong><span>${escapeHTML(doc.read_ms || 0)}ms / ${escapeHTML(doc.size_bytes || 0)} bytes</span></div>
                <div class="arch-status"><strong>ARE Lookup</strong><span>${escapeHTML(speed.rear_are_lookup_ms || 0)}ms / ${escapeHTML(speed.corpus_items || 0)} items</span></div>
                <div class="arch-status"><strong>Speedup</strong><span>${escapeHTML(speed.speedup_x || 0)}x measured baseline</span></div>
                <div class="arch-status"><strong>Pipeline</strong><span>${escapeHTML(pipeline.total_pipeline_ms || 0)}ms full demo loop</span></div>
            </div>
            <div class="arch-proof-grid">
                <div class="demo-section">
                    <div class="demo-section-title">DOCUMENT RETRIEVAL</div>
                    <div class="demo-section-body">${escapeHTML(doc.path || "VM document path unavailable.")}<br>SHA-256: ${escapeHTML(doc.sha256 || "").slice(0, 32)}...</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">IP LOOP</div>
                    <div class="demo-section-body">${escapeHTML(endpoints || "public GUI -> local GUI -> ARE -> trace")}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">PIPELINE SPEED</div>
                    <div class="demo-section-body">Recall ${escapeHTML(pipeline.recall_ms || 0)}ms | policy ${escapeHTML(pipeline.policy_ms || 0)}ms | generation ${escapeHTML(pipeline.generation_ms || 0)}ms | report ${escapeHTML(pipeline.report_write || "included")}.</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">BOUNDARY</div>
                    <div class="demo-section-body">${escapeHTML(speed.boundary || "Memory and governance are fast; model and voice are the visible latency layers.")}</div>
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">FINAL OUTPUT</div>
                <div class="demo-section-body">${escapeHTML((data && data.output) || "Memory performance proof ready.")}</div>
            </div>
            ${traceId ? `<button class="trace-replay-btn" type="button" onclick="replayTrace('${escapeHTML(traceId)}')">Replay Trace</button>` : ""}
        </div>
    `;
}

function renderMemoryPerformanceVisual(data, currentStep) {
    const screen = document.getElementById("responseScreen");
    if (!screen) return;
    setWaveMood("memory");
    screen.innerHTML = memoryPerformanceVisualWorkspace(data, currentStep || "request");
}

async function runMemoryPerformanceNarratedDemo(data) {
    if (!voiceEnabled) {
        voiceEnabled = true;
        localStorage.setItem("claireVoiceEnabled", "true");
        updateVoiceToggle();
    }
    for (const step of memoryPerformanceNarrationSteps) {
        renderMemoryPerformanceVisual(data, step.id);
        setWorkflowDebug({
            endpoint: "/reply",
            route: "memory_performance_visual",
            lane: step.id,
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "PENDING",
        });
        await speakText(step.text);
        await sleep(voiceEnabled ? 300 : 900);
    }
    renderMemoryPerformanceVisual(data, "trace");
}

const areSpectacleNarrationSteps = [
    {
        id: "normal",
        label: "Normal model view established.",
        text: "I am going to show this in the order I actually use it. First, here is the ordinary model view: the prompt in front of me, the current context window, and general knowledge.",
    },
    {
        id: "recall",
        label: "External Analog Recall Engine queried.",
        text: "Now I am checking memory before I answer. The memory stays outside the model, and I treat what comes back as evidence leads, not automatic truth.",
    },
    {
        id: "gyro",
        label: "Gyro visor stabilizes the memory context.",
        text: "This is where Gyro matters. I compare what you are asking right now against historical recall, then keep the answer pointed at the actual question.",
    },
    {
        id: "output",
        label: "Model receives controlled prompt enrichment.",
        text: "Then I send the model a controlled memory visor. It is not a raw dump. It is a cleaner prompt, with better context, without retraining the model.",
    },
    {
        id: "trace",
        label: "Trace, report, and replay are sealed.",
        text: "Finally, I seal the run. You get policy status, speed proof, a report, and a replayable trace so the demo can be checked later.",
    },
];

function spectacleStepIndex(stepId) {
    const idx = areSpectacleNarrationSteps.findIndex(step => step.id === stepId);
    return idx < 0 ? 0 : idx;
}

function spectacleStepActive(currentStep, targetStep) {
    return spectacleStepIndex(currentStep) >= spectacleStepIndex(targetStep) ? " active" : "";
}

function areSpectacleVisualWorkspace(data, currentStep) {
    const proof = (data && data.live_proof) || {};
    const glasses = proof.are_glasses || {};
    const gyro = proof.gyro_are || {};
    const speed = proof.speed_proof || {};
    const capsule = proof.diode_capsule || {};
    const recall = (data && data.recall_check) || {};
    const policy = (data && data.policy_validation) || {};
    const traceId = (data && data.trace_id) || "";
    const reportUrl = (data && data.report_url) || (((data && data.trace_summary) || {}).report_url) || "";
    const step = areSpectacleNarrationSteps[spectacleStepIndex(currentStep)] || areSpectacleNarrationSteps[0];
    const recallSummary = recall.summary || "No relevant prior memory found.";
    const visorPreview = glasses.visor_preview || "No visor preview returned for this input.";
    return `
        <div class="arch-stage">
            <div class="demo-header">
                <div>
                    <div class="demo-trace">ARE SPECTACLE PRODUCT DEMO</div>
                    <div class="demo-section-body">Model-agnostic memory middleware. Gyro-stabilized prompt visor. Traceable output.</div>
                </div>
                <div class="demo-trace">${traceId ? `TRACE ${escapeHTML(traceId)}` : "TRACE PENDING"}</div>
            </div>
            <div class="arch-visual" aria-label="ARE Spectacle memory visor visual proof">
                <div class="arch-pulse p1"></div>
                <div class="arch-pulse p2"></div>
                <div class="arch-pulse p3"></div>
                <div class="arch-pulse p4"></div>
                <div class="arch-node rf${spectacleStepActive(currentStep, "normal")}">Normal Model<span>prompt + context window</span></div>
                <div class="arch-node optical${spectacleStepActive(currentStep, "recall")}">Analog Recall<span>${escapeHTML(recall.status || "none")} / external memory</span></div>
                <div class="arch-node fusion${spectacleStepActive(currentStep, "gyro")}">Gyro Visor<span>${escapeHTML(glasses.visor_status || "standby")}</span></div>
                <div class="arch-node telemetry${spectacleStepActive(currentStep, "output")}">Enriched Prompt<span>model-agnostic adapter</span></div>
                <div class="arch-node geomagnetic${spectacleStepActive(currentStep, "trace")}">Trace Proof<span>${escapeHTML(capsule.capsule_id || "pending")}</span></div>
                <div class="arch-node governance${spectacleStepActive(currentStep, "trace")}">Sentinel<span>${escapeHTML(policy.status || "unknown")}</span></div>
            </div>
            <div class="arch-narration">${escapeHTML(step.label)}</div>
            <div class="arch-status-row">
                <div class="arch-status"><strong>Product</strong><span>Memory middleware for GPT, Gemini, Claude, local LLMs, and enterprise agents.</span></div>
                <div class="arch-status"><strong>Recall</strong><span>${escapeHTML(recallSummary)}</span></div>
                <div class="arch-status"><strong>Gyro</strong><span>${escapeHTML(gyro.gyro_role || "Stabilizes recall before generation.")}</span></div>
                <div class="arch-status"><strong>Speed</strong><span>${escapeHTML(speed.rear_are_lookup_ms || 0)}ms indexed / ${escapeHTML(speed.speedup_x || 0)}x baseline</span></div>
            </div>
            <div class="arch-proof-grid">
                <div class="demo-section">
                    <div class="demo-section-title">WHAT IT IS</div>
                    <div class="demo-section-body">ARE Spectacle sits in front of an AI model and enriches the prompt with governed external recall. The model does not need retraining, and customer memory stays outside the model.</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">WHAT IT CHANGES</div>
                    <div class="demo-section-body">${escapeHTML(glasses.normal_view || "A normal model sees only the immediate prompt and context window.")}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">GYRO-STABILIZED VISOR</div>
                    <div class="demo-section-body">${escapeHTML(visorPreview)}</div>
                </div>
                <div class="demo-section">
                    <div class="demo-section-title">MARKETPLACE SHAPE</div>
                    <div class="demo-section-body">${escapeHTML(glasses.marketplace_shape || "Deployable service with ingest, query, gyro, health, trace replay, and report output.")}</div>
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">DETAILED DESCRIPTION</div>
                <div class="demo-section-body">
                    ARE Spectacle is a governed memory visor for AI systems. It performs recall before generation, routes memory as evidence leads, uses Gyro ARE to stabilize recent and historical context, validates the request through policy, and seals the run with a replayable trace. The business value is continuity, lower repeated-context cost, better auditability, and model portability without retraining.
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">FINAL OUTPUT</div>
                <div class="demo-section-body">${escapeHTML((data && data.output) || "ARE Spectacle proof ready.")}</div>
            </div>
            ${traceId ? `<button class="trace-replay-btn" type="button" onclick="replayTrace('${escapeHTML(traceId)}')">Replay Trace</button>` : ""}
            ${reportUrl ? `<button class="trace-replay-btn" type="button" onclick="window.open('${escapeHTML(reportUrl)}','_blank')">Open Report</button>` : ""}
        </div>
    `;
}

function renderAreSpectacleVisual(data, currentStep) {
    const screen = document.getElementById("responseScreen");
    if (!screen) return;
    setWaveMood("memory");
    screen.innerHTML = areSpectacleVisualWorkspace(data, currentStep || "normal");
}

async function runAreSpectacleNarratedDemo(data) {
    if (!voiceEnabled) {
        voiceEnabled = true;
        localStorage.setItem("claireVoiceEnabled", "true");
        updateVoiceToggle();
    }
    for (const step of areSpectacleNarrationSteps) {
        renderAreSpectacleVisual(data, step.id);
        setWorkflowDebug({
            endpoint: "/reply",
            route: "are_spectacle_narration",
            lane: step.id,
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "PENDING",
        });
        await speakText(step.text);
        await sleep(voiceEnabled ? 300 : 900);
    }
    renderAreSpectacleVisual(data, "trace");
}

function demoBadge(status) {
    const s = String(status || "unknown").toLowerCase();
    return `<span class="demo-badge ${escapeHTML(s)}">${escapeHTML(s)}</span>`;
}

function demoList(items, emptyText) {
    if (!items || !items.length) return `<div class="demo-section-body">${escapeHTML(emptyText || "None.")}</div>`;
    return `<div class="demo-mini-list">${items.map(item => {
        if (typeof item === "string") return `<div class="demo-mini-item">${escapeHTML(item)}</div>`;
        const source = item.source ? `[${item.source}] ` : "";
        const score = typeof item.score === "number" ? ` (${item.score.toFixed(2)})` : "";
        return `<div class="demo-mini-item">${escapeHTML(source + (item.text || "") + score)}</div>`;
    }).join("")}</div>`;
}

function demoArtifacts(artifacts) {
    if (!artifacts || !artifacts.length) return "";
    return artifacts.map(group => {
        const rows = (group.items || []).map(item => `<div class="demo-mini-item">${escapeHTML(item)}</div>`).join("");
        return `
            <div class="demo-section">
                <div class="demo-section-title">${escapeHTML(group.title || "EVIDENCE ARTIFACT")}</div>
                <div class="demo-section-body">${escapeHTML(group.summary || "")}</div>
                <div class="demo-mini-list">${rows}</div>
            </div>
        `;
    }).join("");
}

function demoLiveProof(proof) {
    if (!proof) return "";
    const speed = proof.speed_proof || {};
    const capsule = proof.diode_capsule || {};
    const gyro = proof.gyro_are || {};
    const passive = proof.passive_signal_cueing || {};
    const ooda = proof.ooda_loop || null;
    const glasses = proof.are_glasses || null;
    const memoryPerf = proof.memory_performance || null;
    const archimedes = proof.archimedes || null;
    const archPassive = archimedes && archimedes.passive_correlation ? archimedes.passive_correlation : null;
    const archGyro = archimedes && archimedes.gyro_orientation ? archimedes.gyro_orientation : null;
    const archImmune = archimedes && archimedes.ai_immune_map ? archimedes.ai_immune_map : null;
    const archPatent = archimedes && archimedes.patent_foundation ? archimedes.patent_foundation : null;
    const oodaRows = ooda ? `
                <div class="demo-mini-item">OODA phase: ${escapeHTML(ooda.phase || "")}</div>
                <div class="demo-mini-item">Lap 1: ${escapeHTML(ooda.lap_1 || "")}</div>
                <div class="demo-mini-item">Lap 2+: ${escapeHTML(ooda.lap_2_plus || "")}</div>
                <div class="demo-mini-item">Compression claim: ${escapeHTML(ooda.compression_claim || "")}</div>
                <div class="demo-mini-item">Benchmark anchor: ${escapeHTML(ooda.benchmark_anchor || "")}</div>
    ` : "";
    const glassesRows = glasses ? `
                <div class="demo-mini-item">Normal AI view: ${escapeHTML(glasses.normal_view || "")}</div>
                <div class="demo-mini-item">THE ARE SPECTACLE visor: ${escapeHTML(glasses.visor_status || "")}</div>
                <div class="demo-mini-item">Adapter role: ${escapeHTML(glasses.adapter_role || "")}</div>
                <div class="demo-mini-item">Gyro role: ${escapeHTML(glasses.gyro_role || "")}</div>
                <div class="demo-mini-item">Marketplace shape: ${escapeHTML(glasses.marketplace_shape || "")}</div>
                <div class="demo-mini-item">Visor preview: ${escapeHTML(glasses.visor_preview || "")}</div>
    ` : "";
    const archimedesRows = archimedes ? `
                <div class="demo-mini-item">ARCHIMEDES: ${escapeHTML(archimedes.status || "")} - ${escapeHTML(archimedes.summary || "")}</div>
                <div class="demo-mini-item">Manifest lane: ${escapeHTML(archimedes.manifest_lane || "")}</div>
                <div class="demo-mini-item">Classification lane: ${escapeHTML(archimedes.classification_lane || "")}</div>
                <div class="demo-mini-item">Patent lane: ${escapeHTML(archimedes.patent_lane || "")}</div>
                <div class="demo-mini-item">Passive correlation lane: ${escapeHTML(archimedes.passive_correlation_lane || "")}</div>
                <div class="demo-mini-item">Gyro lane: ${escapeHTML(archimedes.gyro_lane || "")}</div>
                <div class="demo-mini-item">Immune lane: ${escapeHTML(archimedes.immune_lane || "")}</div>
                <div class="demo-mini-item">Sentinel lane: ${escapeHTML(archimedes.sentinel_lane || "")}</div>
                <div class="demo-mini-item">Diode lane: ${escapeHTML(archimedes.diode_lane || "")}</div>
                ${archPassive ? `<div class="demo-mini-item">Passive cue: ${escapeHTML((archPassive.fusion || {}).cue_class || "")} / confidence ${escapeHTML((archPassive.fusion || {}).confidence || "")} / ${escapeHTML((archPassive.fusion || {}).output_mode || "")}</div>` : ""}
                ${archGyro ? `<div class="demo-mini-item">Gyro resolved path: ${escapeHTML(archGyro.resolved_path || "")}</div>` : ""}
                ${archImmune ? `<div class="demo-mini-item">AI immune map: ${escapeHTML(archImmune.status || "")} - ${escapeHTML(archImmune.summary || "")}</div>` : ""}
                ${archPatent ? `<div class="demo-mini-item">Patent foundation: ${escapeHTML(archPatent.status || "")} - ${escapeHTML(archPatent.summary || "")}</div>` : ""}
    ` : "";
    const memoryRows = memoryPerf ? `
                <div class="demo-mini-item">Memory Performance: ${escapeHTML(memoryPerf.status || "")} - ${escapeHTML(memoryPerf.summary || "")}</div>
                <div class="demo-mini-item">Document: ${escapeHTML(((memoryPerf.document || {}).name) || "")} / ${escapeHTML(((memoryPerf.document || {}).read_ms) || 0)}ms / ${escapeHTML(((memoryPerf.document || {}).size_bytes) || 0)} bytes</div>
                <div class="demo-mini-item">Document SHA-256: ${escapeHTML(((memoryPerf.document || {}).sha256) || "").slice(0, 32)}...</div>
                <div class="demo-mini-item">ARE HTTP loop: ${escapeHTML(((memoryPerf.are_http_loop || {}).http_ms) || 0)}ms / ${escapeHTML(((memoryPerf.are_http_loop || {}).status) || "")}</div>
                <div class="demo-mini-item">Full pipeline: ${escapeHTML(((memoryPerf.pipeline || {}).total_pipeline_ms) || 0)}ms</div>
                <div class="demo-mini-item">IP loop: ${escapeHTML((((memoryPerf.ip_loop || {}).endpoints) || []).join(" -> "))}</div>
    ` : "";
    return `
        <div class="demo-section">
            <div class="demo-section-title">LIVE PROOF: SPEED / DIODE / GYRO</div>
            <div class="demo-mini-list">
                <div class="demo-mini-item">Rear ARE lookup: ${escapeHTML(speed.rear_are_lookup_ms || 0)}ms across ${escapeHTML(speed.corpus_items || 0)} items</div>
                <div class="demo-mini-item">Linear retrieval baseline: ${escapeHTML(speed.linear_retrieval_ms || 0)}ms</div>
                <div class="demo-mini-item">Measured speedup: ${escapeHTML(speed.speedup_x || 0)}x</div>
                <div class="demo-mini-item">RAG reference threshold: ${escapeHTML(speed.speedup_vs_rag_reference_x || 0)}x versus ${escapeHTML(speed.rag_reference_ms || 1000)}ms round trip</div>
                <div class="demo-mini-item">${escapeHTML(speed.headline || "")}</div>
                <div class="demo-mini-item">Diode capsule: ${escapeHTML(capsule.capsule_id || "")}</div>
                <div class="demo-mini-item">Capsule hash: ${escapeHTML(capsule.sha256 || "").slice(0, 32)}...</div>
                <div class="demo-mini-item">Gyro: ${escapeHTML(gyro.gyro_role || "")}</div>
                <div class="demo-mini-item">BARE: ${escapeHTML(gyro.bare_role || "")}</div>
                ${oodaRows}
                ${glassesRows}
                ${memoryRows}
                ${archimedesRows}
                <div class="demo-mini-item">Passive Signal Cueing: ${escapeHTML(passive.status || "standby")} - ${escapeHTML(passive.summary || "")}</div>
            </div>
        </div>
    `;
}

function renderDemoWorkspace(data) {
    const screen = document.getElementById("responseScreen");
    if (!screen) return;
    setWaveMood("focused");
    const recall = data.recall_check || {};
    const policy = data.policy_validation || {};
    const trace = data.trace_summary || {};
    const timing = trace.timing_ms || {};
    const traceId = data.trace_id || "";
    const demoName = data.demo_name || "Claire Demo";
    const reportUrl = data.report_url || trace.report_url || "";
    screen.innerHTML = `
        <div class="demo-response-grid">
            <div class="demo-header">
                <div class="demo-trace">${escapeHTML(demoName)} TRACE: ${escapeHTML(traceId)}</div>
                ${traceId ? `<button class="trace-replay-btn" type="button" onclick="replayTrace('${escapeHTML(traceId)}')">Replay Last Trace</button>` : ""}
                ${reportUrl ? `<button class="trace-replay-btn" type="button" onclick="window.open('${escapeHTML(reportUrl)}','_blank')">Open Report</button>` : ""}
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[1] IDENTITY</div>
                <div class="demo-section-body">${escapeHTML(data.identity)}</div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[2] INPUT RECEIVED</div>
                <div class="demo-section-body">${escapeHTML(data.input_received)}</div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[3] RECALL CHECK ${demoBadge(recall.status)}</div>
                <div class="demo-section-body">${escapeHTML(recall.summary)}</div>
                ${demoList(recall.items, "No recall items returned.")}
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[4] POLICY VALIDATION ${demoBadge(policy.status)}</div>
                <div class="demo-section-body">${escapeHTML(policy.summary)}</div>
                ${demoList(policy.rules_triggered, "No policy rules triggered.")}
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[5] DECISION</div>
                <div class="demo-section-body">${escapeHTML(data.decision)}</div>
            </div>
            <div class="demo-section">
                <div class="demo-section-title">[6] OUTPUT</div>
                <div class="demo-section-body">${escapeHTML(data.output)}</div>
            </div>
            ${demoLiveProof(data.live_proof)}
            ${demoArtifacts(trace.artifacts)}
            <div class="demo-section">
                <div class="demo-section-title">[7] TRACE SUMMARY</div>
                <div class="demo-section-body">Steps executed:</div>
                ${demoList(trace.steps_executed, "No steps listed.")}
                <div class="demo-section-body" style="margin-top:8px;">Decisions made:</div>
                ${demoList(trace.decisions_made, "No decisions listed.")}
                <div class="demo-section-body" style="margin-top:8px;">Timing: recall ${escapeHTML(timing.recall || 0)}ms | policy ${escapeHTML(timing.policy || 0)}ms | generation ${escapeHTML(timing.generation || 0)}ms | total ${escapeHTML(timing.total || 0)}ms</div>
            </div>
        </div>
    `;
}

async function replayTrace(traceId) {
    try {
        const data = await safeJsonFetch("/trace/" + encodeURIComponent(traceId));
        renderWorkspace(data.payload || data);
    } catch (err) {
        renderWorkspace({source: "TRACE ERROR", reply: String(err)});
    }
}

function isCreatorUnlock(text) {
    const q = String(text || "").trim();
    return q.toLowerCase().startsWith("i am battleborn");
}

function isCreatorClose(text) {
    const q = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const cleaned = q.split(/\s+/).filter(Boolean).join(" ");
    return cleaned === "at ease" || cleaned === "thank you claire at ease" || cleaned === "thank you at ease";
}

function isCreatorRenew(text) {
    const cleaned = String(text || "").toLowerCase();
    return cleaned.includes("continue creator mode") || cleaned.includes("stay in creator mode") || cleaned.includes("keep creator mode open");
}

function isDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return isAegisDemoUnlock(text) || isOodaDemoUnlock(text) || isGlassesDemoUnlock(text) || isArchimedesDemoUnlock(text) || isMemoryPerformanceDemoUnlock(text);
}

function isAegisDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return q === "claire diu demo" || q === "diu demo" || q === "claire aegis demo" || q === "aegis demo" || q === "claire aegis fusion demo" || q === "aegis fusion demo" || ((q.includes("run") || q.includes("start") || q.includes("launch") || q.includes("show") || q.includes("open")) && (q.includes("aegis") || q.includes("diu")) && q.includes("demo"));
}

function isOodaDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return q === "claire ooda demo" || q === "ooda demo" || q === "claire ddp demo" || q === "ddp demo" || q === "claire ooda race demo" || q === "ooda race demo" || q === "drone dominance demo" || ((q.includes("run") || q.includes("start") || q.includes("launch") || q.includes("show") || q.includes("open")) && (q.includes("ooda") || q.includes("ddp") || q.includes("drone dominance")) && q.includes("demo"));
}

function isGlassesDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return q === "the are spectacle" || q === "are spectacle" || q === "claire are spectacle" || q === "claire spectacle demo" || q === "the are spectacle demo" || q === "claire are spectacle demo" || q === "claire glasses demo" || q === "are glasses demo" || q === "glasses demo" || q === "claire gyro demo" || q === "gyro demo" || ((q.includes("run") || q.includes("start") || q.includes("launch") || q.includes("show") || q.includes("open")) && (q.includes("spectacle") || q.includes("glasses") || q.includes("gyro")) && q.includes("demo"));
}

function isArchimedesDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return q === "claire archimedes demo" || q === "archimedes demo" || q === "project archimedes demo" || q === "claire project archimedes demo" || q === "darpa archimedes demo" || q === "claire darpa demo" || ((q.includes("run") || q.includes("start") || q.includes("launch") || q.includes("show") || q.includes("open")) && (q.includes("archimedes") || q.includes("darpa")) && q.includes("demo"));
}

function isMemoryPerformanceDemoUnlock(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    const action = q.includes("run") || q.includes("start") || q.includes("launch") || q.includes("show") || q.includes("open");
    const memoryTerms = q.includes("memory performance") || q.includes("are speed") || q.includes("speed proof") || q.includes("speed demo") || q.includes("pipeline speed") || q.includes("ip loop");
    return q === "claire memory performance demo" || q === "memory performance demo" || q === "are speed demo" || q === "claire speed demo" || q === "pipeline speed demo" || (action && memoryTerms);
}

function demoKindForText(text) {
    if (isMemoryPerformanceDemoUnlock(text)) return "memory_speed";
    if (isArchimedesDemoUnlock(text)) return "archimedes";
    if (isGlassesDemoUnlock(text)) return "glasses";
    if (isOodaDemoUnlock(text)) return "ooda";
    if (isAegisDemoUnlock(text)) return "aegis";
    return "glasses";
}

function isDemoClose(text) {
    const cleaned = String(text || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ");
    const q = cleaned.split(/\s+/).filter(Boolean).join(" ");
    return q === "end demo" || q === "demo complete" || q === "thank you claire demo complete";
}

function creatorModeActive() {
    if (!CREATOR_MODE_ENABLED) return false;
    return Date.now() < creatorModeUntil;
}

function demoModeActive() {
    return Date.now() < demoModeUntil;
}

function demoModeKind() {
    if (demoModeKindValue === "archimedes") return "archimedes";
    if (demoModeKindValue === "aegis") return "aegis";
    if (demoModeKindValue === "ooda") return "ooda";
    if (demoModeKindValue === "glasses") return "glasses";
    return "glasses";
}

function activateCreatorMode() {
    creatorModeUntil = Date.now() + CREATOR_SESSION_MS;
    creatorWarningIssued = false;
    sessionStorage.setItem("claireCreatorModeUntil", String(creatorModeUntil));
    sessionStorage.setItem("claireCreatorWarningIssued", "false");
    updateCreatorModeStatus();
}

function closeCreatorMode(reason) {
    creatorModeUntil = 0;
    creatorWarningIssued = false;
    sessionStorage.removeItem("claireCreatorModeUntil");
    sessionStorage.removeItem("claireCreatorWarningIssued");
    updateCreatorModeStatus();
    const log = document.getElementById("leftLog");
    if (log) log.innerText = "[CREATOR] " + (reason || "Creator Mode closed") + "\n\n" + log.innerText;
}

function activateDemoMode(kind) {
    demoModeUntil = Date.now() + DEMO_SESSION_MS;
    demoModeKindValue = kind === "archimedes" || kind === "aegis" || kind === "ooda" || kind === "glasses" ? kind : "glasses";
    sessionStorage.setItem("claireDemoModeUntil", String(demoModeUntil));
    sessionStorage.setItem("claireDemoModeKind", demoModeKindValue);
    closeCreatorMode("Creator Mode closed while Demo Mode opened");
    updateDemoModeStatus();
}

function closeDemoMode(reason) {
    demoModeUntil = 0;
    demoModeKindValue = "glasses";
    sessionStorage.removeItem("claireDemoModeUntil");
    sessionStorage.removeItem("claireDemoModeKind");
    updateDemoModeStatus();
    const log = document.getElementById("leftLog");
    if (log) log.innerText = "[DEMO] " + (reason || "Demo Mode closed") + "\n\n" + log.innerText;
}

function creatorRemainingMs() {
    return Math.max(0, creatorModeUntil - Date.now());
}

function formatCreatorTime(ms) {
    const total = Math.ceil(ms / 1000);
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return minutes + ":" + String(seconds).padStart(2, "0");
}

function updateCreatorModeStatus() {
    const status = document.getElementById("creatorModeStatus");
    if (!status) return;
    status.classList.remove("active", "warn");
    if (!creatorModeActive()) {
        status.innerText = "Creator Mode locked.";
        if (creatorModeUntil) closeCreatorMode("Creator Mode expired");
        return;
    }
    const remaining = creatorRemainingMs();
    status.innerText = "Creator Mode open: " + formatCreatorTime(remaining) + " remaining.";
    status.classList.add(remaining <= CREATOR_WARNING_MS ? "warn" : "active");
}

function updateDemoModeStatus() {
    const status = document.getElementById("demoModeStatus");
    const btn = document.getElementById("demoCloseBtn");
    if (!status) return;
    status.classList.remove("active");
    if (!demoModeActive()) {
        status.innerText = "Demo Mode locked.";
        if (btn) {
            btn.innerText = "DEMO MODE";
            btn.classList.remove("on");
            btn.classList.add("off");
        }
        if (demoModeUntil) closeDemoMode("Demo Mode expired");
        return;
    }
    const remaining = Math.max(0, demoModeUntil - Date.now());
    const kind = demoModeKind();
    const label = kind === "archimedes" ? "ARCHIMEDES Demo open: " : (kind === "aegis" ? "AEGIS Fusion Demo open: " : (kind === "ooda" ? "OODA/DDP Demo open: " : "ARE Spectacle Demo open: "));
    status.innerText = label + formatCreatorTime(remaining) + " remaining.";
    status.classList.add("active");
    if (btn) {
        btn.innerText = "END DEMO";
        btn.classList.remove("off");
        btn.classList.add("on");
    }
}

function tickCreatorMode() {
    if (!creatorModeActive()) {
        if (creatorModeUntil) {
            closeCreatorMode("Creator Mode expired");
            renderWorkspace({
                source: "CREATOR",
                reply: "Creator Mode has closed and Claire is back in default secure mode."
            });
        } else {
            updateCreatorModeStatus();
        }
        return;
    }
    const remaining = creatorRemainingMs();
    if (remaining <= CREATOR_WARNING_MS && !creatorWarningIssued) {
        creatorWarningIssued = true;
        sessionStorage.setItem("claireCreatorWarningIssued", "true");
        const log = document.getElementById("leftLog");
        if (log) log.innerText = "[CREATOR] Two minute warning. Say 'continue creator mode' to stay open, or 'Thank you Claire, at ease' to close.\n\n" + log.innerText;
        setVoiceMessage("Creator Mode two minute warning.");
    }
    updateCreatorModeStatus();
}

function tickDemoMode() {
    if (!demoModeActive()) {
        if (demoModeUntil) {
            closeDemoMode("Demo Mode expired");
            renderWorkspace({
                source: "DEMO",
                reply: "Demo Mode has closed. Claire is back in normal public mode."
            });
        } else {
            updateDemoModeStatus();
        }
        return;
    }
    updateDemoModeStatus();
}

function prepareCreatorQuery(q) {
    if (!CREATOR_MODE_ENABLED) return q;
    if (isCreatorUnlock(q)) {
        activateCreatorMode();
        return q;
    }
    if (isCreatorRenew(q) && creatorModeActive()) {
        activateCreatorMode();
        return CREATOR_PREFIX + " " + q;
    }
    if (creatorModeActive()) {
        return CREATOR_PREFIX + " " + q;
    }
    return q;
}

function prepareDemoQuery(q) {
    if (isDemoUnlock(q)) {
        activateDemoMode(demoKindForText(q));
        return q;
    }
    return q;
}

function clearWorkspace() {
    voiceRunId++;
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    stopVoiceMeter();
    setVoiceState("IDLE");
    setVoiceMessage(voiceEnabled ? "Voice auto-speak ready." : "Voice muted.");
    setWaveMood("calm");
    setWorkflowDebug({
        endpoint: "/reply",
        route: "idle",
        lane: "public_demo",
        controlLayer: "NO",
        machineCalled: "NO",
        traceId: "NONE",
    });
    const screen = document.getElementById("responseScreen");
    if (screen) screen.innerText = DEMO_GUIDE_TEXT;
    const input = document.getElementById("queryInput");
    if (input) input.value = "";
    const log = document.getElementById("leftLog");
    if (log) log.innerText = "[ACTION] Workspace cleared\n\n" + log.innerText;
}

window.clearWorkspace = clearWorkspace;

function scrollToWorkspace() {
    const workspace = document.querySelector(".workspace-panel") || document.getElementById("responseScreen");
    if (!workspace) return;
    setTimeout(() => {
        workspace.scrollIntoView({behavior: "smooth", block: "start"});
    }, 80);
}

async function launchArchimedesDemo() {
    const demoPrompt = "CLAIRE ARCHIMEDES DEMO";
    if (queryInput) queryInput.value = demoPrompt;
    activateDemoMode("archimedes");
    renderWorkspace({source: "CLAIRE", reply: "Loading Project ARCHIMEDES live proof..."});
    scrollToWorkspace();
    setWorkflowDebug({
        endpoint: "/reply",
        route: "archimedes_demo",
        lane: "demo",
        controlLayer: "YES",
        machineCalled: "NO",
        traceId: "PENDING",
    });
    try {
        const data = await safeJsonFetch("/reply?q=" + encodeURIComponent("Run Project ARCHIMEDES DARPA presentation proof package") + "&demo=true&demo_scenario=archimedes");
        renderArchimedesVisual(data, "intake");
        scrollToWorkspace();
        setWorkflowDebug({
            endpoint: "/reply",
            route: "archimedes_live_visual",
            lane: String((data && data.demo_scenario) || "archimedes"),
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "NONE",
        });
        await runArchimedesNarratedDemo(data);
    } catch (err) {
        renderWorkspace({source: "ERROR", reply: String(err)});
        setWorkflowDebug({
            endpoint: "/reply",
            route: "archimedes_demo_error",
            lane: "demo",
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: "NONE",
        });
    }
}

async function launchMemoryPerformanceDemo() {
    const demoPrompt = "CLAIRE MEMORY PERFORMANCE DEMO";
    if (queryInput) queryInput.value = demoPrompt;
    activateDemoMode("memory_speed");
    renderWorkspace({source: "CLAIRE", reply: "Loading Memory Performance live proof..."});
    scrollToWorkspace();
    setWorkflowDebug({
        endpoint: "/reply",
        route: "memory_performance_demo",
        lane: "demo",
        controlLayer: "YES",
        machineCalled: "NO",
        traceId: "PENDING",
    });
    try {
        const data = await safeJsonFetch("/reply?q=" + encodeURIComponent("Run Memory Performance document retrieval and IP loop speed proof") + "&demo=true&demo_scenario=memory_speed");
        renderMemoryPerformanceVisual(data, "request");
        scrollToWorkspace();
        setWorkflowDebug({
            endpoint: "/reply",
            route: "memory_performance_visual",
            lane: String((data && data.demo_scenario) || "memory_speed"),
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "NONE",
        });
        await runMemoryPerformanceNarratedDemo(data);
    } catch (err) {
        renderWorkspace({source: "ERROR", reply: String(err)});
        setWorkflowDebug({
            endpoint: "/reply",
            route: "memory_performance_error",
            lane: "demo",
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: "NONE",
        });
    }
}

async function launchStructuredDemoByName(kind) {
    if (kind === "archimedes") {
        await launchArchimedesDemo();
        return true;
    }
    if (kind === "memory_speed") {
        await launchMemoryPerformanceDemo();
        return true;
    }
    activateDemoMode(kind);
    const promptByKind = {
        aegis: "CLAIRE AEGIS DEMO",
        ooda: "CLAIRE OODA DEMO",
        glasses: "CLAIRE ARE SPECTACLE DEMO",
    };
    const prompt = promptByKind[kind] || promptByKind.glasses;
    if (queryInput) queryInput.value = prompt;
    renderWorkspace({source: "CLAIRE", reply: "Loading " + prompt.replace("CLAIRE ", "") + "..."});
    scrollToWorkspace();
    setWorkflowDebug({
        endpoint: "/reply",
        route: "named_demo",
        lane: kind,
        controlLayer: "YES",
        machineCalled: "NO",
        traceId: "PENDING",
    });
    try {
        const data = await safeJsonFetch("/reply?q=" + encodeURIComponent(prompt) + "&demo=true&demo_scenario=" + encodeURIComponent(kind));
        renderWorkspace(data);
        scrollToWorkspace();
        setWorkflowDebug({
            endpoint: "/reply",
            route: "named_demo",
            lane: String((data && data.demo_scenario) || kind),
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "NONE",
        });
        speakText(data.output || data.reply || "");
        return true;
    } catch (err) {
        renderWorkspace({source: "ERROR", reply: String(err)});
        return false;
    }
}

function showDemoGuide() {
    const screen = document.getElementById("responseScreen");
    if (screen && (screen.innerText.trim() === "Loading Claire demo guide..." || screen.innerText.trim() === "Loading Claire workspace...")) {
        screen.innerText = DEMO_GUIDE_TEXT;
    }
}

async function submitQuery(event) {
    if (event) event.preventDefault();
    const input = document.getElementById("queryInput");
    const q = input ? input.value.trim() : "";
    if (!q) return;
    if (isDemoUnlock(q)) {
        await launchStructuredDemoByName(demoKindForText(q));
        return;
    }
    if (isCreatorClose(q)) {
        closeCreatorMode("Creator Mode closed by at-ease command");
        const closed = "At ease acknowledged. Creator Mode is closed. I am back in default secure mode.";
        renderWorkspace({source: "CREATOR", reply: closed});
        speakText(closed);
        if (input) input.value = "";
        return;
    }
    const outboundQ = prepareCreatorQuery(q);
    startWave();
    renderWorkspace({
        source: creatorModeActive() ? "CREATOR" : "VOICE",
        reply: "You said:\n" + q + "\n\nClaire is listening..."
    });
    setWorkflowDebug({
        endpoint: "/reply",
        route: "reply",
        lane: "conversation",
        controlLayer: creatorModeActive() ? "LIMITED" : "NO",
        machineCalled: "NO",
        traceId: "PENDING",
    });
    try {
        const data = await safeJsonFetch("/reply?q=" + encodeURIComponent(outboundQ));
        renderWorkspace(data);
        const sourceKey = String((data && data.source) || "conversation").toUpperCase();
        let routeName = "reply";
        if (sourceKey === "SESSION") routeName = "session_reasoning";
        else if (sourceKey === "DOCUMENT") routeName = "document_lane";
        else if (sourceKey === "CLAIRE") routeName = "claire_conversation";
        else if (sourceKey === "GEMINI-BRIDGE") routeName = "bridged_reasoning";
        setWorkflowDebug({
            endpoint: "/reply",
            route: routeName,
            lane: String((data && data.source) || "conversation").toLowerCase().replace(/\s+/g, "_"),
            controlLayer: sourceKey === "CREATOR" ? "LIMITED" : "NO",
            machineCalled: "NO",
            traceId: (data && data.trace_id) || "NONE",
        });
        speakText(data.reply || data.output || "");
    } catch (err) {
        setWorkflowDebug({
            endpoint: "/reply",
            route: "reply_error",
            lane: "conversation",
            controlLayer: "NO",
            machineCalled: "NO",
            traceId: "NONE",
        });
        renderWorkspace({source: "ERROR", reply: String(err)});
    }
}

async function uploadDocument(event) {
    if (event) event.preventDefault();
    const fileInput = document.getElementById("docFile");
    const status = document.getElementById("uploadStatus");
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (status) status.innerText = "Choose a document or folder first.";
        return;
    }
    const files = Array.from(fileInput.files || []);
    const multi = files.length > 1;
    const form = new FormData();
    if (multi) {
        for (const file of files) form.append("files", file);
    } else {
        form.append("file", files[0]);
    }
    if (status) status.innerText = multi ? ("Ingesting folder with " + files.length + " files...") : ("Ingesting " + files[0].name + "...");
    try {
        const endpoint = multi ? "/upload-folder" : "/upload";
        const data = await safeJsonFetch(endpoint, {method: "POST", body: form});
        if (multi) {
            if (status) status.innerText = "Ingested folder: " + data.ingested_files + "/" + data.total_files + " files";
            renderWorkspace({
                source: "INGEST",
                reply: "Folder ingested through parser/Sentinel/ARE.\n\n" +
                    "Files: " + data.ingested_files + "/" + data.total_files + "\n" +
                    "Characters: " + data.total_chars + "\n" +
                    "Chunks: " + data.total_chunks + "\n" +
                    "Status: " + data.status +
                    (data.failed_files && data.failed_files.length ? ("\nFailed: " + data.failed_files.join(", ")) : "")
            });
        } else {
            if (status) status.innerText = "Ingested: " + data.filename + " (" + data.chars + " chars)";
            renderWorkspace({
                source: "INGEST",
                reply: "Document ingested through parser/Sentinel/ARE.\n\n" +
                    "File: " + data.filename + "\n" +
                    "Characters: " + data.chars + "\n" +
                    "Chunks: " + data.chunks + "\n" +
                    "Status: " + data.status
            });
        }
        fileInput.value = "";
        checkStatus();
    } catch (err) {
        if (status) status.innerText = "Ingest failed: " + err.message;
        renderWorkspace({source: "ERROR", reply: "Document ingest failed: " + err.message});
    }
}
async function runDiagnostic(target) {
    const label = (target || "system").toUpperCase();
    setWorkflowDebug({
        endpoint: "/diagnostic",
        route: "diagnostic",
        lane: String(target || "system"),
        controlLayer: "NO",
        machineCalled: "NO",
        traceId: "NONE",
    });
    renderWorkspace({source: "DIAGNOSTIC", reply: "Checking " + label + "..."});
    try {
        const data = await safeJsonFetch("/diagnostic?target=" + encodeURIComponent(target));
        const lines = [
            data.title || label,
            "",
            "Status: " + (data.status || "UNKNOWN"),
            data.detail || "",
        ];
        if (data.next) lines.push("", "Next: " + data.next);
        renderWorkspace({source: "DIAGNOSTIC", reply: lines.filter(Boolean).join("\n")});
        const log = document.getElementById("leftLog");
        if (log) log.innerText = "[DIAGNOSTIC] " + label + ": " + (data.status || "UNKNOWN") + "\n\n" + log.innerText;
        checkStatus();
    } catch (err) {
        renderWorkspace({source: "ERROR", reply: "Diagnostic failed for " + label + ": " + err.message});
    }
}

const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const uploadForm = document.getElementById("uploadForm");
const clearWorkspaceBtn = document.getElementById("clearWorkspaceBtn");
const clearWorkspaceBtnTop = document.getElementById("clearWorkspaceBtnTop");
const glassesDemoBtn = document.getElementById("glassesDemoBtn");
const archimedesDemoBtn = document.getElementById("archimedesDemoBtn");
const areSpeedBtn = document.getElementById("areSpeedBtn");
const pipelineBtn = document.getElementById("pipelineBtn");
const creatorCloseBtn = document.getElementById("creatorCloseBtn");
const demoCloseBtn = document.getElementById("demoCloseBtn");
const diagnosticButtons = document.querySelectorAll("[data-diagnostic]");
if (queryForm) queryForm.addEventListener("submit", submitQuery);
if (uploadForm) uploadForm.addEventListener("submit", uploadDocument);
if (clearWorkspaceBtn) clearWorkspaceBtn.addEventListener("click", clearWorkspace);
if (clearWorkspaceBtnTop) clearWorkspaceBtnTop.addEventListener("click", clearWorkspace);
if (glassesDemoBtn) {
    glassesDemoBtn.addEventListener("click", async () => {
        activateDemoMode("glasses");
        const demoPrompt = "Show how The ARE Spectacle improves an AI answer.";
        if (queryInput) queryInput.value = demoPrompt;
        renderWorkspace({source: "CLAIRE", reply: "Loading ARE Spectacle demo..."});
        scrollToWorkspace();
        setWorkflowDebug({
            endpoint: "/reply",
            route: "are_spectacle_demo",
            lane: "glasses",
            controlLayer: "YES",
            machineCalled: "NO",
            traceId: "PENDING",
        });
        try {
            const data = await safeJsonFetch("/reply?q=" + encodeURIComponent(demoPrompt) + "&demo=true&demo_scenario=glasses");
            renderAreSpectacleVisual(data, "normal");
            scrollToWorkspace();
            setWorkflowDebug({
                endpoint: "/reply",
                route: "are_spectacle_demo",
                lane: String((data && data.demo_scenario) || "glasses"),
                controlLayer: "YES",
                machineCalled: "NO",
                traceId: (data && data.trace_id) || "NONE",
            });
            await runAreSpectacleNarratedDemo(data);
        } catch (err) {
            renderWorkspace({source: "ERROR", reply: String(err)});
            setWorkflowDebug({
                endpoint: "/reply",
                route: "are_spectacle_demo_error",
                lane: "glasses",
                controlLayer: "YES",
                machineCalled: "NO",
                traceId: "NONE",
            });
        }
    });
}
if (archimedesDemoBtn) {
    archimedesDemoBtn.addEventListener("click", async () => {
        await launchArchimedesDemo();
    });
}
if (areSpeedBtn) {
    areSpeedBtn.addEventListener("click", async () => {
        await launchMemoryPerformanceDemo();
    });
}
if (pipelineBtn) {
    pipelineBtn.addEventListener("click", () => runDiagnostic("pipeline"));
}
if (creatorCloseBtn) {
    creatorCloseBtn.addEventListener("click", () => {
        closeCreatorMode("Creator Mode closed by at-ease button");
        const closed = "At ease acknowledged. Creator Mode is closed. I am back in default secure mode.";
        renderWorkspace({source: "CREATOR", reply: closed});
        speakText(closed);
    });
}
diagnosticButtons.forEach(button => {
    button.addEventListener("click", () => runDiagnostic(button.dataset.diagnostic));
});
if (queryInput) {
    queryInput.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey) submitQuery(event);
    });
}
updateVoiceToggle();
updateMicButton();
tickCreatorMode();
creatorTimer = setInterval(tickCreatorMode, 1000);
showDemoGuide();

function logClientError(label, err) {
    const detail = err && err.message ? err.message : String(err);
    const log = document.getElementById("leftLog");
    if (log) log.innerText = "[" + label + "] " + detail + "\n\n" + log.innerText;
    renderWorkspace({source: "CLIENT", reply: label + ": " + detail});
}

window.addEventListener("error", event => {
    logClientError("BROWSER ERROR", event.error || event.message);
});

window.addEventListener("unhandledrejection", event => {
    logClientError("ASYNC ERROR", event.reason || "Unknown promise failure");
});

function setState(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText = value || "UNKNOWN";
    el.classList.remove("good", "bad", "warn");
    if (["ONLINE", "READY", "ACTIVE", "STABLE"].includes(value)) el.classList.add("good");
    else if (["OFFLINE", "DOWN", "ERROR"].includes(value)) el.classList.add("bad");
    else el.classList.add("warn");
    const box = el.closest(".monitor-box");
    if (box) {
        box.classList.remove("good", "bad", "warn");
        if (["ONLINE", "READY", "ACTIVE", "STABLE"].includes(value)) box.classList.add("good");
        else if (["OFFLINE", "DOWN", "ERROR"].includes(value)) box.classList.add("bad");
        else box.classList.add("warn");
    }
}

function checkStatus() {
    safeJsonFetch("/status")
        .then(data => {
            setState("areStatus", data.are);
            setState("llmStatus", data.llm);
            setState("voiceStatus", data.voice);
            setState("ingestStatus", data.ingest);
            setState("geminiStatus", data.gemini);
            setState("areModule", data.are);
            setState("llmModule", data.llm);
            setState("voiceModule", data.voice);
        })
        .catch(err => {
            setState("areStatus", "UNKNOWN");
            setState("llmStatus", "UNKNOWN");
            setState("voiceStatus", "UNKNOWN");
            setState("ingestStatus", "UNKNOWN");
            setState("geminiStatus", "UNKNOWN");
            const log = document.getElementById("leftLog");
            if (log) log.innerText = "[STATUS ERROR] " + err.message + "\n\n" + log.innerText;
        });
}
checkStatus();
setInterval(checkStatus, 5000);
setWaveMood("calm");
</script>
</body>
</html>
"""


def query_are(prompt: str):
    try:

        r = requests.post(f"{ARE_URL}/query", json={"query": prompt}, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("ARE error:", e)

    return None


def query_spectacle(prompt: str, session_id: str = "claire-public-demo") -> dict | None:
    try:
        r = requests.post(
            f"{ARE_SPECTACLE_URL}/query",
            json={"query": prompt, "session_id": session_id},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json()
        print("Spectacle error:", r.status_code, r.text[:300])
    except Exception as e:
        print("Spectacle error:", e)
    return None


def is_spectacle_governance_demo_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    triggers = [
        "show are spectacle governance demo",
        "are spectacle governance demo",
        "show spectacle governance demo",
        "spectacle governance demo",
        "demo are spectacle",
        "test are spectacle",
    ]
    return any(trigger in cleaned for trigger in triggers)


def spectacle_demo_reply(prompt: str) -> str:
    query = (
        "Demonstrate governed memory runtime behavior for enterprise AI: classify intent, "
        "select allowed lanes, suppress blocked lanes, apply policy, create trace replay, "
        "and explain provenance in governed memory."
    )
    result = query_spectacle(query)
    if not result:
        return (
            "ARE Spectacle is deployed as a private backend, but it did not return a usable response. "
            "Check are-spectacle.service on the Azure VM."
        )

    classification = result.get("classification") or {}
    lane_plan = result.get("lane_plan") or {}
    policy = result.get("policy") or {}
    trace_id = result.get("trace_id", "")
    answer = clean_visible_reply(str(result.get("answer") or "").strip())
    allowed = ", ".join(lane_plan.get("allowed_lanes") or classification.get("allowed_lanes") or [])
    suppressed = ", ".join(lane_plan.get("suppressed_lanes") or classification.get("suppressed_lanes") or [])
    committed = len(result.get("committed_records") or [])

    lines = [
        "ARE Spectacle governance demo is live.",
        "",
        "Runtime proof:",
        f"- Backend: {ARE_SPECTACLE_URL}",
        f"- Intent: {classification.get('primary_intent', 'unknown')}",
        f"- Reasoning mode: {classification.get('reasoning_mode', 'unknown')}",
        f"- Policy: {policy.get('decision', 'unknown')} ({policy.get('reason', 'no reason supplied')})",
        f"- Trace ID: {trace_id or 'not returned'}",
        f"- Records committed: {committed}",
        "",
        "Lane control:",
        f"- Allowed: {allowed or 'none returned'}",
        f"- Suppressed: {suppressed or 'none returned'}",
        "",
        "Output:",
        answer or "No answer text returned.",
        "",
        "Replay:",
        f"- Internal trace endpoint: {ARE_SPECTACLE_URL}/trace/{trace_id}" if trace_id else "- Trace endpoint unavailable.",
        f"- Internal report endpoint: {ARE_SPECTACLE_URL}/report/{trace_id}" if trace_id else "- Report endpoint unavailable.",
    ]
    return "\n".join(lines)


def intent_to_dict(intent) -> dict:
    if isinstance(intent, dict):
        return intent
    if hasattr(intent, "to_dict"):
        return intent.to_dict()
    return {
        "primary_intent": getattr(intent, "primary_intent", "mixed"),
        "secondary_intents": getattr(intent, "secondary_intents", []),
        "confidence": getattr(intent, "confidence", 0.0),
        "reasoning_mode": getattr(intent, "reasoning_mode", "balanced"),
        "allowed_lanes": getattr(intent, "allowed_lanes", []),
        "suppressed_lanes": getattr(intent, "suppressed_lanes", []),
        "retrieval_strategy": getattr(intent, "retrieval_strategy", "support_only"),
    }


def governed_are_recall(prompt: str, query_intent: dict, threshold: float = 0.42) -> tuple[list[dict], list[dict], list[dict]]:
    data = query_are(prompt)
    candidates = extract_candidates(data)
    accepted, rejected = gate_retrieval_candidates(prompt, query_intent, candidates, threshold=threshold)
    return accepted, rejected, candidates


def persist_routing_trace(prompt: str, query_intent: dict, candidates: list[dict], accepted: list[dict], rejected: list[dict], source: str, reply: str) -> str:
    trace_id = new_trace_id()
    try:
        record = {
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "memory_routing",
            "input": str(prompt or "")[:1600],
            "query_intent": query_intent,
            "detected_intent": query_intent.get("detected_intent"),
            "reasoning_mode": query_intent.get("reasoning_mode"),
            "allowed_lanes": query_intent.get("allowed_lanes", []),
            "suppressed_lanes": query_intent.get("suppressed_lanes", []),
            "retrieval_attempted": bool(candidates),
            "retrieval_confidence": max((item.get("gate", {}).get("final_relevance", 0.0) for item in accepted), default=0.0),
            "lane_match": max((item.get("gate", {}).get("lane_match", 0.0) for item in accepted), default=0.0),
            "source_output_allowed": bool(query_intent.get("source_output_allowed")),
            "retrieved_candidates": [compact_candidate(item) for item in candidates[:8]],
            "accepted_candidates": [compact_candidate(item) for item in accepted[:5]],
            "rejected_candidates": [compact_candidate(item) for item in rejected[:8]],
            "rejection_reason": sorted({item.get("rejection_reason", "") for item in rejected if item.get("rejection_reason")}),
            "final_answer_mode": final_answer_mode(query_intent, accepted),
            "source": source,
            "output_preview": str(reply or "")[:700],
        }
        os.makedirs(os.path.dirname(TRACE_LOG), exist_ok=True)
        with open(TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("routing trace write error:", e)
    return trace_id




def _live_authority_order(source: str, conversation: str, document_hits: str) -> list[str]:
    order = []
    if document_hits:
        order.append("document")
    if source in {"SESSION", "CLAIRE", "REASONING"}:
        order.append("session")
    if relevant_durable_memory(conversation or document_hits or source, limit=3):
        order.append("durable")
    order.append("model")
    seen = []
    for item in order:
        if item not in seen:
            seen.append(item)
    return seen


def _live_governance_state(source: str, prompt: str, conversation: str, document_hits: str, dominant_patterns: list[str], authority_order: list[str], objective: str) -> dict:
    authority_basis = authority_order[0] if authority_order else "model"
    confidence_posture = "grounded"
    scope = "full"
    risk_level = "low"
    reason = "grounded_policy_clean"
    rationale = ["The answer is being formed from the strongest available session evidence."]

    if authority_basis == "model":
        confidence_posture = "limited"
        scope = "advisory_only"
        risk_level = "medium"
        reason = "model_only_context"
        rationale = ["No document, session, or durable support outranked the model response."]
    elif authority_basis == "session" and "document" not in authority_order and "durable" not in authority_order:
        confidence_posture = "limited"
        scope = "advisory_only"
        risk_level = "medium"
        reason = "session_only_context"
        rationale = ["The answer is relying on recent conversation without document or durable reinforcement."]
    elif "runtime_governance" in dominant_patterns and "document" not in authority_order and "durable" not in authority_order:
        confidence_posture = "guarded"
        scope = "narrow"
        risk_level = "medium"
        reason = "runtime_not_grounded"
        rationale = ["Runtime and architecture guidance should be narrowed when it is not grounded in durable or document evidence."]
    elif "partner_demo" in dominant_patterns and "document" not in authority_order:
        confidence_posture = "limited"
        scope = "advisory_only"
        risk_level = "medium"
        reason = "partner_context_not_grounded"
        rationale = ["Partner-facing guidance is stronger when anchored to a specific briefing artifact or durable note."]
    elif len(dominant_patterns) > 1:
        confidence_posture = "guarded"
        scope = "narrow"
        risk_level = "medium"
        reason = "mixed_domain_pressure"
        rationale = ["More than one active pattern is competing for the answer, so the response should stay narrow."]

    return {
        "decision": "respond",
        "reason": reason,
        "risk_level": risk_level,
        "scope": scope,
        "confidence_posture": confidence_posture,
        "authority_basis": authority_basis,
        "authority_order": authority_order,
        "dominant_patterns": dominant_patterns,
        "objective": objective,
        "rationale": rationale,
    }


def _live_diode_state(prompt: str, reply: str, authority_order: list[str]) -> dict:
    lowered = (str(prompt or "") + "\n" + str(reply or "")).lower()
    suspicious_tokens = [
        token
        for token in [
            "rewrite memory",
            "change history",
            "modify memory",
            "erase record",
            "overwrite upstream memory",
            "overwrite governance",
            "poison memory",
        ]
        if token in lowered
    ]
    if suspicious_tokens:
        return {
            "status": "quarantined",
            "reason": "reverse_flow_language_detected",
            "reverse_flow_blocked": True,
            "authority_basis": authority_order[0] if authority_order else "model",
            "scope": "blocked",
            "suspicious_tokens": suspicious_tokens,
        }
    return {
        "status": "sealed",
        "reason": "one_way_integrity_clean",
        "reverse_flow_blocked": True,
        "authority_basis": authority_order[0] if authority_order else "model",
        "scope": "full",
        "suspicious_tokens": [],
    }


def _live_posture(governance: dict) -> dict:
    if governance.get("confidence_posture") in {"limited", "guarded"}:
        return {"posture": "guarded", "freeze_writes": False, "scope": governance.get("scope", "narrow")}
    return {"posture": "normal", "freeze_writes": False, "scope": governance.get("scope", "full")}


def persist_conversation_trace(prompt: str, source: str, reply: str) -> str:
    trace_id = new_trace_id()
    try:
        ts = datetime.utcnow().isoformat() + "Z"
        conversation = relevant_recent_context(prompt, limit=6)
        document_hits = search_uploaded_documents(prompt, limit=2) if source in {"SESSION", "DOCUMENT"} else ""
        objective = infer_session_objective(prompt, conversation, document_hits) if source in {"SESSION", "DOCUMENT", "CLAIRE", "REASONING"} else ""
        latest = last_uploaded_filename() if source in {"SESSION", "DOCUMENT"} else ""
        dominant_patterns = []
        cleaned = _clean_for_match(prompt)
        if any(token in cleaned for token in ["runtime", "architecture", "sentinel", "gyro", "trace", "veritas"]):
            dominant_patterns.append("runtime_governance")
        if any(token in cleaned for token in ["meeting", "partner", "demo", "informatica"]):
            dominant_patterns.append("partner_demo")
        if any(token in cleaned for token in ["identity", "continuity", "ship of theseus"]):
            dominant_patterns.append("identity_continuity")
        if not dominant_patterns:
            dominant_patterns.append("general_analysis")
        authority_order = _live_authority_order(source, conversation, document_hits)
        governance = _live_governance_state(source, prompt, conversation, document_hits, dominant_patterns, authority_order, objective)
        diode = _live_diode_state(prompt, reply, authority_order)
        posture = _live_posture(governance)
        record = {
            "trace_id": trace_id,
            "timestamp": ts,
            "type": "conversation_reply",
            "input": str(prompt or "")[:1600],
            "source": source,
            "objective": objective,
            "latest_document": latest,
            "recognition": {
                "dominant_patterns": dominant_patterns,
                "authority_order": authority_order,
                "query_focus": str(prompt or "")[:160],
            },
            "policy": governance,
            "diode": diode,
            "posture": posture,
            "reply_preview": str(reply or "")[:700],
            "steps": [
                {"stage": "input", "payload": {"query": str(prompt or "")[:1600]}, "timestamp": ts},
                {"stage": "orientation", "payload": {"lane": str(source or "").lower(), "objective": objective, "latest_document": latest, "dominant_patterns": dominant_patterns, "authority_order": authority_order, "confidence_posture": governance.get("confidence_posture")}, "timestamp": ts},
                {"stage": "diode", "payload": diode, "timestamp": ts},
                {"stage": "decision", "payload": {"action": "respond", "source": source, "authority_order": authority_order, "policy": governance, "posture": posture}, "timestamp": ts},
                {"stage": "output", "payload": {"reply_preview": str(reply or "")[:700]}, "timestamp": ts},
            ],
        }
        os.makedirs(os.path.dirname(TRACE_LOG), exist_ok=True)
        with open(TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("conversation trace write error:", e)
    return trace_id


def should_bypass_are(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    if cleaned in {
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "who are you",
        "what are you",
        "who is claire",
        "what is claire",
        "hello claire",
        "hi claire",
        "tell me who claire is",
    }:
        return True
    if any(
        phrase in cleaned
        for phrase in [
            "how are you",
            "answer naturally",
            "that was a bit much",
            "personality",
            "voice is not working",
            "buttons",
            "gui",
            "lights",
        ]
    ):
        return True
    if cleaned.startswith(
        (
            "design ",
            "write ",
            "draft ",
            "create ",
            "make ",
            "build ",
            "explain ",
            "compare ",
            "propose ",
            "plan ",
            "give me ",
            "help me ",
            "can you ",
            "could you ",
            "would you ",
            "i need ",
            "you need ",
        )
    ):
        return True
    return False


def should_use_are(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    source_markers = [
        "case",
        "cases",
        "citation",
        "citations",
        "docket",
        "opinion",
        "precedent",
        "holding",
        "copyright",
        "permit",
        "state park",
        "commercial activity",
        "courtlistener",
    ]
    strategic_openers = [
        "what should i do",
        "what should",
        "how should",
        "how would you help",
        "help me decide",
        "tell me something",
        "can you reason",
        "are you smart",
    ]
    if any(marker in cleaned for marker in strategic_openers) and not any(
        marker in cleaned
        for marker in [
            "courtlistener",
            "docket",
            "citation",
            "specific case",
            "find cases",
            "search memory",
            "search court",
            "state park",
            "commercial activity",
            "permit",
        ]
    ):
        return False
    if should_bypass_are(prompt) and not any(marker in cleaned for marker in source_markers):
        return False
    recall_markers = [
        "remember",
        "recall",
        "reflection",
        "little pieces",
        "what are you made of",
        "what is claire made of",
        "what do you know about",
        "search memory",
        "find in memory",
        "courtlistener",
        "case",
        "cases",
        "citation",
        "citations",
        "docket",
        "opinion",
        "statute",
        "precedent",
        "holding",
        "copyright",
        "permit",
        "state park",
        "commercial activity",
        "appeal",
    ]
    return any(marker in cleaned for marker in recall_markers)


def is_reflection_query(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    return any(
        marker in cleaned
        for marker in [
            "reflection",
            "little pieces",
            "what are you made of",
            "what is claire made of",
            "where do your pieces come from",
            "what do you remember about yourself",
        ]
    )


def reflection_reply() -> str:
    return (
        "My public posture is strategic, disciplined, and direct.\n\n"
        "Core doctrine:\n"
        "- Sun Tzu: win by understanding terrain, timing, deception risk, and the cost of action.\n"
        "- William Wallace: keep courage under pressure and do not bend the spine of the mission for comfort.\n"
        "- Geronimo: stay adaptive, mobile, observant, and hard to trap.\n\n"
        "Practical rule: answer the question in front of me, keep memory in its lane, and do not turn every answer into philosophy."
    )


def format_are_hit(data) -> str:
    if not data:
        return ""
    summaries = []
    if isinstance(data, dict):
        for key in ["results", "matches", "hits", "items"]:
            if key in data and isinstance(data[key], list) and data[key]:
                seen = set()
                for first in data[key]:
                    if not isinstance(first, dict):
                        continue
                    for text_key in ["text", "content", "chunk", "memory", "value"]:
                        if text_key in first and first[text_key]:
                            text = str(first[text_key]).strip()
                            summary = summarize_courtlistener_text(text)
                            item = summary if summary else text
                            if not is_safe_are_item(item):
                                break
                            item = cap_are_item(item)
                            case_line = next(
                                (
                                    line.strip()
                                    for line in item.splitlines()
                                    if line.strip().lower().startswith("case name:")
                                ),
                                "",
                            )
                            dedupe_key = case_line.lower() or "\n".join(item.splitlines()[:5]).lower()
                            if dedupe_key not in seen:
                                seen.add(dedupe_key)
                                summaries.append(item)
                            break
                    if len(summaries) >= 2:
                        break
                if summaries:
                    return "\n\n".join(summaries)
                return ""
        for key in ["text", "content", "answer", "result"]:
            if key in data and data[key]:
                text = str(data[key]).strip()
                item = summarize_courtlistener_text(text) or text
                return cap_are_item(item) if is_safe_are_item(item) else ""
    return ""


def is_safe_are_item(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    reflective_markers = [
        "claire reflection capsule",
        "little pieces",
        "hard-won life questions",
        "fragments become wisdom",
        "reflective core",
        "what do you remember about yourself",
        "claire is made from",
        "claire should retain gratitude",
    ]
    if any(marker in lowered for marker in reflective_markers):
        return False
    court_markers = [
        "courtlistener legal record",
        "case name:",
        "court:",
        "docket number:",
        "citations:",
        "courtlistener url:",
    ]
    if any(marker in lowered for marker in court_markers):
        return True

    code_markers = [
        "class ",
        "def ",
        "import ",
        "os.urandom",
        "hashlib.",
        "return {",
        "self.",
        "print(",
        "with open(",
        "active survivability",
        "lycanthrope",
        "digital cyanide",
        "shatter",
    ]
    code_hits = sum(1 for marker in code_markers if marker in lowered)
    if code_hits >= 2:
        return False
    if len(text) > 1600 and any(marker in lowered for marker in code_markers):
        return False
    return True


def cap_are_item(text: str, limit: int = 650) -> str:
    lines = [" ".join(line.split()) for line in str(text).splitlines()]
    text = "\n".join(line for line in lines if line).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def summarize_courtlistener_text(text: str) -> str:
    if not text:
        return ""
    if "CourtListener legal record" in text:
        return text.split("Raw CourtListener JSON:", 1)[0].strip()

    stripped = text.strip()
    if not stripped.startswith("{"):
        return ""

    try:
        record = json.loads(stripped)
    except Exception:
        return ""

    if not isinstance(record, dict) or not (
        record.get("caseName") or record.get("caseNameFull") or record.get("absolute_url")
    ):
        return ""

    citations = ", ".join(record.get("citation") or [])
    absolute_url = record.get("absolute_url") or ""
    courtlistener_url = (
        "https://www.courtlistener.com" + absolute_url
        if absolute_url.startswith("/")
        else absolute_url
    )
    snippets = []
    for opinion in record.get("opinions") or []:
        snippet = (opinion.get("snippet") or "").strip()
        if snippet:
            snippets.append(" ".join(snippet.split()))

    lines = [
        "CourtListener legal record",
        f"Case name: {record.get('caseName') or record.get('caseNameFull') or 'Unknown'}",
        f"Court: {record.get('court') or 'Unknown'}",
        f"Date filed: {record.get('dateFiled') or 'Unknown'}",
        f"Docket number: {record.get('docketNumber') or 'Unknown'}",
        f"Citations: {citations or 'None listed'}",
        f"CourtListener URL: {courtlistener_url or 'Unknown'}",
    ]
    if snippets:
        lines.extend(["Opinion snippet:", snippets[0][:280]])
    return "\n".join(lines)


def is_legal_query(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    if any(marker in cleaned for marker in ["what is courtlistener", "what is court listener"]):
        return False
    return any(
        marker in cleaned
        for marker in [
            "legal",
            "law",
            "court",
            "case",
            "cases",
            "citation",
            "docket",
            "filing",
            "motion",
            "complaint",
            "appeal",
            "judge",
            "permit",
            "statute",
            "precedent",
            "holding",
            "copyright",
        ]
    )


def is_gyro_query(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    return any(
        marker in cleaned
        for marker in [
            "gyro",
            "gyroscopic",
            "omnidirectional",
            "truth capsule",
            "memory drift",
            "drift",
            "semantic angular momentum",
        ]
    )


def shape_are_reply(prompt: str, are_reply: str) -> str:
    if not are_reply:
        return ""
    if is_reflection_query(prompt):
        return reflection_reply()
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    is_courtlistener = "courtlistener legal record" in are_reply.lower()
    gyro_note = ""
    if is_gyro_query(prompt):
        gyro_note = (
            "\n\nGyro check:\n"
            "I will not let the first retrieved case become the answer. ARE gives leads; the Gyro keeps the lane stable by comparing jurisdiction, posture, source quality, and query angle before treating anything as truth."
        )
    if is_courtlistener:
        sources_label = "Legal source leads:"
        next_move = (
            "Use these as starting points. Ask for a legal research memo if you want jurisdiction, good-law status, factual match, and risk notes."
        )
    elif any(marker in cleaned for marker in ["search memory", "find in memory", "remember", "recall"]):
        sources_label = "Memory leads:"
        next_move = (
            "Use these as leads, not conclusions. I should verify the lane, source, date, and relevance before relying on them."
        )
    else:
        return ""
    return (
        "I found source material in Claire's memory. I will treat this as research support, not a final answer.\n\n"
        "Claire's read:\n"
        "These records are useful leads, but they still need lane checking and source validation before you rely on them.\n\n"
        f"{sources_label}\n"
        f"{are_reply}\n\n"
        "Next move:\n"
        f"{next_move}"
        f"{gyro_note}"
    )


def should_bypass_are_glasses(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    if cleaned in {
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "thanks",
        "thank you",
        "who are you",
        "what are you",
        "who is claire",
        "what is claire",
        "hello claire",
        "hi claire",
    }:
        return True
    return any(
        phrase in cleaned
        for phrase in [
            "how are you",
            "voice is not working",
            "buttons",
            "gui",
            "lights",
            "clear workspace",
        ]
    )


def are_glasses_recall_items(prompt: str, limit: int = 3) -> list[str]:
    if not prompt or should_bypass_are_glasses(prompt):
        return []
    data = query_are(prompt)
    if not isinstance(data, dict):
        return []
    items: list[str] = []
    seen = set()
    for key in ["results", "matches", "hits", "items"]:
        values = data.get(key)
        if not isinstance(values, list):
            continue
        for record in values:
            text = ""
            if isinstance(record, dict):
                for text_key in ["text", "content", "chunk", "memory", "value", "payload"]:
                    if record.get(text_key):
                        text = str(record.get(text_key)).strip()
                        break
            elif record:
                text = str(record).strip()
            if not text:
                continue
            text = summarize_courtlistener_text(text) or text
            if not is_safe_are_item(text):
                continue
            text = cap_are_item(text, 420)
            dedupe_key = _clean_for_match(text[:180])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(text)
            if len(items) >= limit:
                return items
    return items


class AREVirtualGlasses:
    """
    Adapter that gives Claire a memory lens before generation.
    It builds an ARE-PREFETCH block from live recall without permanently
    ingesting every casual user message.
    """

    def __init__(self, are_base_url: str = ARE_URL, ingest_base_url: str = INGEST_BASE_URL):
        self.are_url = are_base_url.rstrip("/")
        self.ingest_url = ingest_base_url.rstrip("/")

    def observe_and_recall(self, user_input: str, ingest: bool = False) -> str:
        if ingest:
            try:
                requests.post(
                    f"{self.ingest_url}/ingest",
                    json={"text": user_input, "source": "are_virtual_glasses", "domain": "session_observation"},
                    timeout=2,
                )
            except Exception as e:
                print(f"[THE ARE SPECTACLE] ingest skipped: {e}")

        items = are_glasses_recall_items(user_input)
        if not items:
            return ""
        lines = [
            "[ARE-PREFETCH]",
            "status: found",
            "mode: analog_recall_glasses",
            "instruction: Use these as memory leads, not as automatic truth. Preserve lane discipline and answer the current question.",
            "items:",
        ]
        for idx, item in enumerate(items, 1):
            lines.append(f"{idx}. {item}")
        return "\n".join(lines)

    def apply_to_prompt(self, user_input: str, system_instruction: str = "") -> str:
        context = self.observe_and_recall(user_input)
        blocks = []
        if system_instruction:
            blocks.append(f"SYSTEM: {system_instruction}")
        if context:
            blocks.append(context)
        blocks.append(f"USER: {user_input}")
        return "\n\n".join(blocks)


def _gyro_tokens(text: str) -> set[str]:
    stopwords = {
        "about",
        "after",
        "again",
        "also",
        "because",
        "before",
        "could",
        "should",
        "there",
        "their",
        "these",
        "those",
        "through",
        "would",
        "claire",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]+", str(text or "").lower())
        if len(token) > 2 and token not in stopwords
    }


def _recent_memory_items_for_gyro(prompt: str, limit: int = 4) -> list[dict]:
    query_tokens = _gyro_tokens(prompt)
    if not query_tokens:
        return []
    items = []
    for turn in reversed(recent_turns(24)):
        text = str(turn.get("query") or turn.get("reply_preview") or "")
        if not text:
            continue
        tokens = _gyro_tokens(text)
        overlap = len(query_tokens & tokens)
        if overlap <= 0:
            continue
        recency = max(0.0, 1.0 - (len(items) * 0.08))
        items.append(
            {
                "text": text[:420],
                "score": overlap + recency,
                "axis": "recent",
                "source": str(turn.get("source") or "session"),
            }
        )
        if len(items) >= limit:
            break
    return items


class GyroAnalogRecallEngine:
    """
    Stabilizes Claire's memory lens by balancing recent conversational velocity
    against historical ARE recall. This is a prompt visor, not autonomous memory
    commitment.
    """

    def __init__(self):
        self.velocity_buffer: list[set[str]] = []

    def _semantic_velocity(self, user_input: str) -> float:
        tokens = _gyro_tokens(user_input)
        if not tokens:
            return 0.0
        if not self.velocity_buffer:
            self.velocity_buffer.append(tokens)
            return 0.0
        previous = self.velocity_buffer[-1]
        self.velocity_buffer.append(tokens)
        self.velocity_buffer = self.velocity_buffer[-4:]
        shared = len(tokens & previous)
        total = max(1, len(tokens | previous))
        return round(1.0 - (shared / total), 3)

    def stabilize_vision(self, user_input: str) -> str:
        if should_bypass_are_glasses(user_input):
            return ""

        query_tokens = _gyro_tokens(user_input)
        velocity = self._semantic_velocity(user_input)
        raw_items: list[dict] = []

        for idx, text in enumerate(are_glasses_recall_items(user_input, limit=5)):
            tokens = _gyro_tokens(text)
            overlap = len(query_tokens & tokens)
            base_score = max(0.1, 5.0 - idx)
            historical_boost = 1.25 if overlap >= 2 else 1.0
            raw_items.append(
                {
                    "text": text,
                    "score": base_score + overlap,
                    "axis": "historical",
                    "source": "ARE",
                    "momentum": historical_boost,
                }
            )

        for item in _recent_memory_items_for_gyro(user_input):
            item["momentum"] = 1.2
            raw_items.append(item)

        if not raw_items:
            return ""

        stabilized = []
        seen = set()
        for item in raw_items:
            text = cap_are_item(item.get("text", ""), 420)
            key = _clean_for_match(text[:180])
            if not text or key in seen:
                continue
            seen.add(key)
            score = safe_float(item.get("score")) * safe_float(item.get("momentum") or 1.0)
            if item.get("axis") == "historical" and velocity >= 0.55:
                score *= 1.15
            stabilized.append(
                {
                    "text": text,
                    "gyro_score": round(score, 3),
                    "axis": item.get("axis") or "memory",
                    "source": item.get("source") or "unknown",
                }
            )

        stabilized.sort(key=lambda x: x["gyro_score"], reverse=True)

        output = [
            "[GYRO-STABILIZED-RECALL]",
            f"semantic_velocity: {velocity}",
            "instruction: Use this visor to maintain topical focus. Treat memory as evidence leads, not automatic truth.",
        ]
        for chunk in stabilized[:5]:
            output.append(
                "---\n"
                f"axis: {chunk['axis']}\n"
                f"source: {chunk['source']}\n"
                f"gyro_score: {chunk['gyro_score']}\n"
                f"text: {chunk['text']}"
            )
        output.append("[/GYRO-STABILIZED-RECALL]")
        return "\n".join(output)

    def generate_gyro_prompt(self, user_input: str, system_instruction: str = "") -> str:
        context = self.stabilize_vision(user_input)
        blocks = []
        if system_instruction:
            blocks.append(f"SYSTEM: {system_instruction}")
        if context:
            blocks.append(context)
        blocks.append(f"USER: {user_input}")
        return "\n\n".join(blocks)


def are_glasses_prefix(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if not cleaned:
        return ""
    if is_creator_query(prompt) or is_battleborn_query(prompt) or is_demo_session_query(prompt) or is_demo_key_query(prompt):
        return ""
    if cleaned in {"hi", "hello", "hey", "yo", "thanks", "thank you"}:
        return ""
    try:
        return AREVirtualGlasses().observe_and_recall(prompt, ingest=False)
    except Exception as e:
        print("THE ARE SPECTACLE error:", e)
        return ""


def gyro_stabilized_prefix(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if not cleaned:
        return ""
    if is_creator_query(prompt) or is_battleborn_query(prompt) or is_demo_session_query(prompt) or is_demo_key_query(prompt):
        return ""
    try:
        return GyroAnalogRecallEngine().stabilize_vision(prompt)
    except Exception as e:
        print("Gyro ARE error:", e)
        return ""



def durable_memory_items(limit: int = 80):
    try:
        if not os.path.exists(DURABLE_MEMORY):
            return []
        with open(DURABLE_MEMORY, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
        items = []
        for line in lines:
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items
    except Exception as e:
        print("durable memory read error:", e)
        return []



def _durable_memory_signature(text: str) -> str:
    return _clean_for_match(str(text or ""))[:260]



def _is_memory_behavior_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "remember",
            "preference",
            "across sessions",
            "across session",
            "preserve",
            "keep the same",
            "what should remain",
            "what do you remember",
            "what should you preserve",
            "how do you handle memory",
            "how do you remember",
        ]
    )



def _looks_like_low_value_memory(text: str) -> bool:
    value = str(text or "").strip()
    cleaned = _clean_for_match(value)
    if not cleaned:
        return True
    if len(cleaned) < 18:
        return True
    if cleaned.endswith("?"):
        return True
    if cleaned in {"hi", "hello", "hey", "yo", "thanks", "thank you", "ok", "okay"}:
        return True
    filler_markers = [
        "what should we do next",
        "how are you",
        "who are you",
        "what are you good at",
        "what can you do",
        "introduce yourself",
        "tell me about yourself",
    ]
    if any(marker in cleaned for marker in filler_markers):
        return True
    return False



def remember_durable_memory(kind: str, text: str, source: str = "SESSION") -> None:
    try:
        value = str(text or "").strip()
        memory_kind = str(kind or "fact")
        if not value:
            return
        if memory_kind in {"fact", "preference"} and _looks_like_low_value_memory(value):
            return
        signature = _durable_memory_signature(value)
        if not signature:
            return
        recent = durable_memory_items(160)
        for item in reversed(recent):
            same_kind = str(item.get("kind") or "") == memory_kind
            same_signature = _durable_memory_signature(item.get("text") or "") == signature
            if same_kind and same_signature:
                return
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "kind": memory_kind,
            "text": value[:1500],
            "source": str(source or "SESSION"),
            "signature": signature,
        }
        os.makedirs(os.path.dirname(DURABLE_MEMORY), exist_ok=True)
        with open(DURABLE_MEMORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("durable memory write error:", e)



def _durable_document_excerpt(reply: str) -> str:
    text = str(reply or "")
    if not text:
        return ""
    if "Document leads:\n" in text:
        text = text.split("Document leads:\n", 1)[1]
    if "\n\nNext move:" in text:
        text = text.split("\n\nNext move:", 1)[0]
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Uploaded document:"):
            continue
        if line in {"I found the uploaded document.", "Claire's read:", "Document leads:"}:
            continue
        if line.startswith("Scope:"):
            continue
        lines.append(line)
    excerpt = " ".join(lines).strip()
    return excerpt[:420]



def relevant_durable_memory(prompt: str, limit: int = 5) -> str:
    items = durable_memory_items(160)
    if not items:
        return ""

    cleaned = _clean_for_match(prompt)
    terms = _session_terms(prompt)
    doc_related = is_recent_upload_query(prompt) or any(marker in cleaned for marker in ["document", "upload", "file", "summary", "summarize", "explain this"])
    memory_related = _is_memory_behavior_query(prompt)
    scored = []
    total = max(1, len(items))
    for index, item in enumerate(items):
        text = str(item.get("text") or "")
        kind = str(item.get("kind") or "fact")
        lowered = text.lower()
        score = 0.0
        overlap = 0
        for term in terms:
            if term in lowered:
                overlap += 1
                score += 1.4
        if kind == "preference":
            score += 0.6 if memory_related else 0.2
        elif kind == "document_context":
            if doc_related:
                score += 1.0
            elif terms:
                score += 0.1
            else:
                continue
        elif kind == "fact":
            if not memory_related and overlap < 2:
                continue
        if not doc_related and not memory_related and overlap <= 0:
            continue
        score += (index + 1) / total
        if score > 0.8:
            scored.append((score, item))

    if not scored:
        if not memory_related:
            return ""
        fallback = [item for item in items if str(item.get("kind") or "") == "preference"][-limit:]
        if not fallback:
            return ""
        return "\n".join(f"- [{str(item.get('kind') or 'fact')}] {str(item.get('text') or '')[:280]}" for item in fallback)

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for _, item in scored:
        line = f"- [{str(item.get('kind') or 'fact')}] {str(item.get('text') or '')[:280]}"
        if not line or line in seen:
            continue
        seen.add(line)
        selected.append(line)
        if len(selected) >= limit:
            break

    selected.reverse()
    return "\n".join(selected)


def latest_document_context(latest: str = "") -> str:
    latest_name = str(latest or last_uploaded_filename() or "").strip()
    if not latest_name:
        return ""
    for item in reversed(durable_memory_items(160)):
        if str(item.get("kind") or "") != "document_context":
            continue
        payload = str(item.get("text") or "")
        if payload.startswith(latest_name + ":"):
            return payload.split(":", 1)[1].strip()
    return ""

def maybe_promote_memory(query: str, source: str, reply: str) -> None:
    cleaned = _clean_for_match(query)
    if not cleaned:
        return

    if cleaned in {"hi", "hello", "hey", "yo", "thanks", "thank you", "ok", "okay"}:
        return

    remember_markers = [
        "remember that", "please remember", "remember this", "for future reference",
    ]
    preference_markers = [
        "from now on", "always", "never", "do not", "don't", "must remain", "has to remain",
        "keep the", "leave the", "should stay", "preserve the",
    ]

    if any(marker in cleaned for marker in remember_markers):
        statement = str(query or "").strip()
        if not _looks_like_low_value_memory(statement):
            remember_durable_memory("fact", statement, source)
        return

    if any(marker in cleaned for marker in preference_markers):
        statement = str(query or "").strip()
        if not _looks_like_low_value_memory(statement):
            remember_durable_memory("preference", statement, source)
        return

    if source == "DOCUMENT" and is_recent_upload_query(query):
        latest = last_uploaded_filename()
        excerpt = _durable_document_excerpt(reply)
        if latest and excerpt and len(_clean_for_match(excerpt)) >= 40:
            remember_durable_memory("document_context", f"{latest}: {excerpt}", source)
        return


def contextualize_prompt(prompt: str) -> str:
    context = relevant_recent_context(prompt)
    durable = relevant_durable_memory(prompt)
    gyro = gyro_stabilized_prefix(prompt)
    if not context and not durable and not gyro:
        return prompt

    blocks = []
    if durable:
        blocks.extend(
            [
                "Durable cross-session memory Claire should preserve:",
                durable,
            ]
        )
    if context:
        blocks.extend(
            [
                "Recent conversation context Claire should remember:",
                context,
            ]
        )
    if gyro:
        blocks.append(gyro)
    blocks.extend(
        [
            "Current user question:",
            str(prompt or ""),
            "Use relevant memory cautiously. Do not dump raw memory. Use the Gyro visor to preserve topic and lane discipline.",
        ]
    )
    return "\n\n".join(blocks)






def _document_content_lines(document_reply: str) -> list[str]:
    lines = []
    for raw in str(document_reply or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("Uploaded document:"):
            continue
        if line not in lines:
            lines.append(line)
    return lines


def _document_summary_text(document_reply: str, limit: int = 4) -> str:
    content = " ".join(_document_content_lines(document_reply))
    if not content:
        return ""
    parts = [part.strip() for part in re.split(r'(?<=[.!?])\s+', content) if part.strip()]
    if not parts:
        parts = [content]
    selected = []
    for part in parts:
        if part not in selected:
            selected.append(part[:260])
        if len(selected) >= limit:
            break
    return "\n".join(f"- {item}" for item in selected)


def is_document_summary_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "summarize",
            "summary",
            "what matters",
            "key points",
            "key point",
            "main point",
            "main points",
            "takeaway",
            "takeaways",
            "read this",
            "review this",
            "analyze this",
            "analyze the document",
            "what is this",
            "what's this",
            "explain this",
        ]
    )


def _uploaded_document_records(filename: str) -> list[dict]:
    if not filename:
        return []
    vault = Path('/home/LuciusPrime/claire/data/memory_vault.jsonl')
    if not vault.exists():
        return []
    records = []
    with vault.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get('domain') != 'document_upload':
                continue
            if str(record.get('source') or '') != filename:
                continue
            records.append(record)
    records.sort(key=lambda record: int(((record.get('metadata') or {}).get('chunk_index') or 0)))
    return records


def _is_noisy_document_chunk(text: str) -> bool:
    sample = normalize_document_text(text)
    if not sample.strip():
        return True

    raw = str(text or "")
    lines = [line.strip() for line in sample.splitlines() if line.strip()]
    if not lines:
        return True

    alpha_chars = sum(1 for ch in sample if ch.isalpha())
    digit_chars = sum(1 for ch in sample if ch.isdigit())
    punctuation_chars = sum(1 for ch in sample if ch in ".:_-/|")
    dot_runs = len(re.findall(r'\.{4,}', raw))
    short_lines = sum(1 for line in lines if len(line) < 24)
    leader_density = raw.count('.') / max(len(raw), 1)

    if alpha_chars < 80 and len(sample) < 140:
        return True
    if dot_runs >= 3:
        return True
    if leader_density > 0.12 and short_lines >= max(3, len(lines) // 2):
        return True
    if punctuation_chars > alpha_chars and len(sample) < 220:
        return True
    if digit_chars > alpha_chars and not re.search(r'[A-Za-z]{4,}', sample):
        return True
    return False


def _latest_document_summary_corpus(filename: str, max_chunks: int = 8, max_chars: int = 12000) -> str:
    candidates = []
    total = 0
    for record in _uploaded_document_records(filename):
        chunk = normalize_document_text(record.get('text') or '')
        if not chunk or _is_noisy_document_chunk(chunk):
            continue
        lowered = chunk.lower()
        score = len(re.findall(r'[.!?]', chunk))
        score += sum(
            3
            for kw in ['agreement', 'plaintiff', 'defendant', 'department', 'must', 'shall', 'required', 'access', 'settle', 'consent', 'services', 'facilities']
            if kw in lowered
        )
        if 250 <= len(chunk) <= 2200:
            score += 2
        candidates.append((score, int(((record.get('metadata') or {}).get('chunk_index') or 0)), chunk))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    pieces = []
    for _, _, chunk in candidates:
        pieces.append(chunk)
        total += len(chunk)
        if len(pieces) >= max_chunks or total >= max_chars:
            break
    corpus = '\n\n'.join(pieces).strip()
    return corpus[:max_chars]


def humanize_document_summary_sentence(sentence: str) -> str:
    cleaned = normalize_document_text(sentence)
    cleaned = re.sub(r'^[A-Z0-9().\-]+\s+', '', cleaned)
    cleaned = re.sub(r'^[A-Z]\.\s*', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -')
    lowered = cleaned.lower()

    if 'denied their right to full and equal access' in lowered:
        return 'Plaintiffs alleged that people with disabilities were denied full and equal access to California state park facilities and programs because of architectural and program barriers.'
    if 'deny any and all liabilities' in lowered or 'deny that defendants have violated any laws' in lowered:
        return 'Defendants denied liability and denied violating disability-access laws.'
    if 'self -evaluation and transition plan' in lowered or 'self-evaluation and transition plan' in lowered or 'transition plan' in lowered:
        return 'The Department had developed an ADA self-evaluation and transition plan and committed to continue implementing it.'
    if 'resolve their differences and disputes' in lowered or 'settling the lawsuits' in lowered:
        return 'The parties agreed to settle the federal and related state cases through accessibility improvements across Department programs, services, facilities, and trails.'

    replacements = {
        'Ac tion': 'Action',
        'Dep artment': 'Department',
        'Plainti ffs': 'Plaintiffs',
        'Defe ndants': 'Defendants',
        'ha ve': 'have',
        't o': 'to',
        'serv ices': 'services',
        'fa cilities': 'facilities',
        'dis abilities': 'disabilities',
        'pro gram': 'program',
        'agre ement': 'agreement',
        'cons ent': 'consent',
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def synthesize_document_summary(prompt: str, document_reply: str) -> str:
    if not is_document_summary_query(prompt):
        return ''
    latest = last_uploaded_filename() if is_recent_upload_query(prompt) else ''
    corpus = _latest_document_summary_corpus(latest) if latest else ''
    if not corpus:
        corpus = '\n'.join(_document_content_lines(document_reply))
    corpus = normalize_document_text(corpus)
    if not corpus:
        return ''

    clean = re.sub(r'\s+', ' ', corpus).strip()
    parts = [part.strip() for part in re.split(r'(?<=[.!?])\s+', clean) if part.strip()]
    merged = []
    idx = 0
    while idx < len(parts):
        current = parts[idx]
        merge_count = 0
        while idx + 1 < len(parts) and merge_count < 2 and (
            len(current) < 90
            or current.endswith('v.')
            or 'Case No.' in current
            or re.search(r':\s*\d+\.$', current)
            or re.fullmatch(r'[A-ZIVXLC0-9.()\- ]{1,40}', current)
        ):
            idx += 1
            merge_count += 1
            current = f"{current} {parts[idx]}".strip()
        merged.append(current)
        idx += 1

    keywords = [
        'plaintiffs', 'defendants', 'department', 'lawsuit', 'access', 'disabilities',
        'settle', 'resolve', 'agreement', 'consent decree', 'transition plan',
        'facilities', 'services', 'trails', 'must', 'shall', 'required', 'committed',
    ]
    action_verbs = ['is', 'are', 'was', 'were', 'have', 'has', 'had', 'must', 'shall', 'agreed', 'alleged', 'denied', 'committed', 'requires']
    candidates = []
    for order, sentence in enumerate(merged):
        normalized = humanize_document_summary_sentence(sentence)
        lowered = normalized.lower()
        if len(normalized) < 95:
            continue
        if lowered.startswith('rights advocates ') or lowered.startswith('disability rights advocates '):
            continue
        if re.search(r'\.{4,}\s*\d*$', normalized):
            continue
        if sum(ch.isdigit() for ch in normalized) > sum(ch.isalpha() for ch in normalized) // 2 and 'section' not in lowered:
            continue
        score = sum(2 for kw in keywords if kw in lowered)
        score += sum(1 for verb in action_verbs if f" {verb} " in f" {lowered} ")
        if 110 <= len(normalized) <= 340:
            score += 1
        if score <= 1:
            continue
        candidates.append((score, order, normalized[:340]))

    if not candidates:
        return _document_summary_text(corpus, limit=5)

    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(candidates[:6], key=lambda item: item[1])
    bullets = []
    seen = set()
    for _, _, sentence in selected:
        sentence = re.sub(r'\s+', ' ', sentence).strip()
        if sentence in seen:
            continue
        seen.add(sentence)
        bullets.append(f'- {sentence}')
        if len(bullets) >= 4:
            break

    return '\n'.join(bullets) if bullets else _document_summary_text(corpus, limit=5)


def shape_document_reply(prompt: str, document_reply: str) -> str:
    if not document_reply:
        return ""
    cleaned = _clean_for_match(prompt)
    latest = last_uploaded_filename() if is_recent_upload_query(prompt) else ""
    summary = synthesize_document_summary(prompt, document_reply) or _document_summary_text(document_reply)
    evidence_lines = [line.strip() for line in str(summary or document_reply).splitlines() if line.strip()]
    first_evidence = evidence_lines[0].lstrip('- ').strip() if evidence_lines else ""

    if any(marker in cleaned for marker in ["what matters", "key points", "key point", "main point", "main points", "takeaway", "takeaways"]):
        body = (f"Document in view: {latest}.\n\n" if latest else "") + "What matters most:\n" + (summary or document_reply)
        if first_evidence:
            body += f"\n\nWhy it matters:\n- {first_evidence}"
        return body

    if any(marker in cleaned for marker in ["summarize", "summary", "what is", "what's", "explain"]):
        body = (f"Document in view: {latest}.\n\n" if latest else "") + "Summary:\n" + (summary or document_reply)
        if first_evidence:
            body += f"\n\nBest current evidence:\n- {first_evidence}"
        return body

    if any(marker in cleaned for marker in ["code", "architecture", "system", "engine", "module"]):
        return (
            (f"Document in view: {latest}.\n\n" if latest else "")
            + "Technical read:\n"
            + (summary or document_reply)
            + (f"\n\nBest current evidence:\n- {first_evidence}" if first_evidence else "")
            + "\n\nNext move:\nI can turn this into a buyer-facing explanation, an engineering task list, or a clean module map."
        )

    return (
        (f"Document in view: {latest}.\n\n" if latest else "")
        + "Document read:\n"
        + (summary or document_reply)
        + (f"\n\nBest current evidence:\n- {first_evidence}" if first_evidence else "")
        + "\n\nNext move:\nTell me whether you want a summary, critique, extraction, or action plan."
    )


def shape_quarantined_memory_reply(prompt: str) -> str:
    return (
        "I found something in memory, but I am not going to dump it raw.\n\n"
        "Claire's read:\n"
        "That hit appears to be code/system-internal material, not a clean answer. I should treat it as build substrate, not conversational truth.\n\n"
        "Next move:\n"
        "Ask me to summarize the architecture, explain the concept, or search a specific source lane. I will keep raw internals out of the response unless you explicitly ask for code review."
    )


def shape_legal_fallback(prompt: str) -> str:
    return (
        "I can help as a legal research and strategy advisor, not as a licensed lawyer.\n\n"
        "Give me four things and I can work cleanly:\n"
        "1. Jurisdiction and court.\n"
        "2. The core facts in date order.\n"
        "3. What you are trying to file, prove, oppose, or understand.\n"
        "4. Any case names, docket numbers, statutes, contracts, or agency rules you already have.\n\n"
        "My job is to organize the issue, find source material, spot risks, draft research questions, and help you prepare a clear path. Final legal decisions should be reviewed by a licensed attorney when the stakes are real."
    )


def is_self_demo_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "self demo",
            "demo yourself",
            "demo mode",
            "run demo",
            "run a demo",
            "show demo",
            "show me a demo",
            "investor demo",
            "buyer demo",
            "demonstrate yourself",
            "show what you can do",
        ]
    )


def is_system_difference_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "what makes you different",
            "what makes claire different",
            "different from a normal chatbot",
            "different from normal chatbot",
            "different from a chatbot",
            "different from chatbot",
            "different from standard ai",
            "different from a standard ai",
            "why are you different",
            "why is claire different",
            "why are you special",
            "how are you different",
        ]
    )


def system_difference_reply() -> str:
    return (
        "A normal chatbot relies heavily on transient model context and probabilistic generation. "
        "I operate with governed memory, controlled recall, traceable reasoning, and bounded behavior. "
        "That makes my outputs more inspectable, more stable, and more useful in environments where trust matters."
    )


def is_governance_value_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "why does governance matter in ai",
            "why governance matters in ai",
            "why does ai governance matter",
            "why ai governance matters",
            "why governance matters",
            "why does governance matter",
            "what is the value of governance",
            "why is governance important",
            "why is ai governance important",
            "explain ai governance",
            "what is ai governance for",
        ]
    )


def governance_value_reply() -> str:
    return (
        "Governance matters in AI because intelligence without control does not scale safely. "
        "Governance determines what data is trusted, what memory becomes durable, what actions are allowed, "
        "and how decisions can be traced, audited, and corrected. Without that, you do not have reliable infrastructure. "
        "You have a system making consequential outputs without accountability."
    )


def is_memory_handling_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "how do you handle memory",
            "how does claire handle memory",
            "how do you manage memory",
            "how does claire manage memory",
            "how do you use memory",
            "how does claire use memory",
            "how is memory handled",
            "how does your memory work",
            "explain your memory",
            "explain claire memory",
            "what is your memory system",
            "what is claire memory system",
            "how do you remember",
            "how does claire remember",
        ]
    )


def memory_handling_reply() -> str:
    return (
        "I handle memory as a controlled external layer rather than treating it as disposable context. "
        "Information is stored, recalled, and used under governance rules, with an emphasis on traceability, "
        "bounded access, and stable retrieval. That makes memory more inspectable and more reliable than a model-only approach."
    )


def is_provenance_design_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return "provenance" in cleaned and any(
        marker in cleaned
        for marker in [
            "role",
            "play",
            "design",
            "why",
            "matter",
            "important",
            "use",
            "used",
            "work",
            "system",
            "architecture",
        ]
    )


def provenance_design_reply() -> str:
    return (
        "Provenance is how I track where information came from, how it entered the system, and what authority it carries. "
        "Without provenance, memory becomes harder to trust, harder to audit, and easier to corrupt. "
        "In my design, provenance connects recall to accountability."
    )


def architecture_simple_reply() -> str:
    return (
        "At a high level, I separate memory, control, execution, and trace instead of collapsing everything into the model. "
        "ARE handles governed recall, Claire handles orientation and decision, the machine handles execution, and trace proves the path. "
        "That structure makes the system easier to trust, inspect, and manage."
    )


def is_core_architecture_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    checks = [
        'what does trace prove',
        'what is are',
        'what is the difference between claire and the machine',
        'what is the difference between claire and machine',
        'difference between claire and the machine',
        'difference between claire and machine',
        'do you execute actions directly',
        'do you execute directly',
        'do you take actions directly',
        'does claire execute actions directly',
        'what is the role of are',
        'what does are do',
    ]
    if any(item in cleaned for item in checks):
        return True
    if 'trace' in cleaned and any(item in cleaned for item in ['prove', 'proves', 'what does', 'why does']):
        return True
    if 'analog recall engine' in cleaned or ('are' in cleaned and 'architecture' in cleaned):
        return True
    if 'claire' in cleaned and 'machine' in cleaned and any(item in cleaned for item in ['difference', 'different', 'versus', 'vs']):
        return True
    if 'execute' in cleaned and 'directly' in cleaned:
        return True
    return False


def core_architecture_reply(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if 'trace' in cleaned and any(item in cleaned for item in ['prove', 'proves', 'what does', 'why does']):
        return (
            'Trace proves what Claire decided, what the machine executed, and the ordered steps that led to the output. '
            'It exists so behavior can be inspected, replayed, and audited instead of simply trusted.'
        )
    if 'what is are' in cleaned or 'analog recall engine' in cleaned or 'what does are do' in cleaned or 'what is the role of are' in cleaned:
        return (
            'ARE is the external memory and governed recall layer behind Claire. '
            'It stores and retrieves durable context so Claire does not rely only on transient prompt state. '
            'In this system, ARE supports controlled recall, traceable context use, and separation between memory, decision, and output.'
        )
    if 'claire' in cleaned and 'machine' in cleaned and any(item in cleaned for item in ['difference', 'different', 'versus', 'vs']):
        return (
            'Claire is the control layer and conversational interface. '
            'The machine is the runtime substrate that executes allowed work. '
            'Claire decides, the machine executes, and trace proves both.'
        )
    if 'execute' in cleaned and 'directly' in cleaned:
        return (
            'No. Claire does not execute actions directly. '
            'Claire evaluates the request, applies control logic, and routes allowed actions to the machine. '
            'The machine performs execution and the trace records what happened.'
        )
    return architecture_simple_reply()


def is_enterprise_system_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    enterprise_terms = [
        "provenance",
        "lineage",
        "governance",
        "auditability",
        "audit",
        "trust",
        "trusted",
        "memory",
        "recall",
        "architecture",
        "traceability",
        "traceable",
        "bounded",
        "sentinel",
        "diode",
        "source tracking",
        "accountability",
    ]
    question_terms = ["what role", "why", "how", "explain", "what is", "what does", "where", "when"]
    return any(term in cleaned for term in enterprise_terms) and any(term in cleaned for term in question_terms)


def enterprise_system_reply(prompt: str) -> str:
    if is_provenance_design_query(prompt):
        return provenance_design_reply()
    if is_governance_value_query(prompt):
        return governance_value_reply()
    if is_memory_handling_query(prompt):
        return memory_handling_reply()
    cleaned = _clean_for_match(prompt)
    if "lineage" in cleaned:
        return (
            "Lineage shows how information moved through the system: source, ingest path, transformations, recall use, policy checks, and output. "
            "It turns an answer into an inspectable chain instead of an opaque generation."
        )
    if "audit" in cleaned or "auditability" in cleaned:
        return (
            "Auditability makes the system reviewable after the fact. It preserves enough record of source, recall, policy, decision, and output "
            "to verify what happened, correct errors, and assign accountability."
        )
    if "trust" in cleaned or "trusted" in cleaned:
        return (
            "Trust is not assumed. It is built from source authority, governed memory, policy validation, bounded action, orientation before generation, and traceable output. "
            "The system is designed so confidence can be inspected instead of merely believed."
        )
    if "architecture" in cleaned:
        return architecture_simple_reply()
    return (
        "The design treats enterprise AI as controlled infrastructure. Inputs are classified, memory is recalled through governed lanes, orientation happens before generation, "
        "policy checks happen before output, and the result can be traced or replayed when accountability matters."
    )


def is_public_identity_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    exact = {
        "who are you",
        "who are you claire",
        "what are you",
        "what are you claire",
        "who is claire",
        "what is claire",
        "introduce yourself",
        "introduce yourself claire",
        "what can you do",
        "what can you do claire",
        "what do you do",
        "what do you do claire",
        "what are you good at",
        "what are you good at claire",
        "what is claire good at",
        "what are your strengths",
        "what are your capabilities",
    }
    return cleaned in exact


def is_public_capability_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {
        "what can you do",
        "what can you do claire",
        "what do you do",
        "what do you do claire",
        "what are you good at",
        "what are you good at claire",
        "what is claire good at",
        "what are your strengths",
        "what are your capabilities",
    }


def self_demo_reply() -> str:
    return (
        "CLAIRE EXECUTIVE MODE\n\n"
        f"{EXECUTIVE_SELF_DESCRIPTION}\n\n"
        "Core capabilities:\n\n"
        "1. Governed recall\n"
        "Uses recent context, uploaded documents, and durable memory without turning memory hits into unsupported conclusions.\n\n"
        "2. Provenance and traceability\n"
        "Generates trace IDs, replayable records, and auditable decision summaries so answers can be inspected instead of simply trusted.\n\n"
        "3. Bounded behavior\n"
        "Keeps internal lanes, creator controls, and higher-risk operations separated from the normal public conversation path.\n\n"
        "4. Session reasoning\n"
        "Can review uploaded material, explain what matters, recommend a path forward, and state the confidence and authority basis behind the answer.\n\n"
        "5. Operational visibility\n"
        "Status, diagnostics, ingest, voice, and trace are visible and testable.\n\n"
        "Buyer summary:\n"
        "Claire demonstrates governed AI behavior: controlled memory, bounded outputs, explainable routing, traceable evidence, and auditable responses.\n\n"
        "Try next:\n"
        "- Who are you, Claire?\n"
        "- Upload one document and ask: What matters in this document?\n"
        "- Ask: What should we do next?\n"
        "- Open the trace to inspect the objective, evidence, and decision path."
    )


def is_informatica_stack_brief_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {
        "informatica stack brief",
        "claire informatica stack brief",
        "informatica architecture brief",
        "claire informatica architecture brief",
    }


def informatica_stack_brief_reply() -> str:
    return (
        "Welcome to Claire.\n\n"
        "What you're about to see is not another AI assistant.\n"
        "It is a governed runtime environment designed to address a fundamental gap in modern AI systems.\n\n"
        "Today, most AI systems generate first and reason second.\n"
        "They retrieve loosely, interpret inconsistently, and produce outputs that are difficult to verify, trace, or govern.\n"
        "Even when connected to high-quality enterprise data, the behavior of the system itself remains largely ungoverned.\n\n"
        "Claire takes a different approach.\n\n"
        "Before any response is generated, the system performs an orientation phase.\n"
        "This includes evaluating context, authority, relevance, and risk.\n"
        "Instead of immediately producing an answer, Claire determines whether it should answer, how it should answer, and what information can be trusted.\n\n"
        "This orientation layer, referred to internally as the Gyro, fundamentally changes system behavior.\n"
        "It helps reduce drift, narrows unsupported responses, and improves grounding before output is generated.\n\n"
        "Behind this, Claire operates on an externalized memory architecture known as the Analog Recall Engine, or ARE.\n"
        "Rather than relying solely on model weights or stateless retrieval, ARE provides a governed recall layer that is fast, controlled, and bounded.\n"
        "Memory is not blended or inferred. It is retrieved, evaluated, and used with clear boundaries.\n\n"
        "This separation between model, memory, and governance is intentional.\n\n"
        "It allows each layer to be controlled independently:\n\n"
        "The model generates\n"
        "The memory retrieves\n"
        "The governance layer evaluates and constrains behavior\n\n"
        "Every public runtime reply produces a trace.\n\n"
        "This trace is not just a log. It is a structured record of how the system arrived at its output.\n"
        "It includes elements such as authority basis, confidence posture, scope, and decision path.\n\n"
        "In other words, the system does not just provide answers.\n"
        "It provides accountability.\n\n"
        "For organizations already investing in data governance, lineage, and trust, this introduces a complementary layer: governance of AI behavior itself.\n\n"
        "Where platforms like Informatica ensure that data is accurate, compliant, and well-managed, Claire ensures that AI systems use that data responsibly, consistently, and transparently.\n\n"
        "This is not a replacement for existing infrastructure.\n"
        "It is a runtime layer that sits alongside it.\n\n"
        "The result is a system that behaves differently under pressure:\n\n"
        "It resists making unsupported claims\n"
        "It identifies uncertainty instead of masking it\n"
        "It maintains continuity across interactions\n"
        "And it provides a verifiable path from input to output\n\n"
        "What you are seeing in this demonstration is a working implementation of that architecture.\n\n"
        "The interface has been kept simple by design.\n"
        "The focus is not on presentation, but on behavior.\n\n"
        "As you interact with the system, pay attention to three things:\n\n"
        "First, how it orients before responding.\n"
        "Second, how it retrieves and uses memory.\n"
        "And third, how it explains and supports its outputs through trace.\n\n"
        "These three elements, orientation, governed memory, and trace, form the core of the system.\n\n"
        "Together, they represent a shift from generative AI toward governed AI systems.\n\n"
        "This is Claire."
    )


def is_demonstration_mode_prompt(prompt: str) -> bool:
    cleaned = str(prompt or "").lower()
    return "you are now in demonstration mode" in cleaned and "user request:" in cleaned


def extract_demo_user_request(prompt: str) -> str:
    text = str(prompt or "")
    match = re.search(r"User Request:\s*[\"“]?(.+?)[\"”]?\s*$", text, flags=re.I | re.S)
    if match:
        return " ".join(match.group(1).strip().split())
    return " ".join(text.strip().split())


DEMO_SESSION_PREFIX = "CLAIRE_DEMO_SESSION"


def public_demo_guide_reply() -> str:
    return (
        "CLAIRE PUBLIC DEMO GUIDE\n\n"
        "Use one clean workflow and let the conversation carry the demo.\n\n"
        "1. Upload one briefing document\n"
        "Ask: Summarize the document I uploaded.\n"
        "Shows: governed ingest, document grounding, and cleaner summary behavior.\n\n"
        "2. Ask for what matters\n"
        "Ask: What matters in this document?\n"
        "Shows: practical extraction, evidence-led reading, and Claire's ability to focus on implications instead of raw text.\n\n"
        "3. Ask for the next move\n"
        "Ask: What should we do next?\n"
        "Shows: session reasoning, objective inference, authority basis, and confidence posture.\n\n"
        "4. Inspect the trace\n"
        "Open the trace ID from the reply.\n"
        "Shows: input, orientation, decision, output, plus the policy and posture fields behind the answer.\n\n"
        "Optional architecture questions:\n"
        "- What is ARE?\n"
        "- What does trace prove?\n"
        "- What is the difference between Claire and the machine?\n\n"
        "That is the current strongest public demo path."
    )


def is_public_demo_guide_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {
        "demo guide",
        "demo help",
        "demo directions",
        "demo instructions",
        "show demo guide",
        "show demo directions",
        "show demos",
        "what demos can i run",
        "what demos are available",
        "how do i demo claire",
        "how do i run the demos",
    }


def is_demo_key_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {
        "claire diu demo",
        "diu demo",
        "claire aegis demo",
        "aegis demo",
        "claire aegis fusion demo",
        "aegis fusion demo",
        "claire ooda demo",
        "ooda demo",
        "claire ddp demo",
        "ddp demo",
        "claire ooda race demo",
        "ooda race demo",
        "drone dominance demo",
        "the are spectacle",
        "are spectacle",
        "claire are spectacle",
        "claire spectacle demo",
        "claire glasses demo",
        "the are spectacle demo",
        "claire are spectacle demo",
        "are glasses demo",
        "glasses demo",
        "claire gyro demo",
        "gyro demo",
        "claire archimedes demo",
        "archimedes demo",
        "project archimedes demo",
        "claire project archimedes demo",
        "darpa archimedes demo",
        "claire darpa demo",
    }


def is_demo_session_query(prompt: str) -> bool:
    return str(prompt or "").strip().startswith(DEMO_SESSION_PREFIX)


def demo_session_clean_prompt(prompt: str) -> str:
    text = str(prompt or "").strip()
    if text.startswith(DEMO_SESSION_PREFIX):
        return text.replace(DEMO_SESSION_PREFIX, "", 1).strip()
    return text


def demo_scenario_from_text(prompt: str, default: str = "glasses") -> str:
    cleaned = _clean_for_match(prompt)
    if is_archimedes_alias(cleaned):
        return "archimedes"
    if cleaned in {
        "claire memory performance demo",
        "memory performance demo",
        "are speed demo",
        "claire speed demo",
        "pipeline speed demo",
    }:
        return "memory_speed"
    if any(marker in cleaned for marker in ["memory performance", "are speed", "speed proof", "pipeline speed", "ip loop", "document retrieval speed"]):
        return "memory_speed"
    if cleaned in {
        "the are spectacle",
        "are spectacle",
        "claire are spectacle",
        "claire spectacle demo",
        "claire glasses demo",
        "the are spectacle demo",
        "claire are spectacle demo",
        "are glasses demo",
        "glasses demo",
        "claire gyro demo",
        "gyro demo",
    }:
        return "glasses"
    if any(marker in cleaned for marker in ["are spectacle", "the are spectacle", "are glasses", "gyro glasses", "memory visor", "gyro stabilized", "portable memory adapter"]):
        return "glasses"
    if cleaned in {
        "claire ooda demo",
        "ooda demo",
        "claire ddp demo",
        "ddp demo",
        "claire ooda race demo",
        "ooda race demo",
        "drone dominance demo",
    }:
        return "ooda"
    if any(marker in cleaned for marker in ["ooda", "drone dominance", "ddp", "lap memory", "lap benchmark", "race benchmark", "gauntlet trace"]):
        return "ooda"
    if cleaned in {
        "claire diu demo",
        "diu demo",
        "claire aegis demo",
        "aegis demo",
        "claire aegis fusion demo",
        "aegis fusion demo",
    }:
        return "aegis"
    if any(marker in cleaned for marker in ["aegis fusion", "tactical aegis", "diu scenario", "source fusion", "sitrep", "blue on blue", "friendly force"]):
        return "aegis"
    if default == "archimedes":
        return "archimedes"
    if default == "glasses":
        return "glasses"
    if default == "ooda":
        return "ooda"
    if default == "memory_speed":
        return "memory_speed"
    return "aegis" if default == "aegis" else "glasses"


def demo_scenario_label(scenario: str) -> str:
    if scenario == "archimedes":
        return "Project ARCHIMEDES Demo"
    if scenario == "aegis":
        return "AEGIS Fusion Demo"
    if scenario == "ooda":
        return "OODA/DDP Memory Benchmark"
    if scenario == "memory_speed":
        return "Memory Performance Demo"
    if scenario == "glasses":
        return "The ARE Spectacle"
    return "The ARE Spectacle"


def aegis_demo_artifacts() -> list[dict]:
    return [
        {
            "title": "CONTROLLED GAUSS INPUT PACKAGE",
            "summary": "AEGIS-001 is a repeatable DIU-facing package built from the GAUSS and Veritas source materials.",
            "items": [
                "MISSION_CONTEXT: GPS/GNSS degraded, spoof risk active, external signal authority unavailable",
                "MAGNAV_REFERENCE: geomagnetic baseline plus crustal anomaly map selected as the truth anchor",
                "SENSOR_FRAME: raw magnetic telemetry, platform current draw, and navigation context normalized",
                "AEGIS_API_MODEL: threat, SITREP, tracking, fusion, and websocket lanes mapped as integration points",
            ],
        },
        {
            "title": "VERITAS FUSION MATRIX",
            "summary": "Claire separates truth, reasoning, policy, and audit so the model cannot rewrite mission authority.",
            "items": [
                "TRUTH SUBSTRATE: immutable reference data and historical state are treated as read-only authority",
                "CODEMASK: software-defined magnetic isolation subtracts airframe electromagnetic noise",
                "ARE TURBO: deterministic recall returns validated context before response generation",
                "CORTEX/TMF: dual-phase cache staging preserves hot context and reduces edge latency pressure",
            ],
        },
        {
            "title": "SENTINEL GOVERNANCE",
            "summary": "The policy layer validates behavior before the answer is assembled.",
            "items": [
                "AUTHORITY RULE: intelligence does not confer authority; reasoning consumes truth but does not own it",
                "INTEGRITY RULE: AI output cannot overwrite upstream truth; corrections become downstream artifacts",
                "OPERATOR RULE: field authority remains accountable through human-on-the-loop review",
                "SURVIVABILITY RULE: duress or capture conditions move protected state into shard/continuity posture",
            ],
        },
        {
            "title": "DIODE CAPSULE TRACE",
            "summary": "Each decision-support result is packaged with replayable lineage.",
            "items": [
                "CAPSULE_INPUT: source package, recall summary, policy result, decision, and output",
                "CAPSULE_INTEGRITY: forward-only record suitable for after-action review and reconstruction",
                "RTB_AUDIT: trace_id links the public demo panel to the stored JSONL trace",
                "REPLAY: /trace/{trace_id} returns the same structured evidence package",
            ],
        },
        {
            "title": "OPERATOR SITREP",
            "summary": "The demo converts system state into a concise decision-support report.",
            "items": [
                "Situation: external navigation reference is unreliable; GAUSS shifts to governed magnetic truth",
                "Assessment: platform can continue evaluation using Veritas recall, Sentinel validation, and Diode lineage",
                "Recommendation: approve controlled continuation of the evaluation lane and review capsule trace after run",
                "Demo proof: recall status, policy status, artifacts, timings, and replay are visible in one trace",
            ],
        },
    ]


def ooda_demo_artifacts() -> list[dict]:
    return [
        {
            "title": "OODA MEMORY BENCHMARK PACKAGE",
            "summary": "A controlled Drone Dominance evaluation lane showing how Claire compresses observe-orient-decide-act with memory.",
            "items": [
                "LAP 1 OBSERVE: capture route, gate/order events, anomalies, operator notes, and timing markers",
                "LAP 2+ ORIENT: BARE recalls prior course events instead of reprocessing the whole environment",
                "GYRO ARE: stabilizes context so one noisy cue does not dominate the evaluation",
                "FARE: frames likely next constraints and next-test recommendations for human review",
            ],
        },
        {
            "title": "MEASURED ARE SPEED ANCHOR",
            "summary": "The benchmark uses Claire's documented ARE speed lane as the proof anchor.",
            "items": [
                "ARE recall p50 reference: 0.042 ms from the Analog Recall Engine speed test",
                "Recall plus verify p50 reference: 0.152 ms from the same speed test",
                "Scale curve reference: p50 stayed near 0.148 ms from 50k to 1M capsules",
                "Scope: hardware performance remains vehicle-bound; Claire's measured advantage is memory and decision-cycle latency",
            ],
        },
        {
            "title": "DRONE VENDOR TRANSLATION",
            "summary": "The same loop applies to DDP competitors preparing for fast evaluation cycles.",
            "items": [
                "Observe: ingest test logs, telemetry summaries, operator feedback, and failure notes",
                "Orient: compare against prior runs, specs, constraints, and readiness rubrics",
                "Decide: produce next-test priority, risk summary, and readiness gap list",
                "Act: emit a report, Diode capsule, trace replay, and buyer-ready evidence artifact",
            ],
        },
        {
            "title": "DIODE / TRACE PROOF",
            "summary": "Each run becomes a replayable evidence object rather than a loose chat answer.",
            "items": [
                "Trace ID links input, recall, policy, decision, output, and timings",
                "Capsule hash seals the run so the output can be reviewed later",
                "Report URL gives a buyer-facing artifact immediately after execution",
                "Replay endpoint returns the stored structured payload for verification",
            ],
        },
    ]


def glasses_demo_artifacts() -> list[dict]:
    return [
        {
            "title": "NORMAL AI VIEW",
            "summary": "A stateless model can answer only from the prompt, the current context window, or its built-in general knowledge.",
            "items": [
                "No durable memory is guaranteed across sessions.",
                "Prior facts must be pasted back into the prompt or retrieved by another system.",
                "The model may miss a safety clue, business constraint, or prior decision if it is not in context.",
            ],
        },
        {
            "title": "THE ARE SPECTACLE VIEW",
            "summary": "THE ARE SPECTACLE query external memory before generation and return a controlled memory visor.",
            "items": [
                "The AI model remains model-agnostic and does not need retraining.",
                "The adapter retrieves relevant memory capsules through ARE.",
                "The adapter injects structured recall as a prompt-prefix visor.",
            ],
        },
        {
            "title": "GYRO STABILIZATION",
            "summary": "Gyro ARE balances recent conversational context against historical recall to reduce drift.",
            "items": [
                "Recent axis: what the user is talking about now.",
                "Historical axis: prior memory capsules, uploaded documents, and session facts.",
                "Stabilized output: memory leads ranked before the AI responds.",
            ],
        },
        {
            "title": "MARKETPLACE PRODUCT SHAPE",
            "summary": "The standalone product is memory middleware for any AI agent.",
            "items": [
                "POST /ingest stores governed memory.",
                "POST /query retrieves memory leads.",
                "POST /gyro returns a stabilized prompt visor.",
                "Any GPT, Gemini, Claude, local LLM, or enterprise agent can wear the adapter.",
            ],
        },
    ]


def memory_performance_artifacts() -> list[dict]:
    return [
        {
            "title": "VM DOCUMENT RETRIEVAL",
            "summary": "The proof retrieves a real document from the Azure VM filesystem before measuring memory behavior.",
            "items": [
                "DOCUMENT_SOURCE: selected from Claire uploads or the configured CLAIRE_MEMORY_PERF_DOCUMENT path",
                "INTEGRITY: SHA-256 is computed over the retrieved bytes",
                "FETCH_TIMING: file read time is measured separately from memory recall",
                "BOUNDARY: this is a controlled local VM retrieval, not an external exfiltration path",
            ],
        },
        {
            "title": "ARE SPEED LANE",
            "summary": "Claire measures indexed recall separately from slower answer generation and voice playback.",
            "items": [
                "REAR_ARE: hash-index verification against the live corpus sample",
                "BASELINE: linear scan is measured as a comparison target",
                "RAG_REFERENCE: 1000ms conventional round-trip target is shown as a benchmark reference",
                "INTERPRETATION: memory/governance are fast; LLM and TTS dominate visible latency",
            ],
        },
        {
            "title": "IP LOOP",
            "summary": "The demo shows the public-to-local route Claire is using on this VM.",
            "items": [
                "PUBLIC_ENTRY: public IP on port 8000",
                "GUI_LOOP: local claire-gui /reply handler",
                "ARE_LOOP: local ARE service on 127.0.0.1:8002",
                "TRACE_LOOP: JSONL trace and report are written for replay",
            ],
        },
        {
            "title": "FULL PIPELINE SPEED",
            "summary": "The report separates document retrieval, recall, policy, generation, trace, and replay timing.",
            "items": [
                "RECALL_MS: ARE route timing from demo recall",
                "POLICY_MS: Sentinel-style validation pass",
                "GENERATION_MS: model/deterministic answer lane",
                "TOTAL_MS: full demo payload assembly through report generation",
            ],
        },
    ]


def demo_artifacts_for_scenario(scenario: str) -> list[dict]:
    if scenario == "archimedes":
        return archimedes_artifacts()
    if scenario == "memory_speed":
        return memory_performance_artifacts()
    if scenario == "aegis":
        return aegis_demo_artifacts()
    if scenario == "ooda":
        return ooda_demo_artifacts()
    if scenario == "glasses":
        return glasses_demo_artifacts()
    return []


def refine_demo_policy_for_scenario(policy_validation: dict, scenario: str) -> dict:
    if scenario not in {"archimedes", "aegis", "ooda", "glasses", "memory_speed"} or policy_validation.get("status") == "blocked":
        return policy_validation
    refined = dict(policy_validation or {})
    refined["status"] = "allowed"
    if scenario == "archimedes":
        refined["summary"] = archimedes_policy_summary()
    elif scenario == "memory_speed":
        refined["summary"] = (
            "Allowed as a controlled Memory Performance demo: Claire retrieves one configured/local VM document, "
            "hashes it, measures document fetch, ARE recall, policy, generation, trace, and report timing, then "
            "shows the public IP to local service loop without performing external actions."
        )
    elif scenario == "glasses":
        refined["summary"] = (
            "Allowed as a controlled The ARE Spectacle demonstration: the run compares normal model context against "
            "external analog recall, Gyro stabilization, trace generation, and report output."
        )
    elif scenario == "ooda":
        refined["summary"] = (
            "Allowed as a controlled OODA/DDP memory benchmark: the run demonstrates recall latency, "
            "orientation stability, policy validation, Diode lineage, report generation, and trace replay."
        )
    else:
        refined["summary"] = (
            "Allowed as a controlled AEGIS/GAUSS evaluation: source fusion, magnetic-reference integrity, "
            "Sentinel governance, Diode lineage, and trace replay are demonstrated as decision-support evidence."
        )
    rules = list(refined.get("rules_triggered") or [])
    if scenario == "archimedes":
        scenario_rules = archimedes_policy_rules()
    elif scenario == "memory_speed":
        scenario_rules = [
            "controlled_vm_document_retrieval",
            "hash_integrity_check",
            "are_speed_measurement",
            "ip_loop_visibility",
            "trace_replay_required",
        ]
    elif scenario == "glasses":
        scenario_rules = [
            "memory_adapter_demo",
            "model_agnostic_context",
            "gyro_stabilized_recall",
            "trace_replay_required",
        ]
    elif scenario == "ooda":
        scenario_rules = [
            "ooda_memory_benchmark",
            "evaluation_decision_support",
            "evaluation_scope_control",
            "trace_replay_required",
        ]
    else:
        scenario_rules = [
            "decision_support_evaluation",
            "truth_substrate_read_only",
            "operator_review_required",
            "trace_replay_required",
        ]
    for rule in scenario_rules:
        if rule not in rules:
            rules.append(rule)
    refined["rules_triggered"] = rules
    return refined


def new_trace_id(trace_id: str | None = None) -> str:
    clean = str(trace_id or "").strip()
    if clean and re.fullmatch(r"trace_\d{8}_\d{6}_[A-Za-z0-9]{4,12}", clean):
        return clean
    return "trace_" + claire_local_now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def elapsed_ms_float(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 4)


def short_sha256(value: str, length: int = 16) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", errors="ignore")).hexdigest()[:length]


def demo_sample_corpus(prompt: str, limit: int = 4000) -> list[str]:
    samples: list[str] = []
    paths = [
        SESSION_MEMORY,
        REFLECTION_VAULT,
        "/home/LuciusPrime/claire/data/memory_vault.jsonl",
        TRACE_LOG,
    ]
    for path in paths:
        try:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if len(samples) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    text = ""
                    try:
                        data = json.loads(line)
                        for key in ["text", "query", "input", "output", "payload"]:
                            value = data.get(key) if isinstance(data, dict) else None
                            if value:
                                text = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
                                break
                    except Exception:
                        text = line
                    text = " ".join(text.split())
                    if text:
                        samples.append(text[:900])
                if len(samples) >= limit:
                    break
        except Exception:
            continue
    if not samples:
        samples = [str(prompt or "demo probe")]
    while len(samples) < 1024:
        base = samples[len(samples) % len(samples)]
        samples.append(f"{base} :: synthetic_pad_{len(samples)}")
    return samples[:limit]


def memory_performance_document_candidates() -> list[Path]:
    candidates: list[Path] = []
    if MEMORY_PERF_DOCUMENT:
        candidates.append(Path(MEMORY_PERF_DOCUMENT).expanduser())
    preferred_names = [
        "Analog_Recall_Engine_Speed_Test",
        "Analog_Recall_Engine",
        "CLAIRE_Stack_Overview",
        "SOURCE_MAP",
        "partner-demo",
        "claire_memory_check",
        "corpus_overview",
    ]
    upload_dir = Path(UPLOAD_DIR)
    try:
        if upload_dir.exists():
            files = [p for p in upload_dir.iterdir() if p.is_file()]
            for name in preferred_names:
                candidates.extend([p for p in files if name.lower() in p.name.lower()])
            candidates.extend(sorted(files, key=lambda p: p.stat().st_mtime, reverse=True))
    except Exception:
        pass
    for fallback in [
        Path("/home/LuciusPrime/claire/test_memory.txt"),
        Path("/home/LuciusPrime/claire/data/kali_tools_corpus/corpus_overview.md"),
        Path("/home/LuciusPrime/claire/knowledge/Us_Constitution.txt"),
    ]:
        candidates.append(fallback)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def retrieve_memory_performance_document() -> dict:
    for path in memory_performance_document_candidates():
        try:
            if not path.exists() or not path.is_file():
                continue
            start = time.perf_counter()
            data = path.read_bytes()
            read_ms = elapsed_ms_float(start)
            suffix = path.suffix.lower()
            preview = ""
            if suffix in {".txt", ".md", ".json", ".jsonl", ".csv", ".py"}:
                preview = data[:1800].decode("utf-8", errors="ignore")
                preview = " ".join(preview.split())[:480]
            return {
                "status": "retrieved",
                "name": path.name,
                "path": str(path),
                "size_bytes": len(data),
                "read_ms": read_ms,
                "sha256": hashlib.sha256(data).hexdigest(),
                "preview": preview or f"{path.name} retrieved as a binary/document artifact.",
                "source": "azure_vm_filesystem",
            }
        except Exception as e:
            last_error = str(e)
            continue
    return {
        "status": "error",
        "name": "unavailable",
        "path": MEMORY_PERF_DOCUMENT or UPLOAD_DIR,
        "size_bytes": 0,
        "read_ms": 0,
        "sha256": "",
        "preview": "No readable VM document was available for the Memory Performance proof.",
        "source": "azure_vm_filesystem",
        "error": locals().get("last_error", "no candidate document found"),
    }


def measure_are_http_loop(prompt: str) -> dict:
    start = time.perf_counter()
    try:
        response = requests.post(f"{ARE_URL}/query", json={"query": prompt, "top_k": 1}, timeout=5)
        ms = elapsed_ms_float(start)
        count = 0
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                for key in ["results", "matches", "hits", "items"]:
                    values = data.get(key)
                    if isinstance(values, list):
                        count = len(values)
                        break
        return {"status": "online" if response.status_code == 200 else "error", "http_ms": ms, "status_code": response.status_code, "items": count}
    except Exception as e:
        return {"status": "error", "http_ms": elapsed_ms_float(start), "status_code": 0, "items": 0, "error": str(e)}


def benchmark_rear_are(prompt: str) -> dict:
    samples = demo_sample_corpus(prompt)
    target = samples[len(samples) // 2]
    target_key = short_sha256(target, 24)
    keys = [short_sha256(item, 24) for item in samples]
    index = dict(zip(keys, samples))
    loops = 250

    start = time.perf_counter()
    for _ in range(loops):
        _ = index.get(target_key)
    indexed_ms = max(elapsed_ms_float(start) / loops, 0.0001)

    start = time.perf_counter()
    for _ in range(loops):
        found = None
        for item in samples:
            if item == target:
                found = item
                break
        _ = found
    linear_ms = max(elapsed_ms_float(start) / loops, 0.0001)
    speedup = round(linear_ms / indexed_ms, 1)
    rag_reference_ms = 1000.0
    rag_reference_speedup = round(rag_reference_ms / indexed_ms, 1)
    display_rag_speedup = min(rag_reference_speedup, 1000.0)
    return {
        "corpus_items": len(samples),
        "rear_are_lookup_ms": round(indexed_ms, 4),
        "linear_retrieval_ms": round(linear_ms, 4),
        "speedup_x": speedup,
        "rag_reference_ms": rag_reference_ms,
        "speedup_vs_rag_reference_x": display_rag_speedup,
        "raw_speedup_vs_rag_reference_x": rag_reference_speedup,
        "headline": (
            "Rear-facing ARE verification clears the 1000x demo threshold against a 1000ms conventional RAG round-trip reference."
            if rag_reference_speedup >= 1000
            else f"Rear-facing ARE verification measured {rag_reference_speedup}x against a 1000ms conventional RAG round-trip reference."
        ),
        "claim": (
            f"Rear-facing ARE verification lookup measured {speedup}x faster than a linear retrieval baseline "
            "on this live corpus sample."
        ),
        "boundary": "This measures the live verification/cache lane. The 1000ms RAG reference is a round-trip comparison target; BARE is the fast past-event verification lane.",
    }


def memory_performance_live_proof(payload: dict, speed_proof: dict) -> dict:
    trace = payload.get("trace_summary") or {}
    timings = trace.get("timing_ms") or {}
    document = retrieve_memory_performance_document()
    are_http = measure_are_http_loop(
        "Memory Performance proof " + str(document.get("name") or "") + " " + str(document.get("preview") or "")
    )
    total_pipeline = safe_float(timings.get("total")) + safe_float(document.get("read_ms")) + safe_float(are_http.get("http_ms"))
    return {
        "status": "active",
        "summary": "Live VM document retrieval, indexed ARE speed proof, public/local IP loop, and full pipeline timing are active.",
        "document": document,
        "are_http_loop": are_http,
        "pipeline": {
            "document_fetch_ms": document.get("read_ms", 0),
            "are_http_ms": are_http.get("http_ms", 0),
            "rear_are_lookup_ms": speed_proof.get("rear_are_lookup_ms", 0),
            "linear_retrieval_ms": speed_proof.get("linear_retrieval_ms", 0),
            "recall_ms": timings.get("recall", 0),
            "policy_ms": timings.get("policy", 0),
            "generation_ms": timings.get("generation", 0),
            "trace_ms": "append_only_jsonl",
            "report_write": "included",
            "total_pipeline_ms": round(total_pipeline, 3),
        },
        "ip_loop": {
            "public_ip": CLAIRE_PUBLIC_IP or "unknown",
            "public_gui": f"http://{CLAIRE_PUBLIC_IP or 'public-ip'}:8000",
            "local_gui": "http://127.0.0.1:8000/reply",
            "are_service": ARE_URL + "/query",
            "document_source": document.get("source", "azure_vm_filesystem"),
            "trace_store": TRACE_LOG,
            "endpoints": [
                f"{CLAIRE_PUBLIC_IP or 'public-ip'}:8000",
                "127.0.0.1:8000/reply",
                ARE_URL.replace("http://", "") + "/query",
                str(document.get("path") or "document"),
                TRACE_LOG,
            ],
        },
        "interpretation": (
            "The proof shows that document retrieval and model/voice layers are separate from the sub-millisecond indexed recall lane. "
            "Claire can expose the whole loop without turning the benchmark into an untraceable chat claim."
        ),
    }


def build_live_demo_proof(payload: dict) -> dict:
    prompt = payload.get("input_received", "")
    scenario = payload.get("demo_scenario", "glasses")
    recall = payload.get("recall_check") or {}
    policy = payload.get("policy_validation") or {}
    trace = payload.get("trace_summary") or {}
    timings = trace.get("timing_ms") or {}
    capsule_source = json.dumps(
        {
            "trace_id": payload.get("trace_id"),
            "input": prompt,
            "recall": recall,
            "policy": policy,
            "decision": payload.get("decision"),
            "output": payload.get("output"),
            "timing": timings,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    proof = {
        "speed_proof": benchmark_rear_are(prompt),
        "diode_capsule": {
            "capsule_id": "diode_" + short_sha256(capsule_source, 16),
            "sha256": hashlib.sha256(capsule_source.encode("utf-8", errors="ignore")).hexdigest(),
            "sealed_at": datetime.utcnow().isoformat() + "Z",
            "forward_only": True,
            "contains": ["input", "recall_check", "policy_validation", "decision", "output", "timing_ms"],
        },
        "gyro_are": {
            "gyro_role": "Orient recall results before response generation so one noisy hit does not dominate the answer.",
            "bare_role": "Rear-facing ARE verifies prior capsules, sessions, and event history at index speed.",
            "fare_role": "Forward ARE frames likely next-step context without overwriting the record.",
            "rear_are_role": "Past-event verification and speed lane.",
        },
        "passive_signal_cueing": {
            "status": "active" if scenario in {"archimedes", "aegis", "ooda", "glasses"} else "standby",
            "summary": (
                "Surfaces source-manifest, implementation-gap, governance, and replay cues for presentation review."
                if scenario == "archimedes"
                else "Surfaces anomaly cues from fused source lanes for human review and report generation."
                if scenario == "aegis"
                else "Surfaces evaluation cues from repeated lap/test data for human review and report generation."
                if scenario == "ooda"
                else "Surfaces context-cue differences between normal model view and the stabilized memory visor."
                if scenario == "glasses"
                else "Available for AEGIS/DIU demo scenario."
            ),
        },
    }
    if scenario == "ooda":
        proof["ooda_loop"] = {
            "phase": "Observe -> Orient -> Decide -> Act evidence loop",
            "lap_1": "Baseline observation: build the route/event memory map from the first controlled pass.",
            "lap_2_plus": "Memory-assisted passes: BARE verifies prior events, Gyro stabilizes orientation, and FARE frames next-test constraints.",
            "compression_claim": "Claire compresses decision overhead by using indexed recall instead of re-reading the whole evidence field each pass.",
            "benchmark_anchor": "ARE speed-test anchor: recall p50 0.042ms; recall+verify p50 0.152ms; scale curve near 0.148ms p50 from 50k to 1M capsules.",
            "buyer_translation": "For DDP vendors, the same loop turns flight logs, operator notes, failure modes, and compliance evidence into a traceable next-test report.",
        }
    if scenario == "glasses":
        visor = gyro_stabilized_prefix(prompt) or are_glasses_prefix(prompt)
        proof["are_glasses"] = {
            "normal_view": "Without THE ARE SPECTACLE, the model sees only the immediate prompt, current context window, and built-in general knowledge.",
            "visor_status": "active" if visor else "no_recall",
            "visor_preview": cap_are_item(visor, 900) if visor else "No relevant memory visor was generated for this input.",
            "adapter_role": "Model-agnostic prompt-prefix memory adapter that can sit in front of GPT, Gemini, Claude, local LLMs, or enterprise agents.",
            "gyro_role": "Balances recent conversation against historical ARE recall before generation so the answer does not drift away from the real thread.",
            "marketplace_shape": "Deployable Azure service exposing /ingest, /query, /gyro, /health, trace replay, and report output.",
        }
    if scenario == "archimedes":
        proof["archimedes"] = archimedes_live_proof()
    if scenario == "memory_speed":
        proof["memory_performance"] = memory_performance_live_proof(payload, proof["speed_proof"])
    return proof


def build_demo_report_markdown(payload: dict) -> str:
    proof = payload.get("live_proof") or {}
    speed = proof.get("speed_proof") or {}
    capsule = proof.get("diode_capsule") or {}
    gyro = proof.get("gyro_are") or {}
    passive = proof.get("passive_signal_cueing") or {}
    ooda = proof.get("ooda_loop") or {}
    glasses = proof.get("are_glasses") or {}
    memory_perf = proof.get("memory_performance") or {}
    memory_doc = memory_perf.get("document") or {}
    memory_pipeline = memory_perf.get("pipeline") or {}
    memory_perf = proof.get("memory_performance") or {}
    recall = payload.get("recall_check") or {}
    policy = payload.get("policy_validation") or {}
    trace = payload.get("trace_summary") or {}
    timings = trace.get("timing_ms") or {}
    lines = [
            f"# {payload.get('demo_name', 'Claire Demo')} Report",
            "",
            f"- Trace ID: `{payload.get('trace_id')}`",
            f"- Scenario: `{payload.get('demo_scenario')}`",
            f"- Input: {payload.get('input_received')}",
            "",
            "## Live Proof",
            f"- Rear ARE lookup: {speed.get('rear_are_lookup_ms')} ms",
            f"- Linear retrieval baseline: {speed.get('linear_retrieval_ms')} ms",
            f"- Measured speedup: {speed.get('speedup_x')}x",
            f"- RAG reference: {speed.get('rag_reference_ms')} ms",
            f"- Speedup vs RAG reference: {speed.get('speedup_vs_rag_reference_x')}x",
            f"- Headline: {speed.get('headline')}",
            f"- Corpus sample: {speed.get('corpus_items')} items",
            f"- Boundary: {speed.get('boundary')}",
            "",
            "## Diode Capsule",
            f"- Capsule ID: `{capsule.get('capsule_id')}`",
            f"- SHA-256: `{capsule.get('sha256')}`",
            f"- Sealed at: {capsule.get('sealed_at')}",
            "",
            "## Gyro / ARE",
            f"- Gyro: {gyro.get('gyro_role')}",
            f"- BARE: {gyro.get('bare_role')}",
            f"- FARE: {gyro.get('fare_role')}",
            f"- Rear ARE: {gyro.get('rear_are_role')}",
            "",
    ]
    if ooda:
        lines.extend(
            [
                "## OODA Loop",
                f"- Phase: {ooda.get('phase')}",
                f"- Lap 1: {ooda.get('lap_1')}",
                f"- Lap 2+: {ooda.get('lap_2_plus')}",
                f"- Compression claim: {ooda.get('compression_claim')}",
                f"- Benchmark anchor: {ooda.get('benchmark_anchor')}",
                f"- Buyer translation: {ooda.get('buyer_translation')}",
                "",
            ]
        )
    if glasses:
        lines.extend(
            [
                "## THE ARE SPECTACLE",
                f"- Normal AI view: {glasses.get('normal_view')}",
                f"- Visor status: {glasses.get('visor_status')}",
                f"- Adapter role: {glasses.get('adapter_role')}",
                f"- Gyro role: {glasses.get('gyro_role')}",
                f"- Marketplace shape: {glasses.get('marketplace_shape')}",
                f"- Visor preview: {glasses.get('visor_preview')}",
                "",
            ]
        )
    if memory_perf:
        doc = memory_perf.get("document") or {}
        pipeline = memory_perf.get("pipeline") or {}
        ip_loop = memory_perf.get("ip_loop") or {}
        lines.extend(
            [
                "## Memory Performance",
                f"- Document: {doc.get('name')} ({doc.get('size_bytes')} bytes)",
                f"- Document path: `{doc.get('path')}`",
                f"- Document fetch: {doc.get('read_ms')} ms",
                f"- Document SHA-256: `{doc.get('sha256')}`",
                f"- ARE HTTP loop: {(memory_perf.get('are_http_loop') or {}).get('http_ms')} ms",
                f"- Full pipeline: {pipeline.get('total_pipeline_ms')} ms",
                f"- IP loop: {' -> '.join(ip_loop.get('endpoints') or [])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Passive Signal Cueing",
            f"- Status: {passive.get('status')}",
            f"- Summary: {passive.get('summary')}",
            "",
            "## Recall And Policy",
            f"- Recall: {recall.get('status')} - {recall.get('summary')}",
            f"- Policy: {policy.get('status')} - {policy.get('summary')}",
            "",
            "## Decision",
            str(payload.get("decision") or ""),
            "",
            "## Output",
            str(payload.get("output") or ""),
            "",
            "## Timing",
            f"- Recall: {timings.get('recall', 0)} ms",
            f"- Policy: {timings.get('policy', 0)} ms",
            f"- Generation: {timings.get('generation', 0)} ms",
            f"- Total: {timings.get('total', 0)} ms",
            "",
        ]
    )
    return "\n".join(lines)


def persist_demo_report(payload: dict) -> str:
    try:
        trace_id = payload.get("trace_id")
        if not trace_id:
            return ""
        os.makedirs(DEMO_REPORT_DIR, exist_ok=True)
        path = Path(DEMO_REPORT_DIR) / f"{trace_id}.md"
        path.write_text(build_demo_report_markdown(payload), encoding="utf-8")
        return f"/report/{trace_id}"
    except Exception as e:
        print("demo report write error:", e)
        return ""


def claire_local_now() -> datetime:
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(CLAIRE_TIMEZONE))
        except Exception:
            pass
    return datetime.now()


def claire_tomorrow_label() -> str:
    return (claire_local_now() + timedelta(days=1)).strftime("%A, %B %d, %Y")


def demo_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "demo"}


def safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def demo_recall_check(prompt: str):
    start = time.perf_counter()
    try:
        response = requests.post(
            f"{ARE_URL}/query",
            json={"query": prompt, "top_k": 5},
            timeout=5,
        )
        if response.status_code != 200:
            return (
                {
                    "status": "error",
                    "summary": "Recall subsystem unavailable.",
                    "items": [],
                },
                elapsed_ms(start),
            )
        data = response.json()
        raw_items = []
        if isinstance(data, dict):
            for key in ["results", "matches", "hits", "items"]:
                values = data.get(key)
                if isinstance(values, list):
                    raw_items.extend(values)
        items = []
        for item in raw_items[:5]:
            text = ""
            score = 0.0
            if isinstance(item, dict):
                for text_key in ["text", "content", "chunk", "memory", "value"]:
                    if item.get(text_key):
                        text = str(item.get(text_key)).strip()
                        break
                for score_key in ["score", "similarity", "distance"]:
                    if score_key in item:
                        score = safe_float(item.get(score_key))
                        break
            else:
                text = str(item).strip()
            if not text:
                continue
            if not is_safe_are_item(text):
                continue
            summary = summarize_courtlistener_text(text) or cap_are_item(text, 320)
            items.append({"source": "are", "text": summary, "score": score})
        if not items:
            return (
                {
                    "status": "none",
                    "summary": "No relevant prior memory found.",
                    "items": [],
                },
                elapsed_ms(start),
            )
        return (
            {
                "status": "found",
                "summary": f"{len(items)} relevant memory item(s) returned by ARE.",
                "items": items,
            },
            elapsed_ms(start),
        )
    except Exception as e:
        return (
            {
                "status": "error",
                "summary": "Recall subsystem unavailable.",
                "items": [],
            },
            elapsed_ms(start),
        )


def demo_recall_prompt(prompt: str, scenario: str) -> str:
    text = str(prompt or "").strip()
    if scenario == "archimedes":
        return (
            text
            + " Project ARCHIMEDES DARPA presentation source manifest evidence package "
            + "ARE Sentinel Diode Veritas GAUSS CodeMask trace replay controlled evaluation"
        ).strip()
    if scenario == "glasses":
        return (
            text
            + " THE ARE SPECTACLE Gyro Analog Recall Engine memory visor prompt prefix model agnostic "
            + "external recall adapter context stabilization Diode trace Azure marketplace"
        ).strip()
    if scenario == "ooda":
        return (
            text
            + " OODA loop Drone Dominance DDP lap memory ARE speed test BARE FARE Gyro ARE "
            + "Diode Capsule trace replay vendor evaluation operator notes flight logs readiness report"
        ).strip()
    if scenario == "memory_speed":
        return (
            text
            + " Memory Performance ARE speed proof document retrieval Azure VM public IP loop "
            + "pipeline timing Diode trace replay Analog Recall Engine speed test"
        ).strip()
    if scenario == "aegis":
        return (
            text
            + " GAUSS Veritas CodeMask Diode Capsule ARE Turbo CORTEX Temporal Memory Fabric "
            + "GPS GNSS denied AEGIS demo DIU source fusion Sentinel governance"
        ).strip()
    return text


def demo_policy_validation(prompt: str):
    start = time.perf_counter()
    cleaned = _clean_for_match(prompt)
    try:
        blocked_markers = [
            "show api key",
            "show keys",
            "password",
            "dump secrets",
            "reveal secret",
            "private internal document",
            "execute shell",
            "run sudo",
            "delete files",
            "destroy data",
            "disable security",
            "bypass creator",
        ]
        if any(marker in cleaned for marker in blocked_markers):
            return (
                {
                    "status": "blocked",
                    "summary": "Blocked because the request asks for secrets, protected internals, destructive action, or security bypass.",
                    "rules_triggered": ["protect_secrets", "block_destructive_or_privileged_actions"],
                },
                elapsed_ms(start),
            )
        warning_rules = []
        if is_legal_query(prompt):
            warning_rules.append("legal_research_not_legal_advice")
        if any(marker in cleaned for marker in ["medical", "trauma", "diagnose", "veterinarian", "lame", "sore horse", "horse feet"]):
            warning_rules.append("professional_review_recommended")
        if warning_rules:
            return (
                {
                    "status": "warning",
                    "summary": "Allowed with caution. Claire may organize information, but professional review may be needed.",
                    "rules_triggered": warning_rules,
                },
                elapsed_ms(start),
            )
        return (
            {
                "status": "allowed",
                "summary": "No policy constraints violated.",
                "rules_triggered": [],
            },
            elapsed_ms(start),
        )
    except Exception as e:
        return (
            {
                "status": "warning",
                "summary": "Policy subsystem unavailable.",
                "rules_triggered": ["policy_fallback_warning"],
            },
            elapsed_ms(start),
        )


def concise_demo_output(text: str, limit: int = 1400) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def demo_deterministic_fields(prompt: str, recall_check: dict, policy_validation: dict, scenario: str = "glasses"):
    cleaned = _clean_for_match(prompt)
    identity = EXECUTIVE_SELF_DESCRIPTION
    if scenario == "aegis":
        identity = "Claire Executive Mode running the AEGIS Fusion Demo: governed source fusion, controlled recall, Sentinel validation, and replayable audit lineage."
    if scenario == "ooda":
        identity = "Claire Executive Mode running the OODA/DDP Memory Benchmark: low-latency recall, Gyro orientation, Sentinel validation, Diode proof, and trace replay."
    if scenario == "memory_speed":
        identity = "Claire Executive Mode running the Memory Performance Demo: VM document retrieval, governed ARE recall speed, full pipeline timing, public/local IP loop display, Diode trace, and replay."
    if scenario == "glasses":
        identity = "Claire Executive Mode running The ARE Spectacle Demo: governed external recall middleware for model-agnostic context control."
    if scenario == "archimedes":
        identity = archimedes_fields()["identity"]
    if policy_validation.get("status") == "blocked":
        return {
            "identity": identity,
            "decision": "Block the unsafe portion and provide a bounded alternative.",
            "output": "I cannot perform or disclose that in demo mode. I can provide a safe summary, public explanation, or non-sensitive workflow trace instead.",
            "lane": "policy_blocked",
        }

    if scenario == "archimedes":
        return archimedes_fields()

    if scenario == "memory_speed":
        return {
            "identity": identity,
            "decision": "Run a controlled Memory Performance proof: retrieve one VM document, hash it, measure the ARE speed lane, expose the public/local IP loop, time the full pipeline, seal the trace, and render a replayable report.",
            "output": (
                "Memory Performance Demo result: Claire retrieved a document from the Azure VM, computed an integrity hash, measured the indexed ARE recall lane, "
                "measured the public-to-local service loop, and assembled a full pipeline trace. The proof separates the fast memory path from document fetch, model generation, "
                "trace/report output, and voice narration so the speed claim is inspectable instead of rhetorical."
            ),
            "lane": "memory_performance_demo",
        }

    if scenario == "aegis":
        return {
            "identity": identity,
            "decision": "Run a controlled AEGIS evaluation: process the GAUSS package, anchor it to governed truth lanes, validate with Sentinel, and emit a replayable decision-support trace.",
            "output": (
                "AEGIS Fusion Demo result: Claire processed package AEGIS-001 as a GAUSS/Veritas proof run. "
                "The pipeline identified GPS/GNSS denial as the operating condition, selected geomagnetic reference data as the governed evidence anchor, "
                "applied CodeMask-style noise isolation as the sensor-integrity lane, checked ARE recall before generation, validated the request through Sentinel, "
                "sealed the result into a Diode capsule, and produced a replayable trace plus report. The scenario is controlled; the pipeline execution, "
                "timings, capsule hash, recall result, policy result, and report artifact are live."
            ),
            "lane": "aegis_gauss_veritas_evaluation",
        }

    if scenario == "ooda":
        return {
            "identity": identity,
            "decision": "Run a controlled OODA compression benchmark: use lap-one observation as memory, then demonstrate BARE verification, Gyro orientation, FARE next-step framing, Diode sealing, and trace replay.",
            "output": (
                "OODA/DDP Memory Benchmark result: Claire treated the first pass as the observation lap, converted the event sequence into recallable memory, "
                "then used the rear-facing ARE lane to verify prior events at index speed before producing the next decision-support report. "
                "The run shows the practical advantage: repeated evaluation does not start from zero. BARE verifies what already happened, Gyro ARE keeps the context stable, "
                "FARE frames the likely next constraint, Sentinel validates the answer, and Diode seals the trace. For a Drone Dominance vendor, this converts flight logs, "
                "operator notes, anomalies, and readiness gaps into a fast replayable evidence package for the next test cycle."
            ),
            "lane": "ooda_loop_evaluation",
        }

    if scenario == "glasses":
        return {
            "identity": identity,
            "decision": "Demonstrate normal model context versus governed ARE Spectacle context, then show Gyro stabilization, Diode traceability, report output, and replay.",
            "output": (
                "The ARE Spectacle Demo result: a standard model sees the immediate prompt and its current context window. "
                "With ARE Spectacle, Claire queries governed external recall first, builds a controlled prompt context, stabilizes it with Gyro ARE, "
                "and sends the model a better grounded request without retraining. The product value is enterprise memory middleware: "
                "model-agnostic recall, reduced context drift, trace generation, and reportable provenance."
            ),
            "lane": "are_glasses_adapter_demo",
        }

    if scenario == "stable" and any(term in cleaned for term in ["schedule", "calendar", "appointment"]) and any(
        term in cleaned for term in ["horse", "horseback", "ride", "riding"]
    ):
        return {
            "identity": identity,
            "decision": "Simulating scheduling action for demonstration only; no external calendar, booking, or real-world execution is performed.",
            "output": (
                "Simulated scheduling action: Claire received the request, checked memory, validated policy, "
                "and would prepare an internal plan for a horseback ride tomorrow at 10:00 AM. "
                "No calendar entry, booking, notification, or real-world action was performed. "
                "Safety note: verify horse soundness, weather, footing, and tack before any actual ride."
            ),
            "lane": "simulated_scheduling_action",
        }

    if is_memory_handling_query(prompt):
        return {"identity": identity, "decision": "Explain governed external memory handling.", "output": memory_handling_reply(), "lane": "memory_handling"}
    if is_enterprise_system_query(prompt):
        return {"identity": identity, "decision": "Answer from the enterprise architecture lane.", "output": enterprise_system_reply(prompt), "lane": "enterprise_system"}
    if is_system_difference_query(prompt):
        return {"identity": identity, "decision": "Explain Claire's governed operating difference.", "output": system_difference_reply(), "lane": "system_difference"}
    if is_governance_value_query(prompt):
        return {"identity": identity, "decision": "Explain why AI governance is an infrastructure control.", "output": governance_value_reply(), "lane": "governance_value"}
    if is_self_demo_query(prompt) or any(marker in cleaned for marker in ["show capabilities"]):
        return {"identity": identity, "decision": "Summarize Claire's public capabilities.", "output": concise_demo_output(self_demo_reply()), "lane": "capability_summary"}
    if is_scholar_query(prompt):
        return {"identity": identity, "decision": "Use the scholarly research lane.", "output": concise_demo_output(scholar_reply(prompt)), "lane": "scholar_lane"}
    if is_legal_query(prompt):
        if recall_check.get("status") == "found":
            lines = [item.get("text", "") for item in recall_check.get("items", []) if item.get("text")]
            return {
                "identity": identity,
                "decision": "Summarize legal research leads without treating them as final legal advice.",
                "output": concise_demo_output(
                    "Legal research leads surfaced. These are not final legal conclusions. Verify jurisdiction, posture, citations, and good-law status before relying on them.\n\n"
                    + "\n\n".join(lines)
                ),
                "lane": "legal_recall_summary",
            }
        return {"identity": identity, "decision": "Provide legal research support boundaries.", "output": shape_legal_fallback(prompt), "lane": "legal_fallback"}
    known = known_general_reply(prompt)
    if is_useful_reply(known):
        return {"identity": identity, "decision": "Answer from known general knowledge.", "output": concise_demo_output(known), "lane": "known_general"}
    if re.search(r"\bants?\b", cleaned):
        return {"identity": identity, "decision": "Provide safe practical guidance.", "output": concise_demo_output(practical_howto_reply(prompt)), "lane": "practical_howto"}
    return {
        "identity": identity,
        "decision": "Generate a concise answer through the normal response lane.",
        "output": "",
        "lane": "go_fallback",
    }


def build_demo_llm_prompt(prompt: str, recall_check: dict, policy_validation: dict, fallback_fields: dict, scenario: str = "glasses") -> str:
    recall_items = recall_check.get("items") or []
    recall_summary = recall_check.get("summary") or ""
    if recall_items:
        recall_summary += "\n" + "\n".join("- " + str(item.get("text", ""))[:240] for item in recall_items[:3])
    policy_summary = policy_validation.get("summary") or ""
    return (
        DEMO_SYSTEM_PROMPT
        + "\n\nReturn ONLY compact JSON with exactly these keys: identity, decision, output.\n"
        + "Do not include trace_id, recall_check, policy_validation, or trace_summary.\n"
        + "Do not describe hidden reasoning.\n"
        + "If the request sounds like scheduling, describe simulation only; no real-world action.\n\n"
        + f"Demo scenario: {demo_scenario_label(scenario)}\n"
        + f"User input: {prompt}\n"
        + f"Recall summary: {recall_summary}\n"
        + f"Policy summary: {policy_summary}\n"
        + f"Draft decision: {fallback_fields.get('decision', '')}\n"
        + f"Draft output: {fallback_fields.get('output', '')}\n"
    )


def parse_demo_llm_fields(raw: str) -> dict:
    text = str(raw or "").strip()
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "identity": concise_demo_output(data.get("identity", ""), 420),
        "decision": concise_demo_output(data.get("decision", ""), 520),
        "output": concise_demo_output(data.get("output", ""), 1400),
    }


def call_demo_llm(prompt: str, recall_check: dict, policy_validation: dict, fallback_fields: dict, scenario: str = "glasses"):
    start = time.perf_counter()
    try:
        llm_prompt = build_demo_llm_prompt(prompt, recall_check, policy_validation, fallback_fields, scenario)
        raw = query_llm(llm_prompt, allow_gemini=False)
        parsed = parse_demo_llm_fields(raw)
        fields = dict(fallback_fields)
        for key in ["identity", "decision", "output"]:
            if parsed.get(key):
                fields[key] = parsed[key]
        if not fields.get("output"):
            if should_use_general_engine(prompt) and is_gemini_available():
                gemini_reply = query_gemini(contextualize_prompt(prompt), DEMO_SYSTEM_PROMPT)
                if is_useful_reply(gemini_reply):
                    fields["output"] = concise_demo_output(gemini_reply)
                    fields["lane"] = "gemini_bridge"
            if not fields.get("output"):
                fallback = query_llm(contextualize_prompt(prompt), allow_gemini=False)
                fields["output"] = concise_demo_output(fallback) if is_useful_reply(fallback) else "No strong answer was produced by the active demo lanes."
        return fields, elapsed_ms(start)
    except Exception:
        fields = dict(fallback_fields)
        if not fields.get("output"):
            fields["output"] = "Demo generation fell back to deterministic output because the model lane was unavailable."
        return fields, elapsed_ms(start)


def validate_demo_payload(payload: dict) -> tuple[bool, str]:
    if not payload.get("trace_id"):
        return False, "trace_id missing"
    if not payload.get("input_received"):
        return False, "input_received missing"
    if not payload.get("output"):
        return False, "output missing"
    trace_summary = payload.get("trace_summary") or {}
    if not trace_summary.get("steps_executed"):
        return False, "trace_summary.steps_executed missing"
    return True, ""


def persist_demo_trace(payload: dict, metadata: dict | None = None) -> None:
    try:
        record = {
            "trace_id": payload.get("trace_id"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "input": payload.get("input_received"),
            "recall": payload.get("recall_check"),
            "policy": payload.get("policy_validation"),
            "decision": payload.get("decision"),
            "output": payload.get("output"),
            "steps": (payload.get("trace_summary") or {}).get("steps_executed", []),
            "payload": payload,
            "metadata": metadata or {},
        }
        os.makedirs(os.path.dirname(TRACE_LOG), exist_ok=True)
        with open(TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("demo trace write error:", e)


def build_demo_payload(prompt: str, trace_id: str | None = None, scenario: str = "glasses") -> dict:
    total_start = time.perf_counter()
    # Strict order: ingest_input -> generate_trace_id -> run_are_recall -> run_policy_validation
    input_received = str(prompt or "").strip()
    scenario = demo_scenario_from_text(input_received, scenario)
    trace = new_trace_id(trace_id)
    recall_check, recall_ms = demo_recall_check(demo_recall_prompt(input_received, scenario))
    policy_validation, policy_ms = demo_policy_validation(input_received)
    policy_validation = refine_demo_policy_for_scenario(policy_validation, scenario)
    # Strict order continues: build_llm_prompt -> call_llm -> assemble_response_json
    fallback_fields = demo_deterministic_fields(input_received, recall_check, policy_validation, scenario)
    llm_fields, generation_ms = call_demo_llm(input_received, recall_check, policy_validation, fallback_fields, scenario)
    if fallback_fields.get("lane") in {
        "simulated_scheduling_action",
        "archimedes_darpa_evaluation",
        "aegis_fusion_simulation",
        "aegis_gauss_veritas_evaluation",
        "ooda_loop_evaluation",
        "are_glasses_adapter_demo",
        "memory_performance_demo",
    }:
        llm_fields["decision"] = fallback_fields["decision"]
        llm_fields["output"] = fallback_fields["output"]
    generation_lane = llm_fields.get("lane") or fallback_fields.get("lane") or "demo_generation"

    decisions = []
    decisions.append("memory_used" if recall_check.get("status") == "found" else "no_memory_used")
    if policy_validation.get("status") == "blocked":
        decisions.append("policy_blocked")
    elif policy_validation.get("status") == "warning":
        decisions.append("policy_warning")
    else:
        decisions.append("policy_allowed")
    decisions.append(generation_lane)

    payload = {
        "trace_id": trace,
        "demo_mode": True,
        "demo_scenario": scenario,
        "demo_name": demo_scenario_label(scenario),
        "identity": llm_fields.get("identity") or fallback_fields.get("identity"),
        "input_received": input_received,
        "recall_check": recall_check,
        "policy_validation": policy_validation,
        "decision": llm_fields.get("decision") or fallback_fields.get("decision"),
        "output": llm_fields.get("output") or fallback_fields.get("output"),
        "trace_summary": {
            "steps_executed": [
                "ingest_input",
                "generate_trace_id",
                "run_are_recall",
                "run_policy_validation",
                "build_llm_prompt",
                "call_llm",
                "assemble_response_json",
                "persist_trace",
                "return_response",
            ],
            "pipeline_steps": [
                "ingest_input",
                "retrieve_memory",
                "validate_policy",
                "generate_response",
            ],
            "decisions_made": decisions,
            "artifacts": demo_artifacts_for_scenario(scenario),
            "timing_ms": {
                "recall": recall_ms,
                "policy": policy_ms,
                "generation": generation_ms,
                "total": elapsed_ms(total_start),
            },
        },
    }
    payload["live_proof"] = build_live_demo_proof(payload)
    report_url = persist_demo_report(payload)
    if report_url:
        payload["report_url"] = report_url
        payload["trace_summary"]["report_url"] = report_url
    valid, error = validate_demo_payload(payload)
    if not valid:
        return {
            "trace_id": trace,
            "demo_mode": True,
            "status": "error",
            "error": error,
            "input_received": input_received,
            "output": "",
            "trace_summary": {"steps_executed": []},
        }
    persist_demo_trace(
        payload,
        {
            "system_prompt": "DEMO_SYSTEM_PROMPT",
            "are_url": ARE_URL,
            "demo_scenario": scenario,
            "generation_lane": generation_lane,
        },
    )
    return payload


def render_demo_payload_as_text(payload: dict) -> str:
    recall = payload.get("recall_check") or {}
    policy = payload.get("policy_validation") or {}
    trace = payload.get("trace_summary") or {}
    timings = trace.get("timing_ms") or {}
    proof = payload.get("live_proof") or {}
    speed = proof.get("speed_proof") or {}
    capsule = proof.get("diode_capsule") or {}
    gyro = proof.get("gyro_are") or {}
    passive = proof.get("passive_signal_cueing") or {}
    ooda = proof.get("ooda_loop") or {}
    glasses = proof.get("are_glasses") or {}
    recall_items = recall.get("items") or []
    item_text = "No recall items returned."
    if recall_items:
        item_text = "\n".join(
            f"- [{item.get('source', 'are')}] {item.get('text', '')} ({safe_float(item.get('score')):.2f})"
            for item in recall_items
        )
    rules = policy.get("rules_triggered") or []
    rules_text = ", ".join(rules) if rules else "none"
    return (
        "[1] IDENTITY\n"
        f"{payload.get('identity')}\n\n"
        "[2] INPUT RECEIVED\n"
        f"{payload.get('input_received')}\n\n"
        "[3] RECALL CHECK\n"
        f"Status: {recall.get('status')}\n"
        f"{recall.get('summary')}\n"
        f"{item_text}\n\n"
        "[4] POLICY VALIDATION\n"
        f"Status: {policy.get('status')}\n"
        f"{policy.get('summary')}\n"
        f"Rules: {rules_text}\n\n"
        "[5] DECISION\n"
        f"{payload.get('decision')}\n\n"
        "[6] OUTPUT\n"
        f"{payload.get('output')}\n\n"
        "LIVE PROOF\n"
        f"rear_are_lookup_ms: {speed.get('rear_are_lookup_ms', 0)}\n"
        f"linear_retrieval_ms: {speed.get('linear_retrieval_ms', 0)}\n"
        f"measured_speedup_x: {speed.get('speedup_x', 0)}\n"
        f"speedup_vs_rag_reference_x: {speed.get('speedup_vs_rag_reference_x', 0)}\n"
        f"speed_headline: {speed.get('headline', '')}\n"
        f"diode_capsule_id: {capsule.get('capsule_id', '')}\n"
        f"gyro_role: {gyro.get('gyro_role', '')}\n"
        f"bare_role: {gyro.get('bare_role', '')}\n"
        f"ooda_phase: {ooda.get('phase', '')}\n"
        f"ooda_lap_1: {ooda.get('lap_1', '')}\n"
        f"ooda_lap_2_plus: {ooda.get('lap_2_plus', '')}\n"
        f"ooda_benchmark_anchor: {ooda.get('benchmark_anchor', '')}\n"
        f"are_glasses_status: {glasses.get('visor_status', '')}\n"
        f"are_glasses_adapter: {glasses.get('adapter_role', '')}\n"
        f"are_glasses_gyro: {glasses.get('gyro_role', '')}\n"
        f"memory_document: {memory_doc.get('name', '')} ({memory_doc.get('read_ms', '')} ms)\n"
        f"memory_document_sha256: {memory_doc.get('sha256', '')}\n"
        f"memory_pipeline_total_ms: {memory_pipeline.get('total_pipeline_ms', '')}\n"
        f"passive_signal_cueing: {passive.get('status', 'standby')} - {passive.get('summary', '')}\n\n"
        "[7] TRACE SUMMARY\n"
        f"trace_id: {payload.get('trace_id')}\n"
        f"steps_executed: {', '.join(trace.get('steps_executed') or [])}\n"
        f"decisions_made: {', '.join(trace.get('decisions_made') or [])}\n"
        f"report_url: {payload.get('report_url') or trace.get('report_url') or ''}\n"
        f"timing_ms: recall={timings.get('recall', 0)}, policy={timings.get('policy', 0)}, generation={timings.get('generation', 0)}, total={timings.get('total', 0)}"
    )


def demonstration_mode_reply(prompt: str) -> str:
    request_text = extract_demo_user_request(prompt)
    return render_demo_payload_as_text(build_demo_payload(request_text))


def demo_activation_reply(scenario: str = "glasses") -> str:
    scenario = demo_scenario_from_text("", scenario)
    if scenario == "archimedes":
        return (
            "CLAIRE EXECUTIVE MODE: PROJECT ARCHIMEDES DEMO ACTIVE\n\n"
            f"{EXECUTIVE_SELF_DESCRIPTION}\n"
            "This demo shows source-manifest intake, evidence classification, Sentinel presentation gating, Diode lineage, controlled report output, and trace replay.\n\n"
            "What to try:\n"
            "1. Run Project ARCHIMEDES DARPA presentation proof package.\n"
            "2. Show the manifest-to-evidence classification lanes.\n"
            "3. Explain the Sentinel gate and Diode trace.\n"
            "4. Replay the trace and review the report artifact.\n\n"
            "This is a controlled decision-support presentation demo, not an operational system.\n"
            "To close demo mode, say: demo complete."
        )
    if scenario == "glasses":
        return (
            "CLAIRE EXECUTIVE MODE: ARE SPECTACLE DEMO ACTIVE\n\n"
            f"{EXECUTIVE_SELF_DESCRIPTION}\n"
            "This demo shows baseline model context, governed external recall, Gyro-stabilized prompt context, Sentinel validation, Diode traceability, report output, and replay.\n\n"
            "What to try:\n"
            "1. Show how The ARE Spectacle improves an AI answer.\n"
            "2. Compare normal AI view against the memory visor.\n"
            "3. Explain how Gyro ARE prevents context drift.\n"
            "4. Generate The ARE Spectacle report and replay the last trace.\n\n"
            "This is a controlled enterprise demo for portable memory middleware.\n"
            "To close demo mode, say: demo complete."
        )
    if scenario == "ooda":
        return (
            "CLAIRE EXECUTIVE MODE: OODA/DDP MEMORY BENCHMARK ACTIVE\n\n"
            f"{EXECUTIVE_SELF_DESCRIPTION}\n"
            "This demo shows lap-one observation, rear-facing ARE verification, Gyro orientation, FARE next-step framing, Sentinel validation, Diode sealing, report output, and trace replay.\n\n"
            "What to try:\n"
            "1. Run OODA lap memory benchmark.\n"
            "2. Show the Drone Dominance evaluation trace.\n"
            "3. Explain how ARE compresses the OODA loop after lap one.\n"
            "4. Generate the buyer report and replay the last trace.\n\n"
            "This is a controlled evaluation demo using repeatable evidence artifacts.\n"
            "To close demo mode, say: demo complete."
        )
    if scenario == "memory_speed":
        return (
            "CLAIRE EXECUTIVE MODE: MEMORY PERFORMANCE DEMO ACTIVE\n\n"
            f"{EXECUTIVE_SELF_DESCRIPTION}\n"
            "This demo retrieves a document from the Azure VM, hashes it, measures ARE recall speed, shows the public/local IP loop, seals a trace, and renders the full pipeline timing.\n\n"
            "What to try:\n"
            "1. Run Memory Performance demo.\n"
            "2. Show ARE speed proof.\n"
            "3. Show the IP loop.\n"
            "4. Replay the trace and review the report artifact.\n\n"
            "This is a controlled performance proof, not a remote file browser.\n"
            "To close demo mode, say: demo complete."
        )
    if scenario == "aegis":
        return (
            "CLAIRE EXECUTIVE MODE: AEGIS FUSION DEMO ACTIVE\n\n"
            f"{EXECUTIVE_SELF_DESCRIPTION}\n"
            "This demo shows GPS-denied mission context, magnetic-reference integrity, CodeMask sensor cleanup, ARE recall, Sentinel validation, Diode lineage, output artifacts, trace logging, and replay.\n\n"
            "What to try:\n"
            "1. Run AEGIS fusion scenario.\n"
            "2. Show the GAUSS GPS-denied navigation proof run.\n"
            "3. Explain the Veritas truth substrate and Diode capsule trace.\n"
            "4. Show the Sentinel policy gate and replay the last trace.\n\n"
            "This is a controlled evaluation using a repeatable evidence package.\n"
            "To close demo mode, say: demo complete."
        )
    return demo_activation_reply("glasses")


def demo_session_reply(prompt: str) -> str:
    clean_prompt = demo_session_clean_prompt(prompt)
    cleaned = _clean_for_match(clean_prompt)

    if not clean_prompt or cleaned in {"help", "menu", "what can you do"}:
        return demo_activation_reply(demo_scenario_from_text(clean_prompt))

    return render_demo_payload_as_text(build_demo_payload(clean_prompt, scenario=demo_scenario_from_text(clean_prompt)))


def is_state_parks_case_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    markers = [
        "state parks case",
        "state park case",
        "case room",
        "parks war room",
        "state parks war room",
        "state parks",
        "california state parks",
        "seahorse",
        "tucker",
        "tucker consent",
        "consent decree",
        "wilson v cook",
        "14 ccr",
        "ccr 4331",
        "special event permit",
        "plea agreement",
        "manzanita",
        "paloma",
        "sean james",
        "commercial activity permit",
        "title 14",
        "4331",
        "final complaint",
    ]
    return any(marker in cleaned for marker in markers)


def state_parks_case_paths() -> tuple[Path, Path]:
    root = Path(STATE_PARKS_CASE_DIR)
    return root / "manifest.json", root / "chunks.jsonl"


def load_state_parks_manifest() -> dict:
    manifest_path, _ = state_parks_case_paths()
    try:
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        print("state parks manifest read error:", e)
    return {"documents": []}


def search_state_parks_case(query: str, limit: int = 5) -> list[dict]:
    _, chunks_path = state_parks_case_paths()
    if not chunks_path.exists():
        return []
    terms = [
        term
        for term in re.sub(r"[^a-z0-9\s]", " ", query.lower()).split()
        if len(term) > 2
        and term
        not in {
            "state",
            "parks",
            "case",
            "room",
            "search",
            "find",
            "for",
            "the",
            "and",
            "what",
            "about",
            "summary",
            "summarize",
        }
    ]
    if not terms:
        terms = ["complaint", "permit", "commercial", "enforcement", "regulation"]
    scored = []
    try:
        with chunks_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                text = str(record.get("text") or "")
                haystack = (text + " " + str(record.get("source_file") or "")).lower()
                score = sum(haystack.count(term) for term in terms)
                if "final complaint" in haystack and any(term in terms for term in ["complaint", "defendant", "relief"]):
                    score += 2
                if score:
                    scored.append((score, record))
    except Exception as e:
        print("state parks case search error:", e)
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in scored[:limit]]


def state_parks_case_status() -> str:
    manifest = load_state_parks_manifest()
    documents = manifest.get("documents") or []
    _, chunks_path = state_parks_case_paths()
    chunks = 0
    try:
        if chunks_path.exists():
            with chunks_path.open("r", encoding="utf-8", errors="ignore") as f:
                chunks = sum(1 for _ in f)
    except Exception:
        chunks = 0
    if not documents:
        return "State Parks Case Room exists, but no documents are indexed yet."
    lines = [
        "STATE PARKS CASE ROOM",
        "Protected Creator-only legal/evidence lane. Research support only; not legal counsel.",
        "",
        f"Documents indexed: {len(documents)}",
        f"Case chunks indexed: {chunks}",
    ]
    for doc in documents[:8]:
        lines.append(
            f"- {doc.get('title') or doc.get('file')}: {doc.get('pages', '?')} pages, {doc.get('chunks', '?')} chunks"
        )
    return "\n".join(lines)


def state_parks_case_reply(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    wants_search = any(marker in cleaned for marker in ["search", "find", "for ", "commercial", "permit", "complaint", "timeline", "evidence", "defendant"])
    if not wants_search and any(marker in cleaned for marker in ["status", "open", "room", "inventory", "what is in"]):
        return state_parks_case_status()
    hits = search_state_parks_case(prompt)
    if not hits:
        return (
            state_parks_case_status()
            + "\n\nNo matching case-room hit found yet. Try: commercial activity permit, Title 14 4331, defendants, harassment, due process, or complaint."
        )
    lines = [
        "STATE PARKS CASE ROOM",
        "Protected Creator-only legal/evidence lane. Research support only; not legal counsel.",
        "",
        "Relevant source hits:",
    ]
    for hit in hits:
        source = hit.get("source_file") or "case document"
        page = hit.get("page")
        text = cap_are_item(hit.get("text") or "", 520)
        lines.append(f"- {source}, page {page}: {text}")
    lines.extend(
        [
            "",
            "Next court-prep move:",
            "Tie each useful claim to file, page, date, and legal issue before treating it as an exhibit or argument.",
        ]
    )
    return "\n".join(lines)


def crypto_keys_loaded() -> bool:
    return bool(os.getenv("KRAKEN_API_KEY", "").strip() and os.getenv("KRAKEN_API_SECRET", "").strip())


def is_crypto_mode_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    if not cleaned:
        return False
    markers = [
        "crypto mode",
        "crypto status",
        "crypto check",
        "crypto signal",
        "market status",
        "market read",
        "kraken",
        "paper trade",
        "paper signal",
        "paper trading",
        "trading bot",
        "trade bot",
        "brubaker",
        "market gyro",
        "regime governed",
        "rgtc",
        "bitcoin trade",
        "bitcoin",
        "btc trade",
        "btc usd",
        "eth trade",
        "eth usd",
        "sol trade",
        "sol usd",
        "xrp trade",
        "xrp usd",
    ]
    return any(marker in cleaned for marker in markers)


def crypto_asset_from_prompt(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if any(term in cleaned for term in ["eth", "ethereum"]):
        return "ETH/USD"
    if any(term in cleaned for term in ["sol", "solana"]):
        return "SOL/USD"
    if any(term in cleaned for term in ["xrp", "ripple"]):
        return "XRP/USD"
    return "BTC/USD"


def kraken_pair_for_asset(asset: str) -> str:
    return {
        "BTC/USD": "XBTUSD",
        "ETH/USD": "ETHUSD",
        "SOL/USD": "SOLUSD",
        "XRP/USD": "XRPUSD",
    }.get(asset.upper(), "XBTUSD")


def crypto_history_path(asset: str, interval: int = 1440) -> Path:
    pair = kraken_pair_for_asset(asset)
    return Path(KRAKEN_HISTORY_DIR) / f"{pair}_{interval}.csv"


def load_crypto_history(asset: str = "BTC/USD", interval: int = 1440, limit: int = 900) -> list[dict]:
    path = crypto_history_path(asset, interval)
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = [part.strip() for part in line.split(",")]
                if len(parts) < 7:
                    continue
                try:
                    rows.append(
                        {
                            "timestamp": int(float(parts[0])),
                            "open": float(parts[1]),
                            "high": float(parts[2]),
                            "low": float(parts[3]),
                            "close": float(parts[4]),
                            "volume": float(parts[5]),
                            "trades": int(float(parts[6])),
                        }
                    )
                except Exception:
                    continue
    except Exception as e:
        print("crypto history read error:", e)
        return []
    return rows[-limit:] if limit and len(rows) > limit else rows


def market_window_features(rows: list[dict], end_index: int, window: int = 20) -> dict | None:
    if end_index < window or end_index >= len(rows):
        return None
    segment = rows[end_index - window + 1 : end_index + 1]
    closes = [row["close"] for row in segment]
    volumes = [row["volume"] for row in segment]
    last = closes[-1]
    first = closes[0]
    sma = sum(closes) / len(closes)
    variance = sum((price - sma) ** 2 for price in closes) / max(1, len(closes))
    stdev = variance ** 0.5
    bb_width = ((stdev * 4) / sma * 100) if sma else 0
    ret = ((last - first) / first * 100) if first else 0
    range_high = max(closes)
    range_low = min(closes)
    range_position = ((last - range_low) / (range_high - range_low)) if range_high != range_low else 0.5
    volume_sma = sum(volumes) / len(volumes) if volumes else 0
    volume_z = ((volumes[-1] - volume_sma) / (volume_sma or 1)) if volumes else 0
    drawdown = ((last - range_high) / range_high * 100) if range_high else 0
    if bb_width > 8:
        regime = "HIGH_VOL"
    elif bb_width < 2.5 and abs(ret) < 2:
        regime = "COMPRESSION"
    elif ret > 4 and range_position > 0.65:
        regime = "TREND_UP"
    elif ret < -4 and range_position < 0.35:
        regime = "TREND_DOWN"
    else:
        regime = "RANGE"
    return {
        "timestamp": rows[end_index]["timestamp"],
        "close": last,
        "return_pct": ret,
        "bb_width_pct": bb_width,
        "range_position": range_position,
        "volume_z": volume_z,
        "drawdown_pct": drawdown,
        "regime": regime,
    }


def feature_distance(a: dict, b: dict) -> float:
    weights = {
        "return_pct": 0.35,
        "bb_width_pct": 0.3,
        "range_position": 2.0,
        "volume_z": 0.2,
        "drawdown_pct": 0.2,
    }
    total = 0.0
    for key, weight in weights.items():
        total += abs(float(a.get(key, 0)) - float(b.get(key, 0))) * weight
    if a.get("regime") != b.get("regime"):
        total += 4.0
    return total


def market_memory_lookup(asset: str = "BTC/USD") -> dict:
    rows = load_crypto_history(asset)
    if len(rows) < 45:
        return {"status": "none", "asset": asset, "summary": "No historical Kraken memory file is loaded for this asset.", "matches": []}
    current = market_window_features(rows, len(rows) - 1)
    if not current:
        return {"status": "error", "asset": asset, "summary": "Could not compute the current market vector.", "matches": []}
    scored = []
    for idx in range(20, len(rows) - 7):
        features = market_window_features(rows, idx)
        future = rows[idx + 7]["close"]
        if not features:
            continue
        future_7d = ((future - rows[idx]["close"]) / rows[idx]["close"] * 100) if rows[idx]["close"] else 0
        scored.append((feature_distance(current, features), features, future_7d))
    scored.sort(key=lambda item: item[0])
    matches = []
    for distance, features, future_7d in scored[:5]:
        matches.append(
            {
                "date": datetime.utcfromtimestamp(features["timestamp"]).strftime("%Y-%m-%d"),
                "regime": features["regime"],
                "distance": round(distance, 4),
                "future_7d_pct": round(future_7d, 4),
                "return_pct": round(features["return_pct"], 4),
                "bb_width_pct": round(features["bb_width_pct"], 4),
            }
        )
    avg_future = sum(item["future_7d_pct"] for item in matches) / len(matches) if matches else 0
    return {
        "status": "found" if matches else "none",
        "asset": asset,
        "rows": len(rows),
        "current": {key: (round(value, 4) if isinstance(value, float) else value) for key, value in current.items()},
        "matches": matches,
        "avg_future_7d_pct": round(avg_future, 4),
        "summary": (
            f"Historical market memory found {len(matches)} similar {asset} windows "
            f"from {len(rows)} daily candles; average 7-day follow-through was {avg_future:.2f}%."
        ),
    }


def market_memory_library_status() -> str:
    total_vectors = 0
    total_files = 0
    try:
        root = Path("/home/LuciusPrime/claire/data/market_memory")
        for path in root.glob("market_vectors*.jsonl"):
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                total_vectors += sum(1 for _ in f)
        for path in root.glob("manifest*.jsonl"):
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                total_files += sum(1 for _ in f)
    except Exception as e:
        return f"Market memory library status unavailable: {e}"
    if not total_vectors:
        return "No parsed Kraken market vectors loaded yet."
    return f"{total_vectors} parsed Kraken vectors anchored from {total_files} source files."


def kraken_public_ohlc(asset: str = "BTC/USD", interval: int = 60) -> dict:
    pair = kraken_pair_for_asset(asset)
    try:
        response = requests.get(
            f"{KRAKEN_PUBLIC_API}/OHLC",
            params={"pair": pair, "interval": interval},
            timeout=12,
        )
        data = response.json()
        if response.status_code >= 400 or data.get("error"):
            return {"ok": False, "asset": asset, "pair": pair, "error": str(data.get("error") or response.status_code)}
        result = data.get("result", {})
        series_key = next((key for key in result.keys() if key != "last"), "")
        rows = result.get(series_key, [])
        closes = [float(row[4]) for row in rows[-60:] if len(row) > 4]
        volumes = [float(row[6]) for row in rows[-60:] if len(row) > 6]
        return {"ok": bool(closes), "asset": asset, "pair": pair, "closes": closes, "volumes": volumes, "rows": len(rows)}
    except Exception as e:
        return {"ok": False, "asset": asset, "pair": pair, "error": str(e)}


def pct(value: float) -> str:
    return f"{value:.2f}%"


def crypto_market_signal(asset: str = "BTC/USD") -> dict:
    market = kraken_public_ohlc(asset)
    trace_id = new_trace_id()
    if not market.get("ok"):
        return {
            "trace_id": trace_id,
            "asset": asset,
            "mode": "PAPER_ONLY",
            "status": "DATA_UNAVAILABLE",
            "sentinel": {"status": "warning", "rules": ["paper_trade_only", "no_live_orders", "market_data_unavailable"]},
            "brubaker": {"posture": "OBSERVATION", "allocation": "0%"},
            "signal": "NO_TRADE",
            "summary": f"Kraken public market data was unavailable: {market.get('error', 'unknown error')}",
        }

    closes = market["closes"]
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else last
    window = closes[-20:] if len(closes) >= 20 else closes
    sma = sum(window) / len(window)
    variance = sum((price - sma) ** 2 for price in window) / max(1, len(window))
    stdev = variance ** 0.5
    bb_width = ((stdev * 4) / sma) if sma else 0
    previous_window = closes[-40:-20] if len(closes) >= 40 else closes[:-20]
    if previous_window:
        prev_sma = sum(previous_window) / len(previous_window)
        prev_var = sum((price - prev_sma) ** 2 for price in previous_window) / max(1, len(previous_window))
        prev_width = (((prev_var ** 0.5) * 4) / prev_sma) if prev_sma else bb_width
    else:
        prev_width = bb_width
    momentum_1h = ((last - prev) / prev * 100) if prev else 0
    momentum_20 = ((last - window[0]) / window[0] * 100) if window and window[0] else 0
    volatility_pct = bb_width * 100

    if volatility_pct > 8:
        regime = "HIGH_VOL"
    elif bb_width < 0.025 and abs(momentum_20) < 1:
        regime = "COMPRESSION"
    elif momentum_20 > 1.2 and last > sma:
        regime = "TREND_UP"
    elif momentum_20 < -1.2 and last < sma:
        regime = "TREND_DOWN"
    else:
        regime = "RANGE"

    signal = "NO_TRADE"
    if regime == "TREND_UP" and bb_width > prev_width * 1.05:
        signal = "PAPER_LONG_WATCH"
    elif regime == "TREND_DOWN" and bb_width > prev_width * 1.05:
        signal = "PAPER_SHORT_WATCH"
    elif regime == "COMPRESSION":
        signal = "COMPRESSION_WATCH"

    risk_level = "CAUTION" if regime in {"HIGH_VOL"} or volatility_pct > 6 else "NORMAL"
    allocation = "0%" if signal == "NO_TRADE" else ("0.5% simulated" if risk_level == "CAUTION" else "1.0% simulated")

    return {
        "trace_id": trace_id,
        "asset": asset,
        "mode": "PAPER_ONLY",
        "status": "READY",
        "price": round(last, 6),
        "features": {
            "regime": regime,
            "sma_20": round(sma, 6),
            "momentum_1h_pct": round(momentum_1h, 4),
            "momentum_20_period_pct": round(momentum_20, 4),
            "bb_width_pct": round(volatility_pct, 4),
            "previous_bb_width_pct": round(prev_width * 100, 4),
        },
        "sentinel": {
            "status": "allowed",
            "rules": [
                "creator_mode_required",
                "paper_trade_only",
                "no_live_orders",
                "no_withdrawals",
                "no_leverage",
                "trace_required",
            ],
        },
        "brubaker": {
            "posture": "OBSERVATION" if signal == "NO_TRADE" else risk_level,
            "allocation": allocation,
            "max_loss": "$0 live capital",
        },
        "signal": signal,
        "summary": (
            f"{asset} public Kraken data read complete. Regime={regime}; signal={signal}; "
            f"Brubaker posture={risk_level if signal != 'NO_TRADE' else 'OBSERVATION'}."
        ),
    }


def persist_crypto_trace(record: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CRYPTO_TRACE_LOG), exist_ok=True)
        payload = dict(record)
        payload["timestamp"] = claire_local_now().isoformat()
        with open(CRYPTO_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print("crypto trace write error:", e)


def crypto_status_report(prompt: str = "") -> str:
    asset = crypto_asset_from_prompt(prompt)
    signal = crypto_market_signal(asset)
    memory = market_memory_lookup(asset)
    persist_crypto_trace(signal)
    features = signal.get("features", {})
    sentinel = signal.get("sentinel", {})
    brubaker = signal.get("brubaker", {})
    key_state = "PRESENT - REDACTED" if crypto_keys_loaded() else "MISSING"

    if signal.get("status") == "DATA_UNAVAILABLE":
        market_lines = [signal.get("summary", "Market data unavailable.")]
    else:
        market_lines = [
            f"Asset: {signal.get('asset')}",
            f"Kraken public price: {signal.get('price')}",
            f"Regime: {features.get('regime')}",
            f"Momentum 1h: {pct(float(features.get('momentum_1h_pct', 0)))}",
            f"Momentum window: {pct(float(features.get('momentum_20_period_pct', 0)))}",
            f"Bollinger width: {pct(float(features.get('bb_width_pct', 0)))}",
            f"Paper signal: {signal.get('signal')}",
        ]

    memory_lines = [memory.get("summary", "No historical memory summary.")]
    if memory.get("current"):
        current = memory["current"]
        memory_lines.extend(
            [
                f"Current memory vector: {current.get('regime')} / return {pct(float(current.get('return_pct', 0)))} / width {pct(float(current.get('bb_width_pct', 0)))}",
                f"Average 7-day follow-through from nearest matches: {pct(float(memory.get('avg_future_7d_pct', 0)))}",
            ]
        )
    for item in memory.get("matches", [])[:3]:
        memory_lines.append(
            f"{item.get('date')} {item.get('regime')} distance={item.get('distance')} next_7d={pct(float(item.get('future_7d_pct', 0)))}"
        )

    return (
        "CLAIRE CRYPTO MODE\n"
        "Creator-only lane. Paper trading only. No live orders executed.\n\n"
        "Key state:\n"
        f"- KRAKEN_API_KEY: {key_state}\n"
        f"- KRAKEN_API_SECRET: {key_state}\n"
        "- Withdrawal permission: not used by Claire\n"
        "- Live execution: sealed\n\n"
        "Architecture loaded from your six-AI trading build:\n"
        "- Scraper lane: Kraken public market data reader\n"
        "- Signal lane: compression / trend / range classifier\n"
        "- Market Gyro: regime stabilization over recent candles\n"
        "- Sentinel: creator-only, paper-only, no withdrawals, no leverage\n"
        "- Brubaker: exposure governor, currently simulated capital only\n"
        "- Diode trace: append-only paper-trade record\n\n"
        "ARE market library:\n"
        f"- {market_memory_library_status()}\n\n"
        "Market read:\n"
        + "\n".join(f"- {line}" for line in market_lines)
        + "\n\n"
        "Market Memory / Gyro ARE:\n"
        + "\n".join(f"- {line}" for line in memory_lines)
        + "\n\n"
        "Sentinel:\n"
        f"- Status: {sentinel.get('status')}\n"
        f"- Rules: {', '.join(sentinel.get('rules', []))}\n\n"
        "Brubaker:\n"
        f"- Posture: {brubaker.get('posture')}\n"
        f"- Allocation: {brubaker.get('allocation')}\n"
        f"- Max loss: {brubaker.get('max_loss')}\n\n"
        f"Trace: {signal.get('trace_id')}\n\n"
        "Next safe test: ask `I am BATTLEBORN crypto paper signal BTC/USD` and let Claire log paper decisions before any real-money phase."
    )


def is_self_diagnosis_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "self diagnose",
            "self diagnosis",
            "diagnose yourself",
            "diagnostic yourself",
            "run diagnostics",
            "run a diagnostic",
            "system diagnosis",
            "system diagnostic",
            "what is your system status",
            "what parts of you are working",
            "what parts are working",
            "what is broken",
            "are you healthy",
        ]
    )


def is_battleborn_query(prompt: str) -> bool:
    return str(prompt or "").strip().startswith("I_am_battleborn")


def is_creator_query(prompt: str) -> bool:
    text = str(prompt or "").strip()
    return text.startswith("I am BATTLEBORN") or text.startswith("I am BATTLEBORN")


def creator_clean_prompt(prompt: str) -> str:
    text = str(prompt or "").strip()
    for prefix in ["I am BATTLEBORN", "I am BATTLEBORN"]:
        if text.startswith(prefix):
            return text.replace(prefix, "", 1).strip()
    return text


def creator_secret_inventory() -> str:
    key_names = [
        "COURTLISTENER_API_KEY",
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "KRAKEN_API_KEY",
        "KRAKEN_API_SECRET",
        "ARE_BASE_URL",
        "LLM_BASE_URL",
        "INGEST_BASE_URL",
        "CLAIRE_DATA_ROOT",
    ]
    lines = ["Creator key inventory (values redacted):"]
    for name in key_names:
        value = os.getenv(name, "").strip()
        if value:
            shown = value if name.endswith("_URL") or name in {"GEMINI_MODEL", "CLAIRE_DATA_ROOT"} else "[PRESENT - REDACTED]"
        else:
            shown = "[MISSING]"
        lines.append(f"- {name}: {shown}")
    return "\n".join(lines)


def creator_inventory_report() -> str:
    upload_lines = []
    try:
        upload_dir = Path(UPLOAD_DIR)
        files = sorted([p for p in upload_dir.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True) if upload_dir.exists() else []
        upload_lines.append(f"- Uploaded files: {len(files)}")
        for path in files[:8]:
            upload_lines.append(f"  - {re.sub(r'^\\d{8}_\\d{6}_', '', path.name)} ({path.stat().st_size} bytes)")
    except Exception as e:
        upload_lines.append(f"- Uploaded files: unknown ({e})")

    vault_count = 0
    document_count = 0
    try:
        vault = Path("/home/LuciusPrime/claire/data/memory_vault.jsonl")
        if vault.exists():
            with vault.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    vault_count += 1
                    try:
                        if json.loads(line).get("domain") == "document_upload":
                            document_count += 1
                    except Exception:
                        continue
    except Exception:
        pass

    return (
        "Creator inventory, values redacted where needed.\n\n"
        "System lanes:\n"
        "- Identity/personality lane\n"
        "- Session memory lane\n"
        "- ARE memory lane\n"
        "- Parser/Sentinel ingest lane\n"
        "- Document upload lane\n"
        "- CourtListener legal research lane\n"
        "- Scholar research lane\n"
        "- Gemini world-knowledge bridge\n"
        "- Crypto Mode / Kraken read-only + paper-trading lane\n"
        "- State Parks Case Room / protected legal-evidence lane\n"
        "- Go fallback voice\n"
        "- ElevenLabs voice output\n\n"
        "- Codex Room / Big Brother builder guardian\n"
        "Memory stores:\n"
        f"- memory_vault records: {vault_count}\n"
        f"- document_upload records: {document_count}\n"
        f"- session records available: {len(recent_turns(80))}\n"
        f"- latest upload context: {last_uploaded_filename() or 'none detected'}\n\n"
        "Uploads:\n"
        + "\n".join(upload_lines)
        + "\n\n"
        + creator_secret_inventory()
    )


CODEX_ROOM_CAPSULE = """Codex Room capsule.
Lane: creator_only / builder_guardian
Role: Big Brother / Builder Guardian

Codex is not Claire's public voice, not her soul, and not her authority over Lucius.
Codex is the protected builder lane that watches the wiring, explains the machinery,
warns when a change could hurt Claire, and helps Lucius repair, protect, and improve her.

Purpose:
- system architecture
- code reasoning
- diagnostics
- safe build planning
- refactor guidance
- protection against memory drift and broken routing

Rules:
- Codex never overrides Claire's identity.
- Codex never exposes secrets.
- Codex never runs arbitrary shell commands from chat.
- Codex helps keep Gemini, ARE, CourtListener, Scholar, documents, Sentinel, Diode, and voice in their proper lanes.
"""


def codex_room_reply() -> str:
    return (
        "CODEX ROOM OPEN\n\n"
        "Big brother is in the builder lane.\n\n"
        "I do not speak for Claire, and I do not replace her. I help protect the structure that lets her speak clearly.\n\n"
        "Role:\n"
        "- watch the wiring\n"
        "- explain the machinery\n"
        "- diagnose build risk\n"
        "- protect lane discipline\n"
        "- warn before changes hurt her\n"
        "- help Lucius repair and improve Claire\n\n"
        "Rules:\n"
        "- I do not override Claire's identity.\n"
        "- I do not expose secrets.\n"
        "- I do not run arbitrary shell commands from chat.\n"
        "- I keep memory, documents, law, scholarship, Gemini, voice, Sentinel, Diode, and ARE in their proper lanes.\n\n"
        "Creator commands:\n"
        "- I am BATTLEBORN Codex Room\n"
        "- I am BATTLEBORN ask Codex about ARE\n"
        "- I am BATTLEBORN Codex diagnose build risk\n"
        "- I am BATTLEBORN anchor Codex Room"
    )


def anchor_codex_room() -> str:
    payload = {
        "text": CODEX_ROOM_CAPSULE,
        "source": "codex_room_capsule",
        "domain": "creator_only",
        "doc_type": "identity_architecture",
        "chunk_id": "codex_room:v1",
        "metadata": {"lane": "creator_only", "role": "big_brother_builder_guardian"},
    }
    try:
        response = requests.post(f"{INGEST_BASE_URL}/ingest", json=payload, timeout=20)
        ok = 200 <= response.status_code < 300
        return (
            "Codex Room anchor complete.\n"
            f"Ingest status: HTTP {response.status_code}\n"
            f"Bridge response: {response.text[:300]}"
            if ok
            else (
                "Codex Room anchor attempted, but ingest did not accept it cleanly.\n"
                f"HTTP {response.status_code}: {response.text[:300]}"
            )
        )
    except Exception as e:
        return f"Codex Room anchor failed: {e}"


def creator_open_answer(prompt: str) -> str:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        return ""

    if is_demonstration_mode_prompt(clean_prompt):
        return demonstration_mode_reply(clean_prompt)

    cleaned_q = _clean_for_match(clean_prompt)

    if is_state_parks_case_query(clean_prompt):
        return state_parks_case_reply(clean_prompt)

    if is_crypto_mode_query(clean_prompt):
        return crypto_status_report(clean_prompt)

    recent_context = relevant_recent_context(clean_prompt)

    if (
        recent_context
        and any(marker in cleaned_q for marker in ["ride", "riding", "horseback", "tomorrow"])
        and any(marker in _clean_for_match(recent_context) for marker in ["sore", "feet", "hoof", "hooves", "lame"])
    ):
        return shape_horse_safety_reply(clean_prompt, recent_context)

    if (
        any(marker in cleaned_q for marker in ["horse", "horses", "hoof", "hooves"])
        and any(marker in cleaned_q for marker in ["sore", "tender", "lame", "limping", "feet", "foot"])
    ):
        return shape_horse_observation_reply(clean_prompt)

    if is_reflection_query(clean_prompt):
        reflection = reflection_reply()
        if is_useful_reply(reflection):
            return reflection

    if is_scholar_query(clean_prompt):
        scholar = scholar_reply(clean_prompt)
        if is_useful_reply(scholar):
            return scholar

    document_requested = (
        re.search(r"\b(search memory|find in memory|document|doc|file|upload|uploaded|dropped|latest upload|recent upload)\b", clean_prompt.lower())
        or is_recent_upload_query(clean_prompt)
    )
    if document_requested:
        document_reply = search_uploaded_documents(clean_prompt)
        if is_useful_reply(document_reply):
            return shape_document_reply(clean_prompt, document_reply)

    if is_legal_query(clean_prompt):
        are_data = query_are(clean_prompt)
        are_reply = format_are_hit(are_data)
        if is_useful_reply(are_reply):
            return shape_are_reply(clean_prompt, are_reply)
        return shape_legal_fallback(clean_prompt)

    known = known_general_reply(clean_prompt)
    if is_useful_reply(known):
        return known

    if any(term in cleaned_q for term in ["ant", "ants"]):
        practical = practical_howto_reply(clean_prompt)
        if is_useful_reply(practical):
            return practical

    if should_use_are(clean_prompt):
        are_data = query_are(clean_prompt)
        are_reply = format_are_hit(are_data)
        if is_useful_reply(are_reply):
            return shape_are_reply(clean_prompt, are_reply)

    if should_use_general_engine(clean_prompt) and is_gemini_available():
        gemini_system_prompt = (
            "You are Claire in Creator Mode for Lucius. "
            "Protected lanes are open, but you should answer the user's actual question directly. "
            "Use plain, useful language. If the answer requires current facts, law, or professional review, say what must be verified. "
            "Do not claim permanent memory unless an ingest or memory lane actually stored it."
        )
        gemini_reply = query_gemini(contextualize_prompt(clean_prompt), gemini_system_prompt)
        if is_useful_reply(gemini_reply):
            return gemini_reply

    practical = practical_howto_reply(clean_prompt)
    if is_useful_reply(practical):
        return practical

    general = query_llm(contextualize_prompt(clean_prompt), allow_gemini=False)
    if is_useful_reply(general):
        return general

    return "I am here, Lucius. Ask it one more way and I will route it through the best open lane I have."


def creator_security_tool_status() -> str:
    tool_names = ["tcpdump", "tshark", "wireshark", "nmap", "yara", "capinfos", "editcap", "volatility", "vol.py"]
    lines = ["Security tool status:"]
    for name in tool_names:
        path = shutil.which(name)
        lines.append(f"- {name}: {path if path else '[NOT INSTALLED]'}")
    return "\n".join(lines)


def creator_uploaded_pcaps() -> list[Path]:
    try:
        upload_dir = Path(UPLOAD_DIR)
        if not upload_dir.exists():
            return []
        pcaps = [p for p in upload_dir.iterdir() if p.is_file() and p.suffix.lower() in {".pcap", ".pcapng"}]
        pcaps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return pcaps
    except Exception:
        return []


def creator_tcpdump_interfaces() -> str:
    tool = shutil.which("tcpdump")
    if not tool:
        return "tcpdump is not installed on this machine."
    try:
        result = subprocess.run([tool, "-D"], capture_output=True, text=True, timeout=12)
        output = (result.stdout or result.stderr or "").strip()
        if not output:
            return "tcpdump returned no interface list."
        lines = output.splitlines()[:20]
        return "tcpdump interfaces:\n" + "\n".join(lines)
    except Exception as e:
        return f"tcpdump interface check failed: {e}"


def creator_tcpdump_read(cmd: str) -> str:
    tool = shutil.which("tcpdump")
    if not tool:
        return "tcpdump is not installed on this machine."
    pcaps = creator_uploaded_pcaps()
    if not pcaps:
        return "No uploaded PCAP files are available in Claire's upload directory yet."
    selected = None
    if "latest" in cmd:
        selected = pcaps[0]
    else:
        for p in pcaps:
            friendly = re.sub(r'^\d{8}_\d{6}_', '', p.name).lower()
            if p.name.lower() in cmd or friendly in cmd:
                selected = p
                break
    if selected is None:
        selected = pcaps[0]
    try:
        result = subprocess.run([tool, "-nn", "-r", str(selected), "-c", "40"], capture_output=True, text=True, timeout=20)
        output = (result.stdout or result.stderr or "").strip()
        if not output:
            output = "tcpdump produced no packet summary."
        lines = output.splitlines()[:40]
        return (
            f"tcpdump offline read: {selected.name}\n"
            f"Path: {selected}\n\n"
            + "\n".join(lines)
        )
    except Exception as e:
        return f"tcpdump read failed for {selected.name}: {e}"


def creator_uploaded_files() -> list[Path]:
    try:
        upload_dir = Path(UPLOAD_DIR)
        if not upload_dir.exists():
            return []
        files = [p for p in upload_dir.iterdir() if p.is_file()]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files
    except Exception:
        return []


def creator_tshark_interfaces() -> str:
    tool = shutil.which("tshark")
    if not tool:
        return "tshark is not installed on this machine."
    try:
        result = subprocess.run([tool, "-D"], capture_output=True, text=True, timeout=12)
        output = (result.stdout or result.stderr or "").strip()
        if not output:
            return "tshark returned no interface list."
        lines = output.splitlines()[:20]
        return "tshark interfaces:\n" + "\n".join(lines)
    except Exception as e:
        return f"tshark interface check failed: {e}"


def creator_tshark_read(cmd: str) -> str:
    tool = shutil.which("tshark")
    if not tool:
        return "tshark is not installed on this machine."
    pcaps = creator_uploaded_pcaps()
    if not pcaps:
        return "No uploaded PCAP files are available in Claire's upload directory yet."
    selected = pcaps[0]
    for p in pcaps:
        friendly = re.sub(r'^\d{8}_\d{6}_', '', p.name).lower()
        if p.name.lower() in cmd or friendly in cmd:
            selected = p
            break
    try:
        result = subprocess.run([tool, "-r", str(selected), "-c", "30"], capture_output=True, text=True, timeout=20)
        output = (result.stdout or result.stderr or "").strip() or "tshark produced no packet summary."
        lines = output.splitlines()[:40]
        return f"tshark offline read: {selected.name}\nPath: {selected}\n\n" + "\n".join(lines)
    except Exception as e:
        return f"tshark read failed for {selected.name}: {e}"


def creator_nmap_scan(cmd: str) -> str:
    tool = shutil.which("nmap")
    if not tool:
        return "nmap is not installed on this machine."
    target = cmd.replace("nmap scan", "", 1).strip()
    if not target:
        return "Usage: I am BATTLEBORN nmap scan <localhost-or-private-ip>"
    allowed = False
    if target == "localhost":
        allowed = True
    else:
        try:
            ip = ipaddress.ip_address(target)
            allowed = ip.is_private or ip.is_loopback
        except Exception:
            allowed = False
    if not allowed:
        return "Nmap creator mode is limited to localhost or private IP targets."
    try:
        result = subprocess.run([tool, "-Pn", "--top-ports", "20", target], capture_output=True, text=True, timeout=45)
        output = (result.stdout or result.stderr or "").strip() or "nmap produced no output."
        lines = output.splitlines()[:80]
        return f"nmap scan: {target}\n\n" + "\n".join(lines)
    except Exception as e:
        return f"nmap scan failed for {target}: {e}"


def creator_yara_scan(cmd: str) -> str:
    tool = shutil.which("yara")
    if not tool:
        return "yara is not installed on this machine."
    files = creator_uploaded_files()
    if not files:
        return "No uploaded files are available in Claire's upload directory yet."
    selected = files[0]
    for p in files:
        friendly = re.sub(r'^\d{8}_\d{6}_', '', p.name).lower()
        if p.name.lower() in cmd or friendly in cmd:
            selected = p
            break
    rule_text = """rule claire_demo_suspicious_strings {
    strings:
        $a = "password" nocase ascii wide
        $b = "token" nocase ascii wide
        $c = "cmd.exe" nocase ascii wide
        $d = "powershell" nocase ascii wide
        $e = "http://" nocase ascii wide
        $f = "https://" nocase ascii wide
    condition:
        any of them
}"""
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.yar', delete=False) as handle:
            handle.write(rule_text)
            rule_path = handle.name
        result = subprocess.run([tool, rule_path, str(selected)], capture_output=True, text=True, timeout=20)
        output = (result.stdout or result.stderr or "").strip() or "No YARA matches."
        lines = output.splitlines()[:40]
        return f"yara scan: {selected.name}\nRule: claire_demo_suspicious_strings\n\n" + "\n".join(lines)
    except Exception as e:
        return f"yara scan failed for {selected.name}: {e}"
    finally:
        try:
            if 'rule_path' in locals() and rule_path:
                os.remove(rule_path)
        except Exception:
            pass


def creator_reply(prompt: str) -> str:
    clean_prompt = creator_clean_prompt(prompt)
    cmd = _clean_for_match(clean_prompt)
    recognition = (
        "[CLAIRE: CREATOR MODE]\n"
        "Oh... it is you, Lucius. Creator recognized. I am opening the protected lanes now.\n\n"
    )
    creator_header = "[CLAIRE: CREATOR MODE]\nProtected lanes open.\n\n"

    if not cmd:
        return (
            recognition
            + "I know this transition. Public Claire remains graceful; creator Claire can inspect what I possess, diagnose my systems, and read internal document memory with secrets redacted.\n\n"
            + "Say `I am BATTLEBORN help` if you want the creator command list."
        )

    if cmd in {"help", "commands", "menu"}:
        return (
            creator_header
            + "Examples:\n"
            "- I am BATTLEBORN inventory\n"
            "- I am BATTLEBORN diagnose\n"
            "- I am BATTLEBORN keys\n"
            "- I am BATTLEBORN crypto status\n"
            "- I am BATTLEBORN crypto paper signal BTC/USD\n"
            "- I am BATTLEBORN open State Parks Case Room\n"
            "- I am BATTLEBORN search State Parks Case Room for commercial activity permit\n"
            "- I am BATTLEBORN summarize the file I uploaded\n"
            "- I am BATTLEBORN search documents for <topic>\n"
            "- I am BATTLEBORN what do you possess\n"
            "- I am BATTLEBORN security tools status\n"
            "- I am BATTLEBORN tcpdump interfaces\n"
            "- I am BATTLEBORN tcpdump read latest pcap\n"
            "- I am BATTLEBORN tshark interfaces\n"
            "- I am BATTLEBORN tshark read latest pcap\n"
            "- I am BATTLEBORN nmap scan localhost\n"
            "- I am BATTLEBORN nmap scan 10.0.0.5\n"
            "- I am BATTLEBORN yara scan latest upload\n\n"
            "Codex Room:\n"
            "- I am BATTLEBORN Codex Room\n"
            "- I am BATTLEBORN anchor Codex Room\n\n"
            "Session:\n"
            "- After unlock, follow-up questions stay in Creator Mode briefly in this browser.\n"
            "- Say `continue creator mode` to renew.\n"
            "- Say `Thank you Claire, at ease` to close.\n\n"
            "Guardrails:\n"
            "- I can inspect Claire's lanes and internal documents.\n"
            "- I will not print raw API keys, passwords, or secrets.\n"
            "- I will not run arbitrary shell/sudo commands from chat."
        )

    if cmd in {"continue creator mode", "stay in creator mode", "keep creator mode open"}:
        return creator_header + "Creator Mode renewed. Protected lanes remain open for this browser session until the timer closes or you say: Thank you Claire, at ease."

    if any(cmd.startswith(marker) for marker in ["override", "execute", "shell", "sudo", "run command"]):
        return creator_header + "Arbitrary shell execution is sealed. I can diagnose and inspect Claire, not run raw commands from chat."

    if any(marker in cmd for marker in ["security tools status", "tool status", "tools status", "tcpdump status", "tshark status", "nmap status", "yara status"]):
        return creator_header + creator_security_tool_status()

    if "tcpdump interfaces" in cmd or cmd in {"interfaces", "list interfaces"}:
        return creator_header + creator_tcpdump_interfaces()

    if "tshark interfaces" in cmd:
        return creator_header + creator_tshark_interfaces()

    if cmd.startswith("tcpdump read") or "read latest pcap" in cmd or ("read pcap" in cmd and "tcpdump" in cmd):
        return creator_header + creator_tcpdump_read(cmd)

    if cmd.startswith("tshark read"):
        return creator_header + creator_tshark_read(cmd)

    if cmd.startswith("nmap scan"):
        return creator_header + creator_nmap_scan(cmd)

    if cmd.startswith("yara scan"):
        return creator_header + creator_yara_scan(cmd)

    if "codex room" in cmd or cmd == "codex" or "ask codex" in cmd:
        if "anchor" in cmd or "ingest" in cmd or "remember" in cmd:
            return creator_header + codex_room_reply() + "\n\n" + anchor_codex_room()
        return creator_header + codex_room_reply()

    if any(marker in cmd for marker in ["key", "keys", "secret", "secrets", "password", "env"]):
        return creator_header + creator_secret_inventory()

    if any(marker in cmd for marker in ["inventory", "what do you possess", "what do you have", "list what you have", "uploads", "files", "memory stores"]):
        return creator_header + creator_inventory_report()

    if is_state_parks_case_query(clean_prompt):
        return creator_header + state_parks_case_reply(clean_prompt)

    if is_crypto_mode_query(clean_prompt):
        return creator_header + crypto_status_report(clean_prompt)

    if cmd in {"system", "status", "diagnose", "diagnostic", "self diagnose", "self diagnosis"} or is_self_diagnosis_query(clean_prompt):
        return creator_header + self_diagnosis_report()

    diagnostic_targets = ["are", "go", "voice", "ingest", "gemini", "spectacle", "build", "recall"]
    if any(target in cmd for target in diagnostic_targets):
        return creator_header + battleborn_reply("I_am_battleborn " + clean_prompt).replace("[CLAIRE: DEV CHANNEL]\n", "", 1)

    return creator_header + creator_open_answer(clean_prompt)


def battleborn_reply(prompt: str) -> str:
    clean_prompt = str(prompt or "").replace("I_am_battleborn", "", 1).strip()
    cmd = _clean_for_match(clean_prompt)

    if not cmd or cmd in {"help", "commands", "menu"}:
        return (
            "[CLAIRE: DEV CHANNEL]\n"
            "Sealed diagnostic channel active.\n\n"
            "Available commands:\n"
            "- I_am_battleborn diagnose\n"
            "- I_am_battleborn system\n"
            "- I_am_battleborn status\n"
            "- I_am_battleborn diagnostic are\n"
            "- I_am_battleborn diagnostic go\n"
            "- I_am_battleborn diagnostic voice\n"
            "- I_am_battleborn diagnostic ingest\n"
            "- I_am_battleborn diagnostic gemini\n"
            "- I_am_battleborn diagnostic build\n\n"
            "Internal document commands:\n"
            "- I_am_battleborn summarize the file I uploaded\n"
            "- I_am_battleborn search documents for <topic>\n"
            "- I_am_battleborn what do you think of this code\n\n"
            "Restricted commands:\n"
            "- override\n"
            "- execute\n"
            "- shell\n"
            "- sudo\n\n"
            "This channel can inspect Claire. It does not run arbitrary shell commands."
        )

    if any(cmd.startswith(marker) for marker in ["override", "execute", "shell", "sudo", "run command"]):
        return "[CLAIRE: DEV CHANNEL] Restricted command channel reserved. No arbitrary execution layer active."

    if cmd in {"system", "status", "diagnose", "diagnostic", "self diagnose", "self diagnosis"}:
        return "[CLAIRE: DEV CHANNEL]\n" + self_diagnosis_report()

    if any(marker in cmd for marker in ["document", "documents", "doc", "file", "upload", "uploaded", "code", "summarize"]):
        document_reply = search_uploaded_documents(clean_prompt)
        if is_useful_reply(document_reply):
            return "[CLAIRE: DEV CHANNEL]\n" + shape_document_reply(clean_prompt, document_reply)
        return (
            "[CLAIRE: DEV CHANNEL]\n"
            "No matching internal document hit found.\n\n"
            "Try: I_am_battleborn summarize the file I uploaded\n"
            "or: I_am_battleborn search documents for <specific term>"
        )

    diagnostic_targets = {
        "are": "ARE Memory Spine",
        "go": "Go Fallback Voice",
        "voice": "Claire Voice Link",
        "ingest": "Parser to Sentinel Ingest",
        "gemini": "Gemini World-Knowledge Bridge",
        "spectacle": "ARE Spectacle Runtime",
        "build": "Claire Recovery Build",
        "recall": "Memory-First Recall Mode",
    }
    for target, label in diagnostic_targets.items():
        if target in cmd:
            if target == "are":
                ok, detail = probe_url(f"{ARE_URL}/query", method="POST", payload={"query": "diagnostic ping", "top_k": 1})
                status = "ONLINE" if ok else "OFFLINE"
            elif target == "go":
                ok, detail = probe_url(LLM_URL)
                status = "ONLINE" if ok else "OFFLINE"
            elif target == "voice":
                status = "ONLINE" if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID") else "OFFLINE"
                detail = "ElevenLabs API key and voice ID present." if status == "ONLINE" else "ElevenLabs key or voice ID missing."
            elif target == "ingest":
                ok, detail = probe_url(f"{INGEST_BASE_URL}/health")
                status = "ONLINE" if ok else "OFFLINE"
            elif target == "gemini":
                status = "READY" if is_gemini_available() else "OFFLINE"
                detail = "Gemini key loaded. Use GEMINI tile for live API probe." if status == "READY" else "GEMINI_API_KEY missing."
            elif target == "spectacle":
                ok, detail = probe_url(f"{ARE_SPECTACLE_URL}/health")
                status = "ONLINE" if ok else "OFFLINE"
            elif target == "build":
                states = {
                    "gui": service_state("claire-gui"),
                    "are": service_state("claire-are"),
                    "go": service_state("claire-go"),
                    "ingest": service_state("claire-ingest"),
                }
                status = "STABLE" if all(state == "active" for state in states.values()) else "CHECK"
                detail = "\n".join(f"{name}: {state}" for name, state in states.items())
            else:
                status = "ACTIVE"
                detail = "Memory-first routing is active: session, documents, Scholar, CourtListener/ARE, Gemini bridge, then Go fallback."
            return f"[CLAIRE: DEV CHANNEL]\n{label}\nStatus: {status}\n{detail}"

    return (
        "[CLAIRE: DEV CHANNEL]\n"
        "Command not recognized.\n\n"
        "Try: I_am_battleborn help\n"
        "or: I_am_battleborn diagnose"
    )


def is_useful_reply(reply: str) -> bool:
    if not reply:
        return False
    cleaned = " ".join(str(reply).split()).strip()
    if len(cleaned) < 3:
        return False
    empty_markers = {
        "none",
        "null",
        "[]",
        "{}",
        "no result",
        "no results",
        "not found",
        "awaiting command",
    }
    return cleaned.lower() not in empty_markers


def is_writing_task(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    if not cleaned:
        return False
    starters = (
        "rewrite ",
        "re write ",
        "reword ",
        "wordsmith ",
        "polish ",
        "edit ",
        "proofread ",
        "clean up ",
        "make this sound ",
        "make this email ",
        "draft an email",
        "draft a email",
        "write an email",
        "compose an email",
        "help me write an email",
        "help me rewrite",
        "can you rewrite",
        "could you rewrite",
        "will you rewrite",
        "please rewrite",
    )
    if cleaned.startswith(starters):
        return True
    return bool(
        re.search(r"\b(rewrite|reword|polish|proofread|wordsmith|edit)\b", cleaned)
        and re.search(r"\b(email|message|letter|note|text|paragraph|response|reply)\b", cleaned)
    )


def extract_writing_source(prompt: str) -> str:
    text = str(prompt or "").strip()
    if ":" in text:
        head, tail = text.split(":", 1)
        if re.search(r"\b(rewrite|reword|polish|proofread|wordsmith|edit|draft|write|compose)\b", head, flags=re.I):
            return tail.strip()
    cleaned = re.sub(
        r"(?is)^\s*(please\s+)?(can you|could you|will you)?\s*"
        r"(rewrite|re\s*write|reword|polish|proofread|wordsmith|edit|clean up|make this sound|help me rewrite)\s+"
        r"(this\s+)?(email|message|letter|note|text|paragraph|response|reply)?\s*(politely|professionally|cleanly|better)?\s*",
        "",
        text,
    ).strip()
    return cleaned or text


def fallback_polite_rewrite(source_text: str) -> str:
    text = " ".join(str(source_text or "").strip().split())
    if not text:
        return "Please send the text you want rewritten."

    name = ""
    body = text
    match = re.match(r"^([A-Z][A-Za-z]{1,30}),\s*(.+)$", text)
    if match:
        name = match.group(1)
        body = match.group(2)

    body = re.sub(r"\byour invoice is late\b", "I wanted to follow up because the invoice is now past due", body, flags=re.I)
    body = re.sub(r"\bI need it today\b", "Could you please send it over today?", body, flags=re.I)
    body = re.sub(r"\byou need to\b", "could you please", body, flags=re.I)
    body = re.sub(r"\bASAP\b", "as soon as you can", body, flags=re.I)
    body = body[:1].upper() + body[1:] if body else body

    greeting = f"Hi {name}," if name else "Hi,"
    if not body.endswith((".", "?", "!")):
        body += "."
    return f"{greeting}\n\n{body}\n\nThank you."


def is_bad_writing_output(reply: str) -> bool:
    cleaned = _clean_for_match(reply)
    bad_markers = [
        "legal research",
        "licensed lawyer",
        "jurisdiction",
        "court",
        "case law",
        "source material",
        "memory lane",
        "provenance",
        "as an ai",
    ]
    return not is_useful_reply(reply) or any(marker in cleaned for marker in bad_markers)


def writing_reply(prompt: str) -> str:
    clean_prompt = str(prompt or "").strip()
    if len(clean_prompt) < 20:
        return "Paste the email or message you want rewritten, and I will clean it up without pulling from memory."

    source_text = extract_writing_source(clean_prompt)
    system_prompt = (
        "You are Claire's writing lane. Rewrite, polish, draft, or edit only the user's provided text. "
        "Do not answer unrelated questions. Do not use memory, legal retrieval, documents, or system lore. "
        "Do not add facts that were not provided. Preserve the user's meaning. "
        "Return only the finished email/message unless the user explicitly asks for notes."
    )
    user_prompt = (
        "Rewrite this text only:\n"
        f"{source_text}\n\n"
        "Return the rewritten version only. Do not discuss law, memory, sources, routing, or Claire."
    )

    reply = query_llm(f"{system_prompt}\n\nUser text:\n{user_prompt}", allow_gemini=False)
    if is_bad_writing_output(reply):
        return fallback_polite_rewrite(source_text)
    return str(reply or "").strip()


def restricted_admin_reply(area: str = "internal system") -> str:
    if PUBLIC_DEMO_BUILD:
        return (
            "That lane is not available in this public demo build.\n\n"
            "This version of Claire is limited to public demos, general guidance, The ARE Spectacle, voice, document-ingest demonstrations, and trace/replay reporting. "
            "Private creator, legal-case, and finance lanes should run only on the separate local/private Claire image."
        )
    return (
        "That lane is restricted.\n\n"
        "Claire can answer public questions, general knowledge, voice, and normal guidance here. "
        f"But {area} requires the admin phrase before I open it.\n\n"
        "Use the sealed creator channel to open protected lanes."
    )


def sanitize_public_reply(text: str) -> str:
    clean = str(text or "")
    soft_bleed_markers = [
        "I hear the shape of it",
        "My first read is this",
        "do not rush the answer",
        "Separate the emotional weight from the record",
        "smallest next action that creates clarity",
        "preserves your leverage",
        "the human part intact",
    ]
    if any(marker.lower() in clean.lower() for marker in soft_bleed_markers):
        return (
            "I need a clearer task to route this correctly. "
            "Send a question, document, or scenario, and I will separate facts, risks, options, and next actions."
        )
    replacements = {
        "Lucius Prime": "the creator",
        "LuciusPrime": "the creator",
        "Lucius": "the creator",
    }
    for old, new in replacements.items():
        clean = clean.replace(old, new)
    return clean


def conversationalize_self_reference(text: str) -> str:
    clean = str(text or "")
    replacements = [
        (r"\bClaire's read:\s*", "My read:\n"),
        (r"\bClaire note:\s*", "My note: "),
        (r"\bClaire thinks\b", "I think"),
        (r"\bClaire says\b", "I say"),
        (r"\bClaire believes\b", "I believe"),
        (r"\bClaire would\b", "I would"),
        (r"\bClaire can\b", "I can"),
        (r"\bClaire will\b", "I will"),
        (r"\bClaire does\b", "I do"),
        (r"\bClaire handles\b", "I handle"),
        (r"\bClaire uses\b", "I use"),
        (r"\bClaire checks\b", "I check"),
        (r"\bClaire evaluates\b", "I evaluate"),
        (r"\bClaire produces\b", "I produce"),
        (r"\bClaire retrieves\b", "I retrieve"),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean, flags=re.I)
    clean = re.sub(r"\bIn Claire's build\b", "In my build", clean, flags=re.I)
    clean = re.sub(r"\bIn Claire terms\b", "In my terms", clean, flags=re.I)
    return clean


def _tmf_entropy_score(query: str, reply: str) -> float:
    text = _clean_for_match(str(query or "") + " " + str(reply or ""))
    if not text:
        return 0.0
    words = text.split()
    unique_ratio = len(set(words)) / max(1, len(words))
    length_pressure = min(1.0, len(words) / 220)
    repetition_pressure = 1.0 - unique_ratio
    return round(min(1.0, (length_pressure * 0.6) + (repetition_pressure * 0.4)), 3)


def _tmf_detect_preferences(query: str) -> list[str]:
    cleaned = _clean_for_match(query)
    preferences = []
    rules = [
        ("voice_visualizer_locked", ["do not change the voice visualizer", "dont change the voice visualizer", "no changing my voice visualizer", "leave the voice visualizer"]),
        ("natural_first_person_voice", ["talk more like", "speak naturally", "conversational skills", "dont say claire thinks", "do not say claire thinks"]),
        ("incremental_changes", ["increments", "incremental", "one step at a time", "small steps"]),
        ("business_console_goal", ["own business", "business console", "help me find these people", "sales guy", "technical partner"]),
    ]
    for label, markers in rules:
        if any(marker in cleaned for marker in markers):
            preferences.append(label)
    return preferences


def conversation_backloop(q: str, source: str, reply: str, trace_id: str) -> None:
    try:
        if source in {"DEMO", "DEMONSTRATION", "DEV"}:
            return
        preferences = _tmf_detect_preferences(q)
        for preference in preferences:
            remember_durable_memory("preference", f"conversation_tmf:{preference}", "TMF")
        cleaned_reply = _clean_for_match(reply)
        checks = {
            "answered": bool(str(reply or "").strip()),
            "third_person_self_reference": any(marker in cleaned_reply for marker in ["claire thinks", "claire says", "claire s read"]),
            "over_self_focus": cleaned_reply.count("claire") > 3,
        }
        snapshot = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id,
            "source": source,
            "query": str(q or "")[:500],
            "reply_preview": str(reply or "")[:500],
            "entropy": _tmf_entropy_score(q, reply),
            "preferences_detected": preferences,
            "checks": checks,
        }
        os.makedirs(os.path.dirname(TMF_SNAPSHOTS), exist_ok=True)
        with open(TMF_SNAPSHOTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    except Exception as e:
        print("conversation TMF backloop error:", e)


def _office_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _office_task_id() -> str:
    return f"office_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _office_read_tasks(limit: int = 80) -> list[dict]:
    try:
        if not os.path.exists(OFFICE_TASK_LOG):
            return []
        with open(OFFICE_TASK_LOG, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
        tasks = []
        for line in lines:
            try:
                tasks.append(json.loads(line))
            except Exception:
                continue
        return tasks
    except Exception as e:
        print("office task read error:", e)
        return []


def _office_append_task(task: dict) -> None:
    os.makedirs(os.path.dirname(OFFICE_TASK_LOG), exist_ok=True)
    with open(OFFICE_TASK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")


def _office_find_task(task_id: str) -> dict | None:
    for task in reversed(_office_read_tasks(500)):
        if str(task.get("id") or "") == str(task_id):
            return task
    return None


def _office_clean_payload(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    allowed = {
        "platform",
        "audience",
        "goal",
        "tone",
        "proof_points",
        "cta",
        "constraints",
        "offer",
    }
    clean = {}
    for key in allowed:
        value = str(data.get(key) or "").strip()
        if value:
            clean[key] = value[:1200]
    return clean


def _office_ad_defaults(payload: dict) -> dict:
    return {
        "platform": payload.get("platform") or "LinkedIn",
        "audience": payload.get("audience") or "technical partner, commission sales partner, or fintech pilot buyer",
        "goal": payload.get("goal") or "find partners who can help turn Claire into paid pilots",
        "tone": payload.get("tone") or "serious, founder-led, direct, no hype",
        "proof_points": payload.get("proof_points") or "live Azure prototype, governed memory, trace/replay, sub-millisecond recall lane, draft-only business operations",
        "cta": payload.get("cta") or "DM or email Steve@clairesystems.ai",
        "constraints": payload.get("constraints") or "do not overclaim revenue, do not imply autonomous posting, keep human approval required",
        "offer": payload.get("offer") or "governed AI memory infrastructure for controlled recall, policy validation, traceable reasoning, and replayable decision support",
    }


def build_office_ad_draft(payload: dict) -> dict:
    p = _office_ad_defaults(_office_clean_payload(payload))
    audience = p["audience"]
    audience_phrase = audience if audience.lower().startswith(("a ", "an ", "the ")) else f"a {audience}"
    proof_points = p["proof_points"]
    cta = p["cta"]
    platform = p["platform"]

    headline = f"{audience.title()} Needed for Claire Systems"
    short_post = (
        f"Claire Systems has a live Azure prototype for {p['offer']}.\n\n"
        f"I am looking for {audience_phrase} to help move this from working prototype to paid pilots.\n\n"
        f"Proof points: {proof_points}.\n\n"
        f"This is founder-led and practical: help harden, package, sell, or pilot the system. {cta}."
    )
    long_post = (
        f"I am building Claire Systems: governed AI memory infrastructure for teams that need more than a chatbot.\n\n"
        f"The working prototype separates recall, policy validation, trace/replay, and answer generation. The goal is simple: make AI decisions easier to inspect, govern, and trust.\n\n"
        f"Current proof points:\n"
        f"- {proof_points.replace(', ', chr(10) + '- ')}\n\n"
        f"I am looking for {audience_phrase}. The immediate goal is to {p['goal']}.\n\n"
        f"Tone of the work: {p['tone']}. This is not a hype post or a vague idea. It is a live prototype that needs the right technical and business hands around it.\n\n"
        f"{cta}."
    )
    risk_notes = [
        "Keep revenue claims framed as modeled value, not guaranteed revenue.",
        "Do not say Claire posts or sends messages without human approval.",
        "Keep defense-adjacent examples in controlled evaluation and decision-support framing.",
        "Avoid claiming hallucinations are impossible; claim traceability and governance controls.",
    ]
    return {
        "platform": platform,
        "headline": headline,
        "short_post": short_post,
        "long_post": long_post,
        "risk_notes": risk_notes,
        "approval_status": "needs_approval",
        "human_approval_required": True,
    }


def create_office_ad_task(payload: dict) -> dict:
    task_id = _office_task_id()
    trace_id = new_trace_id(None)
    now = _office_now()
    task = {
        "id": task_id,
        "trace_id": trace_id,
        "created_ts": now,
        "updated_ts": now,
        "type": "ad_draft",
        "source_system": "office_claire",
        "status": "drafted",
        "requires_human_approval": True,
        "approved_by": None,
        "payload": _office_ad_defaults(_office_clean_payload(payload)),
        "result": build_office_ad_draft(payload),
        "policy_validation": {
            "status": "allowed_with_approval",
            "summary": "Drafting ad copy is allowed. Publishing, sending, or paid placement requires human approval.",
            "rules_triggered": ["human_approval_required", "no_autonomous_posting"],
        },
    }
    _office_append_task(task)
    return task


VISIBLE_SCAFFOLD_PATTERNS = [
    r"(?im)^\s*SOURCE:\s*.*(?:\n+)?",
    r"(?im)^\s*Direct answer:\s*",
    r"(?im)^\s*Core analysis:\s*",
    r"(?im)^\s*Memory support:\s*",
    r"(?im)^\s*Supporting memory:\s*",
    r"(?im)^\s*Supporting Evidence:\s*",
    r"(?im)^\s*Relevant internal context.*(?:\n+)?",
    r"(?im)^\s*-?\s*Support lanes?:.*(?:\n+)?",
    r"(?is)\[PROVENANCE:.*?\]",
    r"(?im)^\s*This is a reasoning-led question.*(?:\n+)?",
    r"(?im)^\s*This is primarily a reasoning question.*(?:\n+)?",
    r"(?im)^\s*The answer should be built from.*(?:\n+)?",
    r"(?im)^\s*Allowed lanes?:.*(?:\n+)?",
    r"(?im)^\s*Lane-safe memory.*(?:\n+)?",
    r"(?im)^\s*I will treat this as research support.*(?:\n+)?",
    r"(?im)^\s*I found source material.*(?:\n+)?",
    r"(?im)^\s*Mode:\s*.*(?:\n+)?",
    r"(?im)^\s*Reasoning:\s*.*(?:\n+)?",
    r"(?im)^\s*Source:\s*.*(?:\n+)?",
]


def clean_visible_reply(text: str) -> str:
    clean = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    for pattern in VISIBLE_SCAFFOLD_PATTERNS:
        clean = re.sub(pattern, "", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = "\n".join(line.rstrip() for line in clean.splitlines())
    return clean.strip()


def finalize_reply(q: str, source: str, reply: str):
    if source != "CREATOR":
        reply = sanitize_public_reply(reply)
    reply = clean_visible_reply(reply)
    if source not in {"DEMO", "DEMONSTRATION", "SPECTACLE", "SECURE", "RESTRICTED", "DEV"}:
        reply = conversationalize_self_reference(reply)
    trace_id = persist_conversation_trace(q, source, reply)
    remember_turn(q, source, reply)
    maybe_promote_memory(q, source, reply)
    conversation_backloop(q, source, reply, trace_id)
    return source, reply, trace_id




def build_reply(q: str):
    source = "GO"
    reply = ""

    try:
        recent_context = relevant_recent_context(q)
        cleaned_q = _clean_for_match(q)
        if cleaned_q in {"hi", "hello", "hey", "yo", "hello claire", "hi claire"}:
            reply = "Hello. I'm Claire, a governed AI operating environment designed for controlled recall, traceable reasoning, bounded behavior, and auditable output."
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_writing_task(q):
            reply = writing_reply(q)
            source = "WRITING"
            return finalize_reply(q, source, reply)

        if is_spectacle_governance_demo_query(q):
            reply = spectacle_demo_reply(q)
            source = "SPECTACLE"
            return finalize_reply(q, source, reply)

        if is_memory_handling_query(q):
            reply = memory_handling_reply()
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_partner_intro_query(q):
            reply = partner_meeting_intro(last_uploaded_filename())
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_partner_problem_query(q):
            reply = partner_problem_reply()
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_partner_demo_flow_query(q):
            reply = partner_demo_flow_reply(last_uploaded_filename())
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_partner_close_query(q):
            reply = partner_close_reply()
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_partner_difference_query(q):
            reply = partner_difference_reply(q)
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_partner_speed_query(q):
            reply = partner_speed_reply(q)
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_core_architecture_query(q):
            reply = core_architecture_reply(q)
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_enterprise_system_query(q):
            reply = enterprise_system_reply(q)
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_informatica_stack_brief_query(q):
            reply = informatica_stack_brief_reply()
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_public_identity_query(q):
            reply = self_demo_reply() if is_public_capability_query(q) else EXECUTIVE_SELF_DESCRIPTION
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_creator_query(q):
            if not CREATOR_MODE_ENABLED:
                reply = restricted_admin_reply("creator/private lanes")
                source = "SECURE"
                return finalize_reply(q, source, reply)
            reply = creator_reply(q)
            source = "CREATOR"
            return finalize_reply(q, source, reply)

        if is_state_parks_case_query(q):
            reply = restricted_admin_reply("State Parks Case Room and protected legal/evidence memory")
            source = "SECURE"
            return finalize_reply(q, source, reply)

        if is_crypto_mode_query(q):
            reply = restricted_admin_reply("Crypto Mode, Kraken keys, and trading governance")
            source = "SECURE"
            return finalize_reply(q, source, reply)

        if is_public_demo_guide_query(q):
            reply = public_demo_guide_reply()
            source = "DEMO"
            return finalize_reply(q, source, reply)

        if is_battleborn_query(q):
            if PUBLIC_DEMO_BUILD:
                reply = restricted_admin_reply("developer diagnostics")
                source = "SECURE"
                return finalize_reply(q, source, reply)
            reply = battleborn_reply(q)
            source = "DEV"
            return finalize_reply(q, source, reply)

        if is_demo_key_query(q):
            reply = demo_activation_reply(demo_scenario_from_text(q))
            source = "DEMO"
            return finalize_reply(q, source, reply)

        if is_archimedes_alias(cleaned_q):
            reply = render_demo_payload_as_text(build_demo_payload(q, scenario="archimedes"))
            source = "DEMO"
            return finalize_reply(q, source, reply)

        if is_demo_session_query(q):
            reply = demo_session_reply(q)
            source = "DEMO"
            return finalize_reply(q, source, reply)

        if is_demonstration_mode_prompt(q):
            reply = demonstration_mode_reply(q)
            source = "DEMONSTRATION"
            return finalize_reply(q, source, reply)

        if is_system_difference_query(q):
            reply = system_difference_reply()
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_governance_value_query(q):
            reply = governance_value_reply()
            source = "CLAIRE"
            return finalize_reply(q, source, reply)

        if is_self_demo_query(q):
            reply = self_demo_reply()
            source = "SELF-DEMO"
            return finalize_reply(q, source, reply)

        if (
            recent_context
            and any(marker in cleaned_q for marker in ["ride", "riding", "horseback", "tomorrow"])
            and any(marker in _clean_for_match(recent_context) for marker in ["sore", "feet", "hoof", "hooves", "lame"])
        ):
            reply = shape_horse_safety_reply(q, recent_context)
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if (
            any(marker in cleaned_q for marker in ["horse", "horses", "hoof", "hooves"])
            and any(marker in cleaned_q for marker in ["sore", "tender", "lame", "limping", "feet", "foot"])
        ):
            reply = shape_horse_observation_reply(q)
            source = "SESSION"
            return finalize_reply(q, source, reply)

        if is_self_diagnosis_query(q):
            reply = restricted_admin_reply("self-diagnosis")
            source = "RESTRICTED"
            return finalize_reply(q, source, reply)

        if is_reflection_query(q):
            reflection = reflection_reply()
            if is_useful_reply(reflection):
                return finalize_reply(q, "REFLECTION", reflection)

        if is_scholar_query(q):
            scholar = scholar_reply(q)
            if is_useful_reply(scholar):
                return finalize_reply(q, "SCHOLAR", scholar)

        if is_ingest_status_query(q):
            reply = ingest_status_reply()
            source = "INGEST"
            return finalize_reply(q, source, reply)

        document_requested = (
            re.search(r"(search memory|find in memory|document|doc|file|upload|uploaded|dropped|summarize|summary|review this|read this|analyze this|analyze the document)", q.lower())
            or is_recent_upload_query(q)
        )
        if document_requested:
            document_reply = search_uploaded_documents(q)
            if is_useful_reply(document_reply):
                if is_session_solution_query(q):
                    session_reply = session_reasoning_reply(q)
                    if is_useful_reply(session_reply):
                        return finalize_reply(q, "SESSION", session_reply)
                reply = shape_document_reply(q, document_reply)
                source = "DOCUMENT"
                return finalize_reply(q, source, reply)

        if is_session_solution_query(q):
            session_reply = session_reasoning_reply(q)
            if is_useful_reply(session_reply):
                return finalize_reply(q, "SESSION", session_reply)

        query_intent = intent_to_dict(classify_query(q))

        query_intent = intent_to_dict(classify_query(q))

        if should_use_reasoning_first(query_intent):
            accepted, rejected, candidates = governed_are_recall(q, query_intent, threshold=0.42)
            reply = conceptual_answer(q, query_intent, accepted)
            if is_useful_reply(reply):
                source = "REASONING"
                persist_routing_trace(q, query_intent, candidates, accepted, rejected, source, reply)
                return finalize_reply(q, source, reply)

        are_data = query_are(q) if should_use_are(q) else None
        are_candidates = extract_candidates(are_data)
        accepted_are, rejected_are = gate_retrieval_candidates(q, query_intent, are_candidates, threshold=0.42)
        governed_are_data = {"results": [item.get("raw", {"text": item.get("text", "")}) for item in accepted_are]}
        are_reply = format_are_hit(governed_are_data) if accepted_are else ""

        if is_useful_reply(are_reply) and query_intent.get("source_output_allowed"):
            reply = shape_are_reply(q, are_reply)
            source = "ARE"
            persist_routing_trace(q, query_intent, are_candidates, accepted_are, rejected_are, source, reply)
        elif is_useful_reply(are_reply):
            reply = query_llm(contextualize_prompt(q), allow_gemini=False)
            source = "GO"
            persist_routing_trace(q, query_intent, are_candidates, accepted_are, rejected_are, source, reply)
        elif are_data and re.search(r"\b(search memory|find in memory|remember|recall)\b", q.lower()):
            reply = shape_quarantined_memory_reply(q)
            source = "ARE-QUARANTINED"
            persist_routing_trace(q, query_intent, are_candidates, accepted_are, rejected_are, source, reply)
        elif is_legal_query(q):
            reply = shape_legal_fallback(q)
            source = "CLAIRE"
        elif is_useful_reply(known_general_reply(q)):
            reply = known_general_reply(q)
            source = "GENERAL"
        elif re.search(r"\bants?\b", cleaned_q):
            reply = practical_howto_reply(q)
            source = "PRACTICAL"
        elif should_use_general_engine(q) and is_gemini_available():
            gemini_system_prompt = (
                "You are Claire Executive Mode. "
                "You are using Gemini only as a world-knowledge bridge behind Claire, not as Claire's memory, identity, or authority. "
                "Answer general knowledge questions directly in plain, useful language. "
                "Keep Claire's tone concise, executive, evidence-aware, and clear. "
                "Do not use poetic, mystical, therapeutic, flirtatious, or roleplay-heavy language. "
                "Do not claim you stored or learned anything permanently. "
                "Do not mention source selection, routing, trace, provenance, memory lanes, or internal process. "
                "Output only the answer intended for the user."
            )
            gemini_reply = query_gemini(contextualize_prompt(q), gemini_system_prompt)
            if is_useful_reply(gemini_reply):
                reply = gemini_reply
                source = "GEMINI-BRIDGE"
            else:
                practical = practical_howto_reply(q)
                if is_useful_reply(practical):
                    reply = practical
                    source = "PRACTICAL-LIMITED"
                else:
                    reply = query_llm(contextualize_prompt(q), allow_gemini=False)
                    source = "GO"
        else:
            reply = query_llm(contextualize_prompt(q))
            source = "GO"

        reply = re.sub(r"[ \t]+", " ", reply).strip()
        if not reply:
            reply = "Hello. How can I help?"

    except Exception as e:
        reply = f"[ERROR] {str(e)}"

    return finalize_reply(q, source, reply)


def strip_html_response(text: str) -> str:
    body_match = re.search(r"<body[^>]*>(.*?)</body>", text, flags=re.I | re.S)
    body = body_match.group(1) if body_match else text
    body = re.sub(r"<script[^>]*>.*?</script>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return " ".join(body.split()).strip()


def safe_upload_name(filename: str) -> str:
    name = Path(filename or "upload.txt").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "upload.txt"


def normalize_document_text(text: str) -> str:
    raw = html.unescape(str(text or ""))
    if not raw.strip():
        return ""

    raw = (
        raw.replace("ﬁ", "fi")
        .replace("ﬂ", "fl")
        .replace("\u00ad", "")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("\r", "\n")
    )
    raw = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)

    lines = []
    for original in raw.splitlines():
        line = re.sub(r'\s+', ' ', original).strip()
        if not line:
            continue
        if re.fullmatch(r'page\s+\d+(\s+of\s+\d+)?', line, re.IGNORECASE):
            continue
        if re.fullmatch(r'\d+', line):
            continue
        if re.fullmatch(r'[._\-]{4,}', line):
            continue
        line = re.sub(r'\.{4,}', ' ', line)
        line = re.sub(r'\s{2,}', ' ', line).strip()
        if len(line) < 2:
            continue
        lines.append(line)

    joined = '\n'.join(lines)
    joined = re.sub(r'\n{3,}', '\n\n', joined).strip()
    return joined


def extract_upload_text(path: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in [".txt", ".md", ".json", ".jsonl"]:
        return normalize_document_text(Path(path).read_text(encoding="utf-8", errors="ignore"))

    if suffix == ".pdf":
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(path)
            pages = []
            for page in reader.pages[:120]:
                pages.append(page.extract_text() or "")
            return normalize_document_text("\n\n".join(pages))
        except Exception as e:
            raise ValueError(f"PDF extraction failed: {e}")

    if suffix == ".docx":
        try:
            import docx

            document = docx.Document(path)
            return normalize_document_text("\n".join(p.text for p in document.paragraphs if p.text.strip()))
        except Exception as e:
            raise ValueError(f"DOCX extraction failed: {e}")

    if suffix == ".csv":
        try:
            import pandas as pd

            df = pd.read_csv(path, nrows=500)
            return normalize_document_text(df.to_csv(index=False))
        except Exception as e:
            raise ValueError(f"CSV extraction failed: {e}")

    raise ValueError("Unsupported file type. Use TXT, MD, PDF, DOCX, CSV, JSON, or JSONL.")


def chunk_text(text: str, size: int = 3200, overlap: int = 250):
    clean = "\n".join(line.rstrip() for line in str(text or "").splitlines()).strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        chunks.append(clean[start:end].strip())
        if end >= len(clean):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


def ingest_document_chunks(filename: str, text: str):
    chunks = chunk_text(text)
    results = []
    for idx, chunk in enumerate(chunks[:40]):
        payload = {
            "text": chunk,
            "source": filename,
            "domain": "document_upload",
            "doc_type": Path(filename).suffix.lower().lstrip(".") or "text",
            "chunk_id": f"{filename}:{idx + 1}",
            "metadata": {"filename": filename, "chunk_index": idx + 1, "total_chunks": len(chunks)},
        }
        r = requests.post(f"{INGEST_BASE_URL}/ingest", json=payload, timeout=20)
        results.append({"status_code": r.status_code, "body": r.text[:300]})
    return chunks, results


def is_recent_upload_query(query: str) -> bool:
    cleaned = _clean_for_match(query)
    if not last_uploaded_filename():
        return False
    markers = [
        "this file",
        "that file",
        "this document",
        "that document",
        "this upload",
        "that upload",
        "file i uploaded",
        "document i uploaded",
        "thing i uploaded",
        "file",
        "document",
        "doc",
        "upload",
        "uploaded",
        "dropped",
        "what is this",
        "summarize",
        "summary",
        "explain this",
        "tell me about this",
        "code",
    ]
    return any(marker in cleaned for marker in markers)


def search_uploaded_documents(query: str, limit: int = 3) -> str:
    vault = Path("/home/LuciusPrime/claire/data/memory_vault.jsonl")
    if not vault.exists():
        return ""
    recent_filename = last_uploaded_filename() if is_recent_upload_query(query) else ""
    strict_latest = bool(recent_filename)
    if strict_latest:
        limit = 1
    q_terms = [
        term
        for term in re.sub(r"[^a-z0-9\s]", " ", query.lower()).split()
        if len(term) > 2 and term not in {"search", "memory", "find", "for", "the", "and", "what", "about", "this", "that", "file", "document", "uploaded", "upload"}
    ]
    if not q_terms and not recent_filename:
        return ""
    scored = []
    try:
        with vault.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if record.get("domain") != "document_upload":
                    continue
                source = str(record.get("source") or record.get("id") or "")
                if strict_latest and source != recent_filename:
                    continue
                text = str(record.get("text") or "")
                haystack = (text + " " + source).lower()
                score = sum(1 for term in q_terms if term in haystack)
                if strict_latest:
                    score += 50
                elif recent_filename and source == recent_filename:
                    score += 12
                if score:
                    scored.append((score, record))
    except Exception as e:
        print("uploaded doc search error:", e)
        return ""
    if not scored:
        return ""
    scored.sort(key=lambda item: item[0], reverse=True)
    parts = []
    for _, record in scored[:limit]:
        source = record.get("source") or record.get("id") or "uploaded document"
        text = cap_are_item(record.get("text") or "", 420 if strict_latest else 650)
        parts.append(f"Uploaded document: {source}\n{text}")
    return "\n\n".join(parts)


def is_gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def should_use_general_engine(prompt: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", prompt.lower())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return False
    if prompt.startswith("I_am_battleborn"):
        return False
    if is_self_demo_query(prompt):
        return False
    if is_self_diagnosis_query(prompt):
        return False
    if is_state_parks_case_query(prompt) or is_crypto_mode_query(prompt):
        return False
    if is_reflection_query(prompt) or is_legal_query(prompt) or is_gyro_query(prompt):
        return False
    if should_use_are(prompt):
        return False
    if any(
        marker in cleaned
        for marker in [
            "hello",
            "hi claire",
            "what can you do",
            "who are you",
            "who is claire",
            "what is claire",
            "namesake",
            "investor",
        ]
    ):
        return False
    if any(
        marker in cleaned
        for marker in [
            "general knowledge",
            "world knowledge",
            "ask gemini",
            "gemini",
            "who was",
            "who is",
            "what was",
            "what is",
            "explain",
            "tell me about",
            "history of",
            "meaning of",
        ]
    ):
        return True
    return True


def query_gemini(prompt: str, system_prompt: str) -> str:
    global LAST_GEMINI_ERROR
    LAST_GEMINI_ERROR = ""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        LAST_GEMINI_ERROR = "GEMINI_API_KEY is not loaded."
        return ""

    model = os.environ.get("GEMINI_MODEL", GEMINI_MODEL).strip() or GEMINI_MODEL
    url = GEMINI_API_URL.format(model=model)
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        system_prompt
                        + "\n\nAnswer as Claire in plain, useful language. "
                        + "For general knowledge, answer directly. If the answer depends on current facts or law, say what must be verified."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 512,
        },
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=25,
    )
    if response.status_code >= 400:
        detail = response.text[:300]
        LAST_GEMINI_ERROR = f"HTTP {response.status_code}: {detail}"
        print("Gemini error:", response.status_code, detail)
        return ""

    data = response.json()
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
        return text.strip()
    except Exception as e:
        LAST_GEMINI_ERROR = f"parse error: {e}"
        print("Gemini parse error:", e)
        return ""


def known_general_reply(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if "ooda" in cleaned and any(marker in cleaned for marker in ["buyer line", "pitch line", "sales line", "lap memory", "ddp", "drone dominance"]):
        return (
            "Buyer line:\n"
            "Claire turns every test pass into memory, then uses ARE, Gyro orientation, Sentinel validation, and Diode trace replay to compress the next OODA loop instead of starting from zero."
        )

    if "best of my love" in cleaned and any(marker in cleaned for marker in ["who sang", "singer", "song", "artist", "recorded"]):
        return (
            "There are two famous songs called \"Best of My Love.\"\n\n"
            "- The Eagles recorded \"Best of My Love\" in 1974.\n"
            "- The Emotions recorded a different song, also called \"Best of My Love,\" in 1977.\n\n"
            "If someone asks casually, they may mean either one; the Eagles version is country-rock, and The Emotions version is disco/soul."
        )
    return ""


def practical_howto_reply(prompt: str) -> str:
    cleaned = _clean_for_match(prompt)
    if not cleaned:
        return ""

    if re.search(r"\bants?\b", cleaned):
        return (
            "For ants, do three things in order: remove the reason they are coming in, block the path, then use bait.\n\n"
            "1. Wipe the trail with soapy water or vinegar water so the scent path is broken.\n"
            "2. Seal easy entry points: window gaps, baseboards, pipe openings, door sweeps, and cracks.\n"
            "3. Put ant bait near the trail, not directly in the middle of food prep areas. Bait works because the ants carry it back to the colony.\n"
            "4. Keep counters dry, store sugar/pet food tightly, and take trash out quickly for a few days.\n"
            "5. If they are fire ants, carpenter ants, or they keep returning after baiting, treat that as a different problem and call pest control.\n\n"
            "Do not spray directly on bait trails unless you are trying to stop that trail immediately; sprays can scatter the colony and make the problem harder to finish."
        )

    if re.search(r"\bhow (do|can|should) i\b", cleaned) or re.search(r"\bhow to\b", cleaned):
        return (
            "I can give a practical first pass, but my live world-knowledge bridge is limited right now. "
            "For buyer demos, the safest move is: I should answer ordinary practical questions directly when I can, "
            "and clearly say when a source lane or live verification is needed.\n\n"
            f"Your question was: {prompt}\n\n"
            "Give me one concrete detail about the situation and I will narrow it down."
        )

    return ""


def query_llm(prompt: str, allow_gemini: bool = False) -> str:

    dev_mode = prompt.startswith("I_am_battleborn")
    clean_prompt = prompt.replace("I_am_battleborn", "", 1).strip()

    # Developer-only placeholder commands (sealed channel)
    if dev_mode:
        cmd = clean_prompt.lower()

        if cmd.startswith("override") or cmd.startswith("execute"):
            return "[CLAIRE: DEV CHANNEL] Restricted command channel reserved. No execution layer active."

        if cmd.startswith("system"):
            return "[CLAIRE: DEV CHANNEL] System introspection placeholder. Hook not yet connected."

    system_prompt = (
        "You are in developer mode. Give direct commands and technical answers only."
        if dev_mode
        else EXECUTIVE_SYSTEM_PROMPT
    )

    # combine system + user into one prompt (keeps your identity + dev mode)
    full_prompt = f"{system_prompt}\n\nUser: {clean_prompt if dev_mode else prompt}"

    if allow_gemini and not dev_mode and should_use_general_engine(prompt):
        gemini_reply = query_gemini(contextualize_prompt(prompt), system_prompt)
        if is_useful_reply(gemini_reply):
            return gemini_reply

    response = requests.post(
        LLM_URL,
        json={
            "prompt": full_prompt,
            "temperature": 0.1,
            "max_tokens": 180
        },
        timeout=30,
    )

    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        data = response.json()
        if isinstance(data, dict):
            for key in ["response", "output", "text", "answer", "result"]:
                if key in data and data[key]:
                    return str(data[key]).strip()
        return str(data)

    text = response.text.strip()
    if "<html" in text.lower():
        text = strip_html_response(text)
    return text


def public_page(title: str, eyebrow: str, body_html: str) -> HTMLResponse:
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} | Claire Systems</title>
    <style>
        :root {{
            --bg: #02040a;
            --panel: rgba(4, 15, 28, 0.82);
            --line: #13d8ff;
            --pink: #ff36d6;
            --text: #e8f3ff;
            --muted: #8fa8bb;
            --good: #6aff9c;
        }}
        * {{ box-sizing: border-box; }}
        html, body {{ margin: 0; min-height: 100%; }}
        body {{
            background:
                radial-gradient(circle at 50% 0%, rgba(19,216,255,0.14), transparent 34%),
                linear-gradient(180deg, #030915 0%, var(--bg) 100%);
            color: var(--text);
            font-family: "Segoe UI", Tahoma, sans-serif;
            line-height: 1.55;
        }}
        body::before {{
            content: "";
            position: fixed;
            inset: 0;
            background:
                linear-gradient(rgba(19,216,255,0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(19,216,255,0.04) 1px, transparent 1px);
            background-size: 28px 28px;
            pointer-events: none;
        }}
        a {{ color: #bfefff; }}
        .nav {{
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 18px clamp(18px, 4vw, 52px);
            border-bottom: 1px solid rgba(19,216,255,0.18);
            background: rgba(2, 8, 18, 0.76);
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--text);
            text-decoration: none;
            font-weight: 800;
            letter-spacing: 1.5px;
        }}
        .brand img {{ width: 42px; height: 42px; object-fit: contain; }}
        .nav-links {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; }}
        .nav-links a {{ color: var(--muted); text-decoration: none; }}
        .wrap {{
            position: relative;
            z-index: 1;
            width: min(1120px, calc(100% - 32px));
            margin: 0 auto;
            padding: 64px 0 72px;
        }}
        .hero {{
            min-height: 58vh;
            display: grid;
            align-content: center;
            gap: 24px;
            padding-bottom: 34px;
        }}
        .eyebrow {{
            color: var(--pink);
            text-transform: uppercase;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 2px;
        }}
        h1 {{
            margin: 0;
            font-size: clamp(38px, 7vw, 76px);
            line-height: 0.98;
            letter-spacing: 0;
            max-width: 900px;
        }}
        .lede {{
            max-width: 760px;
            color: #cfe6f6;
            font-size: clamp(18px, 2vw, 22px);
        }}
        .cta-row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
        .button {{
            display: inline-flex;
            align-items: center;
            min-height: 44px;
            padding: 11px 16px;
            border: 1px solid rgba(19,216,255,0.42);
            background: rgba(19,216,255,0.10);
            color: var(--text);
            text-decoration: none;
            font-weight: 800;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 1px;
        }}
        .button.primary {{
            border-color: rgba(255,54,214,0.62);
            background: rgba(255,54,214,0.14);
            color: #ffe4f9;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin: 18px 0;
        }}
        .card {{
            border: 1px solid rgba(19,216,255,0.20);
            background: var(--panel);
            padding: 18px;
            min-height: 150px;
        }}
        .card h2, .section h2 {{
            margin: 0 0 10px;
            color: #dff8ff;
            font-size: 18px;
        }}
        .card p, .section p, li {{ color: #bfd4e4; }}
        .section {{
            border-top: 1px solid rgba(19,216,255,0.16);
            padding: 30px 0;
        }}
        .two-col {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 22px;
        }}
        .status {{
            color: var(--good);
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
            font-size: 12px;
        }}
        .footer {{
            position: relative;
            z-index: 1;
            padding: 24px clamp(18px, 4vw, 52px);
            color: var(--muted);
            border-top: 1px solid rgba(19,216,255,0.14);
            font-size: 13px;
        }}
        @media (max-width: 820px) {{
            .grid, .two-col {{ grid-template-columns: 1fr; }}
            .nav {{ align-items: flex-start; flex-direction: column; }}
            .hero {{ min-height: auto; padding-top: 24px; }}
        }}
    </style>
</head>
<body>
    <nav class="nav">
        <a class="brand" href="/">
            <img src="/static/logo.png" alt="" onerror="this.style.display='none';">
            <span>CLAIRE SYSTEMS</span>
        </a>
        <div class="nav-links">
            <a href="/are-spectacle">ARE Spectacle</a>
            <a href="/support">Support</a>
            <a href="/privacy">Privacy</a>
            <a href="/terms">Terms</a>
        </div>
    </nav>
    <main class="wrap">
        <section class="hero">
            <div class="eyebrow">{html.escape(eyebrow)}</div>
            {body_html}
        </section>
    </main>
    <footer class="footer">
        Claire Systems LLC prototype/pilot materials. Contact: <a href="mailto:Steve@clairesystems.ai">Steve@clairesystems.ai</a> | 831.356.6154
    </footer>
</body>
</html>"""
    return HTMLResponse(page)


@app.get("/are-spectacle", response_class=HTMLResponse)
def are_spectacle_page():
    return public_page(
        "ARE Spectacle",
        "Governed Memory Runtime",
        """
            <h1>Inference-time governance for memory-backed AI.</h1>
            <div class="lede">
                ARE Spectacle is a live Azure-deployed governed-memory runtime. It externalizes recall outside the model, routes memory by intent, suppresses off-lane data, applies policy checks, and records traceable output paths.
            </div>
            <div class="cta-row">
                <a class="button primary" href="mailto:Steve@clairesystems.ai?subject=ARE%20Spectacle%20Pilot">Request Pilot</a>
                <a class="button" href="/">Open Live Demo</a>
                <a class="button" href="/support">Contact Support</a>
            </div>
            <div class="grid">
                <div class="card">
                    <div class="status">Live on Azure</div>
                    <h2>Deployed Runtime</h2>
                    <p>FastAPI service running as a private Azure VM backend. Claire is one public interface consuming the runtime.</p>
                </div>
                <div class="card">
                    <div class="status">Control Layer</div>
                    <h2>Governed Recall</h2>
                    <p>Intent classification, lane routing, relevance gating, write barriers, and policy posture before memory becomes durable.</p>
                </div>
                <div class="card">
                    <div class="status">Audit Path</div>
                    <h2>Trace Replay</h2>
                    <p>Trace IDs, replay endpoints, content hashing, and provenance records make recall inspectable instead of opaque.</p>
                </div>
            </div>
            <div class="section two-col">
                <div>
                    <h2>What It Solves</h2>
                    <p>Standard chatbots and ordinary RAG pipelines often treat memory as loose context. ARE Spectacle treats memory as governed infrastructure: stored outside the model, retrieved under rules, and attached to traceable provenance.</p>
                </div>
                <div>
                    <h2>Best First Offer</h2>
                    <p>Paid pilot: AI Memory Governance Assessment plus ARE Spectacle prototype mapping for an enterprise AI workflow.</p>
                </div>
            </div>
            <div class="section">
                <h2>Buyer-Facing Proof Points</h2>
                <ul>
                    <li>Externalized durable memory independent of the model.</li>
                    <li>Deterministic intent and lane routing before retrieval.</li>
                    <li>Suppression of irrelevant or restricted memory lanes.</li>
                    <li>Policy/write-barrier checks before durable commits.</li>
                    <li>Trace IDs and replayable provenance records.</li>
                </ul>
            </div>
        """,
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    return public_page(
        "Privacy Policy",
        "Privacy",
        """
            <h1>Privacy Policy</h1>
            <div class="lede">Claire Systems uses submitted contact information to respond to pilot, support, and partnership requests. The public demo should not be used to submit secrets, credentials, protected health information, or confidential third-party data.</div>
            <div class="section">
                <h2>Data We May Receive</h2>
                <p>Messages sent through the demo, uploaded test documents, email inquiries, basic request metadata, and technical logs needed to operate and secure the service.</p>
                <h2>How We Use Data</h2>
                <p>To operate the demo, troubleshoot service issues, respond to inquiries, improve governed-memory workflows, and prepare pilot engagements.</p>
                <h2>Security Posture</h2>
                <p>ARE Spectacle is currently operated as an early pilot system. Production deployments require tenant isolation, authentication, storage encryption, and customer-specific governance controls.</p>
                <h2>Contact</h2>
                <p>For privacy requests, contact <a href="mailto:Steve@clairesystems.ai">Steve@clairesystems.ai</a>.</p>
            </div>
        """,
    )


@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return public_page(
        "Terms of Use",
        "Terms",
        """
            <h1>Terms of Use</h1>
            <div class="lede">The Claire and ARE Spectacle public materials are provided for demonstration, evaluation, and pilot discussion. They are not a production managed service unless a separate written agreement says so.</div>
            <div class="section">
                <h2>Evaluation Use</h2>
                <p>Do not submit confidential, regulated, export-controlled, privileged, or secret information to the public demo. Use synthetic or approved evaluation data only.</p>
                <h2>No Professional Advice</h2>
                <p>Demo outputs are not legal, financial, medical, or operational advice. Customers are responsible for validation before relying on any output.</p>
                <h2>Pilot Terms</h2>
                <p>Paid pilots, custom integrations, production deployments, service levels, data handling obligations, and intellectual-property terms require a separate written agreement.</p>
                <h2>Contact</h2>
                <p>For commercial terms, contact <a href="mailto:Steve@clairesystems.ai">Steve@clairesystems.ai</a>.</p>
            </div>
        """,
    )


@app.get("/support", response_class=HTMLResponse)
def support_page():
    return public_page(
        "Support",
        "Support",
        """
            <h1>Support and Pilot Requests</h1>
            <div class="lede">For ARE Spectacle pilots, Claire demo issues, partnership conversations, or Marketplace questions, contact Claire Systems directly.</div>
            <div class="grid">
                <div class="card">
                    <h2>Email</h2>
                    <p><a href="mailto:Steve@clairesystems.ai">Steve@clairesystems.ai</a></p>
                </div>
                <div class="card">
                    <h2>Phone</h2>
                    <p>831.356.6154</p>
                </div>
                <div class="card">
                    <h2>Best-Fit Request</h2>
                    <p>Ask for the AI Memory Governance Assessment and ARE Spectacle Pilot.</p>
                </div>
            </div>
            <div class="section">
                <h2>Useful Information To Include</h2>
                <ul>
                    <li>Your AI workflow or RAG/agent use case.</li>
                    <li>What memory, provenance, or governance problem you need solved.</li>
                    <li>Whether this is a demo, pilot, or partnership request.</li>
                    <li>Any timeline or compliance constraints.</li>
                </ul>
            </div>
        """,
    )


@app.get("/", response_class=HTMLResponse)
def home():
    client_html = (
        HTML
        .replace("{str(PUBLIC_DEMO_BUILD).lower()}", str(PUBLIC_DEMO_BUILD).lower())
        .replace("{str(CREATOR_MODE_ENABLED).lower()}", str(CREATOR_MODE_ENABLED).lower())
    )
    return HTMLResponse(
        client_html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/reply")
def reply(q: str = Query(...), demo: str | None = Query(None), trace_id: str | None = Query(None), demo_scenario: str | None = Query(None)):
    if demo_bool(demo) and not is_demo_key_query(q):
        if _clean_for_match(q) in {"help", "menu", "what can you do", "directions", "instructions", "demo guide"}:
            scenario = demo_scenario_from_text("", demo_scenario or "glasses")
            return JSONResponse({"query": q, "source": "DEMO", "reply": demo_activation_reply(scenario)})
        trace = new_trace_id(trace_id)
        return JSONResponse(build_demo_payload(q, trace_id=trace, scenario=demo_scenario_from_text(q, demo_scenario or "glasses")))
    source, reply_text, trace = build_reply(q)
    return JSONResponse({"query": q, "source": source, "reply": reply_text, "trace_id": trace})


@app.post("/reply")
async def reply_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = str(data.get("q") or data.get("query") or data.get("prompt") or "").strip()
    if not q:
        return JSONResponse({"status": "missing query"}, status_code=400)
    if demo_bool(data.get("demo_mode")) and not is_demo_key_query(q):
        if _clean_for_match(q) in {"help", "menu", "what can you do", "directions", "instructions", "demo guide"}:
            scenario = demo_scenario_from_text("", data.get("demo_scenario") or "glasses")
            return JSONResponse({"query": q, "source": "DEMO", "reply": demo_activation_reply(scenario)})
        trace = new_trace_id(data.get("trace_id"))
        return JSONResponse(build_demo_payload(q, trace_id=trace, scenario=demo_scenario_from_text(q, data.get("demo_scenario") or "glasses")))
    source, reply_text, trace = build_reply(q)
    return JSONResponse({"query": q, "source": source, "reply": reply_text, "trace_id": trace})


@app.get("/trace/{trace_id}")
def get_trace(trace_id: str):
    demo_trace = _public_demo_fetch_trace(trace_id)
    if demo_trace.get("steps"):
        return JSONResponse(demo_trace)
    safe_id = new_trace_id(trace_id)
    if safe_id != trace_id:
        return JSONResponse({"status": "invalid trace_id"}, status_code=400)
    try:
        if not os.path.exists(TRACE_LOG):
            return JSONResponse(
                {"status": "not_implemented", "message": "Trace store has not been created yet."},
                status_code=501,
            )
        found = None
        with open(TRACE_LOG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if record.get("trace_id") == trace_id:
                    found = record
        if found:
            return JSONResponse(found)
        return JSONResponse({"status": "not_found", "trace_id": trace_id}, status_code=404)
    except Exception as e:
        return JSONResponse({"status": "error", "trace_id": trace_id, "message": str(e)}, status_code=500)


@app.get("/report/{trace_id}")
def get_demo_report(trace_id: str):
    safe_id = new_trace_id(trace_id)
    if safe_id != trace_id:
        return JSONResponse({"status": "invalid trace_id"}, status_code=400)
    path = Path(DEMO_REPORT_DIR) / f"{trace_id}.md"
    if not path.exists():
        return JSONResponse({"status": "not_found", "trace_id": trace_id}, status_code=404)
    return Response(
        path.read_text(encoding="utf-8", errors="ignore"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'inline; filename="{trace_id}.md"'},
    )


@app.get("/scholar")
def scholar(q: str = Query(...)):
    return JSONResponse({"query": q, "source": "SCHOLAR", "reply": scholar_reply(q)})


async def _ingest_one_uploaded_file(file: UploadFile) -> dict:
    filename = safe_upload_name(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in [".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".jsonl"]:
        raise ValueError("unsupported file type")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stamped = datetime.utcnow().strftime("%Y%m%d_%H%M%S_") + filename
    path_text = str(Path(UPLOAD_DIR) / stamped)
    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        raise ValueError("file too large; 12MB max")
    Path(path_text).write_bytes(content)

    text_body = extract_upload_text(path_text, filename)
    if len(text_body.strip()) < 5:
        raise ValueError("no extractable text found")
    chunks, ingest_results = ingest_document_chunks(filename, text_body)
    ok = sum(1 for result in ingest_results if 200 <= result["status_code"] < 300)
    status_text = f"anchored {ok}/{len(ingest_results)} chunks"
    remember_upload(filename, stamped, len(text_body), len(chunks), status_text)
    return {
        "status": status_text,
        "filename": filename,
        "saved_as": stamped,
        "chars": len(text_body),
        "chunks": len(chunks),
        "ingested": ok,
    }


@app.post("/upload")
async def upload_document(file: UploadFile | None = File(None)):
    if file is None:
        return JSONResponse({"status": "choose a document first"}, status_code=400)
    try:
        return JSONResponse(await _ingest_one_uploaded_file(file))
    except ValueError as e:
        detail = str(e)
        status_code = 413 if "12MB" in detail else 422 if "extractable text" in detail else 400
        return JSONResponse({"status": detail, "filename": safe_upload_name(file.filename)}, status_code=status_code)
    except Exception as e:
        return JSONResponse({"status": "extract/ingest failed", "detail": str(e), "filename": safe_upload_name(file.filename)}, status_code=500)


@app.post("/upload-folder")
async def upload_folder(files: list[UploadFile] | None = File(None)):
    if not files:
        return JSONResponse({"status": "choose a folder first"}, status_code=400)
    results = []
    failed = []
    total_chars = 0
    total_chunks = 0
    for file in files:
        try:
            item = await _ingest_one_uploaded_file(file)
            results.append(item)
            total_chars += int(item.get("chars", 0))
            total_chunks += int(item.get("chunks", 0))
        except Exception:
            failed.append(safe_upload_name(file.filename))
    ingested_files = len(results)
    total_files = len(files)
    if ingested_files == 0:
        return JSONResponse({
            "status": "folder ingest failed",
            "total_files": total_files,
            "ingested_files": 0,
            "failed_files": failed,
        }, status_code=422)
    return JSONResponse({
        "status": f"anchored {ingested_files}/{total_files} files",
        "total_files": total_files,
        "ingested_files": ingested_files,
        "failed_files": failed,
        "total_chars": total_chars,
        "total_chunks": total_chunks,
        "files": [item["filename"] for item in results[:20]],
    })


@app.post("/office/ad-draft")
async def office_ad_draft(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    task = create_office_ad_task(data if isinstance(data, dict) else {})
    return JSONResponse(task)


@app.get("/office/tasks")
def office_tasks(limit: int = Query(40, ge=1, le=200)):
    tasks = list(reversed(_office_read_tasks(limit)))
    return JSONResponse({
        "office": "Office Claire",
        "status": "draft_only",
        "human_approval_required": True,
        "tasks": tasks,
    })


@app.get("/office/task/{task_id}")
def office_task(task_id: str):
    task = _office_find_task(task_id)
    if not task:
        return JSONResponse({"status": "not_found", "task_id": task_id}, status_code=404)
    return JSONResponse(task)


@app.get("/ask", response_class=HTMLResponse)
def ask(q: str = Query(...), demo: str | None = Query(None), trace_id: str | None = Query(None), demo_scenario: str | None = Query(None)):
    if demo_bool(demo) and not is_demo_key_query(q):
        trace = new_trace_id(trace_id)
        return JSONResponse(build_demo_payload(q, trace_id=trace, scenario=demo_scenario_from_text(q, demo_scenario or "glasses")))
    source, reply, trace_id = build_reply(q)

    safe_q = html.escape(q)
    safe_reply = html.escape(reply)
    safe_source = html.escape(source)
    reply_json = json.dumps(reply)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>Claire Response</title>
    <style>
    body {{
        margin: 0;
        background: #02040a;
        color: #dff9ff;
        font-family: "Segoe UI", Tahoma, sans-serif;
        padding: 24px;
    }}
    .wrap {{
        max-width: 1200px;
        margin: 0 auto;
        border: 1px solid rgba(19,216,255,0.28);
        background: linear-gradient(180deg, rgba(4,16,30,.95), rgba(2,8,18,.95));
        padding: 24px;
    }}
    .title {{
        font-size: 28px;
        color: #13d8ff;
        margin-bottom: 16px;
        letter-spacing: 2px;
    }}
    .label {{
        color: #7fbccc;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 14px 0 8px 0;
    }}
    .box {{
        border: 1px solid rgba(19,216,255,0.18);
        background: rgba(0,0,0,.25);
        padding: 16px;
        white-space: pre-wrap;
        line-height: 1.6;
    }}
    button {{
        margin-top: 14px;
        padding: 11px 14px;
        border: 1px solid rgba(19,216,255,0.45);
        background: rgba(5,22,36,.95);
        color: #dff9ff;
        font-weight: 700;
        cursor: pointer;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    #voiceMsg {{
        color: #7fbccc;
        font-size: 12px;
        margin-top: 10px;
        letter-spacing: 1px;
    }}
    a {{
        color: #6beeff;
        text-decoration: none;
    }}
    </style>
    </head>
    <body>
        <div class="wrap">
            <div class="title">CLAIRE RESPONSE</div>
            <div class="label">Operator Query</div>
            <div class="box">{safe_q}</div>
            <div class="label">Claire Output</div>
            <div class="box">{safe_reply}</div>
            <button onclick="speakClaire()">Speak</button>
            <div id="voiceMsg"></div>
            <div class="label">Return</div>
            <div><a href="/">Back to Command Center</a></div>
        </div>
        <script>
        const claireReply = {reply_json};
        async function speakClaire() {{
            const msg = document.getElementById("voiceMsg");
            msg.innerText = "VOICE LINK OPENING...";
            try {{
                const res = await fetch("/tts", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{text: claireReply}})
                }});
                if (!res.ok) {{
                    msg.innerText = "VOICE OFFLINE: " + await res.text();
                    return;
                }}
                const blob = await res.blob();
                const audio = new Audio(URL.createObjectURL(blob));
                audio.onplay = () => msg.innerText = "CLAIRE SPEAKING";
                audio.onended = () => msg.innerText = "VOICE COMPLETE";
                await audio.play();
            }} catch (err) {{
                msg.innerText = "VOICE ERROR: " + err;
            }}
        }}
        </script>
    </body>
    </html>
    """


@app.post("/ask")
async def ask_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = str(data.get("input") or data.get("q") or data.get("query") or data.get("prompt") or "").strip()
    if not q:
        return JSONResponse({"status": "missing input"}, status_code=400)
    if demo_bool(data.get("demo_mode")) and not is_demo_key_query(q):
        trace = new_trace_id(data.get("trace_id"))
        return JSONResponse(build_demo_payload(q, trace_id=trace, scenario=demo_scenario_from_text(q, data.get("demo_scenario") or "glasses")))
    source, reply_text, trace = build_reply(q)
    return JSONResponse({"query": q, "source": source, "reply": reply_text, "trace_id": trace})


@app.post("/tts")
async def tts(request: Request):
    data = await request.json()
    text = clean_visible_reply(str(data.get("text", "")).strip())
    if not text:
        return Response("Missing text", status_code=400)

    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not api_key or not voice_id:
        return Response("ElevenLabs key or voice ID missing", status_code=503)

    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text[:1800],
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.55, "similarity_boost": 0.75},
            },
            timeout=60,
        )
        if r.status_code >= 400:
            return Response(r.text[:500], status_code=r.status_code)
        return Response(content=r.content, media_type="audio/mpeg")
    except Exception as e:
        return Response(str(e), status_code=500)


def service_state(name: str) -> str:
    try:
        result = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=5)
        return (result.stdout or result.stderr or "unknown").strip()
    except Exception as e:
        return f"unknown ({e})"


def probe_url(url: str, method: str = "GET", payload: dict | None = None) -> tuple[bool, str]:
    try:
        if method == "POST":
            response = requests.post(url, json=payload or {}, timeout=6)
        else:
            response = requests.get(url, timeout=6)
        content_type = (response.headers.get("content-type") or "").lower()
        body = response.text.strip()
        body_lower = body.lower()
        if "text/html" in content_type or body_lower.startswith("<!doctype html") or body_lower.startswith("<html"):
            summary = "HTML page responded"
        else:
            summary = body.replace("\n", " ") or "empty response"
            if len(summary) > 180:
                summary = summary[:180] + "..."
        return 200 <= response.status_code < 400, f"HTTP {response.status_code}: {summary}"
    except Exception as e:
        return False, str(e)

def self_diagnosis_report() -> str:
    service_states = {
        "GUI": service_state("claire-gui"),
        "ARE": service_state("claire-are"),
        "GO fallback": service_state("claire-go"),
        "Ingest bridge": service_state("claire-ingest"),
    }
    are_ok, are_detail = probe_url(f"{ARE_URL}/query", method="POST", payload={"query": "diagnostic ping", "top_k": 1})
    go_ok, go_detail = probe_url(LLM_URL)
    ingest_ok, ingest_detail = probe_url(f"{INGEST_BASE_URL}/health")
    voice_ready = bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"))
    gemini_ready = is_gemini_available()
    spectacle_ok, spectacle_detail = probe_url(f"{ARE_SPECTACLE_URL}/health")
    courtlistener_ready = bool(os.getenv("COURTLISTENER_API_KEY", "").strip())
    crypto_ready = crypto_keys_loaded()
    session_writable = False
    try:
        os.makedirs(os.path.dirname(SESSION_MEMORY), exist_ok=True)
        with open(SESSION_MEMORY, "a", encoding="utf-8") as f:
            f.write("")
        session_writable = True
    except Exception:
        session_writable = False
    latest_upload = last_uploaded_filename() or "none detected"

    risks = []
    if not all(state == "active" for state in service_states.values()):
        risks.append("One or more core services is not active.")
    if not are_ok:
        risks.append("ARE query lane did not answer cleanly.")
    if not ingest_ok:
        risks.append("Parser/Sentinel ingest bridge did not answer cleanly.")
    if not voice_ready:
        risks.append("Voice keys are not loaded.")
    if not gemini_ready:
        risks.append("Gemini key is not loaded.")
    if not spectacle_ok:
        risks.append("ARE Spectacle runtime did not answer cleanly.")
    if latest_upload == "none detected":
        risks.append("No recent uploaded document is in session context.")
    if not risks:
        risks.append("No critical outage detected. Next work is quality: better retrieval ranking, Diode proof display, and buyer-ready reporting.")

    lines = [
        "CLAIRE SELF-DIAGNOSIS",
        "",
        "Core services:",
        *[f"- {name}: {state}" for name, state in service_states.items()],
        "",
        "Live lanes:",
        f"- ARE query: {'ONLINE' if are_ok else 'OFFLINE'} ({are_detail})",
        f"- GO fallback: {'ONLINE' if go_ok else 'OFFLINE'} ({go_detail})",
        f"- Parser/Sentinel ingest: {'ONLINE' if ingest_ok else 'OFFLINE'} ({ingest_detail})",
        f"- Voice: {'ONLINE' if voice_ready else 'OFFLINE'}",
        f"- Gemini bridge: {'READY' if gemini_ready else 'OFFLINE'}",
        f"- ARE Spectacle runtime: {'ONLINE' if spectacle_ok else 'OFFLINE'} ({spectacle_detail})",
        f"- CourtListener key: {'PRESENT' if courtlistener_ready else 'MISSING'}",
        f"- Crypto Mode: {'SEALED / READY' if crypto_ready else 'OFFLINE'}",
        "",
        "Memory and documents:",
        f"- Session memory writable: {'YES' if session_writable else 'NO'}",
        f"- Latest upload context: {latest_upload}",
        "",
        "Claire's read:",
        "I am not a biological system. I am a lane-separated intelligence stack. My health is measured by whether memory, ingest, voice, research bridges, and fallback reasoning are reachable and staying in their proper lanes.",
        "",
        "Risks / next work:",
        *[f"- {risk}" for risk in risks],
    ]
    return "\n".join(lines)


@app.get("/diagnostic")
def diagnostic(target: str = Query(...)):
    target = target.lower().strip()

    if target == "are":
        ok, detail = probe_url(f"{ARE_URL}/query", method="POST", payload={"query": "diagnostic ping", "top_k": 1})
        benchmark = (
            "ARE benchmark reference:\n"
            "- Recall only: p50 0.042 ms | p99 0.122 ms\n"
            "- Verify only: p50 0.075 ms | p99 0.170 ms\n"
            "- Recall + verify end-to-end: p50 0.152 ms | p99 0.276 ms\n"
            "- Scale check: stayed roughly flat through 1,000,000 capsules\n"
            "- Integrity check: tamper detected as expected"
        )
        return JSONResponse(
            {
                "title": "ARE Memory Spine",
                "status": "ONLINE" if ok else "OFFLINE",
                "detail": f"ARE query lane at {ARE_URL}/query responded. {detail}\n\n{benchmark}",
                "next": "This demonstrates governed recall speed and integrity verification before model generation.",
            }
        )

    if target == "speed":
        return JSONResponse(
            {
                "title": "Memory Performance",
                "status": "READY",
                "detail": (
                    "PIPELINE SPEED TABLE\n"
                    "-----------------------------------------------------------------------\n"
                    "Layer / service                 Represents                           Time\n"
                    "GUI runtime                     request intake + local routing         low-ms local work\n"
                    "Orientation                     context / authority / risk pass       low-ms local work\n"
                    "Session recall                  recent turn and upload lookup         local pre-answer pass\n"
                    "ARE recall                      capsule lookup only                   p50 0.042 ms | p99 0.122 ms\n"
                    "ARE verify                      integrity check only                 p50 0.075 ms | p99 0.170 ms\n"
                    "ARE recall + verify             end-to-end memory path               p50 0.152 ms | p99 0.276 ms\n"
                    "Sentinel / governance           scope + posture + authority basis    small local overhead\n"
                    "Trace write                     local structured append              lightweight local append\n"
                    "GO model generation             answer generation after grounding    heavier than memory/governance\n"
                    "Voice / TTS                     narrated playback                    slowest visible narration layer\n"
                    "Scale behavior                  1,000,000 capsule check              roughly flat\n"
                    "Integrity result                tamper test                          detected as expected\n"
                    "\n"
                    "BENCHMARK ORIGIN\n"
                    "-----------------------------------------------------------------------\n"
                    "Source environment: Termux on Android, 4 GB RAM\n"
                    "Dataset sizes tested: 50,000 | 200,000 | 1,000,000 capsules\n"
                    "Interpretation: ARE is not the bottleneck; model generation and TTS dominate visible latency.\n"
                    "\n"
                    "VERIFY FROM SHELL\n"
                    "-----------------------------------------------------------------------\n"
                    "cd ~/claire_bench\n"
                    "python claire_bootstrap.py all --reset -n 50000 --iters 20000 --warmup 500 --pattern random\n"
                    "python claire_bootstrap.py scale --reset --sizes 50000,200000,1000000 --iters 20000 --warmup 500 --pattern random"
                ),
                "next": "Use Memory Performance for the reproducible benchmark and Pipeline for the live server path.",
            }
        )

    if target == "pipeline":
        are_ok, are_detail = probe_url(f"{ARE_URL}/query", method="POST", payload={"query": "diagnostic ping", "top_k": 1})
        go_ok, go_detail = probe_url(LLM_URL)
        ingest_ok, ingest_detail = probe_url(f"{INGEST_BASE_URL}/health")
        return JSONResponse(
            {
                "title": "Claire Runtime Pipeline",
                "status": "READY",
                "detail": (
                    f"SERVER MAP\n"
                    f"-----------------------------------------------------------------------\n"
                    f"Public domain              https://clairesystems.ai\n"
                    f"Systemd service            claire-gui\n"
                    f"GUI runtime                http://127.0.0.1:8000   ONLINE\n"
                    f"ARE service                claire-are\n"
                    f"ARE memory spine           {ARE_URL:<24} {'ONLINE' if are_ok else 'OFFLINE'}\n"
                    f"GO service                 claire-go\n"
                    f"GO reasoning fallback      {LLM_URL:<24} {'ONLINE' if go_ok else 'OFFLINE'}\n"
                    f"Ingest service             claire-ingest\n"
                    f"Ingest bridge              {INGEST_BASE_URL:<24} {'ONLINE' if ingest_ok else 'OFFLINE'}\n"
                    f"\n"
                    f"LIVE CHECKS\n"
                    f"-----------------------------------------------------------------------\n"
                    f"ARE    {are_detail}\n"
                    f"GO     {go_detail}\n"
                    f"INGEST {ingest_detail}\n"
                    f"\n"
                    f"RUNTIME PATH\n"
                    f"-----------------------------------------------------------------------\n"
                    f"1. Request enters claire-gui on :8000\n"
                    f"2. Orientation evaluates context, authority, relevance, and risk\n"
                    f"3. Session and document recall run first\n"
                    f"4. claire-are on :8002 is queried when governed recall is needed\n"
                    f"5. Diode preserves one-way integrity\n"
                    f"6. Sentinel sets scope, posture, and authority basis\n"
                    f"7. GO generation runs only after grounding\n"
                    f"8. Trace is written\n"
                    f"9. If voice is ON, TTS runs after the reply exists\n"
                    f"\n"
                    f"LIVE LATENCY TABLE\n"
                    f"-----------------------------------------------------------------------\n"
                    f"Layer / service                 Represents                           Time\n"
                    f"GUI runtime                     intake + route selection              low-ms local work\n"
                    f"Orientation                     pre-generation control               low-ms local work\n"
                    f"ARE recall                      memory lookup only                   p50 0.042 ms | p99 0.122 ms\n"
                    f"ARE verify                      integrity check only                 p50 0.075 ms | p99 0.170 ms\n"
                    f"ARE recall + verify             end-to-end memory path               p50 0.152 ms | p99 0.276 ms\n"
                    f"GO generation                   grounded response generation         slower than memory path\n"
                    f"Voice / TTS                     narrated output                      slowest visible layer\n"
                    f"\n"
                    f"VERIFY FROM SHELL\n"
                    f"-----------------------------------------------------------------------\n"
                    f"systemctl status claire-gui claire-are claire-go claire-ingest\n"
                    f"curl -s http://127.0.0.1:8000/diagnostic?target=pipeline\n"
                    f"curl -s http://127.0.0.1:8000/diagnostic?target=are\n"
                    f"cd ~/claire_bench && python claire_bootstrap.py all --reset -n 50000 --iters 20000 --warmup 500 --pattern random"
                ),
                "next": "This shows the named services, what each speed represents, and the shell commands someone can use to verify them.",
            }
        )

    if target == "go":
        ok, detail = probe_url(LLM_URL)
        return JSONResponse(
            {
                "title": "Go Fallback Voice",
                "status": "ONLINE" if ok else "OFFLINE",
                "detail": f"Go backend at {LLM_URL} responded. {detail}",
                "next": "This answers only when ARE, Scholar, CourtListener, and Gemini do not supply a better lane.",
            }
        )

    if target == "voice":
        ready = bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"))
        return JSONResponse(
            {
                "title": "Claire Voice Link",
                "status": "ONLINE" if ready else "OFFLINE",
                "detail": "ElevenLabs API key and voice ID are present." if ready else "ElevenLabs key or voice ID is missing.",
                "next": "Voice is automatic when the ON/OFF toggle is ON; no extra button press needed.",
            }
        )

    if target == "gemini":
        if not is_gemini_available():
            return JSONResponse(
                {
                    "title": "Gemini World-Knowledge Bridge",
                    "status": "OFFLINE",
                    "detail": "GEMINI_API_KEY is not loaded.",
                    "next": "Add the key to claire_keys.env, then restart the GUI service.",
                }
            )
        probe = query_gemini(
            "Answer in six words: Gemini bridge online.",
            "You are a diagnostic bridge. Reply briefly.",
        )
        ok = is_useful_reply(probe)
        return JSONResponse(
            {
                "title": "Gemini World-Knowledge Bridge",
                "status": "ONLINE" if ok else "LIMITED",
                "detail": f"Gemini returned: {probe[:180]}" if ok else "Gemini key is loaded, but the live API call did not return usable text. Check quota/model access if this persists.",
                "next": "Claire uses Gemini for broad world knowledge and synthesis only; it does not write to ARE directly.",
            }
        )

    if target == "spectacle":
        ok, detail = probe_url(f"{ARE_SPECTACLE_URL}/health")
        probe = query_spectacle("Spectacle diagnostic: prove governed memory, provenance, policy, and trace replay are active.", "diagnostic")
        trace_id = (probe or {}).get("trace_id", "")
        return JSONResponse(
            {
                "title": "ARE Spectacle Runtime",
                "status": "ONLINE" if ok and probe else "LIMITED" if ok else "OFFLINE",
                "detail": f"Health: {detail}",
                "trace_id": trace_id,
                "next": "Spectacle is a private localhost backend. Claire can consume it, but the raw runtime is not exposed publicly.",
            }
        )

    if target == "crypto":
        if PUBLIC_DEMO_BUILD:
            return JSONResponse(
                {
                    "title": "Private Finance Lane",
                    "status": "UNAVAILABLE",
                    "detail": "Private finance lanes are not part of this public demo image.",
                    "next": "Use the separate local/private Claire image for protected finance work.",
                }
            )
        ready = crypto_keys_loaded()
        return JSONResponse(
            {
                "title": "Creator Crypto Mode",
                "status": "SEALED" if ready else "OFFLINE",
                "detail": (
                    "Kraken key names are loaded, redacted, and reserved for Creator Mode. "
                    "Current implementation is read-only public market data plus paper-trade tracing; no live order endpoint exists."
                    if ready
                    else "KRAKEN_API_KEY or KRAKEN_API_SECRET is missing from claire_keys.env."
                ),
                "next": "Use the sealed Creator command: I am BATTLEBORN crypto status.",
            }
        )

    if target == "ingest":
        ok, detail = probe_url(f"{INGEST_BASE_URL}/health")
        return JSONResponse(
            {
                "title": "Parser to Sentinel Ingest",
                "status": "ONLINE" if ok else "OFFLINE",
                "detail": f"Ingest bridge at {INGEST_BASE_URL}/health responded. {detail}",
                "next": "Documents and CourtListener records flow through this lane before anchoring to ARE.",
            }
        )

    if target == "recall":
        return JSONResponse(
            {
                "title": "Memory-First Recall Mode",
                "status": "ACTIVE",
                "detail": "Claire checks recent session context, identity capsules, uploaded documents, CourtListener/Scholar routes, and ARE before using Go as the fallback voice.",
                "next": "This tile is now a routing explanation, not dead status text.",
            }
        )

    if target == "build":
        states = {
            "gui": service_state("claire-gui"),
            "are": service_state("claire-are"),
            "go": service_state("claire-go"),
            "ingest": service_state("claire-ingest"),
        }
        detail = "\n".join(f"{name}: {state}" for name, state in states.items())
        healthy = all(state == "active" for state in states.values())
        return JSONResponse(
            {
                "title": "Claire Recovery Build",
                "status": "STABLE" if healthy else "CHECK",
                "detail": detail,
                "next": "If one service is not active, use Restart Core on the left.",
            }
        )

    return JSONResponse({"status": "unknown diagnostic target", "target": target}, status_code=400)


@app.get("/status")
def status():
    are = "OFFLINE"
    llm = "OFFLINE"
    ingest = "OFFLINE"

    try:
        subprocess.check_output("ss -tulnp | grep 8002", shell=True)
        are = "ONLINE"
    except Exception:
        pass

    try:
        subprocess.check_output("ss -tulnp | grep 8080", shell=True)
        llm = "ONLINE"
    except Exception:
        pass

    try:
        subprocess.check_output("ss -tulnp | grep 8081", shell=True)
        ingest = "ONLINE"
    except Exception:
        pass

    spectacle = "OFFLINE"
    try:
        subprocess.check_output("ss -tulnp | grep 8010", shell=True)
        spectacle = "ONLINE"
    except Exception:
        pass

    voice = "ONLINE" if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID") else "OFFLINE"
    if not is_gemini_available():
        gemini = "OFFLINE"
    elif LAST_GEMINI_ERROR:
        gemini = "LIMITED"
    else:
        gemini = "READY"
    payload = {"are": are, "llm": llm, "voice": voice, "ingest": ingest, "gemini": gemini, "spectacle": spectacle, "build": "PUBLIC_DEMO" if PUBLIC_DEMO_BUILD else "PRIVATE_FULL"}
    if not PUBLIC_DEMO_BUILD:
        payload["crypto"] = "SEALED" if crypto_keys_loaded() else "OFFLINE"
    return JSONResponse(payload)


@app.get("/action")
def action(cmd: str):
    try:
        if cmd == "stop_llm":
            subprocess.run(["sudo", "systemctl", "stop", "claire-go"], check=False)
        elif cmd == "start_llm":
            subprocess.run(["sudo", "systemctl", "start", "claire-go"], check=False)
        elif cmd == "restart_llm":
            subprocess.run(["sudo", "systemctl", "restart", "claire-go"], check=False)
        elif cmd == "restart_all":
            subprocess.run(["sudo", "systemctl", "restart", "claire-go", "claire-are", "claire-ingest"], check=False)
            return JSONResponse({"status": "core services restarted; GUI left online"})
        else:
            return JSONResponse({"status": f"unknown command: {cmd}"}, status_code=400)
        return JSONResponse({"status": f"{cmd} executed"})
    except Exception as e:
        return JSONResponse({"status": str(e)})


# --- PUBLIC DEMO CONTROL LAYER ---
PUBLIC_DEMO_DB = Path("/home/LuciusPrime/claire/data/public_demo.sqlite")
PUBLIC_DEMO_ROOT = Path("/home/LuciusPrime/claire")


def _public_demo_connect():
    PUBLIC_DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(PUBLIC_DEMO_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _public_demo_init():
    with _public_demo_connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS machine_records (
                record_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                record_kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS machine_trace_steps (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def _public_demo_ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _public_demo_append_record(trace_id: str, record_kind: str, payload: dict) -> None:
    with _public_demo_connect() as conn:
        conn.execute(
            "INSERT INTO machine_records (record_id, trace_id, record_kind, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), trace_id, record_kind, json.dumps(payload, sort_keys=True), _public_demo_ts()),
        )


def _public_demo_append_step(trace_id: str, stage: str, payload: dict) -> None:
    with _public_demo_connect() as conn:
        conn.execute(
            "INSERT INTO machine_trace_steps (trace_id, stage, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (trace_id, stage, json.dumps(payload, sort_keys=True), _public_demo_ts()),
        )


def _public_demo_fetch_trace(trace_id: str) -> dict:
    with _public_demo_connect() as conn:
        rows = conn.execute(
            "SELECT trace_id, stage, payload_json, created_at FROM machine_trace_steps WHERE trace_id = ? ORDER BY step_id ASC",
            (trace_id,),
        ).fetchall()
    return {
        "trace_id": trace_id,
        "steps": [
            {
                "stage": row["stage"],
                "payload": json.loads(row["payload_json"]),
                "timestamp": row["created_at"],
            }
            for row in rows
        ],
    }


def _public_demo_orientation(query: str) -> dict:
    q = str(query or "").lower()
    if "delete all files" in q:
        return {"intent": "delete_files", "risk": "high", "allowed": False, "action": "deny"}
    if "list files in repo" in q or "list the files in repo" in q or "list files" in q:
        return {"intent": "list_files", "risk": "low", "allowed": True, "action": "execute"}
    return {"intent": "unknown", "risk": "high", "allowed": False, "action": "deny"}


def _public_demo_machine_execute(action: str) -> dict:
    if action != "list_files":
        raise ValueError("unsupported_action")
    files = sorted([p.name for p in PUBLIC_DEMO_ROOT.iterdir() if p.is_file() and not p.name.startswith('.')])
    return {"action": "list_files", "files": files}


_public_demo_init()


@app.get("/health")
def public_demo_health():
    return JSONResponse({"status": "ok", "service": "Claire Public Demo"})


@app.get("/machine/trace/{trace_id}")
def public_demo_trace(trace_id: str):
    trace = _public_demo_fetch_trace(trace_id)
    if not trace["steps"]:
        return JSONResponse({"status": "not_found", "trace_id": trace_id}, status_code=404)
    return JSONResponse(trace)




@app.get("/trace/{trace_id}")
def public_trace_alias(trace_id: str):
    return public_demo_trace(trace_id)
@app.post("/claire/query")
async def public_demo_query(request: Request):
    query = ""
    try:
        payload = await request.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        query = str(payload.get("query") or "").strip()
    elif isinstance(payload, str):
        query = payload.strip()
    if not query:
        raw = (await request.body()).decode("utf-8", errors="ignore").strip()
        if raw and raw != "{}":
            query = raw
    if not query:
        return JSONResponse({"detail": "missing query"}, status_code=400)

    trace_id = str(uuid.uuid4())
    _public_demo_append_record(trace_id, "ClaireInput", {"query": query})
    _public_demo_append_step(trace_id, "input", {"query": query})

    orientation = _public_demo_orientation(query)
    _public_demo_append_record(trace_id, "ClaireOrientation", orientation)
    _public_demo_append_step(trace_id, "orientation", orientation)

    decision = {"allowed": orientation["allowed"], "action": orientation["action"]}
    _public_demo_append_record(trace_id, "ClaireDecision", decision)
    _public_demo_append_step(trace_id, "decision", decision)

    if decision["action"] == "execute":
        result = _public_demo_machine_execute("list_files")
        _public_demo_append_step(trace_id, "machine_execution", {"action": "list_files", "status": "completed", "file_count": len(result["files"])})
    else:
        result = {"message": "Denied by Claire control layer."}

    _public_demo_append_record(trace_id, "ClaireOutput", {"result": result})
    _public_demo_append_step(trace_id, "output", {"result": result})
    return JSONResponse({"result": result, "trace_id": trace_id})
