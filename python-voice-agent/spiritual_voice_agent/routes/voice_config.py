"""
Voice Configuration API Routes
Handles voice switching and character management for production backend
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import os
import logging
from pathlib import Path

router = APIRouter(prefix="/api/voice", tags=["voice"])

# In-memory voice configuration (could be moved to database in production)
current_voice_config = {
    "character": "adina",
    "voice": "af_heart",
    "description": "Compassionate spiritual guide"
}

class VoiceConfig(BaseModel):
    character: str
    voice: Optional[str] = None
    description: Optional[str] = None

class VoiceUpdateRequest(BaseModel):
    character: str  # "adina" or "raffa"

# Available voice configurations
VOICE_CONFIGURATIONS = {
    "adina": {
        "character": "adina",
        "voice": "af_heart",
        "description": "Compassionate spiritual guide",
        "personality": "Warm, nurturing, empathetic"
    },
    "raffa": {
        "character": "raffa", 
        "voice": "am_adam",
        "description": "Wise spiritual mentor",
        "personality": "Authoritative, paternal, strong guidance"
    }
}

@router.get("/current")
async def get_current_voice():
    """Get current voice configuration"""
    return {
        "status": "success",
        "current_voice": current_voice_config,
        "available_voices": list(VOICE_CONFIGURATIONS.keys())
    }

@router.post("/switch")
async def switch_voice(request: VoiceUpdateRequest):
    """Switch voice character for the agent"""
    global current_voice_config
    
    character = request.character.lower()
    
    if character not in VOICE_CONFIGURATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown character '{character}'. Available: {list(VOICE_CONFIGURATIONS.keys())}"
        )
    
    # Update current configuration
    current_voice_config = VOICE_CONFIGURATIONS[character].copy()
    
    # Save to file for agent persistence - with security validation
    config_dir = Path("./config")
    config_dir.mkdir(exist_ok=True, mode=0o755)
    config_file = config_dir / "current_voice_config.json"
    
    # Validate config_file is within allowed directory
    if not str(config_file.resolve()).startswith(str(config_dir.resolve())):
        raise ValueError("Invalid file path")
    
    try:
        with open(config_file, "w") as f:
            json.dump(current_voice_config, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save voice config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save configuration")
    
    return {
        "status": "success",
        "message": f"Voice switched to {character}",
        "new_voice": current_voice_config
    }

@router.get("/characters")
async def list_characters():
    """List all available voice characters"""
    return {
        "status": "success",
        "characters": VOICE_CONFIGURATIONS
    }

@router.get("/test/{character}")
async def test_voice(character: str):
    """Test a specific voice by making a Kokoro API call"""
    character = character.lower()
    
    if character not in VOICE_CONFIGURATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown character '{character}'"
        )
    
    try:
        import httpx
        
        # Test the voice with a short phrase
        test_text = f"Hello, this is {character} speaking. Voice test successful."
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8001/synthesize",
                data={
                    "text": test_text,
                    "voice": character
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Voice test successful for {character}",
                    "character": VOICE_CONFIGURATIONS[character],
                    "audio_generated": len(response.content)
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Voice test failed: {response.status_code} - {response.text}"
                )
                
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Voice test error: {str(e)}"
        )

def get_current_voice_config() -> Dict[str, Any]:
    """Get current voice configuration for use by other modules"""
    return current_voice_config.copy()

def load_voice_config_from_file() -> Dict[str, Any]:
    """Load voice configuration from file if it exists"""
    global current_voice_config
    
    # Use secure file path validation
    config_dir = Path("./config")
    config_file = config_dir / "current_voice_config.json"
    
    # Validate config_file is within allowed directory
    try:
        if not str(config_file.resolve()).startswith(str(config_dir.resolve())):
            logging.warning("Invalid config file path detected")
            return current_voice_config.copy()
    except Exception:
        # If path validation fails, don't load from file
        return current_voice_config.copy()
    
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                loaded_config = json.load(f)
                current_voice_config.update(loaded_config)
        except Exception as e:
            logging.warning(f"Could not load voice config from file: {e}")
    
    return current_voice_config.copy()

# Initialize voice config on module load
load_voice_config_from_file()