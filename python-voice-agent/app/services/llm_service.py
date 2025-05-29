from livekit.plugins import openai

def create_gpt4o_mini(instructions=None):
    """Create GPT-4o Mini LLM with optional character instructions"""
    llm = openai.LLM(
        model="gpt-4o-mini",
        temperature=0.7
    )
    
    # Set instructions if provided
    if instructions:
        llm.instructions = instructions
    
    return llm

def create_character_llm(character_personality):
    """Create LLM configured with character personality"""
    return create_gpt4o_mini(instructions=character_personality) 