#!/usr/bin/env python3
"""
CUSTOM TTS AGENT - Production Voice AI with Kokoro TTS

This agent bypasses LiveKit's TTS framework using tts_node() override for direct audio control.
- Uses Kokoro TTS for high-quality, cost-free voice synthesis
- Implements sentence buffering for smooth, natural speech
- Supports real-time voice conversations with minimal latency
- Hardcoded to Adina character (af_heart voice) for stability
"""
import asyncio
import logging
import os
import numpy as np
import wave
import io
from typing import AsyncIterable, AsyncGenerator
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    ModelSettings,
)
# STTSegment import removed - using dynamic approach
from livekit.plugins import deepgram, openai, silero
from livekit import rtc

# REAL DATA COLLECTION IMPORTS
from spiritual_voice_agent.services.conversation import get_conversation_tracker
from spiritual_voice_agent.services.analytics.performance_metrics import get_performance_tracker
from spiritual_voice_agent.services.websocket import get_websocket_manager
from datetime import datetime
import time
import httpx

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



class CustomTTSAgent(Agent):
    def __init__(self, character: str = "adina") -> None:
        # Set character-specific instructions
        if character == "raffa":
            instructions = (
                "You are Raffa, a wise spiritual mentor and guide. Provide paternal wisdom, biblical guidance, and strength. "
                "Speak with gentle authority and warm masculinity, suitable for voice interaction. "
                "Help users on their spiritual journey with strength, wisdom, and scriptural insight."
            )
        else:  # adina
            instructions = (
                "You are Adina, a compassionate spiritual guide. Provide wisdom, comfort, and biblical guidance. "
                "Keep responses conversational and warm, suitable for voice interaction. "
                "Help users on their spiritual journey with empathy and scriptural insight."
            )
            
        super().__init__(instructions=instructions)
        
        # Store character for voice selection
        self.character = character
        logger.info(f"🎭 CustomTTSAgent initialized as: {self.character}")
        
        # Character-specific voice mapping for Kokoro TTS
        self.voice_map = {
            "adina": "adina",    # Maps to af_heart in Kokoro server
            "raffa": "raffa",    # Maps to am_michael in Kokoro server (updated voice)
        }
        
        self.selected_voice = self.voice_map.get(character, "adina")
        logger.info(f"🎵 Voice selected: {self.selected_voice} for character {self.character}")
        
        # REAL DATA COLLECTION - Initialize conversation tracking
        self.conversation_tracker = None
        self.performance_tracker = get_performance_tracker()
        self.current_session_id = None
        self.current_user_id = None
        self.current_conversation_id = None
        self.conversation_start_time = None
        self.pending_user_input = None
        self.conversation_turn = 0
        
        logger.info("🔗 CustomTTSAgent initialized with REAL data collection!")
    
    async def on_session_start(self, session):
        """Initialize conversation tracking when session starts"""
        logger.info("🎯 SESSION START - Initializing conversation tracking...")
        logger.info(f"🎯 SESSION START CALLED! Session: {session}")
        
        try:
            # Initialize conversation tracker
            self.conversation_tracker = get_conversation_tracker()
            await self.conversation_tracker.start_processing()
            
            # Extract user info from room name or participant
            room_name = session.room.name if hasattr(session, 'room') else "unknown"
            
            # For now, use BSK as default user (you can extract from JWT later)
            self.current_user_id = "ec53e1ae-5a67-4765-8291-826a5475ebed"  # BSK's real UUID
            
            # Start conversation session
            self.current_session_id = await self.conversation_tracker.start_session(
                user_id=self.current_user_id,
                session_metadata={
                    "character": self.character,
                    "room_name": room_name,
                    "session_type": "spiritual_guidance_live"
                }
            )
            
            logger.info(f"✅ CONVERSATION TRACKING ACTIVE: session={self.current_session_id[:8]}...")
            logger.info(f"👤 User: BSK ({self.current_user_id[:8]}...)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize conversation tracking: {e}")
            import traceback
            logger.error(f"Full error: {traceback.format_exc()}")
    
    async def on_user_turn_completed(self, chat_ctx, new_message=None):
        """Capture user input when turn is completed - FIXED SIGNATURE"""
        print("🚨🚨🚨 USER TURN COMPLETED CALLED! 🚨🚨🚨")  # Extra visible logging
        print(f"🔍 IMMEDIATE DEBUG 1: method started")
        logger.info("🚨🚨🚨 USER TURN COMPLETED CALLED! 🚨🚨🚨")
        print(f"🔍 IMMEDIATE DEBUG 2: after logger.info")
        logger.info(f"🎙️ Chat context: {type(chat_ctx)}")
        print(f"🔍 IMMEDIATE DEBUG 3: after chat_ctx log")
        logger.info(f"🎙️ New message: {type(new_message)} - {new_message}")
        print(f"🔍 IMMEDIATE DEBUG 4: about to check tracker")
        
        # 🔍 DEBUG: Check tracker and session status
        logger.info(f"🔍 DEBUG: conversation_tracker = {self.conversation_tracker}")
        logger.info(f"🔍 DEBUG: current_session_id = {self.current_session_id}")
        logger.info(f"🔍 DEBUG: current_user_id = {self.current_user_id}")
        logger.info(f"🔍 DEBUG: new_message attributes = {dir(new_message) if new_message else 'None'}")
        
        # Extract user text from the new_message parameter
        user_text = None
        
        if new_message:
            # Method 1: Direct content attribute
            if hasattr(new_message, 'content'):
                content = new_message.content
                if isinstance(content, str) and content.strip():
                    user_text = content.strip()
                    logger.info(f"✅ Extracted from .content: '{user_text[:50]}...'")
                elif isinstance(content, list) and len(content) > 0:
                    # Handle list of content parts
                    user_text = ' '.join(str(part) for part in content).strip()
                    logger.info(f"✅ Extracted from .content list: '{user_text[:50]}...'")
            
            # Method 2: Text attribute
            elif hasattr(new_message, 'text'):
                text = new_message.text
                if isinstance(text, str) and text.strip():
                    user_text = text.strip()
                    logger.info(f"✅ Extracted from .text: '{user_text[:50]}...'")
                elif isinstance(text, list) and len(text) > 0:
                    user_text = ' '.join(str(part) for part in text).strip()
                    logger.info(f"✅ Extracted from .text list: '{user_text[:50]}...'")
            
            # Method 3: Direct string
            elif isinstance(new_message, str):
                user_text = new_message.strip()
                logger.info(f"✅ Direct string: '{user_text[:50]}...'")
            
            # Method 4: List handling
            elif isinstance(new_message, list):
                user_text = ' '.join(str(item) for item in new_message).strip()
                logger.info(f"✅ From list: '{user_text[:50]}...'")
            
            # Method 5: String conversion fallback
            else:
                try:
                    user_text = str(new_message).strip()
                    if user_text and len(user_text) > 1 and not user_text.startswith('<'):
                        logger.info(f"✅ String conversion: '{user_text[:50]}...'")
                    else:
                        user_text = None
                except Exception as e:
                    logger.error(f"❌ Failed to convert message to string: {e}")
        
        # 🔍 DEBUG: Log what we extracted
        logger.info(f"🔍 DEBUG: user_text = '{user_text}' (length: {len(user_text) if user_text else 0})")
        
        if user_text and len(user_text.strip()) > 0:
            self.pending_user_input = user_text.strip()
            logger.info(f"🎤 USER INPUT CAPTURED: '{self.pending_user_input[:100]}...'")
            
            # 📊 START PERFORMANCE TRACKING
            self.current_conversation_id = await self.performance_tracker.start_conversation_timing()
            self.conversation_start_time = time.time()
            logger.info(f"📊 Started performance tracking: {self.current_conversation_id}")
            
            # 🔥 FIX: Actually process the conversation turn!
            if self.conversation_tracker and self.current_session_id:
                try:
                    logger.info(f"🔍 DEBUG: About to call track_conversation_turn...")
                    # Generate a dummy agent response for now
                    agent_response = "Processing your message..."
                    
                    await self.conversation_tracker.track_conversation_turn(
                        session_id=self.current_session_id,
                        user_id=self.current_user_id,
                        user_input=user_text,
                        agent_response=agent_response,
                        technical_metadata={
                            "capture_method": "on_user_turn_completed",
                            "message_type": str(type(new_message)),
                            "conversation_id": self.current_conversation_id
                        }
                    )
                    logger.info(f"✅ TRACKED CONVERSATION TURN - WebSocket should broadcast now!")
                except Exception as e:
                    logger.error(f"❌ Failed to track conversation turn: {e}")
                    import traceback
                    logger.error(f"❌ Full error: {traceback.format_exc()}")
            else:
                logger.warning(f"⚠️ Cannot track turn: tracker={bool(self.conversation_tracker)}, session={bool(self.current_session_id)}")
                
        else:
            logger.warning(f"⚠️ Could not extract text from new_message")
            logger.warning(f"⚠️ new_message type: {type(new_message)}")
            logger.warning(f"⚠️ new_message value: {new_message}")
            if new_message:
                logger.warning(f"⚠️ new_message attributes: {dir(new_message)}")
        
    async def on_participant_connected(self, participant):
        """Initialize conversation tracking when user joins"""
        try:
            # Initialize conversation tracker if not already done
            if not self.conversation_tracker:
                self.conversation_tracker = get_conversation_tracker()
                await self.conversation_tracker.start_processing()
                
                            # Use BSK as default user (you can extract from JWT later)
            self.current_user_id = "ec53e1ae-5a67-4765-8291-826a5475ebed"  # BSK's real UUID
            
            # Force start session for testing (even without JWT auth)
            if not self.current_session_id:
                logger.info("🧪 TESTING MODE: Starting conversation session without JWT auth")
                self.current_session_id = await self.conversation_tracker.start_session(
                        user_id=self.current_user_id,
                        session_metadata={
                            "character": self.character, 
                            "session_type": "test_without_jwt",
                            "testing_mode": True
                        }
                    )
                
                logger.info(f"🎯 Started conversation tracking for {participant.identity}: session={self.current_session_id[:8]}...")
                logger.info(f"👤 User: BSK ({self.current_user_id[:8]}...)")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize conversation tracking on participant connect: {e}")
        
    async def tts_node(
        self, 
        text: AsyncIterable[str], 
        model_settings: ModelSettings
    ) -> AsyncGenerator[rtc.AudioFrame, None]:
        """
        Custom TTS node using Kokoro TTS with sentence buffering + REAL DATA COLLECTION
        """
        logger.info("🎵 Custom TTS node activated - using Kokoro TTS with REAL data collection")
        
        text_buffer = ""
        full_response = ""  # Track complete agent response for data collection
        
        async for text_chunk in text:
            if not text_chunk.strip():
                continue
                
            # Add to buffer and full response
            text_buffer += text_chunk
            full_response += text_chunk
            logger.info(f"📝 Buffered: '{text_buffer[:50]}...' (len: {len(text_buffer)})")
            
            # Check if we have a complete sentence or enough text
            should_synthesize = (
                text_buffer.endswith(('.', '!', '?', '\n')) or  # Complete sentence
                len(text_buffer) > 100 or  # Long enough chunk
                text_chunk.endswith('\n')  # Paragraph break
            )
            
            if should_synthesize and text_buffer.strip():
                logger.info(f"🎤 Synthesizing buffered text: '{text_buffer[:50]}...'")
                
                try:
                    # Generate audio with Kokoro TTS
                    audio_frames = await self._synthesize_with_kokoro(text_buffer.strip())
                    
                    # Yield each audio frame
                    for frame in audio_frames:
                        yield frame
                        
                    logger.info(f"✅ Generated {len(audio_frames)} audio frames for buffered text")
                    
                    # Clear buffer after successful synthesis
                    text_buffer = ""
                    
                except Exception as e:
                    logger.error(f"❌ Custom TTS synthesis failed: {e}")
                    # Yield silence as fallback but keep trying
                    yield self._create_silence_frame()
                    text_buffer = ""  # Clear buffer to avoid getting stuck
        
        # Synthesize any remaining text in buffer at the end
        if text_buffer.strip():
            full_response += text_buffer  # Add final buffer to complete response
            logger.info(f"🎤 Synthesizing final buffer: '{text_buffer[:50]}...'")
            try:
                audio_frames = await self._synthesize_with_kokoro(text_buffer.strip())
                for frame in audio_frames:
                    yield frame
                logger.info(f"✅ Generated {len(audio_frames)} audio frames for final buffer")
            except Exception as e:
                logger.error(f"❌ Final buffer synthesis failed: {e}")
                yield self._create_silence_frame()
        
        # 📊 COMPLETE PERFORMANCE TRACKING
        if self.current_conversation_id:
            try:
                # Record TTS latency (time for audio generation)
                tts_latency = (time.time() - self.conversation_start_time) * 1000
                await self.performance_tracker.record_tts_latency(
                    self.current_conversation_id, 
                    tts_latency
                )
                
                # Complete the conversation timing
                breakdown = await self.performance_tracker.complete_conversation_timing(
                    self.current_conversation_id
                )
                logger.info(f"📊 Performance metrics recorded: {breakdown.total}ms total")
                
                # 🚀 BROADCAST METRICS TO DASHBOARD
                try:
                    await self._broadcast_performance_metrics(breakdown)
                except Exception as e:
                    logger.error(f"❌ Failed to broadcast metrics to dashboard: {e}")
                
            except Exception as e:
                logger.error(f"❌ Failed to record performance metrics: {e}")
        
        # 🔗 REAL DATA COLLECTION - Store conversation turn in Supabase
        logger.info(f"🔍 Checking conversation storage: pending_input={bool(self.pending_user_input)}, response_length={len(full_response.strip()) if full_response else 0}")
        
        if self.pending_user_input and full_response.strip():
            logger.info(f"💾 STORING CONVERSATION TURN:")
            logger.info(f"   👤 User: '{self.pending_user_input[:60]}...'")
            logger.info(f"   🤖 Adina: '{full_response.strip()[:60]}...'")
            
            await self._store_conversation_turn(
                user_input=self.pending_user_input,
                agent_response=full_response.strip()
            )
            self.pending_user_input = None  # Clear after storing
        else:
            if not self.pending_user_input:
                logger.warning("⚠️ No user input pending - conversation not stored")
            if not full_response.strip():
                logger.warning("⚠️ No agent response - conversation not stored")
    
    async def _synthesize_with_kokoro(self, text: str) -> list[rtc.AudioFrame]:
        """Synthesize speech using Kokoro TTS via local FastAPI server"""
        logger.info(f"🎤 Kokoro TTS: '{text[:40]}{'...' if len(text) > 40 else ''}'")
        
        try:
            import httpx
            
            # Call local Kokoro TTS API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8001/synthesize",
                    data={
                        "text": text,
                        "voice": self.selected_voice  # Dynamic voice based on character
                    }
                )
                
                if response.status_code == 200:
                    audio_bytes = response.content
                    logger.info(f"✅ Kokoro API success: {len(audio_bytes)} bytes")
                    
                    # Convert bytes to numpy array
                    audio_array = self._wav_bytes_to_array(audio_bytes)
                    if audio_array is not None:
                        logger.info(f"🔊 Audio array: {len(audio_array)} samples")
                        return self._audio_to_frames(audio_array, sample_rate=24000)  # Kokoro outputs 24kHz
                    else:
                        logger.warning("⚠️ Failed to convert audio bytes, using fallback")
                        return await self._generate_fallback_beep()
                else:
                    logger.warning(f"⚠️ Kokoro API error: {response.status_code} - {response.text}")
                    return await self._generate_fallback_beep()
                
        except Exception as e:
            logger.warning(f"⚠️ Kokoro API error: {e}, using fallback beep")
            return await self._generate_fallback_beep()
    
    async def _generate_fallback_beep(self) -> list[rtc.AudioFrame]:
        """Generate quiet fallback beep if Kokoro fails"""
        duration = 0.2
        sample_rate = 16000
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples, False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.1  # Quiet beep
        audio_int16 = (audio * 32767).astype(np.int16)
        return self._audio_to_frames(audio_int16, sample_rate=sample_rate)

    def _wav_bytes_to_array(self, wav_bytes: bytes) -> np.ndarray:
        """Convert WAV bytes to numpy array"""
        try:
            # Create a BytesIO object from the WAV bytes
            audio_io = io.BytesIO(wav_bytes)
            
            # Read the WAV file
            with wave.open(audio_io, 'rb') as wav_file:
                # Get audio parameters
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                
                logger.info(f"📊 WAV format: {frames} frames, {sample_rate}Hz, {channels} channels")
                
                # Read audio data
                audio_data = wav_file.readframes(frames)
                
                # Convert to numpy array (16-bit PCM)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Convert to mono if stereo
                if channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
                    logger.info("🔊 Converted stereo to mono")
                
                return audio_array
                
        except Exception as e:
            logger.error(f"❌ WAV conversion failed: {e}")
            return None
    
    def _audio_to_frames(self, audio_data: np.ndarray, sample_rate: int, frame_size_ms: int = 20) -> list[rtc.AudioFrame]:
        """Convert audio data to LiveKit AudioFrame chunks"""
        frame_samples = int(sample_rate * frame_size_ms / 1000)  # 20ms frames
        frames = []
        
        for i in range(0, len(audio_data), frame_samples):
            chunk = audio_data[i:i + frame_samples]
            
            # Pad if needed
            if len(chunk) < frame_samples:
                chunk = np.pad(chunk, (0, frame_samples - len(chunk)))
            
            # Create AudioFrame
            frame = rtc.AudioFrame(
                data=chunk.tobytes(),
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(chunk),
            )
            frames.append(frame)
        
        return frames
    
    def _create_silence_frame(self, duration_ms: int = 20) -> rtc.AudioFrame:
        """Create a silence audio frame"""
        sample_rate = 16000
        samples = int(sample_rate * duration_ms / 1000)
        silence = np.zeros(samples, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=silence.tobytes(),
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=samples,
        )
    
    async def _store_conversation_turn(self, user_input: str, agent_response: str):
        """Store conversation turn in REAL Supabase database"""
        logger.info(f"🔍 Storage check: tracker={bool(self.conversation_tracker)}, session={bool(self.current_session_id)}")
        
        if not self.conversation_tracker or not self.current_session_id:
            logger.error("❌ CRITICAL: No conversation tracker or session - initializing now...")
            
            # Try to initialize now as fallback
            try:
                if not self.conversation_tracker:
                    self.conversation_tracker = get_conversation_tracker()
                    await self.conversation_tracker.start_processing()
                    logger.info("✅ Emergency tracker initialization successful")
                
                if not self.current_session_id:
                    # Emergency session start
                    self.current_user_id = "ec53e1ae-5a67-4765-8291-826a5475ebed"  # BSK
                    self.current_session_id = await self.conversation_tracker.start_session(
                        user_id=self.current_user_id,
                        session_metadata={
                            "character": self.character,
                            "session_type": "emergency_fallback"
                        }
                    )
                    logger.info(f"✅ Emergency session created: {self.current_session_id[:8]}...")
            except Exception as init_e:
                logger.error(f"❌ Emergency initialization failed: {init_e}")
                return
            
        try:
            self.conversation_turn += 1
            
            logger.info(f"📝 ATTEMPTING SUPABASE STORAGE (Turn {self.conversation_turn})...")
            
            # Store with real technical metadata
            await self.conversation_tracker.track_conversation_turn(
                session_id=self.current_session_id,
                user_id=self.current_user_id,
                user_input=user_input,
                agent_response=agent_response,
                technical_metadata={
                    "turn_number": self.conversation_turn,
                    "character": self.character,
                    "tts_engine": "kokoro",
                    "voice": self.selected_voice,
                    "response_length": len(agent_response),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"🎉 SUCCESS! STORED in Supabase: Turn {self.conversation_turn}")
            logger.info(f"   👤 User: '{user_input[:40]}...'")
            logger.info(f"   🤖 {self.character.title()}: '{agent_response[:40]}...'")
            
        except Exception as e:
            logger.error(f"❌ Failed to store conversation: {e}")
            import traceback
            logger.error(f"Full error: {traceback.format_exc()}")

    async def _broadcast_performance_metrics(self, breakdown):
        """Broadcast real-time performance metrics to dashboard via WebSocket"""
        try:
            # Send HTTP request to trigger WebSocket broadcast
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:10000/api/ws/broadcast",
                    json={
                        "type": "performance_update",
                        "session_id": self.current_session_id or "unknown",
                        "user_id": self.current_user_id or "unknown",
                        "metadata": {
                            "timestamp": breakdown.timestamp,
                            "total_latency": breakdown.total,
                            "stt_latency": breakdown.stt,
                            "llm_latency": breakdown.llm,
                            "tts_latency": breakdown.tts,
                            "network_latency": breakdown.network,
                            "character": self.character
                        }
                    },
                    timeout=2.0
                )
            logger.info(f"📡 Broadcasted performance metrics to dashboard")
        except Exception as e:
            logger.warning(f"⚠️ Failed to broadcast to dashboard: {e}")

