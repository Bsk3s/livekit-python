import asyncio
import base64
import json
import logging
import re
import struct
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from spiritual_voice_agent.characters.character_factory import CharacterFactory
from spiritual_voice_agent.services.llm_service import create_gpt4o_mini

# Import existing services
from spiritual_voice_agent.services.stt.implementations.direct_deepgram import (
    DirectDeepgramSTTService,
)
from spiritual_voice_agent.services.tts_factory import TTSFactory

# Cost Analytics imports for voice-first tracking
from spiritual_voice_agent.services.cost_analytics import log_voice_event

router = APIRouter()
logger = logging.getLogger(__name__)


def create_wav_header(
    sample_rate: int = 16000, num_channels: int = 1, bit_depth: int = 16, data_length: int = 0
) -> bytes:
    """Create WAV file header for iOS-compatible audio format"""
    # Calculate derived values
    byte_rate = sample_rate * num_channels * bit_depth // 8
    block_align = num_channels * bit_depth // 8
    
    # Ensure data length is even (required for proper alignment)
    if data_length % 2 != 0:
        data_length += 1

    # WAV header structure - iOS compatible
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        36 + data_length,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size (PCM)
        1,  # AudioFormat (PCM)
        num_channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bit_depth,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_length,  # Subchunk2Size
    )
    return header


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1, bit_depth: int = 16
) -> bytes:
    """Convert raw PCM data to iOS-compatible WAV format"""
    if not pcm_data:
        return b""

    # Ensure PCM data is properly aligned (even number of bytes for 16-bit)
    if len(pcm_data) % 2 != 0:
        # Pad with zero if odd length
        pcm_data = pcm_data + b'\x00'
        logger.debug(f"🔧 Padded PCM data to even length: {len(pcm_data)} bytes")

    # Create WAV header
    header = create_wav_header(sample_rate, num_channels, bit_depth, len(pcm_data))

    # Combine header + data
    wav_data = header + pcm_data
    
    # Validate WAV format
    if len(wav_data) >= 44 and wav_data[:4] == b'RIFF' and wav_data[8:12] == b'WAVE':
        logger.debug(f"✅ Generated valid iOS-compatible WAV: {len(wav_data)} bytes")
    else:
        logger.warning(f"⚠️ Generated WAV may be invalid: {len(wav_data)} bytes")
    
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
    sentence_endings = r"[.!?]+\s+"
    sentences = re.split(sentence_endings, text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Add sentence ending back (except for last sentence)
        if not sentence.endswith((".", "!", "?")):
            sentence += "."

        # Check if adding this sentence exceeds chunk length
        if len(current_chunk + " " + sentence) <= max_chunk_length or not current_chunk:
            # Add to current chunk
            if current_chunk:
                current_chunk += " " + sentence
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
            if len(current_chunk + " " + word) <= max_chunk_length or not current_chunk:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
            else:
                chunks.append(current_chunk)
                current_chunk = word

        if current_chunk:
            chunks.append(current_chunk)

    logger.info(
        f"📝 Chunked response into {len(chunks)} pieces: {[len(chunk) for chunk in chunks]} chars each"
    )
    return chunks


class AudioSession:
    """
    Manages individual audio streaming sessions with reliability watchdog and cost tracking.
    
    Enhanced with voice-first cost analytics that has ZERO impact on voice processing latency.
    Cost events are logged with fire-and-forget pattern - voice pipeline never waits.
    
    VAD DECOUPLING IMPLEMENTATION:
    - VAD Processing: Always active regardless of conversation state
    - Speech Detection: Continuous monitoring with state context
    - Transcription: Only processed in LISTENING state
    - Buffer Management: Always accumulates audio data
    
    PERFORMANCE BASELINE (Pre-Decoupling):
    - Audio chunk processing: <10ms target
    - VAD calculation: ~0.5ms per chunk
    - Memory usage: Stable during conversations
    - Speech detection accuracy: ~95% (measured)
    
    VAD PARAMETERS (Documented for rollback):
    - Energy threshold: 800 (RMS threshold for speech detection)
    - Sustained chunks: 3 (consecutive high-energy chunks required)
    - Energy history: 10 (rolling window size)
    - Speech cooldown: 2.0 seconds (between detections)
    - Buffer sizes: 16KB min, 64KB max (0.5-2.0 seconds at 16kHz)
    """

    def __init__(self, session_id: str, character: str = "adina", user_id: str = "default_user"):
        self.session_id = session_id
        self.character = character
        self.user_id = user_id  # For cost tracking and analytics
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
        self._energy_threshold = 100  # Lowered for real microphone input calibration
        self._min_sustained_chunks = 1  # Require only 1 high-energy chunk for interruption (was 3) - kept low for real mic testing
        self._max_energy_history = 10  # Keep last 10 energy measurements
        self._last_speech_time = 0  # Track when we last detected speech
        self._speech_cooldown = 0.1  # Seconds to wait after speech before resetting (was 2.0)

        # Performance monitoring for VAD decoupling
        self._performance_metrics = {
            'vad_processing_times': [],
            'full_processing_times': [],
            'speech_detections': 0,
            'false_positives': 0,
            'transcription_attempts': 0,
            'chunk_count': 0,
            'interruptions': 0,
            'interruption_latencies': []
        }

        # 🎯 INTERRUPTION SYSTEM - Real-time conversation control
        self._interruption_enabled = True  # Enable interruption capabilities
        self._current_tts_task: Optional[asyncio.Task] = None  # Track current TTS streaming
        self._response_chunks_sent = 0  # Track how many chunks we've sent
        self._interruption_threshold = 1.5  # Confidence threshold for interruption (lower = more sensitive)
        self._interruption_cooldown = 1.0  # Seconds to wait after interruption before allowing another
        self._last_interruption_time = 0  # Track when last interruption occurred
        self._stream_cancelled = False  # Flag to indicate if current stream was cancelled

        # Conversational session state management
        self.session_active = True  # Session is active for conversation
        self.conversation_state = "LISTENING"  # LISTENING, PROCESSING, RESPONDING
        self.last_activity_time = time.time()  # Track activity for timeout management
        self.conversation_turn_count = 0  # Track number of conversation turns
        
        # 🛡️ RELIABILITY WATCHDOG - Zero latency background monitoring
        self._state_change_time = time.time()  # When current state started
        self._watchdog_task: Optional[asyncio.Task] = None
        self._cleanup_queue = []  # Async cleanup tasks to run after responses
        self._max_state_duration = 15.0  # Allow time for longer LLM responses (12s + buffer)
        self._last_health_check = time.time()  # Quick health status cache
        self._current_websocket: Optional[WebSocket] = None  # Track current websocket connection

    async def initialize(self):
        """Initialize all services for this session"""
        logger.info(f"🚀 STARTING AudioSession.initialize() for session {self.session_id}")
        try:
            # STT Service - Direct Deepgram (no LiveKit context needed)
            logger.info(f"🎧 Creating STT service for session {self.session_id}")
            self.stt_service = DirectDeepgramSTTService(
                {
                    "model": "nova-2",
                    "language": "en-US",
                    "punctuate": True,
                    "interim_results": False,
                }
            )
            await self.stt_service.initialize()
            logger.info(f"✅ STT service initialized for session {self.session_id}")

            # LLM Service - Fixed OpenAI adapter
            logger.info(f"🧠 Creating LLM service for session {self.session_id}")
            self.llm_service = create_gpt4o_mini()
            logger.info(f"✅ LLM service initialized for session {self.session_id}")

            # TTS Service - Using WAV TTS service for iOS compatibility
            logger.info(f"🎵 Creating WAV TTS service for session {self.session_id}")
            character_config = CharacterFactory.get_character_config(self.character)
            self.tts_service = TTSFactory.create_tts(self.character, model_override="wav")
            logger.info(f"✅ WAV TTS service initialized for session {self.session_id}")

            # Set initial conversation state
            logger.info(f"🛡️ Setting initial state to LISTENING for session {self.session_id}")
            self._set_state("LISTENING")
            self.last_activity_time = time.time()

            # 🛡️ Start reliability watchdog (background monitoring, zero latency impact)
            logger.info(f"🛡️ About to start watchdog for session {self.session_id}")
            self._start_watchdog()
            logger.info(f"🛡️ Watchdog started for session {self.session_id}")

            logger.info(
                f"✅ Audio session {self.session_id} initialized with character {self.character} - Ready for conversation"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize session {self.session_id}: {e}")
            logger.error(f"❌ Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            # 🛡️ GUARANTEED RESET: Always return to safe state
            self._force_reset_state("LISTENING", f"initialization_error: {e}")
            raise

    def _set_state(self, new_state: str):
        """Set conversation state with watchdog tracking (zero latency)"""
        if self.conversation_state != new_state:
            old_state = self.conversation_state
            self.conversation_state = new_state
            self._state_change_time = time.time()
            logger.info(f"🛡️ State change: {old_state} → {new_state} at {self._state_change_time}")

    def _start_watchdog(self):
        """Start background watchdog timer (runs independently, zero latency impact)"""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        
        logger.info(f"🛡️ Starting watchdog for session {self.session_id}")
        self._watchdog_task = asyncio.create_task(self._watchdog_monitor())
        logger.debug(f"🛡️ Watchdog task created: {self._watchdog_task}")

    async def _watchdog_monitor(self):
        """Background watchdog that monitors for stuck states (zero latency impact)"""
        logger.info(f"🛡️ Watchdog monitor started for session {self.session_id}")
        try:
            check_count = 0
            while self.session_active:
                await asyncio.sleep(0.5)  # Check more frequently - every 500ms
                check_count += 1
                
                # Skip monitoring if in LISTENING state (safe state)
                if self.conversation_state == "LISTENING":
                    if check_count % 10 == 0:  # Log every 5 seconds when in LISTENING
                        logger.debug(f"🛡️ Watchdog check #{check_count}: LISTENING state (safe)")
                    continue
                
                state_duration = time.time() - self._state_change_time
                
                # Log every check when not in LISTENING state
                logger.debug(f"🛡️ Watchdog check #{check_count}: State '{self.conversation_state}' for {state_duration:.1f}s")
                
                # More aggressive monitoring with warnings
                if state_duration > 5.0:
                    logger.warning(
                        f"🛡️ WATCHDOG WARNING: State '{self.conversation_state}' running for {state_duration:.1f}s"
                    )
                
                if state_duration > self._max_state_duration:
                    logger.error(
                        f"🛡️ WATCHDOG FORCE RESET: State '{self.conversation_state}' stuck for {state_duration:.1f}s (max: {self._max_state_duration}s) - EMERGENCY RESET"
                    )
                    self._force_reset_state("LISTENING", f"watchdog_emergency_reset_after_{state_duration:.1f}s")
                    break  # Exit monitoring loop after reset
                    
        except asyncio.CancelledError:
            logger.info(f"🛡️ Watchdog cancelled for session {self.session_id}")
        except Exception as e:
            logger.error(f"🛡️ Watchdog error: {e}")
        finally:
            logger.info(f"🛡️ Watchdog monitor ended for session {self.session_id}")

    def _force_reset_state(self, target_state: str = "LISTENING", reason: str = "unknown"):
        """Force immediate state reset (emergency recovery, minimal latency)"""
        logger.error(f"🛡️ EMERGENCY FORCE RESET: {self.conversation_state} → {target_state} (reason: {reason})")
        
        # Immediate state reset
        old_state = self.conversation_state
        self._set_state(target_state)
        
        # Clear processing flags immediately
        self._processing_audio = False
        
        # Force cleanup of buffers immediately
        self._audio_buffer.clear()
        
        # 🛡️ NOTIFY CLIENT: Send error response so client doesn't hang
        if hasattr(self, '_current_websocket') and self._current_websocket:
            try:
                asyncio.create_task(self._send_watchdog_error(reason))
            except Exception as e:
                logger.warning(f"⚠️ Could not send watchdog error to client: {e}")
        
        # Log emergency reset for monitoring
        logger.error(f"🚨 EMERGENCY: Session {self.session_id} force reset from {old_state} after {reason}")
        
        # Schedule heavy cleanup for later (zero latency)
        self._schedule_cleanup(f"emergency_reset_{reason}")
    
    async def _send_watchdog_error(self, reason: str):
        """Send error response to client when watchdog triggers"""
        try:
            if self._current_websocket:
                await self._current_websocket.send_json({
                    "type": "error",
                    "message": f"Request timeout - system reset for reliability",
                    "reason": reason,
                    "conversation_state": self.conversation_state,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info(f"🛡️ Sent watchdog error to client: {reason}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send watchdog error: {e}")

    def _schedule_cleanup(self, reason: str):
        """Schedule cleanup to happen asynchronously (zero latency impact)"""
        cleanup_task = asyncio.create_task(self._async_cleanup(reason))
        self._cleanup_queue.append(cleanup_task)
        
        # Keep only last 5 cleanup tasks
        while len(self._cleanup_queue) > 5:
            old_task = self._cleanup_queue.pop(0)
            if not old_task.done():
                old_task.cancel()

    async def _async_cleanup(self, reason: str):
        """Async cleanup that doesn't block responses (runs in background)"""
        try:
            # Clear buffers
            self._audio_buffer.clear()
            
            # Reset energy tracking
            if len(self._recent_energy_levels) > 5:
                self._recent_energy_levels = self._recent_energy_levels[-3:]
            
            # Update activity time
            self.last_activity_time = time.time()
            
            # Force garbage collection for memory cleanup
            import gc
            gc.collect()
            
            logger.debug(f"🧹 Async cleanup completed for session {self.session_id} (reason: {reason})")
            
        except Exception as e:
            logger.warning(f"⚠️ Async cleanup error: {e}")

    def _is_healthy(self) -> bool:
        """Quick health check (cached for 1 second, minimal latency)"""
        current_time = time.time()
        
        # Use cached result if checked recently
        if current_time - self._last_health_check < 1.0:
            return True
        
        self._last_health_check = current_time
        
        # Quick checks only (no network calls)
        return (
            self.session_active and 
            self.stt_service is not None and 
            self.llm_service is not None and 
            self.tts_service is not None
        )

    async def process_audio_chunk(self, audio_data: bytes, websocket: WebSocket) -> Optional[str]:
        """
        Process incoming audio chunk with always-on VAD and state-aware transcription.
        
        VAD Processing: Always active regardless of conversation state
        Transcription Processing: Only in LISTENING state
        """
        # Performance monitoring for VAD decoupling
        chunk_start_time = time.perf_counter()
        
        # Track chunk processing
        self._track_performance_metric("chunk_processed")
        
        try:
            # Check WebSocket connection state before processing
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(f"⚠️ WebSocket not connected, skipping audio processing")
                return None

            # 🎯 INTERRUPTION FIX: Always allow VAD processing for interruption detection
            # Only check basic service availability, not session_active
            if not (self.stt_service and self.llm_service and self.tts_service):
                logger.warning(f"⚠️ Core services missing, skipping audio processing")
                return None

            # ✅ ALWAYS-ON VAD: Always update activity time and process audio
            self.last_activity_time = time.time()

            # ✅ ALWAYS-ON VAD: Always add to buffer regardless of conversation state
            self._audio_buffer.extend(audio_data)

            # ✅ ALWAYS-ON VAD: Always calculate audio energy
            audio_energy = self._calculate_audio_energy(audio_data)
            current_time = time.time()

            # ✅ ALWAYS-ON VAD: Always update energy history for sustained speech detection
            self._recent_energy_levels.append(audio_energy)
            if len(self._recent_energy_levels) > self._max_energy_history:
                self._recent_energy_levels.pop(0)

            # ✅ ALWAYS-ON VAD: Log audio energy for debugging (every 32KB to avoid spam)
            if len(self._audio_buffer) % 32000 == 0:  # Log every ~1 second
                avg_energy = sum(self._recent_energy_levels) / len(self._recent_energy_levels) if self._recent_energy_levels else 0
                logger.info(
                    f"🎤 Audio energy: {audio_energy:.1f} | Avg: {avg_energy:.1f} | Threshold: {self._energy_threshold} | State: {self.conversation_state}"
                )
                
                # 🔍 VALIDATION: Detailed energy analysis for real audio debugging
                if audio_energy > 0:  # Only log when we have actual audio
                    logger.info(f"🔍 VALIDATION: Energy analysis - Current: {audio_energy:.1f}, Threshold: {self._energy_threshold}, Above threshold: {audio_energy > self._energy_threshold}")
                    logger.info(f"🔍 VALIDATION: Buffer size: {len(self._audio_buffer)} bytes, Recent energies: {self._recent_energy_levels[-3:] if len(self._recent_energy_levels) >= 3 else self._recent_energy_levels}")

            # ✅ ALWAYS-ON VAD: Always perform speech detection regardless of conversation state
            speech_detected = self._detect_sustained_speech(audio_energy, current_time)

            # ✅ ALWAYS-ON VAD: Always emit speech detection events (with state context)
            if speech_detected and not self._processing_audio:
                self._processing_audio = True
                self._last_speech_time = current_time
                
                # Track speech detection
                self._track_performance_metric("speech_detected")

                # Calculate confidence based on energy levels and consistency
                confidence = self._calculate_speech_confidence()

                # Enhanced speech detection event with conversation state context
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "speech_detected",
                            "confidence": confidence,
                            "energy": audio_energy,
                            "conversation_state": self.conversation_state,
                            "can_process_transcription": self.conversation_state == "LISTENING",
                            "sustained_chunks": len(
                                [
                                    e
                                    for e in self._recent_energy_levels[
                                        -self._min_sustained_chunks :
                                    ]
                                    if e > self._energy_threshold
                                ]
                            ),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                
                # State-aware logging and interruption detection
                if self.conversation_state == "LISTENING":
                    logger.info(
                        f"🗣️ BACKEND HEARD YOU: Speech detected (energy: {audio_energy}, confidence: {confidence:.2f}) - WILL PROCESS"
                    )
                elif self.conversation_state == "RESPONDING":
                    logger.info(
                        f"🗣️ BACKEND HEARD YOU: Speech detected during {self.conversation_state} (energy: {audio_energy}, confidence: {confidence:.2f}) - CHECKING FOR INTERRUPTION"
                    )
                    
                    # 🎯 INTERRUPTION DETECTION: Check if user is trying to interrupt AI response
                    await self._handle_potential_interruption(websocket, confidence, audio_energy, current_time)
                else:
                    logger.info(
                        f"🗣️ BACKEND HEARD YOU: Speech detected during {self.conversation_state} (energy: {audio_energy}, confidence: {confidence:.2f}) - VAD ONLY"
                    )

            # 🎯 STATE-AWARE TRANSCRIPTION: Only process transcription if session is active AND in LISTENING state
            if not self.session_active or self.conversation_state != "LISTENING":
                # VAD completed, but skip transcription processing
                chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
                self._track_performance_metric("vad_processing_time", chunk_duration_ms)
                logger.debug(f"🔍 VAD-only processing: {chunk_duration_ms:.2f}ms (active: {self.session_active}, state: {self.conversation_state})")
                return None

            # TRANSCRIPTION PROCESSING: Only when in LISTENING state
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
            recent_avg_energy = (
                sum(self._recent_energy_levels[-5:]) / min(5, len(self._recent_energy_levels))
                if self._recent_energy_levels
                else 0
            )
            if should_process and recent_avg_energy < (self._energy_threshold * 0.3):  # Lowered from 0.6 for real mic sensitivity
                logger.debug(
                    f"🔇 Skipping processing - recent avg energy too low: {recent_avg_energy:.1f}"
                )
                should_process = False
                # Clear buffer of likely noise
                self._audio_buffer.clear()
                self._processing_audio = False

            if should_process:
                # Track transcription attempt
                self._track_performance_metric("transcription_attempted")
                
                # 🛡️ RELIABILITY: Use state tracking for watchdog
                self._set_state("PROCESSING")

                # Get raw audio bytes from buffer
                audio_bytes = bytes(self._audio_buffer)

                # Clear buffer
                self._audio_buffer.clear()

                # Reset processing flag for next audio chunk
                self._processing_audio = False

                logger.info(f"📝 Processing audio buffer: {process_reason}")

                # 🛡️ RELIABILITY: Critical operation with timeout protection
                try:
                    # Convert raw PCM to WAV format for Deepgram
                    wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000, num_channels=1, bit_depth=16)

                    # Send transcription start event (check connection first)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(
                            {
                                "type": "transcription_partial",
                                "text": "",
                                "message": "Processing your speech...",
                                "buffer_size": len(audio_bytes),
                                "conversation_state": self.conversation_state,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    logger.info("📝 BACKEND UNDERSTANDING: Processing speech...")

                    # 🛡️ CRITICAL: STT call with aggressive timeout 
                    logger.debug(f"🛡️ Starting STT transcription...")
                    transcription = await asyncio.wait_for(
                        self.stt_service.transcribe_audio_bytes(wav_audio),
                        timeout=5.0  # Reduced to 5s - aggressive timeout
                    )
                    logger.debug(f"🛡️ STT transcription completed")

                    if transcription and transcription.strip():
                        # Send complete transcription (check connection first)
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                {
                                    "type": "transcription_complete",
                                    "text": transcription.strip(),
                                    "buffer_size": len(audio_bytes),
                                    "conversation_state": self.conversation_state,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        logger.info(f"✅ BACKEND UNDERSTOOD: '{transcription}'")
                        logger.info(f"👤 User ({self.character}): '{transcription}'")

                        # Increment conversation turn
                        self.conversation_turn_count += 1
                        logger.info(f"🔄 Conversation turn #{self.conversation_turn_count}")

                        # 🛡️ RELIABILITY: Return to safe state BEFORE returning result
                        self._set_state("LISTENING")
                        
                        # Performance logging
                        chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
                        self._track_performance_metric("full_processing_time", chunk_duration_ms)
                        logger.info(f"🔍 Full processing: {chunk_duration_ms:.2f}ms")
                        
                        return transcription.strip()
                    else:
                        # Send empty transcription result (check connection first)
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                {
                                    "type": "transcription_complete",
                                    "text": "",
                                    "message": "No speech detected in audio",
                                    "buffer_size": len(audio_bytes),
                                    "conversation_state": self.conversation_state,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        logger.info(f"🔇 No speech in {len(audio_bytes)} bytes of audio")

                        # 🛡️ RELIABILITY: Return to safe state
                        self._set_state("LISTENING")

                except asyncio.TimeoutError:
                    logger.error(f"🛡️ STT timeout after 5s - forcing reset")
                    self._force_reset_state("LISTENING", "stt_timeout")
                    
                except Exception as stt_error:
                    logger.error(f"🛡️ STT processing failed: {stt_error}")
                    self._force_reset_state("LISTENING", f"stt_error: {stt_error}")

            # Performance logging for VAD-only processing
            chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
            self._track_performance_metric("vad_processing_time", chunk_duration_ms)
            logger.debug(f"🔍 VAD processing: {chunk_duration_ms:.2f}ms")

        except Exception as e:
            logger.error(f"❌ Audio processing error in session {self.session_id}: {e}")
            
            # 🛡️ GUARANTEED CLEANUP: Always reset state on any error
            self._force_reset_state("LISTENING", f"audio_chunk_error: {e}")
            
            # Send error event to frontend (only if connection is active)
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Audio processing failed",
                            "details": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                except Exception:
                    logger.debug("Could not send audio processing error - connection closed")

        finally:
            # 🛡️ GUARANTEED: Always ensure we're in a good state
            if self.conversation_state == "PROCESSING":
                self._set_state("LISTENING")

        return None

    def _calculate_audio_energy(self, audio_data: bytes) -> float:
        """Calculate the energy/volume of audio data to detect speech vs silence"""
        try:
            if len(audio_data) < 2:
                return 0.0

            import math
            import struct

            # Convert bytes to 16-bit signed integers
            sample_count = len(audio_data) // 2
            samples = struct.unpack(f"<{sample_count}h", audio_data[: sample_count * 2])

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
            e
            for e in self._recent_energy_levels[-self._min_sustained_chunks :]
            if e > self._energy_threshold
        ]

        # Require at least 3 out of last 3 chunks to be high energy
        return len(recent_high_energy_chunks) >= self._min_sustained_chunks

    def _calculate_speech_confidence(self) -> float:
        """Calculate confidence score based on energy patterns"""
        if not self._recent_energy_levels:
            return 0.0

        # Get recent measurements
        recent_energies = self._recent_energy_levels[-self._min_sustained_chunks :]
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

    async def _handle_potential_interruption(self, websocket: WebSocket, confidence: float, audio_energy: float, current_time: float):
        """
        Handle potential user interruption during AI response.
        
        Analyzes speech confidence and energy to determine if user is trying to interrupt,
        then cancels ongoing TTS streaming if criteria are met.
        """
        interruption_start_time = time.perf_counter()
        
        try:
            # Check if interruption is enabled and not in cooldown
            if not self._interruption_enabled:
                logger.debug("🎯 Interruption disabled, ignoring speech during response")
                return
                
            if current_time - self._last_interruption_time < self._interruption_cooldown:
                logger.debug(f"🎯 Interruption cooldown active ({current_time - self._last_interruption_time:.1f}s), ignoring")
                return
            
            # Check if confidence meets interruption threshold
            if confidence < self._interruption_threshold:
                logger.debug(f"🎯 Speech confidence {confidence:.2f} below interruption threshold {self._interruption_threshold}, ignoring")
                return
            
            # Check if we have an active TTS stream to interrupt
            if not self._current_tts_task or self._current_tts_task.done():
                logger.debug("🎯 No active TTS stream to interrupt")
                return
            
            # 🚨 INTERRUPTION TRIGGERED!
            logger.info(f"🎯 🚨 INTERRUPTION DETECTED!")
            logger.info(f"   - Confidence: {confidence:.2f} (threshold: {self._interruption_threshold})")
            logger.info(f"   - Energy: {audio_energy:.1f}")
            logger.info(f"   - Chunks sent before interruption: {self._response_chunks_sent}")
            
            # Cancel current TTS streaming
            self._stream_cancelled = True
            if self._current_tts_task:
                self._current_tts_task.cancel()
                logger.info("🎯 ✂️ TTS streaming cancelled")
            
            # Update interruption tracking
            self._last_interruption_time = current_time
            self._track_performance_metric("interruptions")
            
            # Calculate interruption latency
            interruption_latency_ms = (time.perf_counter() - interruption_start_time) * 1000
            self._track_performance_metric("interruption_latencies", interruption_latency_ms)
            
            # Send interruption event to client
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "interruption_detected",
                    "confidence": confidence,
                    "energy": audio_energy,
                    "chunks_interrupted": self._response_chunks_sent,
                    "interruption_latency_ms": interruption_latency_ms,
                    "conversation_state": self.conversation_state,
                    "timestamp": datetime.now().isoformat(),
                })
            
            # Reset conversation state to LISTENING (user can now speak)
            self._set_state("LISTENING")
            
            # Reset response tracking
            self._response_chunks_sent = 0
            
            logger.info(f"🎯 ✅ Interruption handled in {interruption_latency_ms:.2f}ms - Ready for new input")
            
        except Exception as e:
            logger.error(f"🎯 ❌ Error handling interruption: {e}")
            # Don't let interruption errors break the conversation
            # Just log and continue

    def configure_interruption_sensitivity(self, threshold: float = 1.5, cooldown: float = 1.0):
        """
        Configure interruption sensitivity parameters.
        
        Args:
            threshold: Confidence threshold for interruption (lower = more sensitive)
            cooldown: Seconds to wait after interruption before allowing another
        """
        old_threshold = self._interruption_threshold
        old_cooldown = self._interruption_cooldown
        
        self._interruption_threshold = max(0.5, min(3.0, threshold))  # Clamp between 0.5-3.0
        self._interruption_cooldown = max(0.1, min(5.0, cooldown))    # Clamp between 0.1-5.0
        
        logger.info(f"🎯 Interruption sensitivity updated:")
        logger.info(f"   - Threshold: {old_threshold:.1f} → {self._interruption_threshold:.1f}")
        logger.info(f"   - Cooldown: {old_cooldown:.1f}s → {self._interruption_cooldown:.1f}s")

    def enable_interruptions(self, enabled: bool = True):
        """Enable or disable interruption detection"""
        old_state = self._interruption_enabled
        self._interruption_enabled = enabled
        
        status = "ENABLED" if enabled else "DISABLED"
        logger.info(f"🎯 Interruption system {status} (was {'enabled' if old_state else 'disabled'})")
        
        return {"interruption_enabled": self._interruption_enabled}

    def get_interruption_stats(self) -> dict:
        """Get interruption performance statistics"""
        stats = {
            "interruption_enabled": self._interruption_enabled,
            "interruption_threshold": self._interruption_threshold,
            "interruption_cooldown": self._interruption_cooldown,
            "total_interruptions": self._performance_metrics.get("interruptions", 0),
            "interruption_latencies": self._performance_metrics.get("interruption_latencies", []),
            "has_active_tts": self._current_tts_task is not None and not self._current_tts_task.done(),
            "response_chunks_sent": self._response_chunks_sent,
            "last_interruption_time": self._last_interruption_time
        }
        
        # Calculate average interruption latency
        latencies = stats["interruption_latencies"]
        if latencies:
            stats["avg_interruption_latency_ms"] = sum(latencies) / len(latencies)
            stats["max_interruption_latency_ms"] = max(latencies)
            stats["min_interruption_latency_ms"] = min(latencies)
        else:
            stats["avg_interruption_latency_ms"] = 0
            stats["max_interruption_latency_ms"] = 0
            stats["min_interruption_latency_ms"] = 0
            
        return stats

    async def generate_response(self, user_input: str) -> str:
        """Generate AI response using character personality"""
        try:
            # Get character personality
            character = CharacterFactory.create_character(self.character)

            # Create conversation context
            messages = [{"role": "system", "content": character.personality}]

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
                if hasattr(chunk, "choices") and chunk.choices and chunk.choices[0].delta.content:
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
        """Convert text chunk to speech in WAV format (iOS compatible)"""
        try:
            logger.info(f"🎤 Starting WAV TTS synthesis for: '{text[:50]}...'")

            # Use direct OpenAI API for WAV output (most reliable approach)
            return await self._fallback_tts_synthesis(text)

        except Exception as e:
            logger.error(f"❌ WAV TTS synthesis error: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            import traceback

            logger.error(f"❌ Traceback: {traceback.format_exc()}")

            # Return empty bytes as fallback
            return b""


    async def _fallback_tts_synthesis(self, text: str) -> bytes:
        """Fallback TTS synthesis using direct OpenAI API (WAV format for iOS compatibility)"""
        try:
            logger.info(f"🔄 Trying fallback TTS for: '{text[:30]}...'")

            # Direct OpenAI TTS call with WAV output
            import openai

            response = await openai.AsyncOpenAI().audio.speech.create(
                model="tts-1",
                voice="nova" if self.character == "adina" else "onyx",
                input=text,
                response_format="wav",  # Changed from mp3 to wav for iOS compatibility
                speed=1.0,  # Normal speed
                # Note: OpenAI TTS doesn't support sample rate specification in the API
                # We'll need to handle this differently
            )

            audio_data = await response.aread()
            
            # 🔍 DETAILED BYTE ANALYSIS
            logger.info(f"🎵 Fallback TTS generated: {len(audio_data)} bytes")
            
            # Check first 20 bytes to identify format
            first_20_bytes = audio_data[:20] if len(audio_data) >= 20 else audio_data
            first_20_hex = ' '.join(f'{b:02x}' for b in first_20_bytes)
            first_20_ascii = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in first_20_bytes)
            
            logger.info(f"🔍 BYTE ANALYSIS: First 20 bytes hex: {first_20_hex}")
            logger.info(f"🔍 BYTE ANALYSIS: First 20 bytes ASCII: {first_20_ascii}")
            
            # Check for common audio format signatures
            is_wav = len(audio_data) >= 4 and audio_data[:4] == b'RIFF'
            is_mp3 = len(audio_data) >= 3 and (audio_data[:3] == b'ID3' or (audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0))
            is_aac = len(audio_data) >= 2 and audio_data[:2] == b'\xff\xf1'
            
            logger.info(f"🔍 FORMAT DETECTION: WAV={is_wav}, MP3={is_mp3}, AAC={is_aac}")
            
            # If it's WAV, check the header details
            if is_wav and len(audio_data) >= 44:
                try:
                    import struct
                    # Parse WAV header
                    riff, size, wave = struct.unpack('<4sI4s', audio_data[:12])
                    fmt, fmt_size, audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack('<4sIHHIIHH', audio_data[12:36])
                    
                    logger.info(f"🔍 WAV HEADER: Sample Rate={sample_rate}, Channels={channels}, Bits={bits_per_sample}, Format={audio_format}")
                    
                    # Check if it's iOS compatible
                    ios_compatible = (sample_rate in [8000, 16000, 22050, 44100, 48000] and 
                                    channels in [1, 2] and 
                                    bits_per_sample in [8, 16, 24, 32] and
                                    audio_format == 1)  # PCM
                    
                    logger.info(f"🔍 iOS COMPATIBILITY: {ios_compatible}")
                    
                    # 🎯 FIX: If not iOS compatible, convert to iOS-compatible format
                    if not ios_compatible and sample_rate == 24000:
                        logger.info(f"🔄 Converting 24kHz WAV to iOS-compatible 22.05kHz")
                        try:
                            import wave
                            import io
                            import numpy as np
                            from scipy import signal
                            
                            # Read the original WAV
                            with io.BytesIO(audio_data) as wav_io:
                                with wave.open(wav_io, 'rb') as wav_in:
                                    # Get original parameters
                                    frames = wav_in.readframes(wav_in.getnframes())
                                    original_sample_rate = wav_in.getframerate()
                                    channels = wav_in.getnchannels()
                                    sample_width = wav_in.getsampwidth()
                                    
                                    # Convert to numpy array
                                    audio_array = np.frombuffer(frames, dtype=np.int16)
                                    
                                    # Resample from 24kHz to 22.05kHz
                                    target_sample_rate = 22050
                                    resampled_audio = signal.resample(audio_array, 
                                                                     int(len(audio_array) * target_sample_rate / original_sample_rate))
                                    
                                    # Convert back to int16
                                    resampled_audio = (resampled_audio * 32767).astype(np.int16)
                                    
                                    # Create new WAV with iOS-compatible format
                                    with io.BytesIO() as new_wav_io:
                                        with wave.open(new_wav_io, 'wb') as wav_out:
                                            wav_out.setnchannels(channels)
                                            wav_out.setsampwidth(sample_width)
                                            wav_out.setframerate(target_sample_rate)
                                            wav_out.writeframes(resampled_audio.tobytes())
                                        
                                        audio_data = new_wav_io.getvalue()
                                        logger.info(f"✅ Successfully converted to iOS-compatible 22.05kHz WAV: {len(audio_data)} bytes")
                                        
                        except Exception as conversion_error:
                            logger.error(f"❌ WAV conversion failed: {conversion_error}")
                            # Fall back to original audio
                    
                except Exception as e:
                    logger.error(f"🔍 WAV HEADER PARSE ERROR: {e}")
            
            logger.info(f"🎵 Fallback TTS generated: {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"❌ Fallback TTS also failed: {e}")
            return b""

    async def process_conversation_turn(self, websocket: WebSocket, user_input: str, audio_duration_seconds: float = None):
        """
        Process a complete conversation turn with zero-impact cost tracking.
        
        This method orchestrates STT → LLM → TTS pipeline while logging cost events
        with fire-and-forget pattern that never blocks voice processing.
        """
        turn_start_time = time.time()
        
        # Initialize timing tracking
        stt_duration_ms = None  # Already completed (from process_audio_chunk)
        llm_duration_ms = None
        tts_duration_ms = None
        
        try:
            # Generate AI response with timing
            llm_start_time = time.time()
            await self.process_and_stream_response(websocket, user_input)
            llm_duration_ms = int((time.time() - llm_start_time) * 1000)
            
            # Calculate total conversation turn latency
            total_latency_ms = int((time.time() - turn_start_time) * 1000)
            
            # 🎯 ZERO-IMPACT COST LOGGING (fire-and-forget, microseconds operation)
            log_voice_event({
                'session_id': self.session_id,
                'user_id': self.user_id,
                'character': self.character,
                'timestamp': turn_start_time,
                'stt_duration_ms': stt_duration_ms,
                'llm_duration_ms': llm_duration_ms,
                'tts_duration_ms': tts_duration_ms,
                'total_latency_ms': total_latency_ms,
                'transcript_text': user_input,
                'response_text': None,  # Will be filled by process_and_stream_response
                'audio_duration_seconds': audio_duration_seconds,
                'success': True
            })
            
            # Voice processing complete - cost logging happens in background
            
        except Exception as e:
            # Even errors get logged for cost analysis (fire-and-forget)
            log_voice_event({
                'session_id': self.session_id,
                'user_id': self.user_id,
                'character': self.character,
                'timestamp': turn_start_time,
                'transcript_text': user_input,
                'success': False,
                'error_message': str(e)
            })
            # Re-raise the exception for normal error handling
            raise

    async def process_and_stream_response(self, websocket: WebSocket, user_input: str):
        """Generate AI response and stream audio chunks in real-time"""
        # 🛡️ RELIABILITY: Track websocket for watchdog notifications
        self._current_websocket = websocket
        
        # 🛡️ RELIABILITY: Pre-flight health checks (minimal latency)
        if not self._is_healthy():
            logger.warning(f"⚠️ Session unhealthy, cannot stream response")
            return
            
        try:
            # Check connection state before starting
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(f"⚠️ WebSocket disconnected, cannot stream response")
                return

            # Check session state
            if not self.session_active:
                logger.warning(f"⚠️ Session inactive, cannot stream response")
                return

            # 🛡️ RELIABILITY: Use state tracking for watchdog
            self._set_state("RESPONDING")

            # 🎯 INTERRUPTION SYSTEM: Initialize response tracking
            self._response_chunks_sent = 0
            self._stream_cancelled = False

            # Send processing started event
            await websocket.send_json(
                {
                    "type": "processing_started",
                    "character": self.character,
                    "message": f"{self.character.title()} is thinking...",
                    "conversation_state": self.conversation_state,
                    "conversation_turn": self.conversation_turn_count,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(
                f"🤖 Processing started with {self.character} (Turn #{self.conversation_turn_count})"
            )

            # 🛡️ CRITICAL: LLM call with aggressive timeout protection
            try:
                logger.debug(f"🛡️ Starting LLM generation...")
                response_text = await asyncio.wait_for(
                    self.generate_response(user_input),
                    timeout=12.0  # Increased to 12s for longer responses (especially during testing)
                )
                logger.debug(f"🛡️ LLM generation completed")
            except asyncio.TimeoutError:
                logger.error(f"🛡️ LLM timeout after 12s - forcing reset")
                self._force_reset_state("LISTENING", "llm_timeout")
                return
            except Exception as llm_error:
                logger.error(f"🛡️ LLM generation failed: {llm_error}")
                self._force_reset_state("LISTENING", f"llm_error: {llm_error}")
                return

            # Split response into chunks
            chunks = chunk_ai_response(response_text, max_chunk_length=120)

            if not chunks:
                logger.warning("⚠️ No chunks generated from AI response")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Failed to generate response chunks",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                # 🛡️ RELIABILITY: Reset state even on empty chunks
                self._force_reset_state("LISTENING", "empty_chunks")
                return

            logger.info(f"🎯 Generating {len(chunks)} audio chunks for concatenated stream")

            # Send response start notification with full details
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "response_started",
                        "character": self.character,
                        "full_response": response_text,
                        "chunk_count": len(chunks),
                        "conversation_state": self.conversation_state,
                        "conversation_turn": self.conversation_turn_count,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # 🎯 NEW APPROACH: Generate all TTS chunks first, then concatenate
            logger.info(f"🎤 Starting TTS generation for {len(chunks)} chunks")
            tts_start_time = time.time()
            
            # Generate all TTS chunks in parallel for better performance
            tts_tasks = []
            for i, chunk in enumerate(chunks):
                task = asyncio.create_task(self.synthesize_speech_chunk(chunk))
                tts_tasks.append((i, chunk, task))
            
            # Wait for all TTS chunks to complete
            audio_chunks = []
            for i, chunk_text, task in tts_tasks:
                try:
                    audio_data = await task
                    if audio_data:
                        audio_chunks.append((i, audio_data))
                        logger.info(f"🎵 Generated TTS chunk {i+1}/{len(chunks)}: {len(audio_data)} bytes")
                    else:
                        logger.warning(f"⚠️ TTS chunk {i+1} returned empty audio")
                except Exception as e:
                    logger.error(f"❌ TTS chunk {i+1} failed: {e}")
            
            # Sort chunks by original order
            audio_chunks.sort(key=lambda x: x[0])
            audio_chunks = [chunk[1] for chunk in audio_chunks]
            
            tts_duration = time.time() - tts_start_time
            logger.info(f"🎤 TTS generation completed: {len(audio_chunks)} chunks in {tts_duration:.2f}s")

            if not audio_chunks:
                logger.error("❌ No audio chunks generated")
                self._force_reset_state("LISTENING", "no_audio_chunks")
                return

            # 🎯 CONCATENATE: Merge all audio chunks into one continuous stream
            logger.info(f"🔄 Concatenating {len(audio_chunks)} audio chunks into single stream")
            concatenated_audio = await self._concatenate_audio_chunks(audio_chunks)
            
            if not concatenated_audio:
                logger.error("❌ Audio concatenation failed")
                self._force_reset_state("LISTENING", "concatenation_failed")
                return

            logger.info(f"✅ Concatenated audio stream: {len(concatenated_audio)} bytes")

            # 🎯 SEND: Stream the concatenated audio as one continuous file
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Send as base64-encoded audio data
                    import base64
                    audio_base64 = base64.b64encode(concatenated_audio).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "audio_stream",
                        "character": self.character,
                        "audio_data": audio_base64,
                        "audio_size_bytes": len(concatenated_audio),
                        "audio_size_base64": len(audio_base64),
                        "chunk_count": len(chunks),
                        "is_concatenated": True,
                        "conversation_state": self.conversation_state,
                        "conversation_turn": self.conversation_turn_count,
                        "timestamp": datetime.now().isoformat(),
                    })
                    
                    logger.info(f"🎵 Sent concatenated audio stream: {len(concatenated_audio)} bytes, {len(audio_base64)} base64 chars")
                    
                except Exception as send_error:
                    logger.error(f"❌ Failed to send concatenated audio: {send_error}")
                    self._force_reset_state("LISTENING", f"send_error: {send_error}")
                    return

            # Send response complete notification
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "response_complete",
                        "character": self.character,
                        "full_response": response_text,
                        "total_audio_size": len(concatenated_audio),
                        "chunk_count": len(chunks),
                        "conversation_state": self.conversation_state,
                        "conversation_turn": self.conversation_turn_count,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            logger.info(f"🎯 Concatenated audio streaming completed")
            self._set_state("LISTENING")
            logger.info(f"🔄 Response complete - Back to LISTENING state (Turn #{self.conversation_turn_count})")

        except Exception as e:
            logger.error(f"❌ Error in process_and_stream_response: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            self._force_reset_state("LISTENING", f"stream_error: {e}")

    async def _concatenate_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """Concatenate multiple WAV audio chunks into one continuous WAV stream"""
        if not audio_chunks:
            return b""
        
        if len(audio_chunks) == 1:
            return audio_chunks[0]
        
        try:
            import wave
            import io
            import struct
            
            logger.info(f"🔄 Concatenating {len(audio_chunks)} WAV chunks")
            
            # Extract audio data from each WAV chunk (remove headers)
            audio_data_chunks = []
            total_samples = 0
            sample_rate = None
            channels = None
            sample_width = None
            
            for i, wav_data in enumerate(audio_chunks):
                try:
                    with io.BytesIO(wav_data) as wav_io:
                        with wave.open(wav_io, 'rb') as wav_in:
                            # Get WAV parameters (should be same for all chunks)
                            if sample_rate is None:
                                sample_rate = wav_in.getframerate()
                                channels = wav_in.getnchannels()
                                sample_width = wav_in.getsampwidth()
                            else:
                                # Verify all chunks have same parameters
                                if (wav_in.getframerate() != sample_rate or 
                                    wav_in.getnchannels() != channels or 
                                    wav_in.getsampwidth() != sample_width):
                                    logger.warning(f"⚠️ WAV chunk {i} has different parameters")
                            
                            # Read audio data (skip header)
                            frames = wav_in.readframes(wav_in.getnframes())
                            audio_data_chunks.append(frames)
                            total_samples += wav_in.getnframes()
                            
                            logger.debug(f"🔄 Chunk {i+1}: {wav_in.getnframes()} frames, {len(frames)} bytes")
                            
                except Exception as e:
                    logger.error(f"❌ Failed to process WAV chunk {i}: {e}")
                    continue
            
            if not audio_data_chunks:
                logger.error("❌ No valid audio data chunks found")
                return b""
            
            # Concatenate all audio data
            concatenated_audio_data = b''.join(audio_data_chunks)
            
            # Create new WAV file with concatenated data
            with io.BytesIO() as new_wav_io:
                with wave.open(new_wav_io, 'wb') as wav_out:
                    wav_out.setnchannels(channels)
                    wav_out.setsampwidth(sample_width)
                    wav_out.setframerate(sample_rate)
                    wav_out.writeframes(concatenated_audio_data)
                
                concatenated_wav = new_wav_io.getvalue()
                
                logger.info(f"✅ Concatenated {len(audio_chunks)} chunks: {total_samples} total frames, {len(concatenated_wav)} bytes")
                logger.info(f"✅ Final WAV: {sample_rate}Hz, {channels} channels, {sample_width*8} bits")
                
                return concatenated_wav
                
        except Exception as e:
            logger.error(f"❌ Audio concatenation failed: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return b""

    def reset_for_next_turn(self):
        """Reset audio processing state between conversation turns (not between sessions)"""
        # 🛡️ RELIABILITY: Ensure we're in safe state
        if self.conversation_state != "LISTENING":
            self._set_state("LISTENING")
            
        # 🛡️ ASYNC CLEANUP: Schedule the actual cleanup work (zero latency)
        self._schedule_cleanup("turn_reset")
        
        logger.debug(f"🔄 Session {self.session_id} reset scheduled for next conversation turn")

    def is_session_active(self) -> bool:
        """Check if session should remain active based on recent activity"""
        inactive_time = time.time() - self.last_activity_time

        # Keep session active for 5 minutes of inactivity
        max_inactive_time = 300  # 5 minutes

        if inactive_time > max_inactive_time:
            logger.info(
                f"⏰ Session {self.session_id} inactive for {inactive_time:.1f}s, marking for cleanup"
            )
            self.session_active = False

        return self.session_active

    async def cleanup(self):
        """Clean up session resources with reliability shutdown"""
        try:
            # Mark session as inactive immediately
            self.session_active = False
            self._set_state("DISCONNECTED")

            # 🛡️ RELIABILITY: Cancel watchdog first
            if self._watchdog_task and not self._watchdog_task.done():
                self._watchdog_task.cancel()
                try:
                    await self._watchdog_task
                except asyncio.CancelledError:
                    pass  # Expected
                logger.debug(f"🛡️ Watchdog cancelled for session {self.session_id}")

            # 🛡️ RELIABILITY: Cancel any pending cleanup tasks
            for task in self._cleanup_queue:
                if not task.done():
                    task.cancel()
            self._cleanup_queue.clear()

            # Shutdown services
            if self.stt_service:
                await self.stt_service.shutdown()
                
            logger.info(
                f"🧹 Session {self.session_id} cleaned up (had {self.conversation_turn_count} turns)"
            )
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error for session {self.session_id}: {e}")

    def _track_performance_metric(self, metric_type: str, value: float = None):
        """Track performance metrics for VAD decoupling and interruption monitoring"""
        try:
            if metric_type == "chunk_processed":
                self._performance_metrics['chunk_count'] += 1
            elif metric_type == "speech_detected":
                self._performance_metrics['speech_detections'] += 1
            elif metric_type == "transcription_attempted":
                self._performance_metrics['transcription_attempts'] += 1
            elif metric_type == "interruptions":
                self._performance_metrics['interruptions'] += 1
            elif metric_type == "vad_processing_time" and value is not None:
                times = self._performance_metrics['vad_processing_times']
                times.append(value)
                # Keep only last 100 measurements
                if len(times) > 100:
                    times.pop(0)
            elif metric_type == "full_processing_time" and value is not None:
                times = self._performance_metrics['full_processing_times']
                times.append(value)
                # Keep only last 100 measurements
                if len(times) > 100:
                    times.pop(0)
            elif metric_type == "interruption_latencies" and value is not None:
                latencies = self._performance_metrics['interruption_latencies']
                latencies.append(value)
                # Keep only last 50 measurements
                if len(latencies) > 50:
                    latencies.pop(0)
        except Exception as e:
            logger.debug(f"Performance tracking error: {e}")

    def get_performance_summary(self) -> dict:
        """Get performance summary for VAD decoupling validation"""
        try:
            metrics = self._performance_metrics
            
            vad_times = metrics['vad_processing_times']
            full_times = metrics['full_processing_times']
            
            interruption_latencies = metrics['interruption_latencies']
            
            summary = {
                'session_id': self.session_id,
                'chunks_processed': metrics['chunk_count'],
                'speech_detections': metrics['speech_detections'],
                'transcription_attempts': metrics['transcription_attempts'],
                'interruptions': metrics['interruptions'],
                'vad_performance': {
                    'count': len(vad_times),
                    'avg_ms': sum(vad_times) / len(vad_times) if vad_times else 0,
                    'max_ms': max(vad_times) if vad_times else 0,
                    'target_met': all(t < 10.0 for t in vad_times) if vad_times else True
                },
                'full_processing_performance': {
                    'count': len(full_times),
                    'avg_ms': sum(full_times) / len(full_times) if full_times else 0,
                    'max_ms': max(full_times) if full_times else 0,
                    'target_met': all(t < 50.0 for t in full_times) if full_times else True
                },
                'interruption_performance': {
                    'total_interruptions': metrics['interruptions'],
                    'avg_latency_ms': sum(interruption_latencies) / len(interruption_latencies) if interruption_latencies else 0,
                    'max_latency_ms': max(interruption_latencies) if interruption_latencies else 0,
                    'min_latency_ms': min(interruption_latencies) if interruption_latencies else 0,
                    'target_met': all(t < 50.0 for t in interruption_latencies) if interruption_latencies else True,  # Target <50ms
                    'enabled': self._interruption_enabled,
                    'threshold': self._interruption_threshold,
                    'cooldown': self._interruption_cooldown
                },
                'conversation_state': self.conversation_state,
                'session_active': self.session_active
            }
            
            return summary
        except Exception as e:
            logger.warning(f"Error generating performance summary: {e}")
            return {'error': str(e)}


# Global session manager
active_sessions: Dict[str, AudioSession] = {}


@router.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    session_id = str(uuid.uuid4())
    session = None

    try:
        await websocket.accept()
        logger.error(f"🚀 WATCHDOG TEST: WebSocket connected - session {session_id} - CODE UPDATED")
        logger.info(f"🔗 WebSocket connected: session {session_id}")

        # Send connection confirmation
        await websocket.send_json(
            {"type": "connected", "session_id": session_id, "timestamp": datetime.now().isoformat()}
        )

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
                    # Handle binary audio data - ALWAYS process for VAD and interruption detection
                    audio_data = data["bytes"]
                    
                    # 🔍 VALIDATION: Check if receiving PCM vs WAV
                    first_bytes = audio_data[:100] if len(audio_data) >= 100 else audio_data
                    first_bytes_hex = ' '.join(f'{b:02x}' for b in first_bytes[:20])  # First 20 bytes as hex
                    first_bytes_ascii = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in first_bytes[:20])  # ASCII representation
                    
                    # Check for WAV header signature
                    is_wav = len(audio_data) >= 4 and audio_data[:4] == b'RIFF'
                    
                    logger.info(f"🎯 AUDIO RECEIVED: {len(audio_data)} bytes, session={session is not None}")
                    logger.info(f"🔍 VALIDATION: First 20 bytes hex: {first_bytes_hex}")
                    logger.info(f"🔍 VALIDATION: First 20 bytes ASCII: {first_bytes_ascii}")
                    logger.info(f"🔍 VALIDATION: Is WAV header: {is_wav} (should be False for raw PCM)")
                    
                    if session:
                        logger.info(f"🎯 SESSION STATE: active={session.session_active}, conversation_state={session.conversation_state}, stt_service={session.stt_service is not None}")
                    
                    if session and session.stt_service:
                        logger.info(f"🎯 PROCESSING AUDIO: {len(audio_data)} bytes in {session.conversation_state} state")
                        
                        # Calculate audio duration for cost tracking (16kHz, 16-bit, mono)
                        audio_duration_seconds = len(audio_data) / (16000 * 2)  # 2 bytes per sample
                        
                        # 🎯 INTERRUPTION SYSTEM: Always process audio for VAD regardless of session_active
                        # This enables interruption detection during RESPONDING state
                        transcription = await session.process_audio_chunk(audio_data, websocket)

                        # Only process conversation turns if session is active and we got transcription
                        if transcription and session.session_active:
                            # Process complete conversation turn with zero-impact cost tracking
                            await session.process_conversation_turn(websocket, transcription, audio_duration_seconds)
                            # Reset for next conversation turn (but keep session alive)
                            session.reset_for_next_turn()

            except asyncio.TimeoutError:
                # Send keepalive ping and check session activity
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "ping",
                            "session_active": session.session_active if session else False,
                            "conversation_turns": session.conversation_turn_count if session else 0,
                        }
                    )

            except WebSocketDisconnect:
                break

            except Exception as e:
                logger.error(f"❌ Error processing message in session {session_id}: {e}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Processing error occurred",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")

    finally:
        # Cleanup
        if session:
            await session.cleanup()
            if session_id in active_sessions:
                del active_sessions[session_id]

        logger.info(f"🔌 WebSocket disconnected: session {session_id}")


async def handle_json_message(
    websocket: WebSocket, session: Optional[AudioSession], message: dict, session_id: str
) -> Optional[AudioSession]:
    """Handle JSON messages from client"""
    message_type = message.get("type")

    try:
        if message_type == "initialize":
            # Initialize session with character
            character = message.get("character", "adina")

            if character not in ["adina", "raffa"]:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Invalid character: {character}. Must be 'adina' or 'raffa'",
                    }
                )
                return session

            # Create and initialize session (with cost tracking)
            user_id = message.get("user_id", f"user_{session_id[:8]}")  # Allow user_id from client or generate one
            session = AudioSession(session_id, character, user_id)
            await session.initialize()
            active_sessions[session_id] = session

            await websocket.send_json(
                {
                    "type": "initialized",
                    "character": character,
                    "session_id": session_id,
                    "message": f"Connected to {character.title()} - Ready for conversation",
                    "conversation_state": session.conversation_state,
                    "session_active": session.session_active,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Send welcome message from character
            character_obj = CharacterFactory.create_character(character)
            welcome_message = f"Hello! I'm {character.title()}. I'm here to listen and support you. How are you feeling today?"

            # Generate WAV audio for welcome message
            try:
                welcome_audio = await session._fallback_tts_synthesis(welcome_message)
                if welcome_audio:
                    welcome_base64 = base64.b64encode(welcome_audio).decode("utf-8")
                    logger.info(f"🎵 Generated welcome WAV: {len(welcome_audio)} bytes, {len(welcome_base64)} base64 chars")
                else:
                    logger.warning("⚠️ Failed to generate welcome audio, sending text only")
                    welcome_base64 = ""
            except Exception as e:
                logger.error(f"❌ Error generating welcome audio: {e}")
                welcome_base64 = ""

            # Send welcome as first response (but don't count as conversation turn)
            await websocket.send_json(
                {
                    "type": "welcome_message",
                    "character": character,
                    "text": welcome_message,
                    "audio": welcome_base64,
                    "conversation_state": session.conversation_state,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            logger.info(f"👋 {character.title()} welcomed user in session {session_id}")

        elif message_type == "switch_character":
            if session:
                new_character = message.get("character", "adina")
                if new_character in ["adina", "raffa"]:
                    session.character = new_character
                    await websocket.send_json(
                        {
                            "type": "character_switched",
                            "character": new_character,
                            "message": f"Switched to {new_character.title()}",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

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
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Failed to process audio data",
                            "details": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Session not initialized or STT service unavailable",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "text_message":
            # Handle text-only message (no audio) - stream chunks too
            if session:
                user_text = message.get("text", "")
                if user_text.strip():
                    await session.process_and_stream_response(websocket, user_text)

        elif message_type == "ping":
            await websocket.send_json({"type": "pong"})

        # 🎯 INTERRUPTION SYSTEM: Control commands
        elif message_type == "configure_interruption":
            if session:
                threshold = message.get("threshold", 1.5)
                cooldown = message.get("cooldown", 1.0)
                session.configure_interruption_sensitivity(threshold, cooldown)
                
                await websocket.send_json({
                    "type": "interruption_configured",
                    "threshold": session._interruption_threshold,
                    "cooldown": session._interruption_cooldown,
                    "timestamp": datetime.now().isoformat()
                })

        elif message_type == "enable_interruption":
            if session:
                enabled = message.get("enabled", True)
                result = session.enable_interruptions(enabled)
                
                await websocket.send_json({
                    "type": "interruption_toggled",
                    **result,
                    "timestamp": datetime.now().isoformat()
                })

        elif message_type == "get_interruption_stats":
            if session:
                stats = session.get_interruption_stats()
                
                await websocket.send_json({
                    "type": "interruption_stats",
                    **stats,
                    "timestamp": datetime.now().isoformat()
                })

        elif message_type == "get_performance_summary":
            if session:
                summary = session.get_performance_summary()
                
                await websocket.send_json({
                    "type": "performance_summary",
                    **summary,
                    "timestamp": datetime.now().isoformat()
                })

    except Exception as e:
        logger.error(f"❌ Error handling JSON message: {e}")
        await websocket.send_json(
            {
                "type": "error",
                "message": "Failed to process message",
                "timestamp": datetime.now().isoformat(),
            }
        )

    return session
