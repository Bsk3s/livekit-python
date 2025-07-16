import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())

# Configure logging for production FIRST
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import routes - no more sys.path hacks needed!
from spiritual_voice_agent.routes import cost, metrics, token, websocket_audio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🌟 Spiritual Guidance API starting up")
    logger.info(f"🔗 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"🎭 Available characters: Adina (compassionate), Raffa (wise)")

    # 📊 METRICS: Initialize zero-latency metrics service
    from spiritual_voice_agent.services.metrics_service import get_metrics_service

    metrics_service = get_metrics_service()
    logger.info("📊 Zero-latency metrics service initialized")

    # 🚀 PERFORMANCE: Preload Kokoro model at startup (eliminate 12s per-request loading)
    logger.info("🚀 Preloading Kokoro TTS model for instant responses...")
    try:
        from spiritual_voice_agent.services.tts.implementations.kokoro.kokoro import KokoroModelSingleton
        
        kokoro_singleton = KokoroModelSingleton()
        kokoro_singleton.initialize()
        logger.info("✅ Kokoro model preloaded successfully - TTS requests will be ~100ms instead of 12s!")
    except Exception as e:
        logger.error(f"❌ Failed to preload Kokoro model: {e}")
        logger.warning("⚠️ TTS will fall back to per-request loading (slower performance)")

    yield
    # Shutdown
    logger.info("👋 Spiritual Guidance API shutting down")


app = FastAPI(
    title="Spiritual Guidance Voice Agent API",
    description="Production API for LiveKit spiritual guidance voice agent with Adina and Raffa characters",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "http://localhost:19006",  # Expo web
        "https://*.up.railway.app",  # Railway deployments
        "https://*.expo.dev",  # Expo hosted apps
        "*",  # Allow all for now - restrict in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


# Health check endpoint for Railway - supports both GET and HEAD
@app.get("/health")
@app.head("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "spiritual-guidance-api",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "components": {
            "websocket": "available",
            "llm": "gpt-4o-mini",
            "stt": "deepgram",
            "tts": "openai",
            "characters": ["adina", "raffa"],
        },
    }


# Root endpoint - supports both GET and HEAD
@app.get("/")
@app.head("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Spiritual Guidance Voice Agent API",
        "version": "1.0.0",
        "status": "healthy",
        "characters": ["adina", "raffa"],
        "endpoints": {
            "health": "/health",
            "websocket": "/ws/audio",
            "token": "/api/spiritual-token",
            "legacy_token": "/api/createToken",
            "metrics": "/metrics",
            "cost": "/cost",
        },
        "docs": "/docs",
    }


# Include routers
app.include_router(token.router, prefix="/api", tags=["Authentication"])
app.include_router(websocket_audio.router, tags=["WebSocket Audio"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(cost.router, tags=["Cost Analytics"])


def main():
    """Main entry point for the FastAPI application"""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="info")


if __name__ == "__main__":
    main()
