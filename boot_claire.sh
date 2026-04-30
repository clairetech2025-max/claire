#!/bin/bash
echo "--- INITIALIZING CLAIRE OS V6.0 ---"
echo "[1/4] Clearing stale ports..."
for port in 8000 8001 8081; do
    sudo fuser -k $port/tcp 2>/dev/null
done
sleep 2
echo "[2/4] Arming local firewall..."
sudo ufw allow 8000/tcp > /dev/null 2>&1
echo "[3/4] Starting CLAIRE Main UI on 8000..."
cd ~/claire
source venv/bin/activate
nohup venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > claire.log 2>&1 &
PUBLIC_IP=$(curl -s ifconfig.me)
echo "--- BOOT SEQUENCE COMPLETE ---"
echo "EXTERNAL ADDR: http://$PUBLIC_IP:8000"
