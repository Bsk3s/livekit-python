#!/usr/bin/env python3
"""
Manual Agent Dispatch API

Provides endpoints for explicitly dispatching agents to rooms.
This supplements auto-dispatch for more reliable agent management.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import Literal
from livekit import api

from spiritual_voice_agent.services.auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


class DispatchAgentRequest(BaseModel):
    room_name: str
    character: str  # Accept any string, validate in custom validator
    user_id: str = "default_user"  # Make optional with default
    user_name: str = "Mobile App User"  # Make optional with default

    @validator("character")
    def validate_character(cls, v):
        # Normalize character name for production compatibility
        char = v.lower().strip()
        if char in ["adina"]:
            return "adina"
        elif char in ["raffa", "rafa"]:  # Accept both spellings
            return "raffa"
        else:
            raise ValueError("Character must be 'adina', 'raffa', or 'rafa'")


class DispatchAgentResponse(BaseModel):
    success: bool
    dispatch_id: str
    message: str


@router.post("/dispatch-agent", response_model=DispatchAgentResponse)
async def dispatch_agent(request: DispatchAgentRequest, _: bool = Depends(verify_api_key)):
    """
    Manually dispatch an agent to a specific room
    
    This provides explicit control over when agents join rooms,
    bypassing unreliable auto-dispatch behavior.
    """
    try:
        logger.info(f"🚀 Manual dispatch requested for {request.character} in room {request.room_name}")
        
        # Create LiveKit API client
        lkapi = api.LiveKitAPI()
        
        # Prepare agent metadata
        metadata = {
            "character": request.character,
            "user_id": request.user_id,
            "user_name": request.user_name,
            "dispatch_type": "manual_api"
        }
        
        # Create dispatch request
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="spiritual-agent",  # Must match worker agent_name
            room=request.room_name,
            metadata=str(metadata)  # Convert to JSON string
        )
        
        logger.info(f"🔧 Dispatch request: agent_name=spiritual-agent, room={request.room_name}")
        
        # Execute dispatch
        dispatch_result = await lkapi.agent_dispatch.create_dispatch(dispatch_request)
        
        logger.info(f"📋 Dispatch result: {dispatch_result}")
        
        await lkapi.aclose()
        
        logger.info(f"✅ Agent dispatched successfully: {dispatch_result.id}")
        
        return DispatchAgentResponse(
            success=True,
            dispatch_id=dispatch_result.id,  # Fixed: was dispatch_result.dispatch_id
            message=f"Agent {request.character} dispatched to room {request.room_name}"
        )
        
    except Exception as e:
        logger.error(f"❌ Agent dispatch failed: {e}")
        logger.error(f"❌ Full error details: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch agent: {str(e)}"
        ) 