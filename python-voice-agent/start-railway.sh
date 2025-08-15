#!/usr/bin/env bash
set -euo pipefail

# 🚀 SIMPLIFIED RAILWAY STARTUP
# Focus on getting the API working first, then agent

echo "🎯 Starting Railway-optimized Voice AI..."

# Railway automatically sets PORT environment variable
API_PORT=${PORT:-10000}
echo "🔧 Using Railway port: $API_PORT"

# Start only the main API server (Railway needs one service on $PORT)
echo "🌐 Starting Railway Voice AI API..."
exec python -m uvicorn spiritual_voice_agent.main_railway:app --host 0.0.0.0 --port $API_PORT --workers 1