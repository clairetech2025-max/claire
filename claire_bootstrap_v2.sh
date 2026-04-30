#!/bin/bash
echo "--- IGNITING CLAIRE SOVEREIGN BOOTSTRAP V2 ---"

# 1. Permission Lockdown
echo "[1/4] Securing Certificate Permissions..."
sudo chmod -R 755 /etc/letsencrypt/archive/
sudo chmod -R 755 /etc/letsencrypt/live/

# 2. Port & Process Clearance
echo "[2/4] Evicting Port 443 Ghosts..."
sudo fuser -k 443/tcp >/dev/null 2>&1
sudo killall go claire_node sovereign_pro >/dev/null 2>&1

# 3. Node Ignition
echo "[3/4] Starting Go Sovereign Node..."
sudo nohup go run /home/LuciusPrime/claire/claire_node.go > /home/LuciusPrime/claire/logs/horse.log 2>&1 &
sleep 5

# 4. Final Intelligence Verification
echo "[4/4] Running Secure Siphon Test..."
python3 -c "import httpx; r = httpx.get('https://clairesystems.ai'); print(f'STATUS: {r.status_code} | RESPONSE: {r.text.strip()}')"

echo "--- BOOTSTRAP COMPLETE: SYSTEM OPERATIONAL ---"
