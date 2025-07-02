from ..base_character import BaseSpiritualAgent
from .personality import AdinaPersonality
from .voice_config import AdinaVoiceConfig


class AdinaAgent(BaseSpiritualAgent):
    def get_instructions(self) -> str:
        base = self.get_base_spiritual_instructions()
        return f"{base}\n\n{AdinaPersonality.INSTRUCTIONS}"

    def get_voice_config(self) -> dict:
        return AdinaVoiceConfig.CONFIG

    def get_tools(self) -> list:
        return AdinaPersonality.TOOLS
