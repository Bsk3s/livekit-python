#!/usr/bin/env python3
"""
Railway Production Voice Agent Worker
Optimized for Railway deployment with OpenAI TTS/STT
"""
import asyncio
import logging
import os
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RailwayVoiceAgent(Agent):
    def __init__(self):
        super().__init__()
        logger.info("🚀 Railway Voice Agent initializing...")
        
    async def aenter_agent(self, ctx: JobContext) -> None:
        logger.info(f"🎯 Agent joining room: {ctx.room.name}")
        
        # Use OpenAI for reliable cloud TTS/STT (no local models)
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
        
        # Determine character from room metadata
        character = "adina"  # Default
        if "raffa" in ctx.room.name.lower():
            character = "raffa"
        elif "adina" in ctx.room.name.lower():
            character = "adina"
            
        # Character-specific system prompts
        if character == "adina":
            system_prompt = """You are Adina, a compassionate spiritual guide. You speak with warmth, 
            empathy, and gentle wisdom. Keep responses concise but meaningful, offering comfort and 
            insight. Use a calm, nurturing tone."""
        else:  # raffa
            system_prompt = """You are Raffa, a wise spiritual mentor. You speak with depth, 
            clarity, and profound insight. Share wisdom through thoughtful questions and gentle 
            guidance. Keep responses focused and enlightening."""
        
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

if __name__ == "__main__":
    logger.info("🌟 Starting Railway Voice Agent Worker...")
    
    # Create status file to indicate agent is running
    try:
        with open("/tmp/agent_running", "w") as f:
            f.write("started")
        logger.info("✅ Agent status file created")
    except Exception as e:
        logger.warning(f"⚠️ Could not create status file: {e}")
    
    # Railway-optimized worker configuration (updated for newer LiveKit API)
    worker_options = WorkerOptions(
        agent_name="railway-spiritual-agent",
        # Remove deprecated parameters that cause TypeError
    )
    
    logger.info(f"🔗 Connecting to LiveKit: {os.getenv('LIVEKIT_URL', 'NOT_SET')}")
    logger.info(f"🔑 API Key: {os.getenv('LIVEKIT_API_KEY', 'NOT_SET')[:10]}...")
    
    cli.run_app(
        RailwayVoiceAgent(),
        worker_options=worker_options,
        auto_download_models=True,
        log_level="INFO"
    )