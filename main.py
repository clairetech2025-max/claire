from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import requests
import subprocess
import os
import html

app = FastAPI()

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
</style>
</head>
<body>
<div class="topbar"><div><strong>CLAIRE</strong> | Sovereign Runtime</div><div>Operator: LuciusPrime</div></div>
<div class="shell">
    <div class="column"><div class="panel"><h3>Controls</h3><button onclick="fetch('/status')">Status Check</button></div></div>
    <div class="column">
        <div class="panel"><h1>Command Center</h1><form action="/ask"><input name="q" placeholder="Speak to Claire..."><button type="submit">Send</button></form></div>
        <div class="panel" id="response">Awaiting Query...</div>
    </div>
    <div class="column"><div class="panel"><h3>Monitors</h3><div id="m">ARE: ONLINE<br>LLM: ONLINE</div></div></div>
</div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML

@app.get("/ask", response_class=HTMLResponse)
def ask(q: str = Query(...)):
    try:
        r = requests.post(LLM_URL, json={"messages": [{"role": "system", "content": "You are Claire."}, {"role": "user", "content": q}], "temperature": 0.1}, timeout=15)
        reply = r.json()["choices"][0]["message"]["content"]
    except: reply = "LLM Connection Error."
    return f"<html><body style='background:#02040a;color:#dff9ff;padding:40px;'><h2>CLAIRE</h2><p>{reply}</p><a href='/' style='color:#13d8ff;'>Back</a></body></html>"

@app.get("/status")
def status(): return {"status": "Sovereign"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
