#!/bin/bash

# 🚀 RELIABLE VOICE AGENT SYSTEM STARTUP
# Ensures all 3 servers start properly for consistent agent spawning

echo "🎯 Starting Complete Voice Agent System..."

# Stop any existing processes
echo "🔥 Cleaning up existing processes..."
./stop.sh 2>/dev/null || true
sleep 3

# Start backend servers (Kokoro TTS + API)
echo "🎤 Starting backend servers..."
./start-simple.sh

# Wait for servers to be stable
echo "⏱️  Waiting for servers to stabilize..."
sleep 8

# Verify servers are healthy
echo "🔍 Verifying server health..."
if ! curl -s http://localhost:8001/health >/dev/null; then
    echo "❌ Kokoro TTS server failed to start"
    exit 1
fi

if ! curl -s http://localhost:10000/health >/dev/null; then
    echo "❌ API server failed to start"
    exit 1
fi

echo "✅ Backend servers are healthy"

# Start agent worker with environment variables
echo "🤖 Starting LiveKit agent worker..."
echo "📝 Loading environment variables..."
source .env
source venv/bin/activate
cd simple_working_agent

echo "🚀 Agent worker starting with proper credentials..."
python main.py dev &
AGENT_PID=$!

cd ..

echo ""
echo "🎯 COMPLETE SYSTEM RUNNING:"
echo "  🎤 Kokoro TTS:  http://localhost:8001"
echo "  🌐 Main API:    http://localhost:10000" 
echo "  🤖 Agent Worker: PID $AGENT_PID (with LiveKit credentials)"
echo ""
echo "🧪 Test agent dispatch:"
echo "  curl -X POST http://localhost:10000/api/dispatch-agent \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"room_name\":\"test\",\"character\":\"adina\"}'"
echo ""
echo "✅ Agents can now spawn consistently with voice!"
echo "🛑 Press Ctrl+C to stop all services"

# Monitor the agent process
wait $AGENT_PID