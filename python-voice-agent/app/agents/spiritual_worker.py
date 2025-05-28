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
from app.services.deepgram_service import DeepgramSTTService
from app.services.llm_service import LLMService
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
            
            # Create optimized services
            deepgram_tts = LiveKitDeepgramTTS()
            deepgram_tts.set_character(character_name)
            
            stt_service = DeepgramSTTService()
            llm_service = LLMService()
            
            logger.info(f"🚀 Services initialized for {character_name}")
            logger.info(f"   🎤 TTS: Deepgram {deepgram_tts.VOICE_CONFIGS[character_name]['model']}")
            logger.info(f"   🎧 STT: Deepgram Nova-3")
            logger.info(f"   🧠 LLM: GPT-4o Mini")
            
            # Create enhanced agent session
            session = AgentSession(
                vad=silero.VAD.load(),
                stt=stt_service,
                llm=llm_service,
                tts=deepgram_tts,
                turn_detection=MultilingualModel() if TURN_DETECTOR_AVAILABLE else None,
                allow_interruptions=True,
                min_interruption_duration=0.5,
                min_endpointing_delay=0.3,
                max_endpointing_delay=2.0,
            )
            
            # Set up event handlers
            session.on("user_input_transcribed", self._on_user_transcribed)
            session.on("agent_state_changed", self._on_agent_state_changed)
            session.on("speech_created", self._on_speech_created)
            session.on("speech_finished", self._on_speech_finished)
            
            # Create agent with character personality
            agent = Agent(
                name=character.name,
                instructions=character.personality,
            )
            
            # Track active session
            self.active_sessions[room_name] = session
            
            logger.info(f"✨ {character_name.title()} is ready for spiritual guidance in {room_name}")
            
            # Start the session
            await session.start(agent=agent, room=ctx.room)
            
            # Generate welcome greeting
            greeting = self._get_character_greeting(character_name)
            await session.generate_reply(instructions=greeting)
            
            logger.info(f"🎉 {character_name.title()} session started successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in spiritual agent session: {e}")
            raise
        finally:
            # Cleanup
            if room_name in self.active_sessions:
                del self.active_sessions[room_name]
            
            if 'deepgram_tts' in locals():
                await deepgram_tts.aclose()
            
            logger.info(f"🧹 Cleaned up session for room {room_name}")
    
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
    
    # Configure worker options for production
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        # Production optimizations
        max_retry_count=3,
        retry_interval=5.0,
        # Resource limits
        max_concurrent_jobs=10,  # Adjust based on server capacity
    )
    
    try:
        # Start the agent worker
        cli.run_app(worker_options)
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Worker crashed: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Spiritual Agent Worker shutdown complete")

if __name__ == "__main__":
    main() 