from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import asyncio
import json
import logging
import base64
import numpy as np
from typing import Dict, Optional, List
import uuid
import time
import struct
import re
from datetime import datetime

# Import existing services
from ..services.stt.implementations.direct_deepgram import DirectDeepgramSTTService
from ..services.llm_service import create_gpt4o_mini
from ..services.openai_tts_service import OpenAITTSService
from ..characters.character_factory import CharacterFactory

router = APIRouter()
logger = logging.getLogger(__name__)

def create_wav_header(sample_rate: int = 16000, num_channels: int = 1, bit_depth: int = 16, data_length: int = 0) -> bytes:
    """Create WAV file header for proper audio format"""
    # Calculate derived values
    byte_rate = sample_rate * num_channels * bit_depth // 8
    block_align = num_channels * bit_depth // 8
    
    # WAV header structure
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                    # ChunkID
        36 + data_length,           # ChunkSize
        b'WAVE',                    # Format
        b'fmt ',                    # Subchunk1ID
        16,                         # Subchunk1Size (PCM)
        1,                          # AudioFormat (PCM)
        num_channels,               # NumChannels
        sample_rate,                # SampleRate
        byte_rate,                  # ByteRate
        block_align,                # BlockAlign
        bit_depth,                  # BitsPerSample
        b'data',                    # Subchunk2ID
        data_length                 # Subchunk2Size
    )
    return header

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1, bit_depth: int = 16) -> bytes:
    """Convert raw PCM data to WAV format with proper headers"""
    if not pcm_data:
        return b''
    
    # Create WAV header
    header = create_wav_header(sample_rate, num_channels, bit_depth, len(pcm_data))
    
    # Combine header + data
    wav_data = header + pcm_data
    return wav_data

def chunk_ai_response(full_response: str, max_chunk_length: int = 100) -> List[str]:
    """
    Split AI response into natural chunks for streaming audio
    
    Args:
        full_response: Complete AI response text
        max_chunk_length: Target maximum characters per chunk
        
    Returns:
        List of text chunks optimized for TTS streaming
    """
    if not full_response or not full_response.strip():
        return []
    
    # Clean the response
    text = full_response.strip()
    
    # Split by sentences first (prioritize natural breaks)
    sentence_endings = r'[.!?]+\s+'
    sentences = re.split(sentence_endings, text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Add sentence ending back (except for last sentence)
        if not sentence.endswith(('.', '!', '?')):
            sentence += '.'
        
        # Check if adding this sentence exceeds chunk length
        if len(current_chunk + ' ' + sentence) <= max_chunk_length or not current_chunk:
            # Add to current chunk
            if current_chunk:
                current_chunk += ' ' + sentence
            else:
                current_chunk = sentence
        else:
            # Start new chunk
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    # If no chunks created, split by words as fallback
    if not chunks and text:
        words = text.split()
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + ' ' + word) <= max_chunk_length or not current_chunk:
                if current_chunk:
                    current_chunk += ' ' + word
                else:
                    current_chunk = word
            else:
                chunks.append(current_chunk)
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
    
    logger.info(f"📝 Chunked response into {len(chunks)} pieces: {[len(chunk) for chunk in chunks]} chars each")
    return chunks

