from livekit import api
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

def get_livekit_credentials():
    """Get LiveKit credentials from environment variables"""
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET environment variables are required")
    
    return api_key, api_secret

def create_spiritual_access_token(
    room: str, 
    user_id: str, 
    user_name: str, 
    character: str,
    duration_minutes: int = 30
) -> str:
    """
    Create a secure LiveKit access token for spiritual guidance sessions
    
    Args:
        room: Room name (format: spiritual-{character}-{session_id})
        user_id: Unique user identifier
        user_name: Display name for the user
        character: Character name (adina or raffa)
        duration_minutes: Token validity duration
    
    Returns:
        JWT token string
    """
    try:
        api_key, api_secret = get_livekit_credentials()
        
        # Validate character
        if character not in ["adina", "raffa"]:
            raise ValueError(f"Invalid character: {character}. Must be 'adina' or 'raffa'")
        
        # Create video grants with appropriate permissions
        grants = api.VideoGrants(
            room_join=True,
            room=room,
            room_create=True,  # Allow room creation if it doesn't exist
            can_publish=True,  # User can publish audio
            can_subscribe=True,  # User can receive agent audio
            can_publish_data=True,  # For potential text chat
            can_update_own_metadata=True  # User can update their own metadata
        )
        
        # Create access token with expiration
        token = api.AccessToken(api_key=api_key, api_secret=api_secret)
        token.grants = grants
        token.identity = f"user_{user_id}"  # Prefix for clarity
        token.name = user_name
        
        # Set token expiration
        token.ttl = timedelta(minutes=duration_minutes)
        
        # Add metadata for character context
        token.metadata = {
            "character": character,
            "session_type": "spiritual_guidance",
            "created_at": datetime.utcnow().isoformat()
        }
        
        jwt_token = token.to_jwt()
        
        logger.info(f"Created spiritual token for user {user_id} ({user_name}) with {character} in room {room}")
        
        return jwt_token
        
    except Exception as e:
        logger.error(f"Failed to create spiritual access token: {e}")
        raise

def create_access_token(room: str, participant_name: str) -> str:
    """
    Legacy token creation function for backward compatibility
    """
    try:
        return create_spiritual_access_token(
            room=room,
            user_id=participant_name,
            user_name=participant_name,
            character="adina",  # Default character
            duration_minutes=30
        )
    except Exception as e:
        logger.error(f"Failed to create legacy access token: {e}")
        raise 