from typing import Literal

CharacterType = Literal["raffa", "adina"]


def determine_character(room_name: str) -> CharacterType:
    """
    Determine which character to use based on room name.
    Default to 'raffa' if no specific character is indicated.
    """
    room_name = room_name.lower()

    if "adina" in room_name:
        return "adina"
    return "raffa"


def get_character_tts(character: CharacterType):
    """
    Get the appropriate TTS configuration for the character.
    """
    from livekit.plugins import elevenlabs

    if character == "raffa":
        return elevenlabs.TTS(voice="Josh", model="eleven_multilingual_v2")  # Male voice
    else:  # adina
        return elevenlabs.TTS(voice="Rachel", model="eleven_multilingual_v2")  # Female voice


def get_spiritual_instructions(character: CharacterType) -> str:
    """
    Get the spiritual instructions for the character.
    """
    base_instructions = """
    You are a wise spiritual guide providing comfort, biblical wisdom, 
    and prayer support. Keep responses warm but concise for voice conversation.
    Remember context from recent exchanges to provide continuity.
    """

    if character == "raffa":
        return base_instructions + " You are Raffa, speaking with a gentle, wise male voice."
    else:  # adina
        return (
            base_instructions + " You are Adina, speaking with a warm, compassionate female voice."
        )