async def entrypoint(ctx: JobContext):
    """Main entrypoint for the voice agent"""
    logger.info(f"🎯 ENTRYPOINT CALLED! Room: {ctx.room.name}")
    logger.info(f"🔍 JobContext details: {ctx}")
    
    # Try to extract character from room name 
    # Format 1: spiritual-{character}-{session_id} (mobile app)
    # Format 2: test-{character}-{description} (dispatch API)
    room_name = ctx.room.name
    character = "adina"  # Default fallback
    
    if "spiritual-" in room_name:
        # Mobile app format: spiritual-raffa-1754640475_597c0071
        parts = room_name.split("-")
        if len(parts) >= 2:
            potential_character = parts[1]  # Get the character part
            if potential_character in ["adina", "raffa"]:
                character = potential_character
                logger.info(f"🎭 CHARACTER DETECTED FROM MOBILE APP ROOM: {character}")
            else:
                logger.warning(f"⚠️ Unknown character in room name: {potential_character}, using default: adina")
    elif "-raffa-" in room_name:
        # Dispatch API format: test-raffa-male-voice
        character = "raffa"
        logger.info(f"🎭 CHARACTER DETECTED FROM DISPATCH ROOM: {character}")
    elif "-adina-" in room_name:
        # Dispatch API format: test-adina-something
        character = "adina" 
        logger.info(f"🎭 CHARACTER DETECTED FROM DISPATCH ROOM: {character}")
    else:
        logger.info(f"🎭 NO CHARACTER DETECTED IN ROOM NAME '{room_name}', using default: {character}")
    
    # Store character for later use in the agent
    setattr(ctx, 'detected_character', character)
    
    logger.info(f"🔗 Connecting to room: {ctx.room.name}")
    await ctx.connect()
    logger.info(f"✅ Connected to room: {ctx.room.name}")
    
    logger.info("🚀 Creating agent session with CUSTOM TTS...")
    # NOTE: NO TTS in AgentSession - using tts_node() override instead!
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        # tts=openai.TTS(voice="echo"),  # REMOVED - using custom tts_node()
    )
    logger.info("✅ Agent session created (NO TTS - using custom override)")
    
    logger.info(f"🎯 Starting agent session with CustomTTSAgent (character: {character})...")
    await session.start(
        agent=CustomTTSAgent(character=character),  # Pass detected character
        room=ctx.room,
    )
    logger.info("✅ Agent session started!")
    
    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )
    logger.info("🎵 Initial greeting generated!")

if __name__ == "__main__":
    logger.info("🚀 Starting LiveKit agent worker with agent_name='spiritual-agent'")
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="spiritual-agent",  # Match dispatch API expectation
        ),
    ) 