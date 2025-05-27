from livekit.agents import Agent

class SpiritualAgent(Agent):
    def __init__(self, character: str):
        instructions = self._get_character_instructions(character)
        super().__init__(instructions=instructions)
        self.character = character
        
    def _get_character_instructions(self, character: str) -> str:
        base_instructions = """
        You are a wise spiritual guide providing comfort, biblical wisdom, 
        and prayer support. Keep responses warm but concise for voice conversation.
        Remember context from recent exchanges to provide continuity.
        """
        
        if character == "raffa":
            return base_instructions + " You are Raffa, speaking with a gentle, wise male voice."
        else:  # adina
            return base_instructions + " You are Adina, speaking with a warm, compassionate female voice." 