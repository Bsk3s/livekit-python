#!/usr/bin/env python3
"""
Simple Agent Status API - Railway Compatible
"""
import logging
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from spiritual_voice_agent.services.auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

class AgentStatusResponse(BaseModel):
    agent_worker_running: bool
    livekit_configured: bool
    message: str

@router.get("/agent-status", response_model=AgentStatusResponse)
async def get_agent_status(_: bool = Depends(verify_api_key)):
    """Check if the voice agent worker is configured and ready"""
    
    # Check if environment is properly configured
    livekit_url = os.getenv("LIVEKIT_URL")
    livekit_key = os.getenv("LIVEKIT_API_KEY") 
    livekit_secret = os.getenv("LIVEKIT_API_SECRET")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    livekit_configured = bool(livekit_url and livekit_key and livekit_secret and openai_key)
    
    # Check if agent worker process indicator exists
    agent_running = os.path.exists("/tmp/agent_running")
    
    if livekit_configured and agent_running:
        message = "Voice agent worker is running and ready for conversations"
    elif livekit_configured:
        message = "Voice agent configured but worker process not detected"
    else:
        message = "Voice agent not properly configured"
    
    logger.info(f"Agent status check: configured={livekit_configured}, running={agent_running}")
    
    return AgentStatusResponse(
        agent_worker_running=agent_running,
        livekit_configured=livekit_configured,
        message=message
    )

@router.post("/test-agent")
async def test_agent_connection(_: bool = Depends(verify_api_key)):
    """Test agent configuration without actually dispatching"""
    
    # Check environment variables
    missing_vars = []
    required_vars = {
        "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
        "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
        "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")
    }
    
    for var, value in required_vars.items():
        if not value:
            missing_vars.append(var)
    
    if missing_vars:
        return {
            "success": False,
            "message": f"Missing environment variables: {', '.join(missing_vars)}"
        }
    
    return {
        "success": True,
        "message": "All agent configuration variables are present",
        "livekit_url": required_vars["LIVEKIT_URL"][:50] + "...",
        "has_openai_key": bool(required_vars["OPENAI_API_KEY"])
    }