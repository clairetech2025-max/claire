#!/bin/bash
echo "--- CLAIRE SYSTEMS: TOTAL RECOVERY INITIALIZED ---"

# 1. KILL EVERYTHING (The "Scorched Earth" phase)
sudo fuser -k 80/tcp 8000/tcp 8001/tcp 8081/tcp 7070/tcp
sudo pkill -9 python
sudo pkill -9 uvicorn
sudo pkill -9 llama-server

# 2. CLEAR SYSTEM MEMORY CACHE
sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches

# 3. SET PERMISSIONS
sudo chown -R LuciusPrime:LuciusPrime /home/LuciusPrime/claire

# 4. START CORE 1: THE GUI (Port 80 for clairesystems.ai)
source /home/LuciusPrime/claire/venv/bin/activate
nohup python3 -m uvicorn server:app --host 0.0.0.0 --port 80 --workers 1 > /home/LuciusPrime/claire/gui.log 2>&1 &
echo "[+] GUI Node launched on Port 80"

# 5. START CORE 2: THE LLM (Port 8081)
nohup /home/LuciusPrime/claire/llama.cpp/build/bin/llama-server \
  -m /home/LuciusPrime/claire/models/qwen2.5-7b-instruct-q4_k_m.gguf \
  --host 0.0.0.0 --port 8081 --ctx-size 4096 --threads 4 > /home/LuciusPrime/claire/llm.log 2>&1 &
echo "[+] LLM Decision Layer launched on Port 8081"

# 6. START CORE 3: THE ARE (Port 8001)
# Assuming your ARE script is named 'are_server.py'
nohup python3 -m uvicorn are_server:app --host 0.0.0.0 --port 8001 > /home/LuciusPrime/claire/are.log 2>&1 &
echo "[+] ARE Memory Spine launched on Port 8001"

echo "--- SYSTEM STANDING BY AT http://clairesystems.ai ---"
