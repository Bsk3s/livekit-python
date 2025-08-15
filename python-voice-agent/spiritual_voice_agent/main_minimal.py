import logging
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Railway Voice AI (Minimal)",
    description="Minimal Railway deployment for voice AI token generation",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Health endpoint (standalone, no dependencies)
@app.get("/health")
@app.head("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "railway-voice-ai-complete",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "agent_worker": "running" if os.path.exists("/tmp/agent_running") else "unknown",
    }

# Simple agent status endpoint
@app.get("/agent-status")
async def agent_status():
    """Check if the voice agent worker is running"""
    return {
        "agent_worker_running": os.path.exists("/tmp/agent_running"),
        "livekit_url": os.getenv("LIVEKIT_URL", "not_set")[:50] + "...",
        "openai_key": "set" if os.getenv("OPENAI_API_KEY") else "not_set",
        "deepgram_key": "set" if os.getenv("DEEPGRAM_API_KEY") else "not_set",
    }

@app.get("/")
async def root():
    return {
        "message": "Railway Voice AI with Dashboard",
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "token": "/api/spiritual-token",
            "dashboard": "/api/dashboard/overview",
            "voice_config": "/api/voice/current",
            "docs": "/docs"
        }
    }

# Import and include core functionality
logger.info("🔄 Loading voice AI components...")

try:
    from spiritual_voice_agent.routes.token import router as token_router
    app.include_router(token_router, prefix="/api", tags=["Authentication"])
    logger.info("✅ Token generation loaded")
    token_available = True
except ImportError as e:
    logger.warning(f"⚠️ Token generation unavailable: {e}")
    token_available = False

try:
    from spiritual_voice_agent.routes.voice_config import router as voice_router
    app.include_router(voice_router, tags=["Voice Configuration"])
    logger.info("✅ Voice configuration loaded")
    voice_available = True
except ImportError as e:
    logger.warning(f"⚠️ Voice config unavailable: {e}")
    voice_available = False

# Add essential dashboard routes for real-time connectivity
dashboard_available = False
try:
    from spiritual_voice_agent.routes.dashboard_api import router as dashboard_router
    app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
    logger.info("✅ Dashboard API loaded")
    dashboard_available = True
except ImportError as e:
    logger.warning(f"⚠️ Dashboard unavailable: {e}")

# Add WebSocket for real-time updates
websocket_available = False
try:
    from spiritual_voice_agent.routes.websocket_dashboard import router as ws_router
    app.include_router(ws_router, prefix="/api", tags=["WebSocket"])
    logger.info("✅ WebSocket dashboard loaded")
    websocket_available = True
except ImportError as e:
    logger.warning(f"⚠️ WebSocket unavailable: {e}")

# Add simple agent status for voice agent monitoring  
dispatch_available = False
try:
    from spiritual_voice_agent.routes.simple_dispatch import router as dispatch_router
    app.include_router(dispatch_router, prefix="/api", tags=["Agent Status"])
    logger.info("✅ Agent status loaded")
    dispatch_available = True
except ImportError as e:
    logger.warning(f"⚠️ Agent status unavailable: {e}")

# Summary
components = []
if token_available:
    components.append("token generation")
if voice_available:
    components.append("voice config")
if dashboard_available:
    components.append("dashboard API")
if websocket_available:
    components.append("real-time updates")
if dispatch_available:
    components.append("agent status")

if components:
    logger.info(f"🎉 Railway Voice AI ready with: {', '.join(components)}")
else:
    logger.info("🚀 Railway Voice AI started (basic mode)")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)