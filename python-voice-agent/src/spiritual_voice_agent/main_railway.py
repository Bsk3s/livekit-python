import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())

# Configure logging for production
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import only essential routes (avoiding heavy monitoring dependencies)
try:
    from spiritual_voice_agent.routes import token, voice_config
    from spiritual_voice_agent.routes.health import router as health_router
except ImportError:
    # Fallback if monitoring services fail
    from spiritual_voice_agent.routes import token, voice_config
    health_router = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🌟 Railway Voice AI starting up (lightweight mode)")
    logger.info(f"🔒 Environment: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"🎭 Available characters: Adina, Raffa")
    logger.info("🚀 Ready for token generation and voice conversations!")
    
    yield
    
    # Shutdown
    logger.info("👋 Railway Voice AI shutting down")

app = FastAPI(
    title="Railway Voice AI API",
    description="Lightweight production API for voice agent token generation",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Railway-friendly CORS
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Health check endpoint for Railway
@app.get("/health")
@app.head("/health")
async def health_check():
    """Health check endpoint for Railway monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "railway-voice-ai",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "mode": "lightweight",
        "components": {
            "api": "ready",
            "token_generation": "available",
            "characters": ["adina", "raffa"],
        },
    }

# Root endpoint
@app.get("/")
@app.head("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Railway Voice AI API",
        "version": "1.0.0",
        "status": "healthy",
        "mode": "lightweight",
        "characters": ["adina", "raffa"],
        "endpoints": {
            "health": "/health",
            "token": "/api/spiritual-token",
            "voice_current": "/api/voice/current",
            "voice_switch": "/api/voice/switch",
            "voice_characters": "/api/voice/characters",
        },
        "docs": "/docs",
    }

# Include lightweight routers
if health_router:
    app.include_router(health_router, tags=["Health"])
app.include_router(token.router, prefix="/api", tags=["Authentication"])
app.include_router(voice_config.router, tags=["Voice Configuration"])

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)