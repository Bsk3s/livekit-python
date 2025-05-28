from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import Literal
import uuid
import time
from datetime import datetime, timedelta
import logging
from app.services.livekit_token import create_spiritual_access_token

router = APIRouter()
logger = logging.getLogger(__name__)

class SpiritualTokenRequest(BaseModel):
    character: Literal["adina", "raffa"]
    user_id: str
    user_name: str
    session_duration_minutes: int = 30  # Default 30 minute sessions
    
    @validator('user_name')
    def validate_user_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('User name must be at least 2 characters')
        return v.strip()
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('User ID must be at least 3 characters')
        return v.strip()
    
    @validator('session_duration_minutes')
    def validate_duration(cls, v):
        if v < 5 or v > 120:  # 5 minutes to 2 hours max
            raise ValueError('Session duration must be between 5 and 120 minutes')
        return v

class TokenResponse(BaseModel):
    token: str
    room_name: str
    character: str
    expires_at: str
    session_id: str

@router.post("/spiritual-token", response_model=TokenResponse)
async def create_spiritual_token(request: SpiritualTokenRequest):
    """
    Create a LiveKit access token for spiritual guidance sessions
    
    - **character**: Choose between 'adina' (compassionate guide) or 'raffa' (wise mentor)
    - **user_id**: Unique identifier for the user
    - **user_name**: Display name for the user
    - **session_duration_minutes**: Session length (5-120 minutes)
    """
    try:
        # Generate unique session ID
        session_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create character-specific room name
        room_name = f"spiritual-{request.character}-{session_id}"
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(minutes=request.session_duration_minutes)
        
        # Create secure access token
        token = create_spiritual_access_token(
            room=room_name,
            user_id=request.user_id,
            user_name=request.user_name,
            character=request.character,
            duration_minutes=request.session_duration_minutes
        )
        
        logger.info(f"Created spiritual token for {request.user_name} with {request.character} in room {room_name}")
        
        return TokenResponse(
            token=token,
            room_name=room_name,
            character=request.character,
            expires_at=expires_at.isoformat() + "Z",
            session_id=session_id
        )
        
    except ValueError as e:
        logger.warning(f"Token validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create access token")

# Legacy endpoint for backward compatibility
@router.post("/createToken")
async def create_token_legacy(request: dict):
    """Legacy token endpoint - use /spiritual-token instead"""
    try:
        # Convert legacy format to new format
        spiritual_request = SpiritualTokenRequest(
            character="adina",  # Default character
            user_id=request.get("participant_name", "anonymous"),
            user_name=request.get("participant_name", "Anonymous User"),
            session_duration_minutes=30
        )
        
        response = await create_spiritual_token(spiritual_request)
        
        # Return legacy format
        return {
            "token": response.token,
            "room": response.room_name
        }
        
    except Exception as e:
        logger.error(f"Legacy token creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Expo app endpoint - matches the format expected by the iOS app
@router.post("/generate-token")
async def generate_token_expo(request: dict):
    """Generate token endpoint for Expo mobile app"""
    try:
        # Extract data from the request format sent by the iOS app
        room = request.get("room", "spiritual-room-adina")
        identity = request.get("identity", "anonymous")
        character = request.get("character", "adina")
        
        # Validate character
        if character not in ["adina", "raffa"]:
            character = "adina"
        
        # Convert to spiritual request format
        spiritual_request = SpiritualTokenRequest(
            character=character,
            user_id=identity,
            user_name=identity,
            session_duration_minutes=30
        )
        
        response = await create_spiritual_token(spiritual_request)
        
        # Return format expected by iOS app
        return {
            "token": response.token,
            "room": response.room_name,
            "character": response.character,
            "ws_url": "wss://heavenly-new-livekit.livekit.cloud"  # LiveKit WebSocket URL
        }
        
    except Exception as e:
        logger.error(f"Expo token generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 