from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession, 
    JobContext,
    WorkerOptions,
    cli
)
from livekit.plugins import silero

# Try to import turn detector, but make it optional
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    TURN_DETECTOR_AVAILABLE = True
except ImportError as e:
    TURN_DETECTOR_AVAILABLE = False
    print(f"⚠️ Turn detector plugin not available: {e}")
    print("🔄 Agent will use standard VAD-based turn detection")

import os
from services.livekit_tts_adapter import LiveKitGeminiTTSAdapter

from ..services.deepgram_service import create_deepgram_stt
from ..factories.character_factory import CharacterFactory
from ..services.gpt4o_mini import create_gpt4o_mini

load_dotenv()

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    character_name = extract_character_from_room(ctx.room.name)
    agent = CharacterFactory.create_character(character_name)
    tts_adapter = LiveKitGeminiTTSAdapter(
        api_key=os.getenv("GEMINI_API_KEY")
    )
    tts_adapter.set_voice_config(agent.get_voice_config())
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=create_deepgram_stt(),
        llm=create_gpt4o_mini(),
        tts=tts_adapter,
        turn_detection=MultilingualModel() if TURN_DETECTOR_AVAILABLE else None,
    )
    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions=f"Greet the user as {character_name} with your characteristic warmth"
    )
    
    # Log when transcription is received
    @session.on("transcription")
    async def handle_transcription(transcript):
        print(f"Received transcription: {transcript}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint)) 