#!/bin/bash

echo "🛑 Stopping Voice Agent System"
echo "============================="

# Kill processes by port
echo "🔥 Killing processes on ports 8001, 10000..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:10000 | xargs kill -9 2>/dev/null || true

# Kill processes by PID if .service_pids exists
if [ -f .service_pids ]; then
    echo "🔥 Killing services by stored PIDs..."
    PIDS=$(cat .service_pids)
    for pid in $PIDS; do
        kill -9 $pid 2>/dev/null || true
    done
    rm .service_pids
fi

# Kill any remaining python processes related to our agent
echo "🔥 Cleaning up agent processes..."
pkill -f "main.py dev" 2>/dev/null || true
pkill -f "app/main.py" 2>/dev/null || true
pkill -f "uvicorn spiritual_voice_agent.main:app" 2>/dev/null || true

sleep 2

echo "✅ All services stopped"