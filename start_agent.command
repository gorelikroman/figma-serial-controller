#!/bin/bash
# Serial Controller Agent Launcher
# Double-click to start the agent

cd "$(dirname "$0")/agent"

echo "🎛 Starting Figma Serial Controller Agent..."
echo "Press Ctrl+C to stop"
echo ""

python3 agent.py
