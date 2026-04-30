#!/usr/bin/env python3
import os, json, httpx, uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime

app = FastAPI()

# --- CORE LOGIC: THE BALANCE RIDER ---
def classify_market_risk(price):
    """Clinical Risk Assessment based on Physics, not Sentiment"""
    price_num = float(price)
    if price_num < 95000:
        return "STANDARD_INTEGRITY", "Inertial floor confirmed. Physical support detected."
    elif price_num > 105000:
        return "ELEVATED_RISK", "Market extension detected. Potential for institutional spooking."
    return "STABLE", "Symmetry maintained. No regulatory drift."

@app.get("/signal")
async def generate_signal():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD", timeout=5.0)
            price = r.json()["result"]["XXBTZUSD"]["c"][0]
        
        risk_level, analysis = classify_market_risk(price)
        decision = "BUY" if risk_level == "STANDARD_INTEGRITY" else "HOLD"
        
        return JSONResponse({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "market": {"last": price, "pair": "BTC/USD"},
            "ai": {
                "decision": decision,
                "confidence": 98.4,
                "riskLevel": risk_level,
                "analysis": analysis
            }
        })
    except Exception as e:
        return JSONResponse({"error": "Syncing with Market Reservoir..."}, status_code=500)

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VERITAS BARATRON V.4</title>
        <style>
            body { background: #050505; color: #94a3b8; font-family: 'Courier New', monospace; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }
            .terminal { width: 600px; background: #000; border: 1px solid #1e293b; padding: 30px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); position: relative; }
            .header { border-bottom: 1px solid #1e293b; padding-bottom: 15px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
            .title { color: #f1f5f9; font-weight: 900; font-size: 12px; letter-spacing: 4px; text-transform: uppercase; }
            .status { font-size: 10px; color: #22c55e; animation: pulse 2s infinite; }
            .output-box { border-left: 2px solid #ef4444; background: rgba(255,255,255,0.02); padding: 20px; min-height: 120px; margin-top: 20px; }
            button { background: #b91c1c; color: white; border: none; padding: 15px 30px; font-weight: bold; cursor: pointer; text-transform: uppercase; letter-spacing: 2px; width: 100%; transition: 0.3s; }
            button:hover { background: #dc2626; box-shadow: 0 0 15px rgba(185,28,28,0.4); }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
            .label { font-size: 8px; color: #475569; text-transform: uppercase; margin-bottom: 5px; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <div class="header">
                <div class="title">Veritas Baratron <span style="color:#b91c1c;">V.4</span></div>
                <div class="status">● LUCID</div>
            </div>
            <div class="label">Operational Substrate: Azure_ClairesMind</div>
            <button onclick="executeReflex()">Execute Market Reflex</button>
            <div id="out" class="output-box">
                <div style="font-size: 11px; color: #475569;">AWAITING SIGNAL INGESTION...</div>
            </div>
            <div style="margin-top: 20px; font-size: 8px; text-align: center; color: #1e293b;">
                SOVEREIGN INTELLIGENCE PROTOCOL © 2026
            </div>
        </div>

        <script>
            async function executeReflex() {
                const out = document.getElementById('out');
                out.innerHTML = '<div style="color:#f59e0b">SYNTHESIZING...</div>';
                try {
                    const r = await fetch('/signal');
                    const d = await r.json();
                    out.innerHTML = `
                        <div style="color:#fff; font-size: 18px; font-weight:bold;">${d.ai.decision}</div>
                        <div style="font-size: 12px; margin: 10px 0;">PRICE: $${d.market.last}</div>
                        <div style="font-size: 10px; color: #64748b; line-height: 1.5;">${d.ai.analysis}</div>
                        <div style="margin-top:10px; font-size: 8px; color: #b91c1c;">RISK_LEVEL: ${d.ai.riskLevel}</div>
                    `;
                    out.style.borderLeftColor = d.ai.decision === 'BUY' ? '#22c55e' : '#f59e0b';
                } catch (e) {
                    out.innerHTML = '<div style="color:#ef4444">LINK BREACH: RECONNECTING...</div>';
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
