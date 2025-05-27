from livekit.agents import (
    Agent, AgentSession, JobContext, WorkerOptions, cli
)
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import logging
import time
import asyncio
from dotenv import load_dotenv

from characters.character_factory import CharacterFactory
from services.deepgram_service import create_deepgram_stt
from services.llm_service import create_gpt4o_mini
from services.livekit_deepgram_tts import LiveKitDeepgramTTS

load_dotenv()
logger = logging.getLogger(__name__)

class TimestampLogger:
    """Utility class for logging STT → LLM → TTS timestamps"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_time = None
        self.stt_complete = None
        self.llm_complete = None
        self.tts_start = None
        self.tts_first_chunk = None
    
    def mark_start(self):
        self.start_time = time.time()
        logger.info("🎯 Voice interaction started")
    
    def mark_stt_complete(self, transcript: str):
        self.stt_complete = time.time()
        if self.start_time:
            stt_latency = (self.stt_complete - self.start_time) * 1000
            logger.info(f"🎧 STT complete ({stt_latency:.0f}ms): '{transcript[:50]}...'")
    
    def mark_llm_complete(self, response: str):
        self.llm_complete = time.time()
        if self.stt_complete:
            llm_latency = (self.llm_complete - self.stt_complete) * 1000
            logger.info(f"🧠 LLM complete ({llm_latency:.0f}ms): '{response[:50]}...'")
    
    def mark_tts_start(self):
        self.tts_start = time.time()
        if self.llm_complete:
            processing_latency = (self.tts_start - self.llm_complete) * 1000
            logger.info(f"🎤 TTS started ({processing_latency:.0f}ms processing)")
    
    def mark_tts_first_chunk(self):
        self.tts_first_chunk = time.time()
        if self.tts_start:
            tts_latency = (self.tts_first_chunk - self.tts_start) * 1000
            logger.info(f"🚀 TTS first chunk ({tts_latency:.0f}ms)")
        
        # Log total pipeline latency
        if self.start_time:
            total_latency = (self.tts_first_chunk - self.start_time) * 1000
            logger.info(f"⚡ TOTAL PIPELINE LATENCY: {total_latency:.0f}ms")

# Global timestamp logger
timestamp_logger = TimestampLogger()

async def entrypoint(ctx: JobContext):
    """Enhanced voice agent entry point with full streaming and logging"""
    try:
        await ctx.connect()
        logger.info(f"🔗 Connected to LiveKit room: {ctx.room.name}")
        
        # Determine character from room name
        character_name = extract_character_from_room(ctx.room.name)
        logger.info(f"🎭 Using character: {character_name}")
        
        # Create character configuration
        character = CharacterFactory.create_character(character_name)
        
        # Create enhanced Deepgram TTS with character voice
        deepgram_tts = LiveKitDeepgramTTS()
        deepgram_tts.set_character(character_name)
        logger.info(f"🎤 Configured Deepgram TTS for {character_name} ({character.description})")
        
        # Create optimized STT with streaming
        stt_service = create_deepgram_stt()
        logger.info("🎧 Deepgram STT configured for streaming transcription")
        
        # Create LLM with context memory (3-5 turns)
        llm_service = create_gpt4o_mini()
        logger.info("🧠 GPT-4o Mini configured with 3-5 turn context memory")
        
        # Create enhanced voice session with streaming components
        session = AgentSession(
            vad=silero.VAD.load(),  # Voice Activity Detection
            stt=stt_service,        # Streaming STT
            llm=llm_service,        # LLM with context
            tts=deepgram_tts,       # Streaming TTS
            turn_detection=MultilingualModel(),  # Smart turn detection
            allow_interruptions=True,  # Enable interruptions
            min_interruption_duration=0.5,  # 500ms minimum for interruption
            min_endpointing_delay=0.3,  # Quick response
            max_endpointing_delay=2.0,  # Don't wait too long
        )
        
        # Set up event handlers for logging and monitoring
        session.on("user_input_transcribed", _on_user_transcribed)
        session.on("agent_state_changed", _on_agent_state_changed)
        session.on("speech_created", _on_speech_created)
        session.on("speech_finished", _on_speech_finished)
        
        logger.info("🚀 Starting enhanced spiritual guidance session")
        
        # Create agent with character personality
        agent = Agent(
            name=character.name,
            instructions=character.personality,
        )
        
        # Start the session with the room
        await session.start(agent=agent, room=ctx.room)
        
        # Generate initial spiritual greeting
        greeting = get_character_greeting(character_name)
        logger.info(f"💬 Generating initial greeting for {character_name}")
        
        # Reset timestamp logger for greeting
        timestamp_logger.reset()
        timestamp_logger.mark_start()
        timestamp_logger.mark_stt_complete("(initial greeting)")
        timestamp_logger.mark_llm_complete(greeting)
        
        await session.generate_reply(instructions=greeting)
        
        logger.info("✅ Enhanced session started - ready for streaming voice interactions")
        logger.info("🎯 Features enabled: STT streaming, LLM context, TTS streaming, interruptions")
        
    except Exception as e:
        logger.error(f"❌ Error in enhanced spiritual session: {e}")
        raise
    finally:
        # Cleanup TTS resources
        if 'deepgram_tts' in locals():
            await deepgram_tts.aclose()
            logger.info("🧹 Cleaned up Deepgram TTS resources")

def _on_user_transcribed(event):
    """Handle user speech transcription with timestamp logging"""
    if event.is_final:
        timestamp_logger.mark_stt_complete(event.transcript)
        logger.info(f"👤 User said: '{event.transcript}'")
    else:
        # Interim results for real-time feedback
        logger.debug(f"👤 User speaking: '{event.transcript}...'")

def _on_agent_state_changed(event):
    """Handle agent state changes"""
    logger.info(f"🤖 Agent state: {event.old_state} → {event.new_state}")
    
    if event.new_state == "listening":
        # Reset for next interaction
        timestamp_logger.reset()
        timestamp_logger.mark_start()
    elif event.new_state == "thinking":
        # LLM processing started
        pass
    elif event.new_state == "speaking":
        timestamp_logger.mark_tts_start()

def _on_speech_created(event):
    """Handle speech creation events"""
    logger.info(f"🗣️ Speech created: {event.source}")

def _on_speech_finished(event):
    """Handle speech completion events"""
    logger.info(f"✅ Speech finished: interrupted={event.interrupted}")

def extract_character_from_room(room_name: str) -> str:
    """Extract character from room name (e.g., spiritual-room-raffa)"""
    room_lower = room_name.lower()
    
    if "raffa" in room_lower or "rafa" in room_lower:
        return "raffa"
    elif "adina" in room_lower:
        return "adina"
    
    # Default to Adina for unknown room names
    logger.info(f"Unknown room pattern '{room_name}', defaulting to Adina")
    return "adina"

def get_character_greeting(character: str) -> str:
    """Get character-specific greeting instructions"""
    config = CharacterFactory.get_character_config(character)
    
    greetings = {
        "adina": f"""Generate a {config['greeting_style']} greeting as Adina. 
        Welcome the user to this spiritual guidance session with compassion and warmth. 
        Let them know you're here to provide comfort and support for whatever they're going through. 
        Keep it natural and conversational, like talking to a close friend. 
        Speak for about 10-15 seconds maximum.""",
        
        "raffa": f"""Generate a {config['greeting_style']} greeting as Raffa. 
        Welcome the user with wisdom and gentle authority. Let them know you're here to offer 
        spiritual guidance and biblical wisdom for their life's journey. 
        Speak with caring insight and make them feel heard and understood.
        Speak for about 10-15 seconds maximum."""
    }
    
    return greetings.get(character, greetings["adina"])

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint)) 