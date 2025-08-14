#!/bin/bash

# 🚀 BULLETPROOF Simple Startup
# No fancy checks, no complex imports - just works

echo "🚀 Simple Voice Agent Startup"
echo "============================="

# Kill any existing processes on our ports
echo "🔥 Cleaning up existing processes..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:10000 | xargs kill -9 2>/dev/null || true
sleep 2

# Create logs directory
mkdir -p logs

echo "🎤 Starting Kokoro TTS Server..."
cd kokoro_fastapi_server
source kokoro_env/bin/activate

# Install Kokoro if missing (simple check)
python -c "import kokoro" 2>/dev/null || pip install -q git+https://github.com/hexgrad/kokoro.git

# Start Kokoro server in background
python app/main.py > ../logs/kokoro.log 2>&1 &
KOKORO_PID=$!
cd ..

echo "   ✅ Kokoro TTS Server started (PID: $KOKORO_PID)"

# Wait a moment for Kokoro to initialize
sleep 3

echo "🌐 Starting Main API Server..."
source venv/bin/activate

# Install the package in development mode (fixes import issues permanently)
pip install -e . -q

# Start API server in background
uvicorn spiritual_voice_agent.main:app --host 0.0.0.0 --port 10000 > logs/api.log 2>&1 &
API_PID=$!

echo "   ✅ Main API Server started (PID: $API_PID)"

# Wait a moment for API to initialize
sleep 3

echo ""
echo "🎯 SERVICES RUNNING:"
echo "  🎤 Kokoro TTS:  http://localhost:8001"
echo "  🌐 Main API:    http://localhost:10000"
echo "  📖 API Docs:    http://localhost:10000/docs"
echo ""
echo "📝 LOGS:"
echo "  tail -f logs/kokoro.log"
echo "  tail -f logs/api.log"
echo ""
echo "🛑 To stop: kill $KOKORO_PID $API_PID"
echo ""
echo "🎉 Ready to test voice switching!"

# Store all PIDs for easy cleanup
echo "$KOKORO_PID $API_PID $AGENT_PID" > .service_pids