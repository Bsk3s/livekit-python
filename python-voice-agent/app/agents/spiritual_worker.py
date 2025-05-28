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
                llm_service = create_gpt4o_mini()
                logger.info("✅ LLM service created")
            except Exception as e:
                logger.error(f"❌ Failed to create LLM service: {e}")
                raise
            
            try:
                # Use simple OpenAI TTS instead of custom Deepgram TTS for stability
                from livekit.plugins import openai
                tts_service = openai.TTS(voice="alloy")  # Simple, reliable TTS
                logger.info("✅ TTS service created (OpenAI)")
            except Exception as e:
                logger.error(f"❌ Failed to create TTS service: {e}")
                raise
            
            logger.info(f"🚀 Services initialized for {character_name}")
            logger.info(f"   🎤 TTS: OpenAI Alloy")
            logger.info(f"   🎧 STT: Deepgram Nova-3")
            logger.info(f"   🧠 LLM: GPT-4o Mini")
            
            # Create simplified agent session (remove complex parameters)
            try:
                session = AgentSession(
                    vad=silero.VAD.load(),
                    stt=stt_service,
                    llm=llm_service,
                    tts=tts_service,
                    # Only include turn_detection if available
                    **({"turn_detection": MultilingualModel()} if TURN_DETECTOR_AVAILABLE else {}),
                    # Use basic interruption settings
                    allow_interruptions=True,
                )
                logger.info("✅ Agent session created")
            except Exception as e:
                logger.error(f"❌ Failed to create agent session: {e}")
                raise
            
            # Create agent with character personality
            try:
                agent = Agent(
                    name=character.name,
                    instructions=character.personality,
                )
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
            
            # Generate welcome greeting (simplified)
            try:
                greeting = f"Hello! I'm {character.name}, and I'm here to provide spiritual guidance and support. How can I help you today?"
                await session.generate_reply(instructions=f"Say this greeting warmly: {greeting}")
                logger.info(f"✅ Welcome greeting sent")
            except Exception as e:
                logger.error(f"❌ Failed to generate greeting: {e}")
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
        # Set worker permissions
        permissions=None,  # Use defaults: can publish, subscribe, publish data
    )
    
    try:
        logger.info("🚀 Starting LiveKit Agent Worker...")
        # Start the agent worker
        cli.run_app(worker_options)
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
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