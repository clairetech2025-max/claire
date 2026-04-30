#!/bin/bash

# --- SOVEREIGN STACK BOOTSTRAP ---
# Architecture: 8000(B), 8001(A), 8081(T)
# ---------------------------------

PROJECT_ROOT="/home/LuciusPrime/claire"
VENV_PATH="$PROJECT_ROOT/venv/bin/activate"
KEYS_FILE="$PROJECT_ROOT/claire_keys.env"

echo "[BOOT] Starting Sovereign Stack Initialization..."

# 1. Environment Guard
if [ ! -f "$KEYS_FILE" ]; then
    echo "[ERROR] Keys file missing at $KEYS_FILE. Aborting."
    exit 1
fi

source "$VENV_PATH"
set -a
source "$KEYS_FILE"
set +a

# 2. Hard Port Eviction (Clear the Lanes)
echo "[BOOT] Clearing zombie processes on 8000, 8001, 8081..."
sudo fuser -k 8000/tcp 8001/tcp 8081/tcp 2>/dev/null
sleep 2

# 3. Sequential Plane Launch
echo "[BOOT] Launching Truth Plane (8081)..."
nohup python3 $PROJECT_ROOT/ARE_SERVER.py --port 8081 > $PROJECT_ROOT/data/are.log 2>&1 &

echo "[BOOT] Launching Authority Plane (8001)..."
nohup python3 $PROJECT_ROOT/SENTINEL_SERVER.py --port 8001 > $PROJECT_ROOT/data/sentinel.log 2>&1 &

echo "[BOOT] Launching Behavior Plane (8000)..."
nohup python3 $PROJECT_ROOT/CLAIRE_SERVER.py --port 8000 > $PROJECT_ROOT/data/claire.log 2>&1 &

sleep 5

# 4. Automatic Memory Ingestion
echo "[BOOT] Feeding 140 chunks into the Truth Spine at 8081..."
# This is the critical bridge
python3 $PROJECT_ROOT/claire_are_loader.py

# 5. Final Handshake
echo "[BOOT] Verifying Integrity..."
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)

if [ "$HEALTH_CHECK" == "200" ]; then
    echo "------------------------------------------------"
    echo "SUCCESS: SOVEREIGN STACK IS ONLINE AND GROUNDED."
    echo "Behavior: 8000 | Authority: 8001 | Truth: 8081"
    echo "------------------------------------------------"
else
    echo "[WARNING] Stack is up but 8000 failed health check. Check logs."
fi
