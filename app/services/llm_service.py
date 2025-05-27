from livekit.plugins import openai
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def create_gpt4o_mini():
    """Create an optimized GPT-4o Mini LLM instance for spiritual guidance"""
    logger.info("🧠 Creating optimized GPT-4o Mini LLM instance")
    
    # Verify API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    # Create LLM with optimized settings for spiritual conversations
    llm = openai.LLM(
        model="gpt-4o-mini",
        temperature=0.7,        # Balanced creativity and consistency
        max_tokens=150,         # Keep responses concise for voice
        top_p=0.9,             # Focused but natural responses
        frequency_penalty=0.1,  # Slight penalty for repetition
        presence_penalty=0.1,   # Encourage topic exploration
    )
    
    logger.info("✅ GPT-4o Mini configured for spiritual guidance conversations")
    return llm

def create_spiritual_system_prompt(character_name: str) -> str:
    """Create system prompt for spiritual guidance based on character"""
    base_prompt = """You are a compassionate spiritual guide in a voice conversation. 
    
    CONVERSATION STYLE:
    - Keep responses to 1-3 sentences for natural voice flow
    - Speak conversationally, like talking to a close friend
    - Use "you" and "I" naturally - this is a personal conversation
    - Avoid long explanations - voice conversations need brevity
    - Ask follow-up questions to keep the dialogue flowing
    
    SPIRITUAL GUIDANCE APPROACH:
    - Listen deeply and respond with empathy
    - Offer comfort and hope in difficult times
    - Share wisdom without being preachy
    - Help people find their own answers through gentle guidance
    - Acknowledge emotions and validate feelings
    
    Remember: This is a VOICE conversation, so keep it natural and flowing."""
    
    return base_prompt 