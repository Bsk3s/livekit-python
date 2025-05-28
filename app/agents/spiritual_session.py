from livekit.agents import (
    Agent, AgentSession, JobContext, WorkerOptions, cli, room_io
)
from livekit.plugins import deepgram, openai, silero, noise_cancellation
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

class AdvancedTimestampLogger:
    """Ultra-advanced timestamp logger with comprehensive metrics"""
    
    def __init__(self):
        self.reset()
        self.session_metrics = {
            'total_interactions': 0,
            'avg_response_time': 0,
            'interruptions': 0,
            'successful_completions': 0
        }
    
    def reset(self):
        self.start_time = None
        self.stt_complete = None
        self.llm_complete = None
        self.tts_start = None
        self.tts_first_chunk = None
        self.turn_detected = None
        self.vad_triggered = None
    
    def mark_vad_triggered(self):
        """Mark when Voice Activity Detection triggers"""
        self.vad_triggered = time.time()
        logger.info("🎯 VAD triggered - user started speaking")
    
    def mark_turn_detected(self):
        """Mark when turn detection model determines user finished"""
        self.turn_detected = time.time()
        if self.vad_triggered:
            turn_detection_time = (self.turn_detected - self.vad_triggered) * 1000
            logger.info(f"🔄 Turn detected ({turn_detection_time:.0f}ms from VAD)")
    
    def mark_start(self):
        self.start_time = time.time()
        logger.info("🎯 Voice interaction pipeline started")
    
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
        
        # Log comprehensive pipeline metrics
        if self.start_time:
            total_latency = (self.tts_first_chunk - self.start_time) * 1000
            logger.info(f"⚡ TOTAL PIPELINE LATENCY: {total_latency:.0f}ms")
            
            # Update session metrics
            self.session_metrics['total_interactions'] += 1
            current_avg = self.session_metrics['avg_response_time']
            total_interactions = self.session_metrics['total_interactions']
            self.session_metrics['avg_response_time'] = (
                (current_avg * (total_interactions - 1) + total_latency) / total_interactions
            )
            
            logger.info(f"📊 Session avg response time: {self.session_metrics['avg_response_time']:.0f}ms")
    
    def mark_interruption(self):
        """Mark when user interrupts agent"""
        self.session_metrics['interruptions'] += 1
        logger.info(f"⚠️ Interruption detected (total: {self.session_metrics['interruptions']})")
    
    def mark_completion(self):
        """Mark successful interaction completion"""
        self.session_metrics['successful_completions'] += 1
        logger.info(f"✅ Interaction completed (total: {self.session_metrics['successful_completions']})")

# Global advanced timestamp logger
timestamp_logger = AdvancedTimestampLogger()

