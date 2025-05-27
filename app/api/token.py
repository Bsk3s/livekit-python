from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging
from livekit import api
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter()

class TokenRequest(BaseModel):
    room: str
    identity: str
    character: str

class TokenResponse(BaseModel):
    token: str
    room: str
    character: str
    ws_url: str

@router.post("/generate-token", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    """Generate LiveKit access token for Expo client"""
    try:
        # Get LiveKit credentials from environment
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        ws_url = os.getenv("LIVEKIT_WS_URL", "ws://localhost:7880")
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=500, 
                detail="LiveKit credentials not configured"
            )
        
        # Validate character
        valid_characters = ["adina", "raffa"]
        if request.character not in valid_characters:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid character. Must be one of: {valid_characters}"
            )
        
        # Create room name with character
        room_name = f"spiritual-room-{request.character}"
        
        # Generate token with appropriate permissions
        token = api.AccessToken(api_key, api_secret) \
            .with_identity(request.identity) \
            .with_name(f"User-{request.identity}") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )) \
            .to_jwt()
        
        logger.info(f"Generated token for {request.identity} in room {room_name}")
        
        return TokenResponse(
            token=token,
            room=room_name,
            character=request.character,
            ws_url=ws_url
        )
        
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "token-generator"} 