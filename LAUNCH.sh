#!/bin/bash
set -euo pipefail

echo "=================================="
echo "CLAIRE SYSTEMD LAUNCH"
echo "=================================="

cd /home/LuciusPrime/claire || exit 1

echo "[1] Restarting locked Claire services..."
sudo systemctl restart claire-go.service claire-are.service claire-ingest.service claire-gui.service

echo "[2] Waiting for services..."
sleep 5

echo "[3] Service state..."
systemctl --no-pager --plain --type=service | grep -E 'claire-(go|are|ingest|gui)' || true

echo
echo "[4] Port check..."
ss -tulnp | grep -E ':(8000|8002|8080|8081)\b' || true

echo
echo "[5] Health check..."
echo "GO:"
curl -s http://127.0.0.1:8080/health || echo "GO not responding"
echo
echo "ARE:"
curl -s http://127.0.0.1:8002/health || echo "ARE not responding"
echo
echo "INGEST:"
curl -s http://127.0.0.1:8081/health || echo "INGEST not responding"
echo
echo "GUI:"
curl -s http://127.0.0.1:8000/status || echo "GUI not responding"
echo

echo "=================================="
echo "CLAIRE LIVE"
echo "Open: http://$(curl -s ifconfig.me):8000"
echo "=================================="