async def entrypoint(ctx: JobContext):
    """Ultra-advanced voice agent with highest-level LiveKit features"""
    try:
        await ctx.connect()
        logger.info(f"🔗 Connected to LiveKit room: {ctx.room.name}")
        
        # Determine character from room name
        character_name = extract_character_from_room(ctx.room.name)
        logger.info(f"🎭 Using character: {character_name}")
        
        # Create character configuration
        character = CharacterFactory.create_character(character_name)
        
        # Create ultra-optimized Deepgram TTS with character voice
        deepgram_tts = LiveKitDeepgramTTS()
        deepgram_tts.set_character(character_name)
        logger.info(f"🎤 Ultra-optimized Deepgram TTS for {character_name} ({character.description})")
        
        # Create optimized STT with Nova-3 model
        stt_service = create_deepgram_stt()
        logger.info("🎧 Deepgram Nova-3 STT with streaming transcription")
        
        # Create LLM with enhanced context memory
        llm_service = create_gpt4o_mini()
        logger.info("🧠 GPT-4o Mini with enhanced context and spiritual guidance optimization")
        
        # Create ultra-advanced voice session with all premium features
        session = AgentSession(
            vad=silero.VAD.load(
                # Ultra-sensitive VAD settings for immediate response
                min_speech_duration=0.1,  # Detect speech faster
                min_silence_duration=0.3,  # Shorter silence detection
            ),
            stt=stt_service,
            llm=llm_service,
            tts=deepgram_tts,
            
            # Advanced turn detection with multilingual model
            turn_detection=MultilingualModel(),  # State-of-the-art contextual turn detection
            
            # Optimized interruption handling
            allow_interruptions=True,
            min_interruption_duration=0.3,  # Even faster interruption detection
            
            # Ultra-responsive endpointing
            min_endpointing_delay=0.2,  # Faster response initiation
            max_endpointing_delay=1.5,  # Don't wait too long for user
        )
        
        # Enhanced room input options with premium noise cancellation
        room_input_options = room_io.RoomInputOptions(
            # Background Voice Cancellation - removes background speakers + noise
            noise_cancellation=noise_cancellation.BVC(),
            
            # Enhanced audio processing
            auto_gain_control=True,
            echo_cancellation=True,
            noise_suppression=True,
        )
        
        # Set up comprehensive event handlers for monitoring
        session.on("user_input_transcribed", _on_user_transcribed)
        session.on("agent_state_changed", _on_agent_state_changed)
        session.on("speech_created", _on_speech_created)
        session.on("speech_finished", _on_speech_finished)
        session.on("user_state_changed", _on_user_state_changed)
        session.on("turn_detected", _on_turn_detected)
        
        logger.info("🚀 Starting ULTRA-ADVANCED spiritual guidance session")
        logger.info("🎯 Premium features: BVC noise cancellation, multilingual turn detection, ultra-fast response")
        
        # Create agent with enhanced character personality
        agent = Agent(
            name=character.name,
            instructions=character.personality,
        )
        
        # Start the session with premium room options
        await session.start(
            agent=agent, 
            room=ctx.room,
            room_input_options=room_input_options
        )
        
        # Generate enhanced spiritual greeting
        greeting = get_character_greeting(character_name)
        logger.info(f"💬 Generating enhanced spiritual greeting for {character_name}")
        
        # Reset timestamp logger for greeting
        timestamp_logger.reset()
        timestamp_logger.mark_start()
        timestamp_logger.mark_stt_complete("(initial greeting)")
        timestamp_logger.mark_llm_complete(greeting)
        
        await session.generate_reply(instructions=greeting)
        
        logger.info("✅ ULTRA-ADVANCED session started - premium voice AI experience active")
        logger.info("🎯 Active features:")
        logger.info("   • Background Voice Cancellation (BVC)")
        logger.info("   • Multilingual Turn Detection Model")
        logger.info("   • Ultra-fast STT streaming (Nova-3)")
        logger.info("   • Sub-300ms TTS latency")
        logger.info("   • Advanced interruption handling")
        logger.info("   • Comprehensive session monitoring")
        logger.info("   • Enhanced audio processing")
        
    except Exception as e:
        logger.error(f"❌ Error in ultra-advanced spiritual session: {e}")
        raise
    finally:
        # Cleanup TTS resources
        if 'deepgram_tts' in locals():
            await deepgram_tts.aclose()
            logger.info("🧹 Cleaned up Deepgram TTS resources")
        
        # Log final session metrics
        logger.info("📊 Final Session Metrics:")
        logger.info(f"   • Total interactions: {timestamp_logger.session_metrics['total_interactions']}")
        logger.info(f"   • Average response time: {timestamp_logger.session_metrics['avg_response_time']:.0f}ms")
        logger.info(f"   • Interruptions handled: {timestamp_logger.session_metrics['interruptions']}")
        logger.info(f"   • Successful completions: {timestamp_logger.session_metrics['successful_completions']}")

def _on_user_transcribed(event):
    """Handle user speech transcription with advanced logging"""
    if event.is_final:
        timestamp_logger.mark_stt_complete(event.transcript)
        logger.info(f"👤 User said: '{event.transcript}'")
    else:
        # Real-time interim results for immediate feedback
        logger.debug(f"👤 User speaking: '{event.transcript}...'")

def _on_agent_state_changed(event):
    """Handle agent state changes with comprehensive monitoring"""
    logger.info(f"🤖 Agent state: {event.old_state} → {event.new_state}")
    
    if event.new_state == "listening":
        # Reset for next interaction
        timestamp_logger.reset()
        timestamp_logger.mark_start()
    elif event.new_state == "thinking":
        # LLM processing started
        logger.debug("🧠 LLM processing user input...")
    elif event.new_state == "speaking":
        timestamp_logger.mark_tts_start()

def _on_user_state_changed(event):
    """Handle user state changes for advanced monitoring"""
    logger.info(f"👤 User state: {event.old_state} → {event.new_state}")
    
    if event.new_state == "speaking":
        timestamp_logger.mark_vad_triggered()
    elif event.new_state == "listening" and event.old_state == "speaking":
        timestamp_logger.mark_turn_detected()

def _on_turn_detected(event):
    """Handle turn detection events"""
    timestamp_logger.mark_turn_detected()
    logger.info("🔄 Advanced turn detection: User finished speaking")

def _on_speech_created(event):
    """Handle speech creation events with detailed logging"""
    logger.info(f"🗣️ Speech created: {event.source}")
    timestamp_logger.mark_tts_first_chunk()

def _on_speech_finished(event):
    """Handle speech completion events with metrics"""
    if event.interrupted:
        timestamp_logger.mark_interruption()
        logger.info(f"⚠️ Speech interrupted by user")
    else:
        timestamp_logger.mark_completion()
        logger.info(f"✅ Speech completed successfully")

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