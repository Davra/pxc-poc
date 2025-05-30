#!/bin/sh

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting installation script..."
./install.sh

echo "Running setup script..."
python -u ./davra_setup.py

echo "Starting mosquitto in background..."
mosquitto -v &

echo "Starting Davra agent..."
exec python ./davra_agent.py
