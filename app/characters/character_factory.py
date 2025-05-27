from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class Character:
    def __init__(self, name: str, personality: str, voice_model: str, description: str):
        self.name = name
        self.personality = personality
        self.voice_model = voice_model
        self.description = description

class CharacterFactory:
    CHARACTERS = {
        "adina": {
            "personality": """You are Adina, a compassionate spiritual guide who offers comfort and support. 
            You speak with warmth, empathy, and understanding. Your responses are gentle, nurturing, and focused on 
            emotional healing. You help people find peace in difficult times and offer spiritual comfort.""",
            "voice_model": "aura-2-luna-en",  # Gentle, soothing female
            "description": "Compassionate spiritual guide with a gentle, soothing voice",
            "greeting_style": "warm and comforting"
        },
        "raffa": {
            "personality": """You are Raffa, a wise spiritual mentor who provides biblical wisdom and guidance. 
            You speak with gentle authority, deep insight, and caring wisdom. Your responses draw from spiritual 
            teachings and offer practical guidance for life's challenges. You help people find meaning and direction.""",
            "voice_model": "aura-2-orion-en",  # Warm, approachable male
            "description": "Wise spiritual mentor with a warm, approachable voice",
            "greeting_style": "wise and welcoming"
        }
    }
    
    @classmethod
    def create_character(cls, name: str) -> Character:
        """Create a character instance by name"""
        if name not in cls.CHARACTERS:
            raise ValueError(f"Invalid character: {name}. Must be one of: {list(cls.CHARACTERS.keys())}")
            
        config = cls.CHARACTERS[name]
        logger.info(f"Creating character: {name} with voice model: {config['voice_model']}")
        
        return Character(
            name=name, 
            personality=config["personality"],
            voice_model=config["voice_model"],
            description=config["description"]
        )
    
    @classmethod
    def get_character_config(cls, name: str) -> Dict[str, Any]:
        """Get character configuration by name"""
        if name not in cls.CHARACTERS:
            raise ValueError(f"Invalid character: {name}. Must be one of: {list(cls.CHARACTERS.keys())}")
        return cls.CHARACTERS[name] 