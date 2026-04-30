#!/bin/bash
# CLAIRE DOUBLE PULSE: Market Gulp (10m) -> Legal Research (20m)

OFFSET=0 # This tracks where she is in the 411,000 legal cases

while true; do
  echo "[$(date)] --- PHASE 1: MARKET GULP (10 MIN) ---"
  ~/claire/claire_bootstrap_v2.sh
  sleep 600 
  
  echo "[$(date)] --- PHASE 2: GOING DARK / RESEARCH GULP (20 MIN) ---"
  # 1. Kill the public listener (No more paid egress)
  sudo fuser -k 443/tcp >/dev/null 2>&1
  
  # 2. Siphon 100 Constitutional cases from Harvard (FREE INGRESS)
  echo "Siphoning Legal Cases starting at offset $OFFSET..."
  curl -s "https://datasets-server.huggingface.co/rows?dataset=harvard-lil/cold-cases&config=default&split=train&offset=$OFFSET&length=100" \
  > ~/claire/memory/legal_gulp_$OFFSET.json
  
  # 3. Increment the offset for the next cycle
  OFFSET=$((OFFSET + 100))
  
  echo "[$(date)] --- LEGAL RESEARCH COMPLETE. SLEEPING. ---"
  sleep 1200
done
