#!/bin/bash
echo "🚀 Starting Kokoro TTS FastAPI Server..."
cd "$(dirname "$0")"
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload 