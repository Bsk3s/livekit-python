from livekit.plugins import openai

def create_gpt4o_mini():
    """Create GPT-4o Mini LLM service with enhanced connection handling"""
    return openai.LLM(
        model="gpt-4o-mini",
        temperature=0.7,
        # Enhanced timeout for production reliability
        timeout=30.0,  # 30 second timeout instead of default 10s
        # Note: max_retries not supported by LiveKit OpenAI plugin
    )

def create_character_llm(character_personality):
    """Create LLM configured with character personality"""
    return create_gpt4o_mini() 