class AudioSession:
    """Manages individual audio streaming sessions"""
    
    def __init__(self, session_id: str, character: str = "adina"):
        self.session_id = session_id
        self.character = character
        self.created_at = datetime.now()
        self.conversation_history = []
        
        # Initialize services
        self.stt_service = None
        self.llm_service = None
        self.tts_service = None
        self._audio_buffer = bytearray()
        self._processing_audio = False
        
        # Enhanced voice activity detection
        self._recent_energy_levels = []  # Track recent energy levels
        self._energy_threshold = 800    # Increased from 300 to reduce false positives
        self._min_sustained_chunks = 3  # Require 3 consecutive high-energy chunks
        self._max_energy_history = 10   # Keep last 10 energy measurements
        self._last_speech_time = 0      # Track when we last detected speech
        self._speech_cooldown = 2.0     # Seconds to wait after speech before resetting
        
        # Conversational session state management
        self.session_active = True      # Session is active for conversation
        self.conversation_state = "LISTENING"  # LISTENING, PROCESSING, RESPONDING
        self.last_activity_time = time.time()  # Track activity for timeout management
        self.conversation_turn_count = 0       # Track number of conversation turns
        
    async def initialize(self):
        """Initialize all services for this session"""
        try:
            # STT Service - Direct Deepgram (no LiveKit context needed)
            self.stt_service = DirectDeepgramSTTService({
                "model": "nova-2",
                "language": "en-US",
                "punctuate": True,
                "interim_results": False
            })
            await self.stt_service.initialize()
            
            # LLM Service - Fixed OpenAI adapter
            self.llm_service = create_gpt4o_mini()
            
            # TTS Service - OpenAI with character voice
            character_config = CharacterFactory.get_character_config(self.character)
            self.tts_service = OpenAITTSService()
            
            # Set initial conversation state
            self.conversation_state = "LISTENING"
            self.last_activity_time = time.time()
            
            logger.info(f"✅ Audio session {self.session_id} initialized with character {self.character} - Ready for conversation")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize session {self.session_id}: {e}")
            raise
    
    async def process_audio_chunk(self, audio_data: bytes, websocket: WebSocket) -> Optional[str]:
        """Process incoming audio chunk and return transcription if available"""
        try:
            # Check WebSocket connection state before processing
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(f"⚠️ WebSocket not connected, skipping audio processing")
                return None
            
            # Check session state - only process audio when LISTENING
            if not self.session_active:
                logger.debug(f"Session inactive, skipping audio processing")
                return None
                
            if self.conversation_state != "LISTENING":
                logger.debug(f"Not in LISTENING state (current: {self.conversation_state}), skipping audio processing")
                return None
            
            # Update activity time
            self.last_activity_time = time.time()
            
            # Add to buffer
            self._audio_buffer.extend(audio_data)
            
            # Calculate audio energy to detect actual speech vs silence/noise
            audio_energy = self._calculate_audio_energy(audio_data)
            current_time = time.time()
            
            # Update energy history for sustained speech detection
            self._recent_energy_levels.append(audio_energy)
            if len(self._recent_energy_levels) > self._max_energy_history:
                self._recent_energy_levels.pop(0)
            
            # Log audio energy for debugging (every 32KB to avoid spam)
            if len(self._audio_buffer) % 32000 == 0:  # Log every ~1 second
                avg_energy = sum(self._recent_energy_levels) / len(self._recent_energy_levels)
                logger.info(f"🎤 Audio energy: {audio_energy:.1f} | Avg: {avg_energy:.1f} | Threshold: {self._energy_threshold}")
            
            # Enhanced speech detection - require sustained high energy
            speech_detected = self._detect_sustained_speech(audio_energy, current_time)
            
            # Only trigger speech detection for sustained high energy
            if speech_detected and not self._processing_audio:
                self._processing_audio = True
                self._last_speech_time = current_time
                
                # Calculate confidence based on energy levels and consistency
                confidence = self._calculate_speech_confidence()
                
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "speech_detected",
                        "confidence": confidence,
                        "energy": audio_energy,
                        "sustained_chunks": len([e for e in self._recent_energy_levels[-self._min_sustained_chunks:] if e > self._energy_threshold]),
                        "timestamp": datetime.now().isoformat()
                    })
                logger.info(f"🗣️ BACKEND HEARD YOU: Speech detected (energy: {audio_energy}, confidence: {confidence:.2f})")
            
            # Smart buffer processing - process when we have enough data AND speech was detected
            buffer_size = len(self._audio_buffer)
            min_buffer_size = 16000  # ~0.5 seconds at 16kHz 16-bit
            max_buffer_size = 64000  # ~2 seconds at 16kHz 16-bit
            
            should_process = False
            
            if self._processing_audio and buffer_size >= min_buffer_size:
                # Process if we detected speech and have minimum data
                should_process = True
                process_reason = f"speech detected + {buffer_size} bytes"
            elif buffer_size >= max_buffer_size:
                # Process if buffer is getting too large (prevent memory issues)
                should_process = True
                process_reason = f"max buffer reached: {buffer_size} bytes"
            
            # Skip processing if no recent high energy (likely just noise)
            recent_avg_energy = sum(self._recent_energy_levels[-5:]) / min(5, len(self._recent_energy_levels)) if self._recent_energy_levels else 0
            if should_process and recent_avg_energy < (self._energy_threshold * 0.6):
                logger.debug(f"🔇 Skipping processing - recent avg energy too low: {recent_avg_energy:.1f}")
                should_process = False
                # Clear buffer of likely noise
                self._audio_buffer.clear()
                self._processing_audio = False
            
            if should_process:
                # Change to PROCESSING state
                self.conversation_state = "PROCESSING"
                
                # Get raw audio bytes from buffer
                audio_bytes = bytes(self._audio_buffer)
                
                # Clear buffer
                self._audio_buffer.clear()
                
                # Reset processing flag for next audio chunk
                self._processing_audio = False
                
                logger.info(f"📝 Processing audio buffer: {process_reason}")
                
                # Convert raw PCM to WAV format for Deepgram
                wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000, num_channels=1, bit_depth=16)
                
                # Send transcription start event (check connection first)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "transcription_partial",
                        "text": "",
                        "message": "Processing your speech...",
                        "buffer_size": len(audio_bytes),
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat()
                    })
                logger.info("📝 BACKEND UNDERSTANDING: Processing speech...")
                
                # Transcribe using Direct Deepgram service
                transcription = await self.stt_service.transcribe_audio_bytes(wav_audio)
                
                if transcription and transcription.strip():
                    # Send complete transcription (check connection first)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "transcription_complete",
                            "text": transcription.strip(),
                            "buffer_size": len(audio_bytes),
                            "conversation_state": self.conversation_state,
                            "timestamp": datetime.now().isoformat()
                        })
                    logger.info(f"✅ BACKEND UNDERSTOOD: '{transcription}'")
                    logger.info(f"👤 User ({self.character}): '{transcription}'")
                    
                    # Increment conversation turn
                    self.conversation_turn_count += 1
                    logger.info(f"🔄 Conversation turn #{self.conversation_turn_count}")
                    
                    return transcription.strip()
                else:
                    # Send empty transcription result (check connection first)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "transcription_complete",
                            "text": "",
                            "message": "No speech detected in audio",
                            "buffer_size": len(audio_bytes),
                            "conversation_state": self.conversation_state,
                            "timestamp": datetime.now().isoformat()
                        })
                    logger.info(f"🔇 No speech in {len(audio_bytes)} bytes of audio")
                    
                    # Return to LISTENING state if no speech found
                    self.conversation_state = "LISTENING"
                    
        except Exception as e:
            logger.error(f"❌ Audio processing error in session {self.session_id}: {e}")
            # Send error event to frontend (only if connection is active)
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Audio processing failed",
                        "details": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    logger.debug("Could not send audio processing error - connection closed")
            
        return None
    
    def _calculate_audio_energy(self, audio_data: bytes) -> float:
        """Calculate the energy/volume of audio data to detect speech vs silence"""
        try:
            if len(audio_data) < 2:
                return 0.0
            
            import struct
            import math
            
            # Convert bytes to 16-bit signed integers
            sample_count = len(audio_data) // 2
            samples = struct.unpack(f'<{sample_count}h', audio_data[:sample_count * 2])
            
            # Calculate RMS (Root Mean Square) energy
            sum_squares = sum(sample * sample for sample in samples)
            rms = math.sqrt(sum_squares / sample_count) if sample_count > 0 else 0.0
            
            return rms
            
        except Exception as e:
            logger.warning(f"⚠️ Error calculating audio energy: {e}")
            return 0.0
    
    def _detect_sustained_speech(self, current_energy: float, current_time: float) -> bool:
        """Detect if we have sustained speech rather than just noise spikes"""
        # Check if enough time has passed since last speech (cooldown)
        if current_time - self._last_speech_time < self._speech_cooldown:
            return False
        
        # Check if current energy is above threshold
        if current_energy < self._energy_threshold:
            return False
        
        # Check if we have enough recent measurements
        if len(self._recent_energy_levels) < self._min_sustained_chunks:
            return False
        
        # Check if recent chunks have sustained high energy
        recent_high_energy_chunks = [
            e for e in self._recent_energy_levels[-self._min_sustained_chunks:] 
            if e > self._energy_threshold
        ]
        
        # Require at least 3 out of last 3 chunks to be high energy
        return len(recent_high_energy_chunks) >= self._min_sustained_chunks
    
    def _calculate_speech_confidence(self) -> float:
        """Calculate confidence score based on energy patterns"""
        if not self._recent_energy_levels:
            return 0.0
        
        # Get recent measurements
        recent_energies = self._recent_energy_levels[-self._min_sustained_chunks:]
        if not recent_energies:
            return 0.0
        
        # Calculate average energy over threshold
        avg_energy = sum(recent_energies) / len(recent_energies)
        
        # Calculate consistency (lower standard deviation = more consistent = higher confidence)
        if len(recent_energies) > 1:
            import math
            variance = sum((e - avg_energy) ** 2 for e in recent_energies) / len(recent_energies)
            std_dev = math.sqrt(variance)
            consistency = max(0, 1 - (std_dev / avg_energy)) if avg_energy > 0 else 0
        else:
            consistency = 1.0
        
        # Base confidence on energy level above threshold
        energy_ratio = min(avg_energy / self._energy_threshold, 3.0)  # Cap at 3x threshold
        energy_confidence = min(0.9, energy_ratio / 3.0)
        
        # Combine energy confidence with consistency
        final_confidence = (energy_confidence * 0.7) + (consistency * 0.3)
        
        return min(0.95, max(0.1, final_confidence))
    
    async def generate_response(self, user_input: str) -> str:
        """Generate AI response using character personality"""
        try:
            # Get character personality
            character = CharacterFactory.create_character(self.character)
            
            # Create conversation context
            messages = [
                {"role": "system", "content": character.personality}
            ]
            
            # Add recent conversation history
            for msg in self.conversation_history[-10:]:  # Last 5 exchanges
                messages.append(msg)
            
            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            # Generate response using LLM
            from livekit.agents import llm
            
            # Create ChatContext with proper message format  
            chat_ctx = llm.ChatContext()
            for msg in messages:
                chat_ctx.add_message(role=msg["role"], content=msg["content"])
            response_stream = await self.llm_service.chat(chat_ctx=chat_ctx)
            
            # Collect full response
            response_text = ""
            async for chunk in response_stream:
                if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            logger.info(f"🤖 {self.character.title()}: '{response_text[:100]}...'")
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Response generation error: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return f"I apologize, I'm having a technical difficulty. Could you please try again?"
    
    async def synthesize_speech_chunk(self, text: str) -> bytes:
        """Convert text chunk to speech in WAV format"""
        try:
            logger.info(f"🎤 Starting TTS synthesis for: '{text[:50]}...'")
            
            # Use TTS service to generate audio
            audio_frames = []
            frame_count = 0
            sample_rate = 48000  # Default OpenAI TTS sample rate
            
            async for synth_audio in self.tts_service.synthesize_streaming(text, self.character):
                frame_count += 1
                logger.debug(f"🎵 Received TTS frame {frame_count}: {type(synth_audio)}")
                
                # Extract audio frame
                audio_frame = synth_audio.frame
                sample_rate = audio_frame.sample_rate  # Get actual sample rate
                
                # Extract audio data properly
                if hasattr(audio_frame, 'data'):
                    audio_data = audio_frame.data.tobytes()
                    audio_frames.append(audio_data)
                    logger.debug(f"🎵 Added frame data: {len(audio_data)} bytes at {sample_rate}Hz")
                else:
                    logger.warning(f"⚠️ Audio frame has no data attribute: {type(audio_frame)}")
            
            logger.info(f"🎵 TTS completed: {frame_count} frames, {len(audio_frames)} audio chunks at {sample_rate}Hz")
            
            # Combine all audio frames
            if audio_frames:
                combined_pcm = b''.join(audio_frames)
                logger.info(f"🎵 Combined PCM: {len(combined_pcm)} bytes")
                
                # Convert PCM to WAV format with correct sample rate
                wav_data = pcm_to_wav(combined_pcm, sample_rate=sample_rate, num_channels=1, bit_depth=16)
                logger.info(f"🎵 Generated {len(wav_data)} bytes WAV for: '{text[:30]}...'")
                return wav_data
            else:
                logger.warning(f"⚠️ No audio frames generated for text: {text[:50]}...")
                logger.warning(f"⚠️ Frame count was: {frame_count}")
                
                # Try fallback approach - direct OpenAI API
                return await self._fallback_tts_synthesis(text)
                
        except Exception as e:
            logger.error(f"❌ Speech synthesis error: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            # Try fallback approach
            return await self._fallback_tts_synthesis(text)
    
    async def _fallback_tts_synthesis(self, text: str) -> bytes:
        """Fallback TTS synthesis using direct OpenAI API"""
        try:
            logger.info(f"🔄 Trying fallback TTS for: '{text[:30]}...'")
            
            # Direct OpenAI TTS call
            import openai
            response = await openai.AsyncOpenAI().audio.speech.create(
                model="tts-1",
                voice="nova" if self.character == "adina" else "onyx",
                input=text,
                response_format="wav"
            )
            
            audio_data = await response.aread()
            logger.info(f"🎵 Fallback TTS generated: {len(audio_data)} bytes")
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ Fallback TTS also failed: {e}")
            return b''
    
    async def process_and_stream_response(self, websocket: WebSocket, user_input: str):
        """Generate AI response and stream audio chunks in real-time"""
        try:
            # Check connection state before starting
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(f"⚠️ WebSocket disconnected, cannot stream response")
                return
            
            # Check session state
            if not self.session_active:
                logger.warning(f"⚠️ Session inactive, cannot stream response")
                return
            
            # Change to RESPONDING state
            self.conversation_state = "RESPONDING"
            
            # Send processing started event
            await websocket.send_json({
                "type": "processing_started",
                "character": self.character,
                "message": f"{self.character.title()} is thinking...",
                "conversation_state": self.conversation_state,
                "conversation_turn": self.conversation_turn_count,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"🤖 Processing started with {self.character} (Turn #{self.conversation_turn_count})")
            
            # Generate AI response
            response_text = await self.generate_response(user_input)
            
            # Split response into chunks
            chunks = chunk_ai_response(response_text, max_chunk_length=120)
            
            if not chunks:
                logger.warning("⚠️ No chunks generated from AI response")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to generate response chunks",
                        "timestamp": datetime.now().isoformat()
                    })
                return
            
            logger.info(f"🎯 Streaming {len(chunks)} audio chunks for response")
            
            # Send response start notification with full details
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "response_start",
                    "character": self.character,
                    "total_chunks": len(chunks),
                    "full_text": response_text,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Process and stream each chunk
            for i, chunk_text in enumerate(chunks):
                # Check connection before processing each chunk
                if websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning(f"⚠️ WebSocket disconnected during chunk {i+1}, stopping stream")
                    break
                
                chunk_start_time = time.time()
                
                # Generate TTS for this chunk
                wav_audio = await self.synthesize_speech_chunk(chunk_text)
                
                if wav_audio and websocket.client_state == WebSocketState.CONNECTED:
                    chunk_duration = (time.time() - chunk_start_time) * 1000
                    
                    # Send audio chunk immediately
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "chunk_id": i + 1,
                        "total_chunks": len(chunks),
                        "is_final": i == len(chunks) - 1,
                        "text": chunk_text,
                        "audio": base64.b64encode(wav_audio).decode('utf-8'),
                        "character": self.character,
                        "generation_time_ms": round(chunk_duration),
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    logger.info(f"🎵 Sent chunk {i+1}/{len(chunks)} ({len(chunk_text)} chars, {chunk_duration:.0f}ms)")
                elif not wav_audio:
                    logger.error(f"❌ Failed to generate audio for chunk {i+1}: '{chunk_text[:30]}...'")
                else:
                    logger.warning(f"⚠️ WebSocket disconnected, cannot send chunk {i+1}")
                    break
            
            # Send completion notification (if still connected)
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "response_complete",
                    "character": self.character,
                    "chunks_sent": len(chunks),
                    "conversation_turn": self.conversation_turn_count,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Return to LISTENING state for next user input
            self.conversation_state = "LISTENING"
            logger.info(f"🔄 Response complete - Back to LISTENING state (Turn #{self.conversation_turn_count})")
            
            # Update activity time
            self.last_activity_time = time.time()
            
        except Exception as e:
            logger.error(f"❌ Error in streaming response: {e}")
            # Only try to send error if connection is still active
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to stream response",
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    logger.debug("Could not send error message - connection already closed")
    
    def reset_for_next_turn(self):
        """Reset audio processing state between conversation turns (not between sessions)"""
        # Clear audio buffers but keep session active
        self._audio_buffer.clear()
        self._processing_audio = False
        
        # Reset speech detection state but keep energy history for context
        # Keep last few energy measurements for better detection
        if len(self._recent_energy_levels) > 5:
            self._recent_energy_levels = self._recent_energy_levels[-3:]
        
        # Update activity time
        self.last_activity_time = time.time()
        
        logger.debug(f"🔄 Session {self.session_id} reset for next conversation turn")
    
    def is_session_active(self) -> bool:
        """Check if session should remain active based on recent activity"""
        inactive_time = time.time() - self.last_activity_time
        
        # Keep session active for 5 minutes of inactivity
        max_inactive_time = 300  # 5 minutes
        
        if inactive_time > max_inactive_time:
            logger.info(f"⏰ Session {self.session_id} inactive for {inactive_time:.1f}s, marking for cleanup")
            self.session_active = False
            
        return self.session_active
    
    async def cleanup(self):
        """Clean up session resources"""
        try:
            # Mark session as inactive
            self.session_active = False
            self.conversation_state = "DISCONNECTED"
            
            if self.stt_service:
                await self.stt_service.shutdown()
            logger.info(f"🧹 Session {self.session_id} cleaned up (had {self.conversation_turn_count} turns)")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error for session {self.session_id}: {e}")

