#!/bin/bash
# CLAIRE SOVEREIGN PULSE: 10m RUN / 20m DARK
# Strategy: Protect the bank while maintaining high-confidence signals.

while true; do
  echo "[$(date)] --- INITIATING 10-MINUTE OPERATIONAL WINDOW ---"
  
  # 1. Clear ghosts and reset certificates
  sudo fuser -k 443/tcp >/dev/null 2>&1
  sudo chmod -R 755 /etc/letsencrypt/live/
  
  # 2. Ignite the Secure Ingest Node (Go)
  sudo nohup go run /home/LuciusPrime/claire/claire_node.go > /home/LuciusPrime/claire/logs/horse.log 2>&1 &
  
  # 3. Verify the loop is live
  sleep 5
  python3 -c "import httpx; r = httpx.get('https://clairesystems.ai'); print(f'GATEWAY STATUS: {r.status_code}')"
  
  echo "[$(date)] --- WINDOW OPEN: SIPHONING GCP DATA ---"
  sleep 600 # 10 Minutes of active ingestion
  
  echo "[$(date)] --- WINDOW CLOSING: ENTERING 20-MINUTE STEALTH ---"
  # Hard kill to stop all data transfer and egress costs
  sudo fuser -k 443/tcp >/dev/null 2>&1
  sudo killall go claire_node >/dev/null 2>&1
  
  echo "[$(date)] --- GOING DARK TO SAVE COSTS. NEXT WAKEUP IN 20M. ---"
  sleep 1200 # 20 Minutes of absolute silence
done
