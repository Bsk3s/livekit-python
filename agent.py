from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, silero
import logging
from dotenv import load_dotenv

from app.services.tts_service import TTSService
from app.services.llm_service import create_gpt4o_mini
from app.services.deepgram_service import create_deepgram_stt

load_dotenv()
logger = logging.getLogger(__name__)

async def entrypoint(ctx: JobContext):
    """Clean LiveKit voice agent for TTS model development"""
    try:
        await ctx.connect()
        logger.info(f"Connected to LiveKit room: {ctx.room.name}")
        
        # Create TTS service
        tts_service = TTSService()
        
        # Create STT service
        stt_service = create_deepgram_stt()
        
        # Create LLM service
        llm_service = create_gpt4o_mini()
        
        # Create simple agent session
        session = AgentSession(
            vad=silero.VAD.load(),
            stt=stt_service,
            llm=llm_service,
            tts=tts_service,
            allow_interruptions=True,
        )
        
        # Create agent
        agent = Agent(
            name="Voice Agent",
            instructions="You are a helpful voice assistant. Respond naturally and conversationally.",
        )
        
        # Start the session
        await session.start(agent=agent, room=ctx.room)
        
        # Generate greeting
        await session.generate_reply(instructions="Greet the user warmly and let them know you're ready to help.")
        
        logger.info("Voice agent session started successfully")
        
    except Exception as e:
        logger.error(f"Error in voice agent session: {e}")
        raise
    finally:
        # Cleanup TTS resources
        if 'tts_service' in locals():
            await tts_service.aclose()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint)) 