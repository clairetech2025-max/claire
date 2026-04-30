#!/bin/bash
# --- CLAIRE SOVEREIGN BOOTSTRAP V1.0 ---
echo "--- [1/5] PURGING STALE STATES ---"
sudo fuser -k 8000/tcp 8001/tcp 8081/tcp 2>/dev/null
sleep 1

echo "--- [2/5] INJECTING SOVEREIGN KEYS ---"
if [ -f /home/LuciusPrime/claire/claire_keys.env ]; then
    set -a
    source /home/LuciusPrime/claire/claire_keys.env
    set +a
    echo "Keys armed: Constitutional, ElevenLabs, Kraken."
else
    echo "ERROR: Key file not found!"
    exit 1
fi

echo "--- [3/5] RESTARTING CORE SERVICES ---"
cd /home/LuciusPrime/claire
source venv/bin/activate

# Start ARE (Memory Spine)
nohup uvicorn ARE_SERVER:app --host 127.0.0.1 --port 8001 > are.log 2>&1 &
echo "ARE (8001) Online."

# Start LLM (Decision Layer)
nohup ~/claire/llama.cpp/build/bin/llama-server -m ~/claire/models/qwen2.5-7b-instruct-q4_k_m.gguf --host 0.0.0.0 --port 8081 --temp 0.1 --ctx-size 4096 > llama.log 2>&1 &
echo "LLM (8081) Online."

# Start GUI (The Face)
nohup uvicorn claire_gui:app --host 0.0.0.0 --port 8000 > gui.log 2>&1 &
echo "GUI (8000) Online."

echo "--- [4/5] FINALIZING SCHOOLING (INGEST) ---"
python3 - <<INGEST
import requests, os
are_url = "http://127.0.0.1:8001/ingest"
knowledge_dir = "/home/LuciusPrime/claire/knowledge"
if os.path.exists(knowledge_dir):
    for f in os.listdir(knowledge_dir):
        if f.endswith(".txt"):
            print(f"Feeding: {f}")
            with open(os.path.join(knowledge_dir, f), 'r') as file:
                requests.post(are_url, json={"id": f, "text": file.read().strip()})
INGEST

echo "--- [5/5] SYSTEM HEALTH CHECK ---"
netstat -tulpn | grep -E '8000|8001|8081'
echo "---------------------------------------"
echo "CLAIRE IS SOVEREIGN. BOOT COMPLETE."
echo "URL: http://$(curl -s ifconfig.me):8000"
echo "---------------------------------------"