# Global session manager
active_sessions: Dict[str, AudioSession] = {}

@router.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    session_id = str(uuid.uuid4())
    session = None
    
    try:
        await websocket.accept()
        logger.info(f"🔗 WebSocket connected: session {session_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                # Check session activity if session exists
                if session and not session.is_session_active():
                    logger.info(f"⏰ Session {session_id} timed out, cleaning up")
                    await session.cleanup()
                    if session_id in active_sessions:
                        del active_sessions[session_id]
                    break
                
                # Receive message from client
                data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                
                if data.get("type") == "websocket.disconnect":
                    break
                
                # Handle different message types
                if "text" in data:
                    message = json.loads(data["text"])
                    session = await handle_json_message(websocket, session, message, session_id)
                    
                elif "bytes" in data:
                    # Handle binary audio data
                    if session and session.stt_service and session.session_active:
                        audio_data = data["bytes"]
                        transcription = await session.process_audio_chunk(audio_data, websocket)
                        
                        if transcription:
                            # Process and stream response in chunks
                            await session.process_and_stream_response(websocket, transcription)
                            # Reset for next conversation turn (but keep session alive)
                            session.reset_for_next_turn()
                            
            except asyncio.TimeoutError:
                # Send keepalive ping and check session activity
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "ping",
                        "session_active": session.session_active if session else False,
                        "conversation_turns": session.conversation_turn_count if session else 0
                    })
                    
            except WebSocketDisconnect:
                break
                
            except Exception as e:
                logger.error(f"❌ Error processing message in session {session_id}: {e}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Processing error occurred",
                        "timestamp": datetime.now().isoformat()
                    })
    
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
        
    finally:
        # Cleanup
        if session:
            await session.cleanup()
            if session_id in active_sessions:
                del active_sessions[session_id]
        
        logger.info(f"🔌 WebSocket disconnected: session {session_id}")

