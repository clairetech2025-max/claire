from fastapi import FastAPI, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse
import os
import html
import time

app = FastAPI()

# Windows-Friendly HTML for clairesystems.ai
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>CLAIRE | WINDOWS NODE</title>
<style>
:root {
    --bg: #02040a;
    --panel: rgba(4, 16, 30, 0.95);
    --line-cyan: #13d8ff;
    --line-red: #ef5350;
    --text: #d9f6ff;
    --border: rgba(19, 216, 255, 0.25);
}

* { box-sizing: border-box; margin: 0; padding: 0; font-family: "Segoe UI", sans-serif; }
body { 
    background: var(--bg); color: var(--text); 
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
}

.topbar {
    padding: 12px 20px; border-bottom: 2px solid var(--line-red);
    background: #051423; display: flex; justify-content: space-between; align-items: center;
}

.shell { flex: 1; display: flex; flex-direction: column; padding: 10px; gap: 10px; overflow-y: auto; }

.panel {
    background: var(--panel); border: 1px solid var(--border);
    padding: 15px; border-radius: 4px;
}

.panel-title { font-size: 11px; color: var(--line-cyan); text-transform: uppercase; margin-bottom: 10px; font-weight: 700; letter-spacing: 1.5px; }

.viz-box { height: 80px; border: 1px solid var(--line-red); background: #000; border-radius: 4px; overflow: hidden; }

.response-screen {
    min-height: 200px; padding: 15px; background: rgba(0,0,0,0.4);
    border: 1px solid var(--border); border-left: 4px solid var(--line-red);
    font-size: 15px; line-height: 1.6; color: #acc1d9;
}

.button-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

button {
    padding: 18px; border: 1px solid var(--line-red); background: #092b42;
    color: #fff; font-weight: bold; text-transform: uppercase; cursor: pointer; font-size: 12px;
}

.footer { 
    padding: 20px; background: var(--panel); border-top: 1px solid var(--border);
    display: flex; gap: 10px; padding-bottom: 40px;
}

input {
    flex: 1; background: #000; border: 1px solid var(--border); 
    color: #fff; padding: 16px; border-radius: 4px; font-size: 16px; outline: none;
}

@media (min-width: 1024px) {
    .shell { display: grid; grid-template-columns: 300px 1fr 300px; }
}
</style>
</head>
<body>
<div class="topbar">
    <div style="font-weight:700; font-size:22px; letter-spacing:2px;">CLAIRE <span style="color:var(--line-red)">SYSTEMS</span></div>
    <div style="font-size:10px; color:var(--line-cyan)">HOST: WINDOWS_OS</div>
</div>

<div class="shell">
    <div class="panel">
        <div class="panel-title">Operations</div>
        <div class="button-grid">
            <button onclick="run('INTEL')">Intel</button>
            <button onclick="run('ATTEST')">Attest</button>
            <button onclick="run('STRIKE')" style="border-color:var(--line-red)">Strike</button>
            <button onclick="run('PURGE')" style="border-color:var(--line-red)">Purge</button>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; gap:10px;">
        <div class="viz-box">
            <svg viewBox="0 0 400 80" preserveAspectRatio="none" style="width:100%; height:100%;">
                <path id="wave" d="" fill="none" stroke="var(--line-red)" stroke-width="3" />
            </svg>
        </div>
        <div class="response-screen" id="display">WINDOWS NODE READY.</div>
    </div>

    <div class="panel">
        <div class="panel-title">Event Log</div>
        <div id="logs" style="font-size:11px; color:var(--line-cyan); font-family:monospace;"></div>
    </div>
</div>

<div class="footer">
    <input type="text" id="inp" placeholder="Operator query..." autocomplete="off">
    <button onclick="run('SEND')" style="background:var(--line-red); border:none; color:#fff; padding:0 25px;">GO</button>
</div>

<script>
const v = document.getElementById('wave');
function animate() {
    let d = "M 0 40 ";
    for(let i=0; i<=400; i+=10) d += `L ${i} ${40 + Math.random()*25*Math.sin(i*0.05 + Date.now()*0.01)} `;
    v.setAttribute('d', d);
    requestAnimationFrame(animate);
}
animate();

async function run(t) {
    const q = document.getElementById('inp').value;
    const fd = new FormData();
    fd.append('action_type', t); fd.append('query', q);
    const r = await fetch('/action', { method: 'POST', body: fd });
    const data = await r.json();
    document.getElementById('display').innerHTML = `<span style="color:var(--line-red)">> ${t}_LOG:</span><br>${data.reply}`;
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML

@app.post("/action")
async def handle_action(action_type: str = Form(...), query: str = Form(None)):
    return {"reply": "Command acknowledged on Windows Production Node."}
