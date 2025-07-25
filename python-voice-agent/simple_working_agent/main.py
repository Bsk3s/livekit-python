#!/usr/bin/env python3
"""
SIMPLE WORKING VOICE AGENT
Back to basics - just get the greeting working again
"""
import logging
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, openai, silero

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SimpleAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant. Keep responses concise and natural. "
                "You can help with questions and have conversations."
            )
        )

async def entrypoint(ctx: JobContext):
    """Main entrypoint for the voice agent"""
    logger.info(f"🔗 Connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    logger.info("🚀 Creating agent session...")
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="echo"),
    )
    logger.info("✅ Agent session created")
    
    logger.info("🎯 Starting agent session...")
    await session.start(
        agent=SimpleAssistant(),
        room=ctx.room,
    )
    logger.info("✅ Agent session started!")
    
    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )
    logger.info("🎵 Initial greeting generated!")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="spiritual-agent",  # Match dispatch API expectation
        ),
    ) 