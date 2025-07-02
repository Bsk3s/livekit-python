from ..base_character import BaseSpiritualAgent
from .personality import RaffaPersonality
from .voice_config import RaffaVoiceConfig


class RaffaAgent(BaseSpiritualAgent):
    def get_instructions(self) -> str:
        base = self.get_base_spiritual_instructions()
        return f"{base}\n\n{RaffaPersonality.INSTRUCTIONS}"

    def get_voice_config(self) -> dict:
        return RaffaVoiceConfig.CONFIG

    def get_tools(self) -> list:
        return RaffaPersonality.TOOLS
