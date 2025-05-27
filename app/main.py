from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.token import router as token_router

app = FastAPI(title="Heavenly Hub Voice Agent API")

# Configure CORS for Expo client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Expo app's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(token_router, prefix="/api", tags=["token"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Heavenly Hub Voice Agent API", "status": "running"}

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "voice-agent-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 