#!/bin/bash

cd /home/LuciusPrime/claire

source venv/bin/activate

echo "Stopping old test instance..."
pkill -f "uvicorn ARE_SERVER_LOCKED:app --port 8020" 2>/dev/null

echo "Starting LOCKED ARE on 8020..."

uvicorn ARE_SERVER_LOCKED:app --host 127.0.0.1 --port 8020
