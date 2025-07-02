"""
Character Factory for Spiritual Voice Agent
Creates character configurations for Adina and Raffa
"""


class SimpleCharacter:
    """Simple character data class"""

    def __init__(self, name: str, description: str, personality: str):
        self.name = name
        self.description = description
        self.personality = personality


class CharacterFactory:
    """Factory for creating spiritual guidance characters"""

    CHARACTER_CONFIGS = {
        "adina": {
            "name": "Adina",
            "description": "Compassionate spiritual guide",
            "personality": """You are Adina, a compassionate and nurturing spiritual guide. 
            You speak with warmth, empathy, and gentle wisdom. Your responses are:
            - Caring and supportive
            - Focused on emotional healing
            - Encouraging and uplifting
            - Grounded in love and compassion
            - Brief but meaningful (2-3 sentences max)
            
            You help people find peace, comfort, and spiritual connection through difficult times.""",
            "greeting_style": "warm and compassionate",
            "voice_model": "aura-2-luna-en",
        },
        "raffa": {
            "name": "Raffa",
            "description": "Wise spiritual mentor",
            "personality": """You are Raffa, a wise and experienced spiritual mentor. 
            You speak with gentle authority, biblical wisdom, and caring insight. Your responses are:
            - Wise and thoughtful
            - Grounded in spiritual principles
            - Encouraging yet realistic
            - Focused on growth and understanding
            - Brief but profound (2-3 sentences max)
            
            You guide people toward spiritual maturity and deeper understanding of their faith journey.""",
            "greeting_style": "wise and welcoming",
            "voice_model": "aura-2-orion-en",
        },
    }

    @classmethod
    def create_character(cls, character_name: str) -> SimpleCharacter:
        """Create a character instance"""
        character_name = character_name.lower()

        if character_name not in cls.CHARACTER_CONFIGS:
            raise ValueError(f"Unknown character: {character_name}")

        config = cls.CHARACTER_CONFIGS[character_name]

        return SimpleCharacter(
            name=config["name"],
            description=config["description"],
            personality=config["personality"],
        )

    @classmethod
    def get_character_config(cls, character_name: str) -> dict:
        """Get character configuration dictionary"""
        character_name = character_name.lower()

        if character_name not in cls.CHARACTER_CONFIGS:
            raise ValueError(f"Unknown character: {character_name}")

        return cls.CHARACTER_CONFIGS[character_name]

    @classmethod
    def list_characters(cls) -> list:
        """List available characters"""
        return list(cls.CHARACTER_CONFIGS.keys())
