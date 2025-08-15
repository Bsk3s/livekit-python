#!/bin/bash

# 🚀 PRODUCTION VOICE AGENT STARTUP (Railway Optimized)
# Handles Railway's single-port constraint and timeout limits

echo "🎯 Starting Production Voice Agent System..."

# Set Railway port from environment (Railway sets PORT automatically)
export API_PORT=${PORT:-10000}
export TTS_PORT=$((API_PORT + 1))

echo "🔧 Using ports: API=$API_PORT, TTS=$TTS_PORT"

# Start Kokoro TTS server in background (lightweight startup)
echo "🎤 Starting Kokoro TTS server..."
cd kokoro_fastapi_server
python -m uvicorn app.main:app --host 0.0.0.0 --port $TTS_PORT &
TTS_PID=$!
cd ..

# Wait for TTS to be ready (with timeout)
echo "⏱️ Waiting for TTS server..."
for i in {1..30}; do
    if curl -s http://localhost:$TTS_PORT/health >/dev/null 2>&1; then
        echo "✅ TTS server ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ TTS server timeout - continuing anyway"
    fi
    sleep 1
done

# Start main API server (this handles the Railway PORT)
echo "🌐 Starting main API server on port $API_PORT..."
cd spiritual_voice_agent
python -m uvicorn main:app --host 0.0.0.0 --port $API_PORT &
API_PID=$!
cd ..

# Wait for API to be ready
echo "⏱️ Waiting for API server..."
for i in {1..20}; do
    if curl -s http://localhost:$API_PORT/health >/dev/null 2>&1; then
        echo "✅ API server ready"
        break
    fi
    sleep 1
done

# Start agent worker with increased timeout and better error handling
echo "🤖 Starting LiveKit agent worker (production mode)..."
source venv/bin/activate 2>/dev/null || echo "No venv found, using system Python"
cd simple_working_agent

# Set production environment variables for agent
export LIVEKIT_WORKER_TIMEOUT=300  # 5 minutes
export AGENT_STARTUP_TIMEOUT=180   # 3 minutes
export KOKORO_INIT_TIMEOUT=120     # 2 minutes for model loading

# Start agent with production settings (using optimized agent)
echo "🚀 Agent worker starting with production optimizations..."
python main_production.py dev &
AGENT_PID=$!

cd ..

echo ""
echo "🎯 PRODUCTION SYSTEM STATUS:"
echo "  🎤 TTS Server:     PID $TTS_PID (port $TTS_PORT)"
echo "  🌐 API Server:     PID $API_PID (port $API_PORT) ⭐ Main"
echo "  🤖 Agent Worker:   PID $AGENT_PID"
echo ""
echo "🌍 Production URL: https://livekit-python-agent.up.railway.app"
echo "📊 Health Check:   https://livekit-python-agent.up.railway.app/health"
echo "📚 API Docs:       https://livekit-python-agent.up.railway.app/docs"
echo ""
echo "✅ Voice AI is live and ready for conversations!"

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down services..."
    kill $TTS_PID $API_PID $AGENT_PID 2>/dev/null || true
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Wait for API server (main process for Railway)
wait $API_PID