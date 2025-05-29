#!/usr/bin/env python3
"""
Production Spiritual Guidance Agent Worker
Runs continuously on Render, spawning character instances when users join rooms
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Dict, Optional
from datetime import datetime

# Add the parent directory to Python path for module resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from livekit.agents import (
    Agent, AgentSession, JobContext, WorkerOptions, cli
)
from livekit.plugins import deepgram, openai, silero
from dotenv import load_dotenv

load_dotenv()

# Configure production logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('spiritual_agent.log') if not os.getenv('RENDER') else logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Try to import turn detector, but make it optional
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    TURN_DETECTOR_AVAILABLE = True
    logger.info("✅ Turn detector plugin available")
except ImportError as e:
    TURN_DETECTOR_AVAILABLE = False
    logger.warning(f"⚠️ Turn detector plugin not available: {e}")
    logger.info("🔄 Agent will use standard VAD-based turn detection")

from app.characters.character_factory import CharacterFactory
from app.services.deepgram_service import create_deepgram_stt
from app.services.llm_service import create_gpt4o_mini
from app.services.livekit_deepgram_tts import LiveKitDeepgramTTS

class SpiritualAgentWorker:
    """Production agent worker for spiritual guidance sessions"""
    
    def __init__(self):
        self.active_sessions: Dict[str, AgentSession] = {}
        self.shutdown_requested = False
        
        # Validate environment variables
        self._validate_environment()
        
        logger.info("🌟 Spiritual Agent Worker initialized")
        logger.info(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL')}")
        logger.info(f"🎭 Available characters: {list(CharacterFactory.CHARACTER_CONFIGS.keys())}")
    
    def _validate_environment(self):
        """Validate all required environment variables are present"""
        required_vars = [
            'LIVEKIT_URL',
            'LIVEKIT_API_KEY', 
            'LIVEKIT_API_SECRET',
            'DEEPGRAM_API_KEY',
            'OPENAI_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            raise ValueError(f"Missing environment variables: {missing_vars}")
        
        logger.info("✅ All required environment variables present")
    
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
            
            # Create basic services (simplified for stability)
            try:
                stt_service = create_deepgram_stt()
                logger.info("✅ STT service created")
            except Exception as e:
                logger.error(f"❌ Failed to create STT service: {e}")
                raise
            
            try:
                llm_service = create_gpt4o_mini(instructions=character.personality)
                logger.info("✅ LLM service created")
            except Exception as e:
                logger.error(f"❌ Failed to create LLM service: {e}")
                raise
            
            try:
                # Restore advanced Deepgram TTS with character-specific voices
                deepgram_tts = LiveKitDeepgramTTS()
                deepgram_tts.set_character(character_name)
                logger.info(f"✅ TTS service created (Deepgram {deepgram_tts.VOICE_CONFIGS[character_name]['model']})")
            except Exception as e:
                logger.error(f"❌ Failed to create Deepgram TTS service: {e}")
                # Fallback to OpenAI TTS if Deepgram fails
                logger.info("🔄 Falling back to OpenAI TTS...")
                try:
                    from livekit.plugins import openai
                    deepgram_tts = openai.TTS(voice="alloy")
                    logger.info("✅ TTS service created (OpenAI fallback)")
                except Exception as fallback_e:
                    logger.error(f"❌ Fallback TTS also failed: {fallback_e}")
                    raise
            
            logger.info(f"🚀 Services initialized for {character_name}")
            try:
                # Try to log Deepgram voice model if available
                if hasattr(deepgram_tts, 'VOICE_CONFIGS') and character_name in deepgram_tts.VOICE_CONFIGS:
                    logger.info(f"   🎤 TTS: Deepgram {deepgram_tts.VOICE_CONFIGS[character_name]['model']}")
                else:
                    logger.info(f"   🎤 TTS: OpenAI (fallback)")
            except:
                logger.info(f"   🎤 TTS: Service created")
            logger.info(f"   🎧 STT: Deepgram Nova-3")
            logger.info(f"   🧠 LLM: GPT-4o Mini")
            
            # Create enhanced agent session with advanced parameters
            try:
                # 🚀 ULTIMATE ADVANCED FEATURE: Try OpenAI Realtime API first (most cutting-edge)
                logger.info("🚀 Attempting ULTRA-ADVANCED OpenAI Realtime API mode...")
                try:
                    from livekit.plugins.openai import realtime
                    
                    # Create ultra-advanced Realtime API session
                    realtime_model = realtime.RealtimeModel(
                        instructions=character.personality,
                        voice="alloy" if character_name == "adina" else "echo",  # Character-specific voices
                        temperature=0.7,  # Optimized for spiritual guidance
                        modalities=["text", "audio"],  # Full multimodal support
                        turn_detection=realtime.ServerVadOptions(
                            threshold=0.5,
                            prefix_padding_ms=300,
                            silence_duration_ms=500,
                            create_response=True
                        ),
                        max_response_output_tokens="inf",  # Unlimited response length
                    )
                    
                    session = AgentSession(
                        llm=realtime_model,  # Use Realtime API as LLM
                        # No separate STT/TTS needed - Realtime API handles everything
                        allow_interruptions=True,
                    )
                    
                    logger.info("🎉 ULTRA-ADVANCED OpenAI Realtime API session created!")
                    logger.info(f"   🎤 Voice: OpenAI Realtime {'Alloy' if character_name == 'adina' else 'Echo'}")
                    logger.info(f"   🎧 STT: OpenAI Realtime (built-in)")
                    logger.info(f"   🧠 LLM: GPT-4o Realtime (multimodal)")
                    logger.info(f"   🔄 Turn Detection: Server VAD (advanced)")
                    
                except Exception as realtime_e:
                    logger.warning(f"⚠️ OpenAI Realtime API not available: {realtime_e}")
                    logger.info("🔄 Falling back to advanced traditional pipeline...")
                    
                    # Fallback to our ultra-optimized traditional pipeline
                    session = AgentSession(
                        vad=silero.VAD.load(),
                        stt=stt_service,
                        llm=llm_service,
                        tts=deepgram_tts,
                        # Only include turn_detection if available
                        **({"turn_detection": MultilingualModel()} if TURN_DETECTOR_AVAILABLE else {}),
                        # Restore advanced interruption settings for natural conversation
                        allow_interruptions=True,
                        min_interruption_duration=0.5,
                        min_endpointing_delay=0.3,
                        max_endpointing_delay=2.0,
                    )
                    logger.info("✅ Advanced traditional pipeline session created")
                    try:
                        if hasattr(deepgram_tts, 'VOICE_CONFIGS') and character_name in deepgram_tts.VOICE_CONFIGS:
                            logger.info(f"   🎤 TTS: Deepgram {deepgram_tts.VOICE_CONFIGS[character_name]['model']}")
                        else:
                            logger.info(f"   🎤 TTS: OpenAI (fallback)")
                    except:
                        logger.info(f"   🎤 TTS: Service created")
                    logger.info(f"   🎧 STT: Deepgram Nova-3")
                    logger.info(f"   🧠 LLM: GPT-4o Mini")
                
                logger.info("✅ Enhanced agent session created with maximum advanced features")
            except Exception as e:
                logger.error(f"❌ Failed to create enhanced agent session: {e}")
                # Try with basic parameters if advanced ones fail
                logger.info("🔄 Falling back to basic agent session...")
                try:
                    session = AgentSession(
                        vad=silero.VAD.load(),
                        stt=stt_service,
                        llm=llm_service,
                        tts=deepgram_tts,
                        allow_interruptions=True,
                    )
                    logger.info("✅ Basic agent session created")
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
            
            # Create agent with character personality
            try:
                # Agent class doesn't accept name or instructions parameters
                # These are handled through the session
                agent = Agent()
                logger.info(f"✅ Agent created for {character.name}")
            except Exception as e:
                logger.error(f"❌ Failed to create agent: {e}")
                raise
            
            # Track active session
            self.active_sessions[room_name] = session
            
            logger.info(f"✨ {character_name.title()} is ready for spiritual guidance in {room_name}")
            
            # Start the session
            try:
                await session.start(agent=agent, room=ctx.room)
                logger.info(f"✅ Session started for {character_name}")
            except Exception as e:
                logger.error(f"❌ Failed to start session: {e}")
                raise
            
            # Generate advanced character-specific greeting
            try:
                greeting = self._get_character_greeting(character_name)
                await session.generate_reply(instructions=greeting)
                logger.info(f"✅ Character-specific welcome greeting sent for {character_name}")
            except Exception as e:
                logger.error(f"❌ Failed to generate character greeting: {e}")
                # Fallback to simple greeting
                try:
                    simple_greeting = f"Hello! I'm {character.name}, and I'm here to provide spiritual guidance and support. How can I help you today?"
                    await session.generate_reply(instructions=f"Say this greeting warmly: {simple_greeting}")
                    logger.info(f"✅ Simple fallback greeting sent")
                except Exception as fallback_e:
                    logger.error(f"❌ Even simple greeting failed: {fallback_e}")
                    # Don't raise - greeting failure shouldn't kill the session
            
            logger.info(f"🎉 {character_name.title()} session started successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in spiritual agent session: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Cleanup
            if 'room_name' in locals() and room_name in self.active_sessions:
                del self.active_sessions[room_name]
            
            # Cleanup TTS service if it's Deepgram
            if 'deepgram_tts' in locals() and hasattr(deepgram_tts, 'aclose'):
                try:
                    await deepgram_tts.aclose()
                    logger.info("🧹 Deepgram TTS service closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing TTS service: {e}")
            
            logger.info(f"🧹 Cleaned up session for room {locals().get('room_name', 'unknown')}")
    
    def _extract_character_from_room(self, room_name: str) -> Optional[str]:
        """Extract character name from room name (spiritual-{character}-{session_id})"""
        try:
            parts = room_name.lower().split('-')
            if len(parts) >= 2 and parts[0] == 'spiritual':
                character = parts[1]
                if character in CharacterFactory.CHARACTER_CONFIGS:
                    return character
            
            logger.warning(f"Could not parse character from room name: {room_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing room name {room_name}: {e}")
            return None
    
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
            Speak with warmth and make them feel heard and understood. Keep it brief (10-15 seconds)."""
        }
        
        return greetings.get(character, greetings["adina"])
    
    def _on_user_transcribed(self, event):
        """Handle user speech transcription"""
        if event.is_final:
            logger.info(f"👤 User: '{event.transcript}'")
    
    def _on_agent_state_changed(self, event):
        """Handle agent state changes"""
        logger.info(f"🤖 Agent state: {event.old_state} → {event.new_state}")
    
    def _on_speech_created(self, event):
        """Handle speech creation"""
        logger.debug(f"🗣️ Speech created: {event.source}")
    
    def _on_speech_finished(self, event):
        """Handle speech completion"""
        logger.info(f"✅ Speech finished: interrupted={event.interrupted}")
    
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