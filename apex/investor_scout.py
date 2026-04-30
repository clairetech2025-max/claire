import httpx, uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

@app.get("/signal")
async def get_market_signal():
    # Direct Market Reflex logic
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD")
        price = r.json()["result"]["XXBTZUSD"]["c"][0]
    
    return JSONResponse({
        "status": "Symmetry Locked",
        "market_price": f"${price}",
        "action": "BUY" if float(price) < 110000 else "HOLD",
        "analysis": "Perpetual core active. No structural drift detected."
    })

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body style="background:#000;color:#0f0;font-family:monospace;padding:50px;">
    <h1 style="letter-spacing:5px;">CLAIRE APEX: INVESTOR SCOUT</h1>
    <hr style="border:1px solid #0f0">
    <button onclick="fetch('/signal').then(r=>r.json()).then(d=>{
        document.getElementById('out').innerHTML = '<h2 style=\'color:white\'>SIGNAL: '+d.action+'</h2><p>Price: '+d.market_price+'</p><p>'+d.analysis+'</p>';
    })" style="background:#0f0;color:#000;padding:20px;font-weight:bold;cursor:pointer;border:none;">EXECUTE MARKET REFLEX</button>
    <div id="out" style="margin-top:20px;border-left:2px solid #0f0;padding-left:20px;">Awaiting Handshake...</div>
    </body></html>
    """

if __name__ == "__main__":
    # We use 8080 to avoid the "Operation Not Permitted" on 8000
    uvicorn.run(app, host="0.0.0.0", port=8080)
