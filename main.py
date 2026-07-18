from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import requests
import subprocess
import os
import html
import json

from claire_runtime import ClaireRuntime

app = FastAPI()
runtime = ClaireRuntime()

ARE_URL = "http://127.0.0.1:8001"
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>CLAIRE</title>
<style>
:root { --bg: #02040a; --line: #13d8ff; --text: #d9f6ff; --panel: rgba(4, 16, 30, 0.92); }
body { margin: 0; background: var(--bg); color: var(--text); font-family: sans-serif; }
.topbar { padding: 20px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; }
.shell { display: grid; grid-template-columns: 300px 1fr 300px; gap: 15px; padding: 20px; }
.panel { background: var(--panel); border: 1px solid rgba(19, 216, 255, 0.3); padding: 15px; min-height: 200px; }
input { width: 100%; padding: 15px; background: #000; color: var(--line); border: 1px solid var(--line); }
button { padding: 10px; background: var(--line); color: #000; font-weight: bold; cursor: pointer; }
.row { display: flex; gap: 10px; align-items: center; margin: 10px 0; }
.row input[type="checkbox"] { width: auto; }
.demo-section { border-top: 1px solid rgba(19, 216, 255, 0.25); padding: 10px 0; }
.demo-section h3 { margin: 0 0 6px; color: var(--line); font-size: 14px; }
pre { white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<div class="topbar"><div><strong>CLAIRE</strong> | Sovereign Runtime</div><div>Operator: LuciusPrime</div></div>
<div class="shell">
    <div class="column"><div class="panel"><h3>Controls</h3><button onclick="fetch('/status')">Status Check</button><button onclick="replayLastTrace()">Replay Last Trace</button></div></div>
    <div class="column">
        <div class="panel"><h1>Command Center</h1><form id="askForm"><input id="askInput" name="q" placeholder="Speak to Claire..."><div class="row"><label><input id="demoMode" type="checkbox"> DEMO MODE</label><button type="submit">Send</button></div></form></div>
        <div class="panel" id="response">Awaiting Query...</div>
    </div>
    <div class="column"><div class="panel"><h3>Monitors</h3><div id="m">ARE: ONLINE<br>LLM: ONLINE</div></div></div>
</div>
<script>
let lastTraceId = "";
const responseEl = document.getElementById("response");
document.getElementById("askForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("askInput").value;
    const demoMode = document.getElementById("demoMode").checked;
    const response = await fetch("/ask", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({input, demo_mode: demoMode})
    });
    const data = await response.json();
    renderResponse(data);
});
async function replayLastTrace() {
    if (!lastTraceId) {
        responseEl.textContent = "No trace selected.";
        return;
    }
    const response = await fetch("/trace/" + encodeURIComponent(lastTraceId));
    renderResponse(await response.json());
}
function renderResponse(data) {
    if (data.trace_id) lastTraceId = data.trace_id;
    if (data.demo_mode || data.recall || data.policy) {
        const trace = data.trace_summary || {};
        responseEl.innerHTML = `
            <p><strong>Trace:</strong> ${escapeHtml(data.trace_id || "")}</p>
            <div class="demo-section"><h3>Identity</h3><div>${escapeHtml(data.identity || "")}</div></div>
            <div class="demo-section"><h3>Input</h3><div>${escapeHtml(data.input_received || data.input || "")}</div></div>
            <div class="demo-section"><h3>Recall</h3><pre>${escapeHtml(JSON.stringify(data.recall_check || data.recall || {}, null, 2))}</pre></div>
            <div class="demo-section"><h3>Policy</h3><pre>${escapeHtml(JSON.stringify(data.policy_validation || data.policy || {}, null, 2))}</pre></div>
            <div class="demo-section"><h3>Decision</h3><div>${escapeHtml(data.decision || "")}</div></div>
            <div class="demo-section"><h3>Output</h3><div>${escapeHtml(data.output || "")}</div></div>
            <div class="demo-section"><h3>Trace</h3><pre>${escapeHtml(JSON.stringify(trace.steps_executed || data.steps || [], null, 2))}</pre></div>
        `;
    } else {
        responseEl.innerHTML = `<p>${escapeHtml(data.answer || data.error || "")}</p>`;
    }
}
function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[char]));
}
</script>
</body></html>
"""

def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)

@app.get("/", response_class=HTMLResponse)
def home(): return HTML

@app.get("/ask", response_class=HTMLResponse)
def ask(q: str = Query(...), demo_mode: bool = Query(False), user_id: str = Query("default"), session_id: str = Query("web")):
    result = runtime.handle_user_message(user_id, session_id, q, {"demo_mode": demo_mode, "debug": False})
    if demo_mode:
        body = f"<pre>{html.escape(json.dumps(result, indent=2))}</pre>"
    else:
        body = f"<p>{html.escape(result['answer'])}</p>"
    return f"<html><body style='background:#02040a;color:#dff9ff;padding:40px;'><h2>CLAIRE</h2>{body}<a href='/' style='color:#13d8ff;'>Back</a></body></html>"


@app.post("/ask")
async def ask_json(request: Request):
    payload = await request.json()
    message = payload.get("input") or payload.get("message") or payload.get("q") or ""
    if not str(message).strip():
        return JSONResponse({"error": "input is required"}, status_code=400)
    result = runtime.handle_user_message(
        str(payload.get("user_id") or "default"),
        str(payload.get("session_id") or "api"),
        str(message),
        {"demo_mode": parse_bool(payload.get("demo_mode")), "debug": parse_bool(payload.get("debug") or payload.get("debug_mode")), "model_config": payload.get("model_config") or {}},
    )
    return JSONResponse(result)


@app.get("/trace/{trace_id}")
def trace(trace_id: str):
    record = runtime.get_trace(trace_id)
    if not record:
        return JSONResponse({"message": "trace not found", "trace_id": trace_id}, status_code=404)
    return JSONResponse(record)

@app.get("/status")
def status(): return {"status": "Sovereign"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
