#!/usr/bin/env python3
"""
Production Spiritual Guidance Agent Worker
Runs continuously on Render, spawning character instances when users join rooms
Deployment: January 29, 2025 - Ensuring worker service is active alongside API
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm, stt, tts
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import deepgram, openai, silero

# CRITICAL: Sanitize environment variables to fix API key issues
# Remove any trailing whitespace/newlines that cause "illegal header value" errors
if os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY").strip()

if os.getenv("DEEPGRAM_API_KEY"):
    os.environ["DEEPGRAM_API_KEY"] = os.getenv("DEEPGRAM_API_KEY").strip()

load_dotenv()

# Configure production logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        (
            logging.FileHandler("spiritual_agent.log")
            if not os.getenv("RENDER")
            else logging.StreamHandler(sys.stdout)
        ),
    ],
)
logger = logging.getLogger(__name__)

# Turn detector removed - using stable VAD-based detection only
TURN_DETECTOR_AVAILABLE = False
logger.info("🔄 Using stable VAD-based turn detection (turn detector disabled)")

from spiritual_voice_agent.characters.character_factory import CharacterFactory

# Import our services - clean imports, no sys.path hacks!
from spiritual_voice_agent.services.llm_service import create_gpt4o_mini

# Import metrics service for performance tracking
from spiritual_voice_agent.services.metrics_service import (
    get_metrics_service,
    PipelineMetrics,
    QualityMetrics,
    ContextMetrics,
    timing_context,
)


class SpiritualAgentWorker:
    """Production agent worker for spiritual guidance sessions"""

    def __init__(self):
        self.active_sessions: Dict[str, AgentSession] = {}
        self.shutdown_requested = False
        
        # 📊 METRICS TRACKING - Performance measurement
        self._metrics_service = get_metrics_service()
        self._conversation_timings: Dict[str, Dict] = {}  # Track timing per room
        self._session_start_times: Dict[str, float] = {}  # Track session start times

        # Validate environment variables
        self._validate_environment()

        logger.info("🌟 Spiritual Agent Worker initialized")
        logger.info(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL')}")
        logger.info(f"🎭 Available characters: {list(CharacterFactory.CHARACTER_CONFIGS.keys())}")

    def _validate_environment(self):
        """Validate all required environment variables are present"""
        required_vars = [
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
            "OPENAI_API_KEY",
            "DEEPGRAM_API_KEY",  # RESTORED: Required for Deepgram STT
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            raise ValueError(f"Missing environment variables: {missing_vars}")

        logger.info("✅ All required environment variables present")

    def _start_conversation_timing(self, room_name: str) -> None:
        """Start timing a new conversation in a room"""
        import time
        
        self._conversation_timings[room_name] = {
            "turn_start_time": time.perf_counter(),
            "stage_timings": {}
        }
        logger.debug(f"📊 Started timing for room: {room_name}")

    def _record_stage_timing(self, room_name: str, stage: str, duration_ms: float) -> None:
        """Record timing for a specific pipeline stage"""
        if room_name in self._conversation_timings:
            self._conversation_timings[room_name]["stage_timings"][stage] = duration_ms
            logger.debug(f"📊 {room_name} - {stage}: {duration_ms:.1f}ms")

    async def _log_agent_metrics_event(self, room_name: str, character_name: str, success: bool, 
                                      user_input: str = "", ai_response: str = "", 
                                      error_message: str = None) -> None:
        """Log a complete metrics event for LiveKit agent"""
        if room_name not in self._conversation_timings:
            return  # No timing data to log
        
        try:
            import time
            
            # Calculate total turn time
            turn_data = self._conversation_timings[room_name]
            total_latency_ms = (time.perf_counter() - turn_data["turn_start_time"]) * 1000
            
            # Get TTS model info (simplified for LiveKit agent)
            tts_model = os.getenv("TTS_MODEL", "openai").lower()
            
            # Create metrics objects
            pipeline_metrics = PipelineMetrics(
                total_latency_ms=total_latency_ms,
                stt_latency_ms=turn_data["stage_timings"].get("stt"),
                llm_latency_ms=turn_data["stage_timings"].get("llm"),
                tts_first_chunk_ms=turn_data["stage_timings"].get("tts"),
                audio_processing_ms=turn_data["stage_timings"].get("audio_processing")
            )
            
            quality_metrics = QualityMetrics(
                success=success,
                error_message=error_message
            )
            
            # Calculate session duration
            session_duration = 0
            if room_name in self._session_start_times:
                session_duration = time.time() - self._session_start_times[room_name]
            
            context_metrics = ContextMetrics(
                user_input_length=len(user_input),
                ai_response_length=len(ai_response),
                session_duration_s=session_duration,
                conversation_turn=len([r for r in self._conversation_timings if r == room_name])
            )
            
            # Log the event
            await self._metrics_service.log_event(
                session_id=room_name,  # Use room name as session ID for LiveKit
                character=character_name,
                tts_model=tts_model,
                pipeline_metrics=pipeline_metrics,
                quality_metrics=quality_metrics,
                context_metrics=context_metrics,
                source="livekit_agent"
            )
            
            logger.debug(f"📊 LiveKit metrics logged for {room_name}: {total_latency_ms:.0f}ms total")
            
        except Exception as e:
            logger.warning(f"📊 Failed to log LiveKit metrics: {e}")  # Don't let metrics break the agent

    async def entrypoint(self, ctx: JobContext):
        """Main agent entry point - spawns character instances"""
        try:
            await ctx.connect()
            room_name = ctx.room.name

            logger.info(f"🔗 Connected to room: {room_name}")
            logger.info(f"👥 Participants in room: {len(ctx.room.remote_participants)}")

            # Extract character from room name
            character_name = self._extract_character_from_room(room_name)

            if not character_name:
                logger.warning(f"⚠️ Could not determine character from room name: {room_name}")
                character_name = "adina"  # Default fallback

            logger.info(f"🎭 Spawning {character_name} for room {room_name}")

            # Create character instance
            character = CharacterFactory.create_character(character_name)

            # Create services
            try:
                # 🎧 DEEPGRAM STT (Nova-3 model for high accuracy)
                logger.info("🎧 Creating Deepgram STT service...")
                stt_service = deepgram.STT(
                    model="nova-2",  # High-quality Nova model
                    language="en-US",  # US English for spiritual guidance
                )
                logger.info("✅ Deepgram STT service created")
                logger.info("   🎧 Model: Nova-2 (high accuracy)")
                logger.info("   🌍 Language: en-US")
            except Exception as e:
                logger.error(f"❌ Failed to create STT service: {e}")
                raise

            try:
                llm_service = create_gpt4o_mini()
                logger.info("✅ LLM service created")
            except Exception as e:
                logger.error(f"❌ Failed to create LLM service: {e}")
                # Add retry logic for LLM service creation
                logger.info("🔄 Retrying LLM service creation...")
                try:
                    import time

                    time.sleep(2)  # Brief pause before retry
                    llm_service = create_gpt4o_mini()
                    logger.info("✅ LLM service created on retry")
                except Exception as retry_e:
                    logger.error(f"❌ LLM service retry also failed: {retry_e}")
                    raise

            try:
                # 🎙️ TTS SERVICE: Use configurable TTS factory for easy model swapping
                logger.info("🎙️ Creating TTS service with factory...")

                # Import TTS factory for easy model swapping
                from spiritual_voice_agent.services.tts_factory import TTSFactory

                # Create TTS service - easily configurable via environment
                tts_service = TTSFactory.create_tts(character_name)
                logger.info(f"✅ TTS service created for {character_name}")
                logger.info("🔧 TTS model configurable via TTS_MODEL environment variable")

            except Exception as e:
                logger.error(f"❌ Failed to create TTS service: {e}")
                # 🛡️ EMERGENCY FALLBACK: Basic OpenAI TTS
                logger.info("🛡️ EMERGENCY: Using basic OpenAI TTS fallback")
                try:
                    tts_service = openai.TTS()  # Use absolute defaults
                    logger.info("✅ Emergency TTS fallback created")
                except Exception as emergency_e:
                    logger.error(f"❌ Emergency fallback failed: {emergency_e}")
                    raise Exception("All TTS services failed - cannot proceed")

            logger.info(f"🚀 Services initialized for {character_name}")
            logger.info(f"   🎙️ TTS: {tts_service.__class__.__name__}")
            logger.info(f"   🎧 STT: Deepgram STT")
            logger.info(f"   🧠 LLM: GPT-4o Mini")

            # Create enhanced agent session with streaming TTS
            try:
                logger.info("🚀 Creating real-time session with streaming TTS...")

                session = AgentSession(
                    vad=silero.VAD.load(
                        min_speech_duration=0.02,  # Quick speech detection
                        min_silence_duration=0.05,  # Fast silence detection
                    ),
                    stt=stt_service,
                    llm=llm_service,
                    tts=tts_service,  # ElevenLabs or OpenAI TTS
                    allow_interruptions=True,
                    min_interruption_duration=0.05,
                    min_endpointing_delay=0.05,
                    max_endpointing_delay=0.5,
                )
                logger.info("✅ Real-time session created with streaming TTS")
                logger.info("🔗 TTS service properly wired into AgentSession pipeline")

                # Log final configuration
                from spiritual_voice_agent.services.tts_factory import get_tts_config

                tts_config = get_tts_config()
                logger.info(
                    f"   🎙️ TTS: {tts_config['current_model']} ({tts_service.__class__.__name__})"
                )
                logger.info(f"   🎧 STT: Deepgram STT")
                logger.info(f"   🧠 LLM: GPT-4o Mini (optimized)")
                logger.info(f"   ⚡ Target: Natural voice with streaming")

            except Exception as e:
                logger.error(f"❌ Failed to create enhanced agent session: {e}")
                # Try with basic parameters if advanced ones fail
                logger.info("🔄 Falling back to basic agent session...")
                try:
                    session = AgentSession(
                        vad=silero.VAD.load(),
                        stt=stt_service,
                        llm=llm_service,
                        tts=tts_service,
                        allow_interruptions=True,
                    )
                    logger.info("✅ Basic agent session created with TTS service")
                except Exception as fallback_e:
                    logger.error(f"❌ Basic agent session also failed: {fallback_e}")
                    raise

            # Restore advanced event handlers for conversation monitoring
            try:
                session.on("user_input_transcribed", self._on_user_transcribed)
                session.on("agent_state_changed", self._on_agent_state_changed)
                session.on("speech_created", self._on_speech_created)
                session.on("speech_finished", self._on_speech_finished)
                logger.info("✅ Advanced event handlers attached")
            except Exception as e:
                logger.warning(f"⚠️ Could not attach event handlers: {e}")
                # Continue without event handlers - not critical

            # Create agent with character personality - USE STANDARD AGENT
            try:
                # 🔧 SIMPLIFIED: Use standard Agent class since TTS is now in AgentSession
                agent = Agent(instructions=character.personality)
                logger.info(f"✅ Standard Agent created for {character.name}")
                logger.info("🔗 TTS pipeline handled by AgentSession automatically")
            except Exception as e:
                logger.error(f"❌ Failed to create agent: {e}")
                raise

            # Track active session
            self.active_sessions[room_name] = session
            
            # 📊 METRICS: Track session start time
            import time
            self._session_start_times[room_name] = time.time()

            logger.info(
                f"✨ {character_name.title()} is ready for spiritual guidance in {room_name}"
            )

            # Start the session
            try:
                await session.start(agent=agent, room=ctx.room)
                logger.info(f"✅ Session started for {character_name}")

                # Session started successfully - LLM will respond to user input automatically
                logger.info(f"ℹ️ {character_name.title()} is ready to respond to user input")
                logger.info(f"🎉 {character_name.title()} session started successfully")

            except Exception as e:
                logger.error(f"❌ Failed to start session: {e}")
                raise

        except Exception as e:
            logger.error(f"❌ Error in spiritual agent session: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback

            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Cleanup
            if "room_name" in locals() and room_name in self.active_sessions:
                del self.active_sessions[room_name]

            # Cleanup TTS service if it's WebSocket Deepgram
            if "tts_service" in locals() and hasattr(tts_service, "aclose"):
                try:
                    await tts_service.aclose()
                    logger.info("🧹 WebSocket TTS service closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing WebSocket TTS service: {e}")

            # Cleanup STT service if it has rate limiting
            if "stt_service" in locals() and hasattr(stt_service, "aclose"):
                try:
                    await stt_service.aclose()
                    logger.info("🧹 Rate-limited STT service closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing STT service: {e}")

            logger.info(f"🧹 Cleaned up session for room {locals().get('room_name', 'unknown')}")

    def _extract_character_from_room(self, room_name: str) -> Optional[str]:
        """Extract character name from room name (spiritual-{character}-{session_id})"""
        try:
            parts = room_name.lower().split("-")
            if len(parts) >= 2 and parts[0] == "spiritual":
                character = parts[1]
                if character in CharacterFactory.CHARACTER_CONFIGS:
                    return character

            logger.warning(f"Could not parse character from room name: {room_name}")
            return None

        except Exception as e:
            logger.error(f"Error parsing room name {room_name}: {e}")
            return None

    def _get_character_greeting_text(self, character: str) -> str:
        """Get character-specific greeting text to be spoken"""
        config = CharacterFactory.get_character_config(character)

        greetings = {
            "adina": "Welcome, dear soul. I'm Adina, and I'm so glad you're here with me today. Know that you are not alone on this journey; I'm here to offer you comfort, support, and gentle wisdom as you navigate whatever you're experiencing. Let's take this time together to find peace and healing.",
            "raffa": "Greetings, my friend. I'm Raffa, and I welcome you with open arms to this sacred space. I'm here to walk alongside you, offering spiritual guidance, biblical wisdom, and caring insight for your life's journey. You are heard, you are valued, and together we'll seek the wisdom you need.",
        }

        return greetings.get(character, greetings["adina"])

    def _get_character_greeting(self, character: str) -> str:
        """Get character-specific greeting instructions"""
        config = CharacterFactory.get_character_config(character)

        greetings = {
            "adina": f"""Generate a {config['greeting_style']} greeting as Adina. 
            Welcome the user warmly to this spiritual guidance session. Let them know you're here 
            to provide comfort, support, and gentle wisdom for whatever they're experiencing. 
            Speak naturally and conversationally, like a caring friend. Keep it brief (10-15 seconds).""",
            "raffa": f"""Generate a {config['greeting_style']} greeting as Raffa. 
            Welcome the user with wisdom and gentle authority. Let them know you're here to offer 
            spiritual guidance, biblical wisdom, and caring insight for their life's journey. 
            Speak with warmth and make them feel heard and understood. Keep it brief (10-15 seconds).""",
        }

        return greetings.get(character, greetings["adina"])

    def _on_user_transcribed(self, event):
        """Handle user speech transcription with metrics tracking"""
        if event.is_final:
            logger.info(f"👤 User: '{event.transcript}'")
            
            # 📊 METRICS: Start timing for this conversation turn
            # Extract room name from event context
            room_name = getattr(event, 'room_name', 'unknown_room')
            if hasattr(event, 'session') and hasattr(event.session, 'room'):
                room_name = event.session.room.name
            
            self._start_conversation_timing(room_name)

    def _on_agent_state_changed(self, event):
        """Handle agent state changes with metrics tracking"""
        logger.info(f"🤖 Agent state: {event.old_state} → {event.new_state}")
        
        # 📊 METRICS: Track timing for different agent states
        if hasattr(event, 'session') and hasattr(event.session, 'room'):
            room_name = event.session.room.name
            
            # Track different processing stages based on state changes
            if event.new_state == "thinking":
                # LLM processing started
                pass  # Start time already captured in user_transcribed
            elif event.new_state == "speaking":
                # TTS processing started (LLM finished)
                if room_name in self._conversation_timings:
                    # Estimate LLM completion time (simplified)
                    import time
                    current_time = time.perf_counter()
                    start_time = self._conversation_timings[room_name]["turn_start_time"]
                    llm_duration = (current_time - start_time) * 1000
                    self._record_stage_timing(room_name, "llm", llm_duration)

    def _on_speech_created(self, event):
        """Handle speech creation with metrics tracking"""
        logger.debug(f"🗣️ Speech created: {event.source}")
        
        # 📊 METRICS: Track TTS start time
        if hasattr(event, 'session') and hasattr(event.session, 'room'):
            room_name = event.session.room.name
            if room_name in self._conversation_timings:
                import time
                self._conversation_timings[room_name]["tts_start_time"] = time.perf_counter()

    def _on_speech_finished(self, event):
        """Handle speech completion with metrics tracking"""
        logger.info(f"✅ Speech finished: interrupted={event.interrupted}")
        
        # 📊 METRICS: Complete the conversation turn and log metrics
        if hasattr(event, 'session') and hasattr(event.session, 'room'):
            room_name = event.session.room.name
            
            # Calculate TTS timing
            if (room_name in self._conversation_timings and 
                "tts_start_time" in self._conversation_timings[room_name]):
                import time
                tts_duration = (time.perf_counter() - 
                              self._conversation_timings[room_name]["tts_start_time"]) * 1000
                self._record_stage_timing(room_name, "tts", tts_duration)
            
            # Log the complete metrics event (simplified for LiveKit)
            character_name = self._extract_character_from_room(room_name) or "unknown"
            
            # Create async task to log metrics (don't block the agent)
            import asyncio
            asyncio.create_task(self._log_agent_metrics_event(
                room_name=room_name,
                character_name=character_name,
                success=not event.interrupted,  # Success if not interrupted
                user_input="",  # Would need to track from transcription
                ai_response="",  # Would need to track from speech generation
            ))

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""

        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


# Global worker instance
spiritual_worker = SpiritualAgentWorker()


async def entrypoint(ctx: JobContext):
    """Entry point for LiveKit agent framework"""
    await spiritual_worker.entrypoint(ctx)


def main():
    """Main function for production deployment"""
    logger.info("🌟 Starting Spiritual Guidance Agent Worker")
    logger.info(f"🕐 Started at: {datetime.utcnow().isoformat()}Z")

    # Setup signal handlers for graceful shutdown
    spiritual_worker.setup_signal_handlers()

    # Configure worker options for production with proper settings
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        # Set a reasonable load threshold (default is 0.75)
        load_threshold=0.8,
        # Allow time for graceful shutdown (30 minutes default)
        drain_timeout=1800,  # 30 minutes in seconds
        # Don't set permissions to None - let it use defaults
    )

    try:
        logger.info("🚀 Starting LiveKit Agent Worker...")
        # Start the agent worker
        cli.run_app(worker_options)
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Worker crashed: {e}")
        logger.error(f"💥 Error type: {type(e).__name__}")
        import traceback

        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        logger.info("👋 Spiritual Agent Worker shutdown complete")


if __name__ == "__main__":
    main()
