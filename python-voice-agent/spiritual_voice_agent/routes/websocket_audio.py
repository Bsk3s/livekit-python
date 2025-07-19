import asyncio
import base64
import io
import json
import logging
import re
import struct
import time
import uuid
import wave
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from spiritual_voice_agent.characters.character_factory import CharacterFactory

# Cost Analytics imports for voice-first tracking
from spiritual_voice_agent.services.cost_analytics import log_voice_event
from spiritual_voice_agent.services.llm_service import create_gpt4o_mini
from spiritual_voice_agent.services.metrics_service import get_metrics_service

# Import existing services
from spiritual_voice_agent.services.stt.implementations.direct_deepgram import (
    DirectDeepgramSTTService,
)
from spiritual_voice_agent.services.tts_factory import TTSFactory

from ..utils.audio import convert_to_ios_format

router = APIRouter()
logger = logging.getLogger(__name__)


def create_wav_header(
    sample_rate: int = 22050, num_channels: int = 1, bit_depth: int = 16, data_length: int = 0
) -> bytes:
    """Create WAV file header for iOS-compatible audio format (22050 Hz default)"""
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
    pcm_data: bytes, sample_rate: int = 22050, num_channels: int = 1, bit_depth: int = 16
) -> bytes:
    """Convert raw PCM data to iOS-compatible WAV format (22050 Hz default)"""
    if not pcm_data:
        return b""

    # Ensure PCM data is properly aligned (even number of bytes for 16-bit)
    if len(pcm_data) % 2 != 0:
        # Pad with zero if odd length
        pcm_data = pcm_data + b"\x00"
        logger.debug(f"🔧 Padded PCM data to even length: {len(pcm_data)} bytes")

    # Create WAV header
    header = create_wav_header(sample_rate, num_channels, bit_depth, len(pcm_data))

    # Combine header + data
    wav_data = header + pcm_data

    # Validate WAV format
    if len(wav_data) >= 44 and wav_data[:4] == b"RIFF" and wav_data[8:12] == b"WAVE":
        logger.debug(f"✅ Generated valid iOS-compatible WAV: {len(wav_data)} bytes")
    else:
        logger.warning(f"⚠️ Generated WAV may be invalid: {len(wav_data)} bytes")

    return wav_data


