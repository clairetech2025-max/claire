import http.server
import socketserver

PORT = 4433
HTML = r"""
[PASTE YOUR VERITAS COMMANDER HTML HERE]
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML.encode())

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"VERITAS NODE LIVE ON PORT {PORT}")
    httpd.serve_forever()