async def handle_json_message(websocket: WebSocket, session: Optional[AudioSession], message: dict, session_id: str) -> Optional[AudioSession]:
    """Handle JSON messages from client"""
    message_type = message.get("type")
    
    try:
        if message_type == "initialize":
            # Initialize session with character
            character = message.get("character", "adina")
            
            if character not in ["adina", "raffa"]:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid character: {character}. Must be 'adina' or 'raffa'"
                })
                return session
            
            # Create and initialize session
            session = AudioSession(session_id, character)
            await session.initialize()
            active_sessions[session_id] = session
            
            await websocket.send_json({
                "type": "initialized",
                "character": character,
                "session_id": session_id,
                "message": f"Connected to {character.title()} - Ready for conversation",
                "conversation_state": session.conversation_state,
                "session_active": session.session_active,
                "timestamp": datetime.now().isoformat()
            })
            
            # Send welcome message from character
            character_obj = CharacterFactory.create_character(character)
            welcome_message = f"Hello! I'm {character.title()}. I'm here to listen and support you. How are you feeling today?"
            
            # Send welcome as first response (but don't count as conversation turn)
            await websocket.send_json({
                "type": "welcome_message",
                "character": character,
                "text": welcome_message,
                "conversation_state": session.conversation_state,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"👋 {character.title()} welcomed user in session {session_id}")
            
        elif message_type == "switch_character":
            if session:
                new_character = message.get("character", "adina")
                if new_character in ["adina", "raffa"]:
                    session.character = new_character
                    await websocket.send_json({
                        "type": "character_switched",
                        "character": new_character,
                        "message": f"Switched to {new_character.title()}",
                        "timestamp": datetime.now().isoformat()
                    })
                    
        elif message_type == "audio":
            # Handle JSON audio message with base64 encoded audio data
            if session and session.stt_service:
                try:
                    audio_base64 = message.get("audio", "")
                    if audio_base64:
                        # Decode base64 audio data
                        audio_data = base64.b64decode(audio_base64)
                        logger.debug(f"🎤 Received {len(audio_data)} bytes of audio data via JSON")
                        
                        # Process audio chunk and get transcription
                        transcription = await session.process_audio_chunk(audio_data, websocket)
                        
                        if transcription:
                            # Process and stream response in chunks
                            await session.process_and_stream_response(websocket, transcription)
                    else:
                        logger.warning("⚠️ Empty audio data in JSON message")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing JSON audio message: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to process audio data",
                        "details": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Session not initialized or STT service unavailable",
                    "timestamp": datetime.now().isoformat()
                })
                    
        elif message_type == "text_message":
            # Handle text-only message (no audio) - stream chunks too
            if session:
                user_text = message.get("text", "")
                if user_text.strip():
                    await session.process_and_stream_response(websocket, user_text)
                    
        elif message_type == "ping":
            await websocket.send_json({"type": "pong"})
            
    except Exception as e:
        logger.error(f"❌ Error handling JSON message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to process message",
            "timestamp": datetime.now().isoformat()
        })
    
    return session 