def chunk_ai_response(
    full_response: str, max_chunk_length: int = 50
) -> List[str]:  # 🚀 SMART CHUNKING: 50 chars for natural phrases
    """
    Split AI response into natural phrase chunks for smooth TTS streaming

    Args:
        full_response: Complete AI response text
        max_chunk_length: Target maximum characters per chunk (BALANCED: 50 chars)

    Returns:
        List of phrase-chunks optimized for natural speech flow + speed
    """
    if not full_response or not full_response.strip():
        return []

    # Clean the response
    text = full_response.strip()

    # 🚀 SMART CHUNKING: Break at natural phrase boundaries
    # Priority: clause breaks > word groups > forced splits
    natural_breaks = [",", ";", " and ", " but ", " or ", " so ", " then ", " now ", " here "]

    chunks = []
    remaining_text = text

    while remaining_text:
        if len(remaining_text) <= max_chunk_length:
            # Remaining text fits in one chunk
            chunks.append(remaining_text.strip())
            break

        # Find best break point within max_chunk_length
        best_break = -1
        best_break_priority = -1

        # Look for natural breaks in priority order
        for i, break_char in enumerate(natural_breaks):
            # Search backward from max_chunk_length for this break type
            search_text = remaining_text[: max_chunk_length + 10]  # Small buffer
            break_pos = search_text.rfind(break_char)

            if break_pos > 20:  # Don't break too early (min 20 chars)
                if best_break_priority == -1 or i < best_break_priority:
                    best_break = break_pos + len(break_char)
                    best_break_priority = i

        # If no natural break found, break at last space within limit
        if best_break == -1:
            search_text = remaining_text[:max_chunk_length]
            last_space = search_text.rfind(" ")
            if last_space > 15:  # Don't break mid-word unless absolutely necessary
                best_break = last_space
            else:
                best_break = max_chunk_length  # Force break if needed

        # Extract chunk and continue
        chunk = remaining_text[:best_break].strip()
        if chunk:
            chunks.append(chunk)
        remaining_text = remaining_text[best_break:].strip()

    # 🚀 SMOOTH FLOW: Add subtle continuation markers for TTS context
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        if i < len(chunks) - 1:
            # Add ellipsis for smoother TTS continuation (Kokoro handles this well)
            if not chunk.endswith((".", "!", "?")):
                processed_chunks.append(chunk + "...")
            else:
                processed_chunks.append(chunk)
        else:
            processed_chunks.append(chunk)

    logger.info(
        f"🚀 SMART CHUNKED: {len(processed_chunks)} natural phrases ({[len(chunk) for chunk in processed_chunks[:3]]}{'...' if len(processed_chunks) > 3 else ''} chars each)"
    )
    return processed_chunks


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

        # 🎯 ADAPTIVE BUFFERING SYSTEM - Balance speed and accuracy
        self._adaptive_buffer_config = {
            "quick_response_threshold": 20000,  # 20KB - Fast response for short phrases
            "normal_speech_threshold": 50000,  # 50KB - Standard speech processing
            "long_thought_threshold": 100000,  # 100KB - Longer thoughts/statements
            "max_buffer_size": 150000,  # 150KB - Absolute maximum
            "silence_detection_ms": 800,  # 800ms silence = speech complete
            "min_speech_duration_ms": 300,  # 300ms minimum speech before processing
        }
        self._speech_start_time = None  # Track when speech started
        self._last_high_energy_time = None  # Track last high energy moment
        self._buffer_processing_mode = "quick"  # quick, normal, long_thought

        # Performance monitoring for VAD decoupling
        self._performance_metrics = {
            "vad_processing_times": [],
            "full_processing_times": [],
            "speech_detections": 0,
            "false_positives": 0,
            "transcription_attempts": 0,
            "chunk_count": 0,
            "interruptions": 0,
            "interruption_latencies": [],
            "adaptive_buffer_decisions": {
                "quick_responses": 0,
                "normal_speech": 0,
                "long_thoughts": 0,
                "buffer_timeouts": 0,
            },
        }

        # 🎯 INTERRUPTION SYSTEM - Real-time conversation control
        self._interruption_enabled = True  # Enable interruption capabilities
        self._current_tts_task: Optional[asyncio.Task] = None  # Track current TTS streaming
        self._response_chunks_sent = 0  # Track how many chunks we've sent
        self._interruption_threshold = (
            1.5  # Confidence threshold for interruption (lower = more sensitive)
        )
        self._interruption_cooldown = (
            1.0  # Seconds to wait after interruption before allowing another
        )
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

        # 📊 METRICS INTEGRATION - Connect voice pipeline to dashboard
        self._metrics_service = get_metrics_service()
        self._timing_data = {}  # Store timing data for complete conversation turn logging

        # 🚀 PHASE 2B: PROGRESSIVE STREAMING - Real-time processing while speaking
        self._progressive_streaming_enabled = True  # Enable progressive streaming by default
        self._progressive_stream_handler = None  # Active progressive stream
        self._progressive_transcript = ""  # Accumulated transcript from progressive stream
        self._early_llm_trigger_sent = False  # Flag to prevent duplicate early triggers
        self._progressive_confidence_threshold = 0.8  # Threshold for early LLM processing
        self._min_progressive_length = 10  # Minimum characters before early trigger

        # 🚀 PHASE 2C: LLM TOKEN STREAMING - Real-time response generation
        self._llm_streaming_enabled = True  # Enable LLM token streaming
        self._current_llm_stream = None  # Active LLM stream
        self._llm_response_buffer = ""  # Accumulated response from LLM stream
        self._sentence_boundary_chars = ".!?,"  # Smart chunking: comma boundaries
        self._min_sentence_length = 12  # 🚀 BALANCED: 12 chars (up from 8, down from 15)
        self._streaming_tts_tasks = []  # Track parallel TTS generation tasks
        self._response_chunk_counter = 0  # Counter for response chunks

    async def initialize(self):
        """Initialize all services for this session"""
        logger.info(f"🚀 STARTING AudioSession.initialize() for session {self.session_id}")
        try:
            # STT Service - Direct Deepgram with streaming capabilities enabled
            logger.info(f"🎧 Creating STT service for session {self.session_id}")
            self.stt_service = DirectDeepgramSTTService(
                {
                    "model": "nova-2",
                    "language": "en-US",
                    "punctuate": True,
                    "interim_results": True,  # Enable streaming mode
                    "streaming_enabled": True,  # Enable WebSocket streaming
                    "progressive_streaming": self._progressive_streaming_enabled,  # 🚀 PHASE 2B
                    "chunk_duration_ms": 250,  # 250ms progressive chunks
                    "early_processing_threshold": self._progressive_confidence_threshold,  # Early LLM trigger
                }
            )
            await self.stt_service.initialize()
            logger.info(
                f"✅ STT service initialized for session {self.session_id} with streaming enabled"
            )

            # LLM Service - Fixed OpenAI adapter
            logger.info(f"🧠 Creating LLM service for session {self.session_id}")
            self.llm_service = create_gpt4o_mini()
            logger.info(f"✅ LLM service initialized for session {self.session_id}")

            # TTS Service - Using WAV TTS service for iOS compatibility
            logger.info(f"🎵 Creating WAV TTS service for session {self.session_id}")
            # character_config = CharacterFactory.get_character_config(self.character)
            self.tts_service = TTSFactory.create_tts(self.character, model_override="kokoro")

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
                logger.debug(
                    f"🛡️ Watchdog check #{check_count}: State '{self.conversation_state}' for {state_duration:.1f}s"
                )

                # More aggressive monitoring with warnings
                if state_duration > 5.0:
                    logger.warning(
                        f"🛡️ WATCHDOG WARNING: State '{self.conversation_state}' running for {state_duration:.1f}s"
                    )

                if state_duration > self._max_state_duration:
                    logger.error(
                        f"🛡️ WATCHDOG FORCE RESET: State '{self.conversation_state}' stuck for {state_duration:.1f}s (max: {self._max_state_duration}s) - EMERGENCY RESET"
                    )
                    self._force_reset_state(
                        "LISTENING", f"watchdog_emergency_reset_after_{state_duration:.1f}s"
                    )
                    break  # Exit monitoring loop after reset

        except asyncio.CancelledError:
            logger.info(f"🛡️ Watchdog cancelled for session {self.session_id}")
        except Exception as e:
            logger.error(f"🛡️ Watchdog error: {e}")
        finally:
            logger.info(f"🛡️ Watchdog monitor ended for session {self.session_id}")

    def _force_reset_state(self, target_state: str = "LISTENING", reason: str = "unknown"):
        """Force immediate state reset (emergency recovery, minimal latency)"""
        logger.error(
            f"🛡️ EMERGENCY FORCE RESET: {self.conversation_state} → {target_state} (reason: {reason})"
        )

        # Immediate state reset
        old_state = self.conversation_state
        self._set_state(target_state)

        # Clear processing flags immediately
        self._processing_audio = False

        # Force cleanup of buffers immediately
        self._audio_buffer.clear()

        # 🛡️ NOTIFY CLIENT: Send error response so client doesn't hang
        if hasattr(self, "_current_websocket") and self._current_websocket:
            try:
                asyncio.create_task(self._send_watchdog_error(reason))
            except Exception as e:
                logger.warning(f"⚠️ Could not send watchdog error to client: {e}")

        # Log emergency reset for monitoring
        logger.error(
            f"🚨 EMERGENCY: Session {self.session_id} force reset from {old_state} after {reason}"
        )

        # Schedule heavy cleanup for later (zero latency)
        self._schedule_cleanup(f"emergency_reset_{reason}")

    async def _send_watchdog_error(self, reason: str):
        """Send error response to client when watchdog triggers"""
        try:
            if self._current_websocket:
                await self._current_websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Request timeout - system reset for reliability",
                        "reason": reason,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
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

            logger.debug(
                f"🧹 Async cleanup completed for session {self.session_id} (reason: {reason})"
            )

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
            self.session_active
            and self.stt_service is not None
            and self.llm_service is not None
            and self.tts_service is not None
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

            # ✅ ALWAYS-ON VAD: Always perform speech detection regardless of conversation state
            speech_detected = self._detect_sustained_speech(audio_energy, current_time)

            # 🎯 ADAPTIVE BUFFERING: Update speech tracking for smart buffer decisions
            self._update_speech_tracking(audio_energy, current_time)

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
                    await self._handle_potential_interruption(
                        websocket, confidence, audio_energy, current_time
                    )
                else:
                    logger.info(
                        f"🗣️ BACKEND HEARD YOU: Speech detected during {self.conversation_state} (energy: {audio_energy}, confidence: {confidence:.2f}) - VAD ONLY"
                    )

            # 🎯 STATE-AWARE TRANSCRIPTION: Only process transcription if session is active AND in LISTENING state
            if not self.session_active or self.conversation_state != "LISTENING":
                # VAD completed, but skip transcription processing
                chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
                self._track_performance_metric("vad_processing_time", chunk_duration_ms)
                logger.debug(
                    f"🔍 VAD-only processing: {chunk_duration_ms:.2f}ms (active: {self.session_active}, state: {self.conversation_state})"
                )
                return None

            # 🚀 PHASE 2B: PROGRESSIVE STREAMING - Process while user is speaking
            if self._progressive_streaming_enabled and not self._progressive_stream_handler:
                # Start progressive stream on first audio chunk
                await self._start_progressive_stream(websocket)

            # Send audio chunk to progressive stream
            if self._progressive_stream_handler:
                progressive_result = await self._send_to_progressive_stream(
                    audio_data, websocket, current_time
                )
                if progressive_result:
                    chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
                    self._track_performance_metric("progressive_processing_time", chunk_duration_ms)
                    logger.info(f"🚀 Progressive streaming completed: {chunk_duration_ms:.2f}ms")
                    return progressive_result

            # 🚀 PHASE 2A: TRY STREAMING FIRST, FALL BACK TO BATCH (Fallback)
            buffer_size = len(self._audio_buffer)

            # Use streaming for small chunks (real-time processing)
            if buffer_size >= 8000:  # 500ms at 16kHz
                logger.debug(f"🚀 Attempting streaming transcription for {buffer_size} bytes")

                # Try streaming transcription first
                streaming_result = await self._process_audio_streaming(websocket, current_time)
                if streaming_result:
                    chunk_duration_ms = (time.perf_counter() - chunk_start_time) * 1000
                    self._track_performance_metric("streaming_processing_time", chunk_duration_ms)
                    logger.info(f"🚀 Streaming transcription successful: {chunk_duration_ms:.2f}ms")
                    return streaming_result

            # 🎯 ADAPTIVE BUFFERING: Smart buffer processing with speed/accuracy balance (FALLBACK)
            should_process, process_reason, processing_mode = self._should_process_buffer(
                buffer_size, current_time
            )

            if should_process:
                logger.debug(f"🔄 Falling back to batch transcription: {process_reason}")
                return await self._process_audio_batch(
                    websocket, processing_mode, current_time, chunk_start_time
                )

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

    # ===== PHASE 2B: PROGRESSIVE STREAMING METHODS =====

    async def _start_progressive_stream(self, websocket: WebSocket) -> bool:
        """
        Start progressive streaming for real-time transcription while user speaks.
        """
        try:
            if not self.stt_service:
                return False

            # Create progressive stream handler with FIXED async callbacks
            async def handle_partial_wrapper(text: str, confidence: float, early_trigger: bool):
                """Proper async wrapper for partial results"""
                try:
                    await self._handle_progressive_partial(
                        websocket, text, confidence, early_trigger
                    )
                except Exception as e:
                    logger.error(f"❌ Error in partial callback: {e}")

            async def handle_final_wrapper(text: str, confidence: float):
                """Proper async wrapper for final results"""
                try:
                    await self._handle_progressive_final(websocket, text, confidence)
                except Exception as e:
                    logger.error(f"❌ Error in final callback: {e}")

            self._progressive_stream_handler = await self.stt_service.start_progressive_stream(
                on_partial_result=handle_partial_wrapper,
                on_final_result=handle_final_wrapper,
                confidence_threshold=self._progressive_confidence_threshold,
            )

            if self._progressive_stream_handler:
                logger.info("🚀 Progressive streaming started - processing while speaking!")

                # Send progressive stream start event
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "progressive_stream_started",
                            "message": "Processing speech in real-time...",
                            "conversation_state": self.conversation_state,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                return True
            else:
                logger.warning("⚠️ Failed to start progressive streaming")
                return False

        except Exception as e:
            logger.error(f"❌ Error starting progressive stream: {e}")
            return False

    async def _send_to_progressive_stream(
        self, audio_data: bytes, websocket: WebSocket, current_time: float
    ) -> Optional[str]:
        """
        Send audio chunk to progressive stream and handle real-time results.
        """
        try:
            if not self._progressive_stream_handler:
                return None

            # Send audio chunk to progressive stream
            success = await self._progressive_stream_handler.send_audio_chunk(audio_data)

            if not success:
                logger.warning("⚠️ Failed to send chunk to progressive stream")
                await self._cleanup_progressive_stream()
                return None

            # Check if we should finalize the stream based on silence detection
            if self._should_finalize_progressive_stream(current_time):
                return await self._finalize_progressive_stream(websocket)

            return None  # Continue progressive processing

        except Exception as e:
            logger.error(f"❌ Error in progressive streaming: {e}")
            await self._cleanup_progressive_stream()
            return None

    async def _handle_progressive_partial(
        self, websocket: WebSocket, text: str, confidence: float, early_trigger: bool
    ):
        """
        Handle partial results from progressive streaming.
        """
        try:
            # Update accumulated transcript
            self._progressive_transcript = text

            # Send partial result to client
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "progressive_partial",
                        "text": text,
                        "confidence": confidence,
                        "early_trigger": early_trigger,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Handle early LLM trigger for super-fast responses
            if early_trigger and not self._early_llm_trigger_sent:
                self._early_llm_trigger_sent = True
                logger.info(f"🚀 EARLY LLM TRIGGER: '{text}' (confidence: {confidence:.2f})")

                # Start LLM processing early while user is still speaking!
                asyncio.create_task(self._process_early_llm_response(websocket, text))

        except Exception as e:
            logger.error(f"❌ Error handling progressive partial: {e}")

    async def _handle_progressive_final(self, websocket: WebSocket, text: str, confidence: float):
        """
        Handle final results from progressive streaming.
        """
        try:
            # Update final transcript
            self._progressive_transcript = text

            # Send final result to client
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "progressive_final",
                        "text": text,
                        "confidence": confidence,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            logger.info(f"🎯 Progressive final: '{text}' (confidence: {confidence:.2f})")

        except Exception as e:
            logger.error(f"❌ Error handling progressive final: {e}")

    async def _should_finalize_progressive_stream(self, current_time: float) -> bool:
        """
        Check if progressive stream should be finalized based on silence detection.
        """
        # Finalize if we haven't detected speech in a while (silence detected)
        silence_duration = current_time - self._last_speech_time
        return silence_duration > (self._adaptive_buffer_config["silence_detection_ms"] / 1000)

    async def _finalize_progressive_stream(self, websocket: WebSocket) -> Optional[str]:
        """
        Finalize the progressive stream and return the complete transcript.
        """
        try:
            if not self._progressive_stream_handler:
                return self._progressive_transcript

            # Finalize the stream
            final_transcript = await self._progressive_stream_handler.finalize_stream()

            # Clean up
            await self._cleanup_progressive_stream()

            # Send finalization event
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "progressive_stream_finalized",
                        "text": final_transcript or self._progressive_transcript,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            result = final_transcript or self._progressive_transcript
            logger.info(f"🏁 Progressive stream finalized: '{result}'")

            return result.strip() if result else None

        except Exception as e:
            logger.error(f"❌ Error finalizing progressive stream: {e}")
            await self._cleanup_progressive_stream()
            return self._progressive_transcript.strip() if self._progressive_transcript else None

    async def _cleanup_progressive_stream(self):
        """Clean up progressive stream resources."""
        try:
            if self._progressive_stream_handler:
                await self._progressive_stream_handler.close()

            self._progressive_stream_handler = None
            self._progressive_transcript = ""
            self._early_llm_trigger_sent = False

            logger.debug("🧹 Progressive stream cleaned up")

        except Exception as e:
            logger.error(f"❌ Error cleaning up progressive stream: {e}")

    async def _cleanup_llm_streaming(self):
        """Clean up LLM streaming resources."""
        try:
            # Cancel any pending TTS tasks
            if self._streaming_tts_tasks:
                for task in self._streaming_tts_tasks:
                    if not task.done():
                        task.cancel()
                self._streaming_tts_tasks.clear()

            # Reset streaming state
            self._current_llm_stream = None
            self._llm_response_buffer = ""
            self._response_chunk_counter = 0

            logger.debug("🧹 LLM streaming resources cleaned up")

        except Exception as e:
            logger.error(f"❌ Error cleaning up LLM streaming: {e}")

    async def _process_early_llm_response(self, websocket: WebSocket, partial_text: str):
        """
        Process LLM response early while user is still speaking (Phase 2C preview).

        This method starts LLM processing on partial transcription for ultra-fast responses.
        """
        try:
            logger.info(f"🧠 EARLY LLM PROCESSING: '{partial_text}'")

            # For now, just log this capability - full implementation in Phase 2C
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "early_llm_triggered",
                        "partial_text": partial_text,
                        "message": "AI is already thinking about your response...",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # TODO: Phase 2C - Implement actual early LLM processing
            # This would start generating response before speech is complete

        except Exception as e:
            logger.error(f"❌ Error in early LLM processing: {e}")

    # ===== PHASE 2C: LLM TOKEN STREAMING METHODS =====

    async def _process_llm_streaming_response(self, websocket: WebSocket, user_input: str):
        """
        🚀 PHASE 2C: Process LLM response with token streaming and real-time TTS.

        This creates a true streaming pipeline:
        1. LLM tokens stream in real-time
        2. Sentence boundaries trigger immediate TTS processing
        3. Audio chunks stream as they're ready
        4. Total latency: First audio in ~200ms instead of 3500ms
        """
        llm_start_time = time.perf_counter()
        first_token_received = False
        first_token_time = None

        try:
            # Initialize streaming state
            self._llm_response_buffer = ""
            self._streaming_tts_tasks = []
            self._response_chunk_counter = 0

            # Get character personality for context
            from spiritual_voice_agent.characters.character_factory import CharacterFactory

            character = CharacterFactory.create_character(self.character)

            # Create conversation context
            messages = [{"role": "system", "content": character.personality}]

            # Add recent conversation history
            for msg in self.conversation_history[-10:]:  # Last 5 exchanges
                messages.append(msg)

            # Add current user input
            messages.append({"role": "user", "content": user_input})

            # 📊 METRICS: Track LLM first token latency
            logger.info("🚀 Starting LLM token streaming...")

            # Start LLM streaming using direct service call
            if not self.llm_service:
                raise Exception("LLM service not initialized")

            # Convert messages to proper format for LLM service
            context = messages[:-1]  # All except last user message
            prompt = user_input

            # Start streaming generation
            token_stream = self.llm_service.generate_stream(
                prompt=prompt, context=context, temperature=0.7, max_tokens=500
            )

            # Send streaming start notification
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "llm_streaming_started",
                        "message": "AI is generating response in real-time...",
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Process tokens as they arrive
            sentence_buffer = ""

            async for token in token_stream:
                # Check for interruption
                if self._stream_cancelled:
                    logger.info("🎯 LLM streaming cancelled due to interruption")
                    break

                # Skip empty tokens (normal OpenAI streaming behavior)
                if not token or not token.strip():
                    continue

                # Track first token timing
                if not first_token_received:
                    first_token_received = True
                    first_token_time = time.perf_counter()
                    first_token_latency = (first_token_time - llm_start_time) * 1000
                    self._timing_data["llm_first_token_ms"] = first_token_latency
                    logger.info(f"🚀 FIRST TOKEN: {first_token_latency:.1f}ms - {repr(token)}")

                # Accumulate token
                self._llm_response_buffer += token
                sentence_buffer += token

                # Send token to client for real-time display
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "llm_token",
                            "content": token,
                            "accumulated_text": self._llm_response_buffer,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    # Check for sentence boundaries
                if self._has_sentence_boundary(sentence_buffer):
                    # Extract complete sentence(s)
                    sentences = self._extract_complete_sentences(sentence_buffer)

                    for sentence in sentences:
                        if len(sentence.strip()) >= self._min_sentence_length:
                            # Start TTS processing immediately
                            task = asyncio.create_task(
                                self._process_streaming_tts_chunk(websocket, sentence.strip())
                            )
                            self._streaming_tts_tasks.append(task)

                    # Keep remaining partial sentence
                    sentence_buffer = self._get_remaining_partial_sentence(sentence_buffer)

            # Process final partial sentence if it exists
            if sentence_buffer.strip() and len(sentence_buffer.strip()) >= 5:
                task = asyncio.create_task(
                    self._process_streaming_tts_chunk(websocket, sentence_buffer.strip())
                )
                self._streaming_tts_tasks.append(task)

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append(
                {"role": "assistant", "content": self._llm_response_buffer}
            )

            # Calculate total LLM streaming time
            total_llm_time = (time.perf_counter() - llm_start_time) * 1000
            self._timing_data["llm_total_streaming_ms"] = total_llm_time

            # Send streaming complete notification
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "llm_streaming_complete",
                        "full_response": self._llm_response_buffer,
                        "total_time_ms": total_llm_time,
                        "first_token_ms": self._timing_data.get("llm_first_token_ms", 0),
                        "pending_tts_chunks": len(self._streaming_tts_tasks),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            logger.info(
                f"🚀 LLM streaming complete: {total_llm_time:.1f}ms total, first token: {self._timing_data.get('llm_first_token_ms', 0):.1f}ms"
            )

            # Wait for all TTS chunks to complete
            if self._streaming_tts_tasks:
                logger.info(
                    f"🎵 Waiting for {len(self._streaming_tts_tasks)} TTS tasks to complete..."
                )
                await asyncio.gather(*self._streaming_tts_tasks, return_exceptions=True)
                logger.info("🎵 All streaming TTS chunks completed")

            # Return to listening state
            self._set_state("LISTENING")

        except Exception as e:
            logger.error(f"❌ LLM streaming error: {e}")
            self._force_reset_state("LISTENING", f"llm_streaming_error: {e}")

            # Send error notification
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "llm_streaming_error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    def _has_sentence_boundary(self, text: str) -> bool:
        """Check if text contains sentence boundary characters"""
        return any(char in text for char in self._sentence_boundary_chars)

    def _extract_complete_sentences(self, text: str) -> list[str]:
        """Extract complete sentences from text buffer"""
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in self._sentence_boundary_chars:
                sentences.append(current_sentence)
                current_sentence = ""

        return sentences

    def _get_remaining_partial_sentence(self, text: str) -> str:
        """Get the partial sentence remaining after extracting complete ones"""
        for i in range(len(text) - 1, -1, -1):
            if text[i] in self._sentence_boundary_chars:
                return text[i + 1 :] if i + 1 < len(text) else ""
        return text

    async def _process_streaming_tts_chunk(self, websocket: WebSocket, sentence: str):
        """
        🚀 PHASE 2C: Process individual sentence for TTS streaming.

        This runs in parallel to continue receiving LLM tokens while processing TTS.
        """
        chunk_start_time = time.perf_counter()
        chunk_id = self._response_chunk_counter
        self._response_chunk_counter += 1

        try:
            logger.info(f"🎵 TTS Chunk {chunk_id}: Starting synthesis for '{sentence[:50]}...'")

            # Send TTS start notification
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "tts_chunk_started",
                        "chunk_id": chunk_id,
                        "text": sentence,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Generate TTS for this sentence
            tts_start_time = time.perf_counter()
            audio_data = await self.synthesize_speech_chunk(sentence)
            tts_duration_ms = (time.perf_counter() - tts_start_time) * 1000

            if audio_data:
                # Send audio chunk immediately
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")

                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "streaming_audio_chunk",
                            "chunk_id": chunk_id,
                            "text": sentence,
                            "audio": audio_base64,
                            "audio_size": len(audio_data),
                            "tts_latency_ms": tts_duration_ms,
                            "conversation_state": self.conversation_state,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                total_chunk_time = (time.perf_counter() - chunk_start_time) * 1000
                logger.info(
                    f"🎵 TTS Chunk {chunk_id}: Completed in {total_chunk_time:.1f}ms (TTS: {tts_duration_ms:.1f}ms)"
                )

                # Track TTS timing for first chunk
                if chunk_id == 0:
                    self._timing_data["tts_first_chunk_ms"] = tts_duration_ms

            else:
                logger.warning(f"⚠️ TTS Chunk {chunk_id}: No audio generated")

        except Exception as e:
            logger.error(f"❌ TTS Chunk {chunk_id} error: {e}")

            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "tts_chunk_error",
                        "chunk_id": chunk_id,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    # ===== NEW STREAMING PROCESSING METHOD (PHASE 2A) =====

    async def _process_audio_streaming(
        self, websocket: WebSocket, current_time: float
    ) -> Optional[str]:
        """
        Process audio using streaming STT for real-time transcription.

        Returns transcription if successful, None if should fall back to batch.
        """
        try:
            # Track streaming attempt
            self._track_performance_metric("streaming_attempted")

            # 🛡️ RELIABILITY: Use state tracking for watchdog
            self._set_state("PROCESSING")

            # Get current audio buffer (don't clear yet)
            audio_bytes = bytes(self._audio_buffer)

            # Send processing start event
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "transcription_partial",
                        "text": "",
                        "message": "Processing your speech (streaming)...",
                        "buffer_size": len(audio_bytes),
                        "conversation_state": self.conversation_state,
                        "processing_mode": "streaming",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            logger.info("🚀 STREAMING: Processing speech in real-time...")

            # Convert raw PCM to WAV format for streaming
            wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000, num_channels=1, bit_depth=16)

            # Prepare streaming callbacks
            partial_results = []
            final_result = None

            async def on_partial(text: str, confidence: float):
                """Handle partial transcription results (FIXED: async)"""
                partial_results.append((text, confidence))
                logger.debug(f"🔄 Partial: '{text}' ({confidence:.2f})")

                # Send partial result to client (FIXED: proper async)
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json(
                            {
                                "type": "transcription_partial",
                                "text": text,
                                "confidence": confidence,
                                "is_interim": True,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to send partial result: {e}")

            async def on_final(text: str, confidence: float):
                """Handle final transcription result (FIXED: async)"""
                nonlocal final_result
                final_result = (text, confidence)
                logger.debug(f"🎯 Final: '{text}' ({confidence:.2f})")

            # 📊 METRICS: Capture STT timing
            stt_start_time = time.perf_counter()

            # Call streaming transcription with callbacks
            transcription = await asyncio.wait_for(
                self.stt_service.transcribe_audio_stream(
                    wav_audio,
                    on_partial_result=on_partial,
                    on_final_result=on_final,
                    confidence_threshold=0.7,  # Lower threshold for streaming
                ),
                timeout=5.0,  # Shorter timeout for streaming
            )

            stt_duration_ms = (time.perf_counter() - stt_start_time) * 1000
            self._timing_data["stt_latency_ms"] = stt_duration_ms

            logger.debug(f"🚀 Streaming STT completed in {stt_duration_ms:.1f}ms")

            if transcription and transcription.strip():
                # Clear buffer only on successful transcription
                self._audio_buffer.clear()

                # Reset processing flag
                self._processing_audio = False

                # Send complete transcription
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "transcription_complete",
                            "text": transcription.strip(),
                            "buffer_size": len(audio_bytes),
                            "conversation_state": self.conversation_state,
                            "processing_mode": "streaming",
                            "stt_latency_ms": stt_duration_ms,
                            "partial_results_count": len(partial_results),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                logger.info(f"✅ STREAMING SUCCESS: '{transcription}' in {stt_duration_ms:.1f}ms")
                logger.info(f"👤 User ({self.character}): '{transcription}'")

                # Increment conversation turn
                self.conversation_turn_count += 1
                logger.info(f"🔄 Conversation turn #{self.conversation_turn_count}")

                # Track streaming success
                self._track_performance_metric("streaming_success")

                # 🛡️ RELIABILITY: Return to safe state BEFORE returning result
                self._set_state("LISTENING")

                return transcription.strip()
            else:
                # No transcription - let batch method try
                logger.debug("🔄 Streaming returned no results, will try batch processing")
                self._track_performance_metric("streaming_no_result")
                self._set_state("LISTENING")
                return None

        except asyncio.TimeoutError:
            logger.warning(f"🚀 Streaming timeout after 5s - falling back to batch")
            self._track_performance_metric("streaming_timeout")
            self._set_state("LISTENING")
            return None

        except Exception as e:
            logger.warning(f"🚀 Streaming error: {e} - falling back to batch")
            self._track_performance_metric("streaming_error")
            self._set_state("LISTENING")
            return None

    # ===== EXISTING BATCH PROCESSING METHOD (REFACTORED) =====

    async def _process_audio_batch(
        self,
        websocket: WebSocket,
        processing_mode: str,
        current_time: float,
        chunk_start_time: float,
    ) -> Optional[str]:
        """
        Process audio using batch STT (existing method, refactored for clarity).
        """
        try:
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

            # Get adaptive timeout based on processing mode
            timeout_seconds = self._get_processing_timeout(processing_mode)

            # Convert raw PCM to WAV format for Deepgram
            wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000, num_channels=1, bit_depth=16)

            # Send transcription start event (check connection first)
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "type": "transcription_partial",
                        "text": "",
                        "message": "Processing your speech (batch)...",
                        "buffer_size": len(audio_bytes),
                        "conversation_state": self.conversation_state,
                        "processing_mode": processing_mode,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            logger.info("📝 BATCH: Processing speech...")

            # 🛡️ CRITICAL: STT call with adaptive timeout
            logger.debug(
                f"🛡️ Starting batch STT transcription (mode: {processing_mode}, timeout: {timeout_seconds}s)..."
            )

            # 📊 METRICS: Capture STT timing
            stt_start_time = time.perf_counter()
            transcription = await asyncio.wait_for(
                self.stt_service.transcribe_audio_bytes(wav_audio), timeout=timeout_seconds
            )
            stt_duration_ms = (time.perf_counter() - stt_start_time) * 1000
            self._timing_data["stt_latency_ms"] = stt_duration_ms

            logger.debug(f"🛡️ Batch STT transcription completed in {stt_duration_ms:.1f}ms")

            if transcription and transcription.strip():
                # Send complete transcription (check connection first)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {
                            "type": "transcription_complete",
                            "text": transcription.strip(),
                            "buffer_size": len(audio_bytes),
                            "conversation_state": self.conversation_state,
                            "processing_mode": processing_mode,
                            "stt_latency_ms": stt_duration_ms,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                logger.info(f"✅ BATCH SUCCESS: '{transcription}' in {stt_duration_ms:.1f}ms")
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
                            "processing_mode": processing_mode,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                logger.info(f"🔇 No speech in {len(audio_bytes)} bytes of audio")

                # 🛡️ RELIABILITY: Return to safe state
                self._set_state("LISTENING")
                return None

        except asyncio.TimeoutError:
            logger.error(
                f"🛡️ Batch STT timeout after {timeout_seconds}s (mode: {processing_mode}) - forcing reset"
            )
            self._force_reset_state("LISTENING", f"stt_timeout_{processing_mode}")
            return None

        except Exception as stt_error:
            logger.error(f"🛡️ Batch STT processing failed: {stt_error}")
            self._force_reset_state("LISTENING", f"stt_error: {stt_error}")
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
        """
        Calculate confidence level for speech detection based on energy consistency.
        Higher confidence = more likely to be actual speech vs noise.
        """
        if not self._recent_energy_levels:
            return 0.0

        # Calculate energy consistency (how stable the energy levels are)
        recent_energies = self._recent_energy_levels[-5:]  # Last 5 measurements
        if len(recent_energies) < 3:
            return 0.5  # Default confidence for insufficient data

        # Calculate energy variance (lower variance = more consistent = higher confidence)
        mean_energy = sum(recent_energies) / len(recent_energies)
        variance = sum((e - mean_energy) ** 2 for e in recent_energies) / len(recent_energies)

        # Normalize variance to 0-1 scale (lower variance = higher confidence)
        max_variance = mean_energy * 2  # Reasonable maximum variance
        consistency_score = max(0, 1 - (variance / max_variance))

        # Calculate energy level score (higher energy = higher confidence)
        energy_score = min(1.0, mean_energy / (self._energy_threshold * 2))

        # Combine scores (consistency is more important than absolute energy)
        confidence = (consistency_score * 0.7) + (energy_score * 0.3)

        return min(1.0, max(0.0, confidence))

    # 🎯 ADAPTIVE BUFFERING METHODS - Smart buffer management
    def _should_process_buffer(
        self, buffer_size: int, current_time: float
    ) -> tuple[bool, str, str]:
        """
        Determine if audio buffer should be processed based on adaptive thresholds.

        Returns:
            (should_process, reason, mode)
        """
        config = self._adaptive_buffer_config

        # Check if we have any speech at all
        if not self._speech_start_time:
            return False, "no_speech_started", "none"

        speech_duration = (current_time - self._speech_start_time) * 1000  # Convert to ms

        # Check minimum speech duration
        if speech_duration < config["min_speech_duration_ms"]:
            return False, f"speech_too_short_{speech_duration:.0f}ms", "none"

        # Check for silence (speech complete)
        silence_duration = 0
        if self._last_high_energy_time:
            silence_duration = (current_time - self._last_high_energy_time) * 1000

        # Quick response mode: Small buffer + silence detection
        if (
            buffer_size >= config["quick_response_threshold"]
            and silence_duration >= config["silence_detection_ms"]
        ):
            self._buffer_processing_mode = "quick"
            self._performance_metrics["adaptive_buffer_decisions"]["quick_responses"] += 1
            return (
                True,
                f"quick_response_{buffer_size}bytes_{silence_duration:.0f}ms_silence",
                "quick",
            )

        # Normal speech mode: Medium buffer + silence detection
        if (
            buffer_size >= config["normal_speech_threshold"]
            and silence_duration >= config["silence_detection_ms"]
        ):
            self._buffer_processing_mode = "normal"
            self._performance_metrics["adaptive_buffer_decisions"]["normal_speech"] += 1
            return (
                True,
                f"normal_speech_{buffer_size}bytes_{silence_duration:.0f}ms_silence",
                "normal",
            )

        # Long thought mode: Large buffer + silence detection
        if (
            buffer_size >= config["long_thought_threshold"]
            and silence_duration >= config["silence_detection_ms"]
        ):
            self._buffer_processing_mode = "long_thought"
            self._performance_metrics["adaptive_buffer_decisions"]["long_thoughts"] += 1
            return (
                True,
                f"long_thought_{buffer_size}bytes_{silence_duration:.0f}ms_silence",
                "long_thought",
            )

        # Emergency timeout: Prevent buffer overflow
        if buffer_size >= config["max_buffer_size"]:
            self._buffer_processing_mode = "timeout"
            self._performance_metrics["adaptive_buffer_decisions"]["buffer_timeouts"] += 1
            return True, f"buffer_timeout_{buffer_size}bytes", "timeout"

        return False, f"waiting_{buffer_size}bytes_{silence_duration:.0f}ms_silence", "waiting"

    def _update_speech_tracking(self, audio_energy: float, current_time: float):
        """
        Update speech tracking for adaptive buffering decisions.
        """
        # Track speech start
        if audio_energy > self._energy_threshold and not self._speech_start_time:
            self._speech_start_time = current_time
            logger.debug(f"🎤 Speech started at {current_time}")

        # Track last high energy moment
        if audio_energy > self._energy_threshold:
            self._last_high_energy_time = current_time

        # Reset speech tracking if no energy for a while
        if self._last_high_energy_time and (current_time - self._last_high_energy_time) > 2.0:
            self._speech_start_time = None
            self._last_high_energy_time = None
            logger.debug(f"🎤 Speech tracking reset - no energy for 2s")

    def _get_processing_timeout(self, mode: str) -> float:
        """
        Get appropriate timeout for different processing modes.
        """
        timeouts = {
            "quick": 3.0,  # 3s for short phrases
            "normal": 5.0,  # 5s for normal speech
            "long_thought": 8.0,  # 8s for longer thoughts
            "timeout": 5.0,  # 5s for emergency processing
        }
        return timeouts.get(mode, 5.0)

    def get_adaptive_buffer_stats(self) -> dict:
        """
        Get adaptive buffering statistics for monitoring and debugging.
        """
        config = self._adaptive_buffer_config
        current_time = time.time()

        # Calculate current speech duration
        speech_duration_ms = 0
        if self._speech_start_time:
            speech_duration_ms = (current_time - self._speech_start_time) * 1000

        # Calculate current silence duration
        silence_duration_ms = 0
        if self._last_high_energy_time:
            silence_duration_ms = (current_time - self._last_high_energy_time) * 1000

        return {
            "buffer_size": len(self._audio_buffer),
            "processing_mode": self._buffer_processing_mode,
            "speech_started": self._speech_start_time is not None,
            "speech_duration_ms": speech_duration_ms,
            "silence_duration_ms": silence_duration_ms,
            "config": config,
            "performance_metrics": self._performance_metrics["adaptive_buffer_decisions"],
        }

    def configure_adaptive_buffering(
        self,
        quick_response_threshold: int = None,
        normal_speech_threshold: int = None,
        long_thought_threshold: int = None,
        max_buffer_size: int = None,
        silence_detection_ms: int = None,
        min_speech_duration_ms: int = None,
    ):
        """
        Configure adaptive buffering parameters dynamically.

        Args:
            quick_response_threshold: 20KB default - Fast response for short phrases
            normal_speech_threshold: 50KB default - Standard speech processing
            long_thought_threshold: 100KB default - Longer thoughts/statements
            max_buffer_size: 150KB default - Absolute maximum buffer size
            silence_detection_ms: 800ms default - Silence duration to consider speech complete
            min_speech_duration_ms: 300ms default - Minimum speech duration before processing
        """
        config = self._adaptive_buffer_config

        if quick_response_threshold is not None:
            config["quick_response_threshold"] = quick_response_threshold
        if normal_speech_threshold is not None:
            config["normal_speech_threshold"] = normal_speech_threshold
        if long_thought_threshold is not None:
            config["long_thought_threshold"] = long_thought_threshold
        if max_buffer_size is not None:
            config["max_buffer_size"] = max_buffer_size
        if silence_detection_ms is not None:
            config["silence_detection_ms"] = silence_detection_ms
        if min_speech_duration_ms is not None:
            config["min_speech_duration_ms"] = min_speech_duration_ms

        logger.info(f"🎯 Adaptive buffering configured: {config}")

        return config

    async def _handle_potential_interruption(
        self, websocket: WebSocket, confidence: float, audio_energy: float, current_time: float
    ):
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
                logger.debug(
                    f"🎯 Interruption cooldown active ({current_time - self._last_interruption_time:.1f}s), ignoring"
                )
                return

            # Check if confidence meets interruption threshold
            if confidence < self._interruption_threshold:
                logger.debug(
                    f"🎯 Speech confidence {confidence:.2f} below interruption threshold {self._interruption_threshold}, ignoring"
                )
                return

            # Check if we have an active TTS stream to interrupt
            if not self._current_tts_task or self._current_tts_task.done():
                logger.debug("🎯 No active TTS stream to interrupt")
                return

            # 🚨 INTERRUPTION TRIGGERED!
            logger.info(f"🎯 🚨 INTERRUPTION DETECTED!")
            logger.info(
                f"   - Confidence: {confidence:.2f} (threshold: {self._interruption_threshold})"
            )
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
                await websocket.send_json(
                    {
                        "type": "interruption_detected",
                        "confidence": confidence,
                        "energy": audio_energy,
                        "chunks_interrupted": self._response_chunks_sent,
                        "interruption_latency_ms": interruption_latency_ms,
                        "conversation_state": self.conversation_state,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Reset conversation state to LISTENING (user can now speak)
            self._set_state("LISTENING")

            # Reset response tracking
            self._response_chunks_sent = 0

            logger.info(
                f"🎯 ✅ Interruption handled in {interruption_latency_ms:.2f}ms - Ready for new input"
            )

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
        self._interruption_cooldown = max(0.1, min(5.0, cooldown))  # Clamp between 0.1-5.0

        logger.info(f"🎯 Interruption sensitivity updated:")
        logger.info(f"   - Threshold: {old_threshold:.1f} → {self._interruption_threshold:.1f}")
        logger.info(f"   - Cooldown: {old_cooldown:.1f}s → {self._interruption_cooldown:.1f}s")

    def enable_interruptions(self, enabled: bool = True):
        """Enable or disable interruption detection"""
        old_state = self._interruption_enabled
        self._interruption_enabled = enabled

        status = "ENABLED" if enabled else "DISABLED"
        logger.info(
            f"🎯 Interruption system {status} (was {'enabled' if old_state else 'disabled'})"
        )

        return {"interruption_enabled": self._interruption_enabled}

    def get_interruption_stats(self) -> dict:
        """Get interruption performance statistics"""
        stats = {
            "interruption_enabled": self._interruption_enabled,
            "interruption_threshold": self._interruption_threshold,
            "interruption_cooldown": self._interruption_cooldown,
            "total_interruptions": self._performance_metrics.get("interruptions", 0),
            "interruption_latencies": self._performance_metrics.get("interruption_latencies", []),
            "has_active_tts": self._current_tts_task is not None
            and not self._current_tts_task.done(),
            "response_chunks_sent": self._response_chunks_sent,
            "last_interruption_time": self._last_interruption_time,
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

            try:
                audio = self.tts_service.asynthesize(text)
                pcm_bytes = b""
                async for chunk in audio:
                    pcm_bytes += chunk
                return pcm_to_wav(
                    pcm_data=pcm_bytes,
                    sample_rate=24000,
                    num_channels=1,
                    bit_depth=16,
                )
            except Exception as e:
                logger.error(f"❌ Error generating welcome audio: {e}")
                return await self._fallback_tts_synthesis(text)

        except Exception as e:
            logger.error(f"❌ WAV TTS synthesis error: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            import traceback

            logger.error(f"❌ Traceback: {traceback.format_exc()}")

            # Return empty bytes as fallback
            return b""

    async def _fallback_tts_synthesis(self, text: str) -> bytes:
        """Fallback TTS synthesis using direct OpenAI API (22050 Hz WAV for iOS compatibility)"""
        try:
            logger.info(f"🔄 Trying fallback TTS for: '{text[:30]}...'")

            # Direct OpenAI TTS call with WAV output
            import openai

            response = await openai.AsyncOpenAI().audio.speech.create(
                model="tts-1",
                voice="nova" if self.character == "adina" else "onyx",
                input=text,
                response_format="wav",  # WAV format for iOS compatibility
                speed=1.0,  # Normal speed
            )

            audio_data = await response.aread()

            # 🔍 DETAILED BYTE ANALYSIS

            # Check first 20 bytes to identify format
            first_20_bytes = audio_data[:20] if len(audio_data) >= 20 else audio_data
            first_20_hex = " ".join(f"{b:02x}" for b in first_20_bytes)
            first_20_ascii = "".join(chr(b) if 32 <= b <= 126 else "." for b in first_20_bytes)

            logger.info(f"🔍 BYTE ANALYSIS: First 20 bytes hex: {first_20_hex}")
            logger.info(f"🔍 BYTE ANALYSIS: First 20 bytes ASCII: {first_20_ascii}")

            # Check for common audio format signatures
            is_wav = len(audio_data) >= 4 and audio_data[:4] == b"RIFF"
            is_mp3 = len(audio_data) >= 3 and (
                audio_data[:3] == b"ID3"
                or (audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0)
            )
            is_aac = len(audio_data) >= 2 and audio_data[:2] == b"\xff\xf1"

            logger.info(f"🔍 FORMAT DETECTION: WAV={is_wav}, MP3={is_mp3}, AAC={is_aac}")

            # If it's WAV, check the header details and convert to 22050 Hz if needed
            if is_wav and len(audio_data) >= 44:
                try:
                    import struct

                    # Parse WAV header
                    riff, size, wave = struct.unpack("<4sI4s", audio_data[:12])
                    (
                        fmt,
                        fmt_size,
                        audio_format,
                        channels,
                        sample_rate,
                        byte_rate,
                        block_align,
                        bits_per_sample,
                    ) = struct.unpack("<4sIHHIIHH", audio_data[12:36])

                    logger.info(
                        f"🔍 WAV HEADER: Sample Rate={sample_rate}, Channels={channels}, Bits={bits_per_sample}, Format={audio_format}"
                    )
                    audio_data = convert_to_ios_format(audio_data, sample_rate)

                except Exception as e:
                    logger.error(f"🔍 WAV HEADER PARSE ERROR: {e}")

            logger.info(f"🎵 Fallback TTS generated: {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"❌ Fallback TTS also failed: {e}")
            return b""

    async def process_conversation_turn(
        self, websocket: WebSocket, user_input: str, audio_duration_seconds: float = None
    ):
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

            # 📊 METRICS LOGGING: Log complete conversation turn metrics
            try:
                metrics_event = {
                    "session_id": self.session_id,
                    "character": self.character,
                    "source": "websocket_audio",
                    "pipeline_metrics": {
                        "stt_latency_ms": self._timing_data.get("stt_latency_ms", 0),
                        "llm_latency_ms": self._timing_data.get("llm_latency_ms", 0),
                        "tts_first_chunk_ms": self._timing_data.get("tts_first_chunk_ms", 0),
                        "total_latency_ms": total_latency_ms,
                    },
                    "quality_metrics": {
                        "success": True,
                        "transcription_success": bool(user_input and user_input.strip()),
                        "response_generated": True,
                    },
                    "context_metrics": {
                        "conversation_turn": self.conversation_turn_count,
                        "audio_duration_seconds": audio_duration_seconds or 0,
                    },
                }

                self._metrics_service.log_event(metrics_event)
                logger.debug(f"📊 Logged metrics event: {total_latency_ms}ms total")

                # Clear timing data for next turn
                self._timing_data.clear()

            except Exception as metrics_error:
                logger.warning(f"📊 Metrics logging failed (non-blocking): {metrics_error}")

            # 🎯 ZERO-IMPACT COST LOGGING (fire-and-forget, microseconds operation)
            log_voice_event(
                {
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "character": self.character,
                    "timestamp": turn_start_time,
                    "stt_duration_ms": stt_duration_ms,
                    "llm_duration_ms": llm_duration_ms,
                    "tts_duration_ms": tts_duration_ms,
                    "total_latency_ms": total_latency_ms,
                    "transcript_text": user_input,
                    "response_text": None,  # Will be filled by process_and_stream_response
                    "audio_duration_seconds": audio_duration_seconds,
                    "success": True,
                }
            )

            # Voice processing complete - cost logging happens in background

        except Exception as e:
            # 📊 METRICS LOGGING: Log error case
            try:
                error_latency_ms = int((time.time() - turn_start_time) * 1000)
                error_metrics_event = {
                    "session_id": self.session_id,
                    "character": self.character,
                    "source": "websocket_audio",
                    "pipeline_metrics": {
                        "stt_latency_ms": self._timing_data.get("stt_latency_ms", 0),
                        "llm_latency_ms": self._timing_data.get("llm_latency_ms", 0),
                        "tts_first_chunk_ms": self._timing_data.get("tts_first_chunk_ms", 0),
                        "total_latency_ms": error_latency_ms,
                    },
                    "quality_metrics": {
                        "success": False,
                        "transcription_success": bool(user_input and user_input.strip()),
                        "response_generated": False,
                        "error_message": str(e),
                    },
                    "context_metrics": {
                        "conversation_turn": self.conversation_turn_count,
                        "audio_duration_seconds": audio_duration_seconds or 0,
                    },
                }

                self._metrics_service.log_event(error_metrics_event)
                logger.debug(f"📊 Logged error metrics event: {error_latency_ms}ms total")

                # Clear timing data
                self._timing_data.clear()

            except Exception as metrics_error:
                logger.warning(f"📊 Error metrics logging failed (non-blocking): {metrics_error}")

            # Even errors get logged for cost analysis (fire-and-forget)
            log_voice_event(
                {
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "character": self.character,
                    "timestamp": turn_start_time,
                    "transcript_text": user_input,
                    "success": False,
                    "error_message": str(e),
                }
            )
            # Re-raise the exception for normal error handling
            raise

    async def process_and_stream_response(self, websocket: WebSocket, user_input: str):
        """Generate AI response and stream audio chunks in real-time"""
        print("DEBUG: process_and_stream_response method started")
        logger.info(
            f"🚀 PHASE 2C ENTRY: process_and_stream_response called with input: '{user_input}'"
        )

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

            # 🚀 PHASE 2C: LLM TOKEN STREAMING - Real-time response generation
            logger.info(
                f"🚀 PHASE 2C DEBUG: _llm_streaming_enabled = {self._llm_streaming_enabled}"
            )
            if self._llm_streaming_enabled:
                logger.info("🚀 PHASE 2C: Starting LLM token streaming for real-time response")
                await self._process_llm_streaming_response(websocket, user_input)
                return
            else:
                logger.info("🚀 PHASE 2C: LLM streaming disabled, using batch mode")

            # 🛡️ FALLBACK: Batch LLM processing (if streaming disabled)
            try:
                logger.debug(f"🛡️ Starting LLM generation (batch mode)...")

                # 📊 METRICS: Capture LLM timing
                llm_start_time = time.perf_counter()
                response_text = await asyncio.wait_for(
                    self.generate_response(user_input),
                    timeout=12.0,  # Increased to 12s for longer responses (especially during testing)
                )
                llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
                self._timing_data["llm_latency_ms"] = llm_duration_ms

                logger.debug(f"🛡️ LLM generation completed in {llm_duration_ms:.1f}ms")
            except asyncio.TimeoutError:
                logger.error(f"🛡️ LLM timeout after 12s - forcing reset")
                self._force_reset_state("LISTENING", "llm_timeout")
                return
            except Exception as llm_error:
                logger.error(f"🛡️ LLM generation failed: {llm_error}")
                self._force_reset_state("LISTENING", f"llm_error: {llm_error}")
                return

            # Split response into chunks
            chunks = chunk_ai_response(
                response_text, max_chunk_length=50
            )  # 🚀 SMART CHUNKING: Use 50-char natural phrases

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
                        logger.info(
                            f"🎵 Generated TTS chunk {i+1}/{len(chunks)}: {len(audio_data)} bytes"
                        )
                    else:
                        logger.warning(f"⚠️ TTS chunk {i+1} returned empty audio")
                except Exception as e:
                    logger.error(f"❌ TTS chunk {i+1} failed: {e}")

            # Sort chunks by original order
            audio_chunks.sort(key=lambda x: x[0])
            audio_chunks = [chunk[1] for chunk in audio_chunks]

            tts_duration = time.time() - tts_start_time
            tts_duration_ms = tts_duration * 1000
            self._timing_data["tts_first_chunk_ms"] = tts_duration_ms

            logger.info(
                f"🎤 TTS generation completed: {len(audio_chunks)} chunks in {tts_duration:.2f}s ({tts_duration_ms:.1f}ms)"
            )

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

                    audio_base64 = base64.b64encode(concatenated_audio).decode("utf-8")

                    await websocket.send_json(
                        {
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
                        }
                    )

                    logger.info(
                        f"🎵 Sent concatenated audio stream: {len(concatenated_audio)} bytes, {len(audio_base64)} base64 chars"
                    )

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
            logger.info(
                f"🔄 Response complete - Back to LISTENING state (Turn #{self.conversation_turn_count})"
            )

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
            import io
            import struct
            import wave

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
                        with wave.open(wav_io, "rb") as wav_in:
                            # Get WAV parameters (should be same for all chunks)
                            if sample_rate is None:
                                sample_rate = wav_in.getframerate()
                                channels = wav_in.getnchannels()
                                sample_width = wav_in.getsampwidth()
                            else:
                                # Verify all chunks have same parameters
                                if (
                                    wav_in.getframerate() != sample_rate
                                    or wav_in.getnchannels() != channels
                                    or wav_in.getsampwidth() != sample_width
                                ):
                                    logger.warning(f"⚠️ WAV chunk {i} has different parameters")

                            # Read audio data (skip header)
                            frames = wav_in.readframes(wav_in.getnframes())
                            audio_data_chunks.append(frames)
                            total_samples += wav_in.getnframes()

                            logger.debug(
                                f"🔄 Chunk {i+1}: {wav_in.getnframes()} frames, {len(frames)} bytes"
                            )

                except Exception as e:
                    logger.error(f"❌ Failed to process WAV chunk {i}: {e}")
                    continue

            if not audio_data_chunks:
                logger.error("❌ No valid audio data chunks found")
                return b""

            # Concatenate all audio data
            concatenated_audio_data = b"".join(audio_data_chunks)

            # Create new WAV file with concatenated data
            with io.BytesIO() as new_wav_io:
                with wave.open(new_wav_io, "wb") as wav_out:
                    wav_out.setnchannels(channels)
                    wav_out.setsampwidth(sample_width)
                    wav_out.setframerate(sample_rate)
                    wav_out.writeframes(concatenated_audio_data)

                concatenated_wav = new_wav_io.getvalue()

                logger.info(
                    f"✅ Concatenated {len(audio_chunks)} chunks: {total_samples} total frames, {len(concatenated_wav)} bytes"
                )
                logger.info(
                    f"✅ Final WAV: {sample_rate}Hz, {channels} channels, {sample_width*8} bits"
                )

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

            # 🚀 PHASE 2B: Clean up progressive streaming
            await self._cleanup_progressive_stream()

            # 🚀 PHASE 2C: Clean up LLM streaming
            await self._cleanup_llm_streaming()

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
                self._performance_metrics["chunk_count"] += 1
            elif metric_type == "speech_detected":
                self._performance_metrics["speech_detections"] += 1
            elif metric_type == "transcription_attempted":
                self._performance_metrics["transcription_attempts"] += 1
            elif metric_type == "interruptions":
                self._performance_metrics["interruptions"] += 1
            elif metric_type == "vad_processing_time" and value is not None:
                times = self._performance_metrics["vad_processing_times"]
                times.append(value)
                # Keep only last 100 measurements
                if len(times) > 100:
                    times.pop(0)
            elif metric_type == "full_processing_time" and value is not None:
                times = self._performance_metrics["full_processing_times"]
                times.append(value)
                # Keep only last 100 measurements
                if len(times) > 100:
                    times.pop(0)
            elif metric_type == "interruption_latencies" and value is not None:
                latencies = self._performance_metrics["interruption_latencies"]
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

            vad_times = metrics["vad_processing_times"]
            full_times = metrics["full_processing_times"]

            interruption_latencies = metrics["interruption_latencies"]

            summary = {
                "session_id": self.session_id,
                "chunks_processed": metrics["chunk_count"],
                "speech_detections": metrics["speech_detections"],
                "transcription_attempts": metrics["transcription_attempts"],
                "interruptions": metrics["interruptions"],
                "vad_performance": {
                    "count": len(vad_times),
                    "avg_ms": sum(vad_times) / len(vad_times) if vad_times else 0,
                    "max_ms": max(vad_times) if vad_times else 0,
                    "target_met": all(t < 10.0 for t in vad_times) if vad_times else True,
                },
                "full_processing_performance": {
                    "count": len(full_times),
                    "avg_ms": sum(full_times) / len(full_times) if full_times else 0,
                    "max_ms": max(full_times) if full_times else 0,
                    "target_met": all(t < 50.0 for t in full_times) if full_times else True,
                },
                "interruption_performance": {
                    "total_interruptions": metrics["interruptions"],
                    "avg_latency_ms": (
                        sum(interruption_latencies) / len(interruption_latencies)
                        if interruption_latencies
                        else 0
                    ),
                    "max_latency_ms": max(interruption_latencies) if interruption_latencies else 0,
                    "min_latency_ms": min(interruption_latencies) if interruption_latencies else 0,
                    "target_met": (
                        all(t < 50.0 for t in interruption_latencies)
                        if interruption_latencies
                        else True
                    ),  # Target <50ms
                    "enabled": self._interruption_enabled,
                    "threshold": self._interruption_threshold,
                    "cooldown": self._interruption_cooldown,
                },
                "conversation_state": self.conversation_state,
                "session_active": self.session_active,
            }

            return summary
        except Exception as e:
            logger.warning(f"Error generating performance summary: {e}")
            return {"error": str(e)}


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
                    first_bytes_hex = " ".join(
                        f"{b:02x}" for b in first_bytes[:20]
                    )  # First 20 bytes as hex
                    first_bytes_ascii = "".join(
                        chr(b) if 32 <= b <= 126 else "." for b in first_bytes[:20]
                    )  # ASCII representation

                    # Check for WAV header signature
                    is_wav = len(audio_data) >= 4 and audio_data[:4] == b"RIFF"

                    # logger.info(
                    #     f"🎯 AUDIO RECEIVED: {len(audio_data)} bytes, session={session is not None}"
                    # )
                    # logger.info(f"🔍 VALIDATION: First 20 bytes hex: {first_bytes_hex}")
                    # logger.info(f"🔍 VALIDATION: First 20 bytes ASCII: {first_bytes_ascii}")
                    # logger.info(
                    #     f"🔍 VALIDATION: Is WAV header: {is_wav} (should be False for raw PCM)"
                    # )

                    # if session:
                    #     logger.info(
                    #         f"🎯 SESSION STATE: active={session.session_active}, conversation_state={session.conversation_state}, stt_service={session.stt_service is not None}"
                    #     )

                    if session and session.stt_service:
                        # logger.info(
                        #     f"🎯 PROCESSING AUDIO: {len(audio_data)} bytes in {session.conversation_state} state"
                        # )

                        # Calculate audio duration for cost tracking (16kHz, 16-bit, mono)
                        # TEMP: 48000 when testing otherwise 16000
                        audio_duration_seconds = len(audio_data) / (48000 * 2)  # 2 bytes per sample

                        # 🎯 INTERRUPTION SYSTEM: Always process audio for VAD regardless of session_active
                        # This enables interruption detection during RESPONDING state
                        transcription = await session.process_audio_chunk(audio_data, websocket)

                        # Only process conversation turns if session is active and we got transcription
                        if transcription and session.session_active:
                            # Process complete conversation turn with zero-impact cost tracking
                            await session.process_conversation_turn(
                                websocket, transcription, audio_duration_seconds
                            )
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
    logger.info(f"🚀 PHASE 2C DEBUG: handle_json_message called with type: {message_type}")
    logger.info(f"🚀 PHASE 2C DEBUG: Full message: {message}")

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
            user_id = message.get(
                "user_id", f"user_{session_id[:8]}"
            )  # Allow user_id from client or generate one
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
            # character_obj = CharacterFactory.create_character(character)
            welcome_message = f"Hello! I'm {character.title()}. I'm here to listen and support you. How are you feeling today?"

            # Generate WAV audio for welcome message
            # TODO: Move error handling and calling of tts to a different function somewhere else. It should just return the pcm bytes or empty
            # TODO: Detect requests from ios vs web to output valid format
            # TODO: This is currently not asynchronous it waits for all bytes
            try:
                audio = session.tts_service.asynthesize(welcome_message)
                pcm_bytes = b""
                async for chunk in audio:
                    pcm_bytes += chunk
                sample_rate = 24000

                welcome_audio = pcm_to_wav(
                    pcm_data=pcm_bytes,
                    sample_rate=sample_rate,
                    num_channels=1,
                    bit_depth=16,
                )
                welcome_audio_ios = convert_to_ios_format(welcome_audio, sample_rate)

            except Exception as e:
                logger.error(f"❌ Error generating welcome audio: {e}")
                welcome_audio_ios = await session._fallback_tts_synthesis(welcome_message)

            if welcome_audio_ios:
                welcome_base64 = base64.b64encode(welcome_audio_ios).decode("utf-8")
                logger.info(
                    f"🎵 Generated welcome WAV: {len(welcome_audio_ios)} bytes, {len(welcome_base64)} base64 chars"
                )
            else:
                logger.warning("⚠️ Failed to generate welcome audio, sending text only")
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
                            # 📊 METRICS: Track complete conversation turn (JSON audio flow)
                            turn_start_time = time.time()

                            # Process and stream response in chunks
                            await session.process_and_stream_response(websocket, transcription)

                            # 📊 METRICS: Log conversation metrics for JSON audio flow
                            try:
                                total_latency_ms = int((time.time() - turn_start_time) * 1000)
                                metrics_event = {
                                    "session_id": session.session_id,
                                    "character": session.character,
                                    "source": "websocket_audio_json",
                                    "pipeline_metrics": {
                                        "stt_latency_ms": session._timing_data.get(
                                            "stt_latency_ms", 0
                                        ),
                                        "llm_latency_ms": session._timing_data.get(
                                            "llm_latency_ms", 0
                                        ),
                                        "tts_first_chunk_ms": session._timing_data.get(
                                            "tts_first_chunk_ms", 0
                                        ),
                                        "total_latency_ms": total_latency_ms,
                                    },
                                    "quality_metrics": {
                                        "success": True,
                                        "transcription_success": bool(
                                            transcription and transcription.strip()
                                        ),
                                        "response_generated": True,
                                    },
                                    "context_metrics": {
                                        "conversation_turn": session.conversation_turn_count,
                                        "audio_duration_seconds": len(audio_data) / (48000 * 2),
                                    },
                                }

                                session._metrics_service.log_event(metrics_event)
                                logger.info(
                                    f"📊 JSON audio metrics logged: {total_latency_ms}ms total"
                                )

                                # Clear timing data
                                session._timing_data.clear()

                            except Exception as metrics_error:
                                logger.warning(
                                    f"📊 JSON audio metrics failed (non-blocking): {metrics_error}"
                                )
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
            logger.info(f"🚀 PHASE 2C: Received text_message with type: {message_type}")
            if session:
                user_text = message.get("text", "")
                logger.info(f"🚀 PHASE 2C: Extracted user_text: '{user_text}'")
                if user_text.strip():
                    logger.info(f"🚀 PHASE 2C: About to call process_and_stream_response")
                    try:
                        await session.process_and_stream_response(websocket, user_text)
                        logger.info(
                            f"🚀 PHASE 2C: process_and_stream_response completed successfully"
                        )
                    except Exception as e:
                        logger.error(f"❌ PHASE 2C: Exception in process_and_stream_response: {e}")
                        logger.error(f"❌ PHASE 2C: Exception type: {type(e)}")
                        import traceback

                        logger.error(f"❌ PHASE 2C: Traceback: {traceback.format_exc()}")
                else:
                    logger.warning(f"🚀 PHASE 2C: user_text is empty after strip()")
            else:
                logger.warning(f"🚀 PHASE 2C: session is None")

        elif message_type == "ping":
            await websocket.send_json({"type": "pong"})

        # 🎯 INTERRUPTION SYSTEM: Control commands
        elif message_type == "configure_interruption":
            if session:
                threshold = message.get("threshold", 1.5)
                cooldown = message.get("cooldown", 1.0)
                session.configure_interruption_sensitivity(threshold, cooldown)

                await websocket.send_json(
                    {
                        "type": "interruption_configured",
                        "threshold": session._interruption_threshold,
                        "cooldown": session._interruption_cooldown,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "enable_interruption":
            if session:
                enabled = message.get("enabled", True)
                result = session.enable_interruptions(enabled)

                await websocket.send_json(
                    {
                        "type": "interruption_toggled",
                        **result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_interruption_stats":
            if session:
                stats = session.get_interruption_stats()
                await websocket.send_json(
                    {"type": "interruption_stats", **stats, "timestamp": datetime.now().isoformat()}
                )

        # 🎯 ADAPTIVE BUFFERING SYSTEM: Configuration and monitoring
        elif message_type == "configure_adaptive_buffering":
            if session:
                config = session.configure_adaptive_buffering(
                    quick_response_threshold=message.get("quick_response_threshold"),
                    normal_speech_threshold=message.get("normal_speech_threshold"),
                    long_thought_threshold=message.get("long_thought_threshold"),
                    max_buffer_size=message.get("max_buffer_size"),
                    silence_detection_ms=message.get("silence_detection_ms"),
                    min_speech_duration_ms=message.get("min_speech_duration_ms"),
                )

                await websocket.send_json(
                    {
                        "type": "adaptive_buffering_configured",
                        "config": config,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_adaptive_buffer_stats":
            if session:
                stats = session.get_adaptive_buffer_stats()
                await websocket.send_json(
                    {
                        "type": "adaptive_buffer_stats",
                        **stats,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_performance_summary":
            if session:
                summary = session.get_performance_summary()

                await websocket.send_json(
                    {
                        "type": "performance_summary",
                        **summary,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

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
