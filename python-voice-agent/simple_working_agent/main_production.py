#!/usr/bin/env python3
"""
PRODUCTION OPTIMIZED VOICE AGENT - Fast startup for Railway deployment
"""
import asyncio
import logging
import os
import time
from typing import AsyncIterable
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

load_dotenv()

# Production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ProductionVoiceAgent(Agent):
    def __init__(self):
        super().__init__()
        logger.info("🚀 Production Voice Agent initializing...")
        
    async def aenter_agent(self, ctx: JobContext) -> None:
        logger.info(f"🎯 Agent entering room: {ctx.room.name}")
        
        # Use faster OpenAI TTS for production reliability
        tts = openai.TTS(
            model="tts-1",
            voice="nova",  # Fast, clear voice
        )
        
        # Optimized LLM for speed
        llm = openai.LLM(
            model="gpt-4o-mini",
            temperature=0.7,
        )
        
        # Fast STT
        stt = deepgram.STT(
            model="nova-2-general",
            language="en",
        )
        
        # Create assistant with minimal latency
        assistant = rtc.AssistantSession(
            chat_ctx=llm.chat(
                chat_history=[
                    {"role": "system", "content": "You are Adina, a compassionate spiritual guide. Keep responses concise and warm."}
                ]
            ),
            stt=stt,
            tts=tts,
            allow_interruptions=True,
        )
        
        assistant.start(ctx.room)
        logger.info("✅ Production agent ready for conversations")
        
        await assistant.aclose()

# Production worker configuration
if __name__ == "__main__":
    logger.info("🎯 Starting PRODUCTION Voice Agent Worker...")
    
    # Optimized for Railway constraints
    worker_options = WorkerOptions(
        agent_name="spiritual-agent-prod",
        ws_url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
        # Increased timeouts for Railway
        max_idle_time=300,  # 5 minutes
        max_session_duration=1800,  # 30 minutes
        # Reduce memory usage
        max_concurrent_jobs=2,
    )
    
    cli.run_app(
        ProductionVoiceAgent(),
        worker_options=worker_options,
        auto_download_models=True,  # Download models automatically
        log_level="INFO"
    )