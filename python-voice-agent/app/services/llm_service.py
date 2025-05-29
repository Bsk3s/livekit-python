from livekit.plugins import openai

def create_gpt4o_mini():
    """Create GPT-4o Mini LLM"""
    return openai.LLM(
        model="gpt-4o-mini",
        temperature=0.7
    )

def create_character_llm(character_personality):
    """Create LLM configured with character personality"""
    return create_gpt4o_mini(instructions=character_personality) 