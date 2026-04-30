from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI(title="CLAIRE HUD v3.0")

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_hud():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CLAIRE HUD</title>
        <style>
            body { background: #0d1117; color: #39ff14; font-family: monospace; padding: 20px; }
            #visualizer { width: 100%; height: 150px; border: 1px solid #238636; background: black; }
            .terminal { background: black; padding: 15px; height: 300px; border: 1px solid #30363d; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>CLAIRE <span style="color: #d4af37;">VOICE_CORE</span></h1>
        <canvas id="visualizer"></canvas>
        <div class="terminal">[*] System Online. Awaiting JSON Gravel...</div>
        <script>
            const canvas = document.getElementById('visualizer');
            const ctx = canvas.getContext('2d');
            canvas.width = canvas.offsetWidth;
            canvas.height = 150;
            function draw() {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.beginPath();
                ctx.strokeStyle = '#39ff14';
                for(let i=0; i<canvas.width; i+=5) {
                    ctx.lineTo(i, 75 + Math.random() * 40 - 20);
                }
                ctx.stroke();
                requestAnimationFrame(draw);
            }
            draw();
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
