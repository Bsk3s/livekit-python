import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())

# Configure logging for production FIRST
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import routes - using absolute imports as module (excluding broken websocket_audio)
from spiritual_voice_agent.routes import agent_dispatch, cost, health, metrics, token, voice_config, dashboard_api, websocket_dashboard
from spiritual_voice_agent.config.environment import get_config, get_config_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🌟 Spiritual Guidance API starting up")
    
    # Initialize and validate configuration
    config_manager = get_config_manager()
    config = config_manager.get_config()
    
    # Log configuration summary
    logger.info(f"🔗 Environment: {config.environment}")
    logger.info(f"🎭 Available characters: Adina (compassionate), Raffa (wise)")
    logger.info(f"🔒 CORS Origins: {len(config.security.cors_origins)} domains configured")
    logger.info(f"🗄️ Database: {config.database.type} ({'URL configured' if config.database.url else 'SQLite'})")
    
    # Validate configuration and warn about issues
    issues = config_manager.validate_config()
    if issues:
        for issue in issues:
            logger.warning(f"⚠️ Configuration: {issue}")
    else:
        logger.info("✅ Configuration validation passed")

    # 📊 METRICS: Initialize zero-latency metrics service
    from spiritual_voice_agent.services.metrics_service import get_metrics_service

    metrics_service = get_metrics_service()
    logger.info("📊 Zero-latency metrics service initialized")
    
    
    logger.info("🎯 Ready to provide spiritual guidance through voice interaction!")

    yield
    
    # Shutdown
    logger.info("👋 Spiritual Guidance API shutting down")
    


app = FastAPI(
    title="Spiritual Guidance Voice Agent API",
    description="Production API for LiveKit spiritual guidance voice agent with Adina and Raffa characters",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS based on environment using new config system
def get_allowed_origins() -> List[str]:
    """Get CORS origins from configuration manager"""
    config = get_config()
    return config.security.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
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
            "voice_current": "/api/voice/current",
            "voice_switch": "/api/voice/switch",
            "voice_characters": "/api/voice/characters",
            "voice_test": "/api/voice/test/{character}",
        },
        "docs": "/docs",
    }


# Include routers (excluding broken websocket_audio)
app.include_router(health.router, tags=["Health"])
app.include_router(token.router, prefix="/api", tags=["Authentication"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(cost.router, tags=["Cost Analytics"])
app.include_router(voice_config.router, tags=["Voice Configuration"])

# Add agent dispatch router (was missing!)
app.include_router(agent_dispatch.router, prefix="/api", tags=["Agent Dispatch"])

# Add dashboard feature routers
app.include_router(dashboard_api.router, prefix="/api", tags=["Dashboard Data APIs"])
app.include_router(websocket_dashboard.router, prefix="/api", tags=["Real-Time Dashboard WebSocket"])


def main():
    """Main entry point for the FastAPI application"""
    import uvicorn
    
    # Get server configuration
    config = get_config()
    
    uvicorn.run(
        app, 
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level.lower(),
        workers=config.server.workers if config.environment == 'production' else 1
    )


if __name__ == "__main__":
    main()
