#!/bin/bash
# CLAIRE V6.0 Virtual Environment Configuration

echo "--- INITIALIZING CLAIRE VIRTUAL ENVIRONMENT ---"

# 1. Install system-level venv dependency if missing
if ! dpkg -l | grep -q python3-venv; then
    echo "[1/3] Installing python3-venv..."
    sudo apt update && sudo apt install -y python3-venv
else
    echo "[1/3] python3-venv already present."
fi

# 2. Create the virtual environment
echo "[2/3] Creating venv in ~/claire/venv..."
cd ~/claire
python3 -m venv venv

# 3. Provision the environment with CLAIRE dependencies
echo "[3/3] Installing FastAPI, Uvicorn, and Requests..."
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn requests

echo "--- SETUP COMPLETE ---"
echo "To manually enter the environment, run: source venv/bin/activate"
echo "You can now execute boot_claire.sh to bring the system online."
