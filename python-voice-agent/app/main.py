import sys
import os
# Add the parent directory to Python path for module resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
from app.routes import token

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Spiritual Guidance Voice Agent API",
    description="Production API for LiveKit spiritual guidance voice agent with Adina and Raffa characters",
    version="1.0.0"
)

# Configure CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "http://localhost:19006",  # Expo web
        "https://*.onrender.com",  # Render deployments
        "https://*.expo.dev",  # Expo hosted apps
        "*"  # Allow all for now - restrict in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "spiritual-guidance-api",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Spiritual Guidance Voice Agent API",
        "version": "1.0.0",
        "characters": ["adina", "raffa"],
        "endpoints": {
            "health": "/health",
            "token": "/api/spiritual-token",
            "legacy_token": "/api/createToken"
        },
        "docs": "/docs"
    }

# Include routers
app.include_router(token.router, prefix="/api", tags=["Authentication"])

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("🌟 Spiritual Guidance API starting up")
    logger.info(f"🔗 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"🎭 Available characters: Adina (compassionate), Raffa (wise)")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Spiritual Guidance API shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    ) 