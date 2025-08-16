#!/usr/bin/env python3
"""
🎙️ SPIRITUAL VOICE AGENT - PRODUCTION WORKER
Long-running LiveKit agent for spiritual guidance conversations
"""
import asyncio
import logging
import os
import signal
import sys
from contextlib import suppress
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, openai
from livekit import rtc

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Fail fast on missing environment variables
REQUIRED_ENV_VARS = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY", 
    "LIVEKIT_API_SECRET",
    "OPENAI_API_KEY",
    "DEEPGRAM_API_KEY"
]

def validate_environment():
    """Validate all required environment variables are present"""
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logger.info("✅ All required environment variables present")
    logger.info(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL')}")

class SpiritualVoiceAgent(Agent):
    """Spiritual guidance voice agent with character selection"""
    
    def __init__(self):
        super().__init__()
        logger.info("🌟 Spiritual Voice Agent initializing...")
        
    async def aenter_agent(self, ctx: JobContext) -> None:
        logger.info(f"🎯 Agent joining room: {ctx.room.name}")
        
        # Initialize AI services
        tts = openai.TTS(
            model="tts-1",
            voice="nova",  # Clear, friendly voice
        )
        
        llm = openai.LLM(
            model="gpt-4o-mini",
            temperature=0.7,
        )
        
        stt = deepgram.STT(
            model="nova-2-general",
            language="en",
        )
        
        # Determine character from room metadata or name
        character = self._detect_character(ctx.room.name)
        system_prompt = self._get_character_prompt(character)
        
        logger.info(f"✨ Starting conversation as {character}")
        
        # Create assistant session
        assistant = rtc.AssistantSession(
            chat_ctx=llm.chat(
                chat_history=[
                    {"role": "system", "content": system_prompt}
                ]
            ),
            stt=stt,
            tts=tts,
            allow_interruptions=True,
        )
        
        assistant.start(ctx.room)
        logger.info(f"🎙️ {character.title()} is ready for spiritual guidance")
        
        await assistant.aclose()
    
    def _detect_character(self, room_name: str) -> str:
        """Detect character from room name"""
        room_lower = room_name.lower()
        if "raffa" in room_lower:
            return "raffa"
        elif "adina" in room_lower:
            return "adina"
        return "adina"  # Default to Adina
    
    def _get_character_prompt(self, character: str) -> str:
        """Get system prompt for character"""
        if character == "adina":
            return """You are Adina, a compassionate spiritual guide. You speak with warmth, 
            empathy, and gentle wisdom. Keep responses concise but meaningful, offering comfort and 
            insight. Use a calm, nurturing tone. Focus on emotional support and gentle guidance."""
        else:  # raffa
            return """You are Raffa, a wise spiritual mentor. You speak with depth, 
            clarity, and profound insight. Share wisdom through thoughtful questions and gentle 
            guidance. Keep responses focused and enlightening. Offer practical spiritual wisdom."""

async def main():
    """Main entry point with graceful shutdown"""
    logger.info("🚀 Starting Spiritual Voice Agent Worker...")
    
    # Validate environment
    validate_environment()
    
    # Set up graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("🛑 Shutdown signal received")
        stop_event.set()
    
    # Register signal handlers
    with suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        loop.add_signal_handler(signal.SIGINT, signal_handler)
    
    # Create and configure worker
    worker_options = WorkerOptions(
        agent_name="spiritual-guidance-agent",
    )
    
    logger.info(f"🔗 Connecting to LiveKit: {os.getenv('LIVEKIT_URL')}")
    logger.info(f"🔑 API Key: {os.getenv('LIVEKIT_API_KEY', 'NOT_SET')[:10]}...")
    
    try:
        # Run the agent
        agent = SpiritualVoiceAgent()
        
        # This will run until stopped
        await cli.run_app_async(
            agent,
            worker_options=worker_options,
            auto_download_models=True,
            log_level="INFO"
        )
        
    except Exception as e:
        logger.error(f"❌ Agent failed: {e}")
        sys.exit(1)
    
    logger.info("👋 Spiritual Voice Agent stopped cleanly")

if __name__ == "__main__":
    asyncio.run(main())