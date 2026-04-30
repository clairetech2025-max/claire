import http.server
import socketserver

PORT = 4455
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NIGHTWATCH | ALPHA-01</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        body { background-color: #000; color: #fff; font-family: 'JetBrains Mono', monospace; }
        .alpha-card { background: #050505; border: 1px solid #111; border-top: 4px solid #fff; }
        .status-pulse { height: 10px; width: 10px; background-color: #fff; border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
    </style>
</head>
<body class="p-8">
    <div class="mb-6 flex justify-between items-center border-b border-white/10 pb-4">
        <h1 class="text-4xl font-black tracking-tighter italic"><span class="status-pulse mr-4"></span>NIGHTWATCH</h1>
        <div id="clock" class="text-xl font-bold opacity-50">00:00:00</div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
        <div class="alpha-card p-6">
            <div class="text-[10px] opacity-40 uppercase tracking-[.3em] font-bold">BTC.Index</div>
            <div id="btc-price" class="text-4xl font-black mt-2">$ --,---</div>
        </div>
        <div class="alpha-card p-6">
            <div class="text-[10px] opacity-40 uppercase tracking-[.3em] font-bold">Persistence</div>
            <div id="net-status" class="text-4xl font-black mt-2">168H_ARMED</div>
        </div>
        <div class="alpha-card p-6 text-white/40">
            <div class="text-[10px] opacity-40 uppercase tracking-[.3em] font-bold">Operator</div>
            <div class="text-4xl font-black mt-2">LUCIUS_PRIME</div>
        </div>
    </div>
    <div class="alpha-card p-2 mb-8"><div id="chart" style="height: 400px; width: 100%;"></div></div>
    <div id="logs" class="bg-[#050505] p-4 text-[11px] h-32 overflow-y-auto border border-white/5 opacity-50 font-mono">
        [SYS] NIGHTWATCH NODE INITIALIZED...
    </div>
    <script>
        async function fetchPrice() {
            try {
                const res = await fetch('https://api.kraken.com/0/public/Ticker?pair=XBTUSDC');
                const data = await res.json();
                document.getElementById('btc-price').innerText = '$' + parseFloat(data.result.XBTUSDC.c[0]).toLocaleString();
            } catch (e) { }
        }
        setInterval(fetchPrice, 5000);
        setInterval(() => { document.getElementById('clock').innerText = new Date().toLocaleTimeString(); }, 1000);
        const chart = LightweightCharts.createChart(document.getElementById('chart'), { layout: { background: { color: 'transparent' }, textColor: '#fff' }, grid: { vertLines: { color: '#111' }, horzLines: { color: '#111' } } });
        const series = chart.addCandlestickSeries({ upColor: '#fff', downColor: '#333' });
        series.setData(Array.from({length: 100}, (_, i) => ({ time: (Math.floor(Date.now()/1000) - (100 - i) * 60), open: 64000, high: 64100, low: 63900, close: 64050 })));
        fetchPrice();
    </script>
</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html"); self.end_headers(); self.wfile.write(HTML.encode())

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
