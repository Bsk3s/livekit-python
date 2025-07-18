# Add future import for Python typing compatibility
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, AsyncGenerator, Callable

import aiohttp
import websockets

from spiritual_voice_agent.services.stt.base import BaseSTTService

logger = logging.getLogger(__name__)


class DirectDeepgramSTTService(BaseSTTService):
    """Direct Deepgram implementation using HTTP API and WebSocket streaming to avoid SDK typing issues."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._api_key = None
        self._initialized = False
        self._session_timeout = 30.0  # 30 second timeout for API calls
        self._base_url = "https://api.deepgram.com/v1"
        
        # Streaming configuration
        self._streaming_url = "wss://api.deepgram.com/v1/listen"
        self._streaming_enabled = config.get("streaming_enabled", True) if config else True
        self._interim_results = config.get("interim_results", True) if config else True
        
        # 🚀 PHASE 2B: Progressive streaming configuration
        self._progressive_streaming = config.get("progressive_streaming", True) if config else True
        self._chunk_duration_ms = config.get("chunk_duration_ms", 250) if config else 250  # 250ms chunks
        self._early_processing_threshold = config.get("early_processing_threshold", 0.8) if config else 0.8
        self._continuous_websocket = None  # Persistent WebSocket connection
        self._websocket_lock = asyncio.Lock()  # Thread safety for WebSocket operations

    def _validate_config(self) -> None:
        """Validate required configuration and environment variables"""
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set or empty")

        self._api_key = api_key
        logger.info(f"🔑 Deepgram API key validated: {self._api_key[:8]}...")

    async def initialize(self) -> None:
        """Initialize the Deepgram client"""
        if not self._initialized:
            try:
                self._validate_config()

                # Test connection with a minimal request
                await self._test_connection()

                self._initialized = True
                logger.info("✅ DirectDeepgramSTTService initialized successfully")
                if self._streaming_enabled:
                    logger.info("🚀 Streaming mode enabled for real-time transcription")

            except Exception as e:
                logger.error(f"❌ Failed to initialize DirectDeepgramSTTService: {e}")
                # Log additional debugging info
                logger.error(f"❌ Python version: {sys.version}")
                logger.error(f"❌ Error type: {type(e)}")
                import traceback

                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                raise

    async def _test_connection(self) -> None:
        """Test the Deepgram connection with a minimal request"""
        try:
            # Create a minimal silent audio sample for testing
            # 0.1 seconds of silence at 16kHz, 16-bit mono
            silence_samples = int(16000 * 0.1)  # 0.1 second at 16kHz
            silence_bytes = b"\x00\x00" * silence_samples  # 16-bit silence

            # Create minimal WAV file
            wav_data = self._create_wav_file(silence_bytes, 16000, 1, 16)

            # Test with Deepgram API
            result = await self._transcribe_with_api(wav_data)
            logger.info("🔗 Deepgram connection test successful")

        except Exception as e:
            logger.warning(f"⚠️ Connection test failed (may be normal): {e}")
            # Don't raise - connection test failure shouldn't block initialization

    def _create_wav_file(
        self,
        pcm_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        bits_per_sample: int = 16,
    ) -> bytes:
        """Create a WAV file from PCM data"""
        import struct

        # Calculate sizes
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        data_size = len(pcm_data)
        file_size = 36 + data_size

        # Create WAV header
        wav_header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",  # Chunk ID
            file_size,  # Chunk size
            b"WAVE",  # Format
            b"fmt ",  # Subchunk1 ID
            16,  # Subchunk1 size (PCM)
            1,  # Audio format (PCM)
            channels,  # Num channels
            sample_rate,  # Sample rate
            byte_rate,  # Byte rate
            block_align,  # Block align
            bits_per_sample,  # Bits per sample
            b"data",  # Subchunk2 ID
            data_size,  # Subchunk2 size
        )

        return wav_header + pcm_data

    async def _transcribe_with_api(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using direct HTTP API call"""
        try:
            # Prepare API parameters
            params = {
                "model": self.config.get("model", "nova-2"),
                "language": self.config.get("language", "en-US"),
                "punctuate": str(self.config.get("punctuate", True)).lower(),
                "smart_format": str(self.config.get("smart_format", True)).lower(),
                "interim_results": "false",
                "utterances": "false",
                "profanity_filter": str(self.config.get("profanity_filter", False)).lower(),
                "numerals": str(self.config.get("numerals", False)).lower(),
                "no_delay": "true",
            }

            # Prepare headers
            headers = {"Authorization": f"Token {self._api_key}", "Content-Type": "audio/wav"}

            # Build URL
            url = f"{self._base_url}/listen"

            # Make API request
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        url,
                        params=params,
                        headers=headers,
                        data=audio_data,
                        timeout=aiohttp.ClientTimeout(total=self._session_timeout),
                    ) as response:

                        if response.status == 200:
                            result = await response.json()
                            return self._extract_transcript_from_json(result)
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Deepgram API error {response.status}: {error_text}")
                            return None

                except asyncio.TimeoutError:
                    logger.error(f"⏰ Deepgram API timeout after {self._session_timeout}s")
                    return None
                except Exception as api_error:
                    logger.error(f"❌ HTTP API error: {api_error}")
                    return None

        except Exception as e:
            logger.error(f"❌ Failed to call Deepgram API: {e}")
            return None

    def _extract_transcript_from_json(self, response_data: dict) -> Optional[str]:
        """Extract transcript from Deepgram JSON response"""
        try:
            # Log the full response for debugging
            logger.debug(f"🔍 Full Deepgram response: {response_data}")

            # Navigate the nested JSON structure
            results = response_data.get("results", {})
            if not results:
                logger.debug("🔍 No results in response")
                return None

            channels = results.get("channels", [])
            if not channels:
                logger.debug("🔍 No channels in results")
                return None

            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                logger.debug("🔍 No alternatives in first channel")
                return None

            transcript = alternatives[0].get("transcript", "")
            confidence = alternatives[0].get("confidence", 0.0)

            logger.debug(f"🔍 Extracted transcript: '{transcript}' (confidence: {confidence})")

            return transcript if transcript.strip() else None

        except Exception as e:
            logger.error(f"❌ Error extracting transcript from JSON: {e}")
            logger.error(f"❌ Response data type: {type(response_data)}")
            logger.error(f"❌ Response data: {response_data}")
            return None

    # ===== EXISTING BATCH METHOD (UNCHANGED) =====
    
    async def transcribe_audio_bytes(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe raw audio bytes using Deepgram HTTP API (BATCH METHOD)

        Args:
            audio_data: Raw audio bytes (WAV format expected)

        Returns:
            Transcription text or None if no speech detected
        """
        if not self._initialized:
            await self.initialize()

        if not audio_data or len(audio_data) == 0:
            logger.debug("⚠️ Empty audio data provided")
            return None

        if not self._api_key:
            logger.error("❌ Deepgram API key not available")
            return None

        try:
            logger.info(f"🎤 STT DEBUG: Processing {len(audio_data)} bytes of audio")
            
            # 🔍 DEBUG: Check audio format
            if len(audio_data) >= 44:
                if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
                    logger.info(f"🎤 STT DEBUG: Audio is valid WAV format")
                    # Parse WAV header for debugging
                    import struct
                    try:
                        riff, size, wave = struct.unpack('<4sI4s', audio_data[:12])
                        fmt, fmt_size, audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack('<4sIHHIIHH', audio_data[12:36])
                        logger.info(f"🎤 STT DEBUG: WAV Header - Sample Rate: {sample_rate}, Channels: {channels}, Bits: {bits_per_sample}, Format: {audio_format}")
                    except Exception as e:
                        logger.warning(f"🎤 STT DEBUG: Could not parse WAV header: {e}")
                else:
                    logger.warning(f"🎤 STT DEBUG: Audio is NOT valid WAV format")
            else:
                logger.warning(f"🎤 STT DEBUG: Audio too short to be WAV: {len(audio_data)} bytes")

            # Ensure we have proper WAV format
            if not audio_data.startswith(b"RIFF"):
                logger.info("🔧 Converting PCM to WAV format")
                # Assume 16kHz, 16-bit, mono PCM
                audio_data = self._create_wav_file(audio_data, 16000, 1, 16)
                logger.info(f"🔧 Converted to WAV: {len(audio_data)} bytes")

            # 🔍 DEBUG: Check final audio format
            logger.info(f"🎤 STT DEBUG: Final audio size: {len(audio_data)} bytes")
            if len(audio_data) >= 44:
                logger.info(f"🎤 STT DEBUG: Final audio starts with: {audio_data[:20].hex()}")

            # Transcribe using HTTP API
            logger.info(f"🎤 STT DEBUG: Calling Deepgram API...")
            transcript = await self._transcribe_with_api(audio_data)
            logger.info(f"🎤 STT DEBUG: Deepgram API returned: {repr(transcript)}")

            if transcript and transcript.strip():
                logger.info(f"👤 Transcribed: '{transcript}'")
                return transcript.strip()
            else:
                logger.info("🔇 No speech detected in audio")
                return None

        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            import traceback

            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return None

    # ===== NEW STREAMING METHOD (PHASE 2A) =====
    
    async def transcribe_audio_stream(
        self, 
        audio_chunk: bytes,
        on_partial_result: Optional[Callable[[str, float], None]] = None,
        on_final_result: Optional[Callable[[str, float], None]] = None,
        confidence_threshold: float = 0.8
    ) -> Optional[str]:
        """
        Transcribe audio chunk using streaming API with real-time partial results
        
        Args:
            audio_chunk: Raw audio bytes (will be converted to WAV if needed)
            on_partial_result: Callback for partial results (text, confidence)
            on_final_result: Callback for final results (text, confidence)  
            confidence_threshold: Minimum confidence for reliable results
            
        Returns:
            Final transcription if confidence > threshold, else None
        """
        if not self._initialized:
            await self.initialize()
            
        if not self._streaming_enabled:
            # Fallback to batch method
            return await self.transcribe_audio_bytes(audio_chunk)
            
        try:
            # Ensure proper WAV format
            if not audio_chunk.startswith(b"RIFF"):
                audio_chunk = self._create_wav_file(audio_chunk, 16000, 1, 16)
                
            # Use WebSocket streaming API for real-time results
            return await self._stream_transcribe_websocket(
                audio_chunk, on_partial_result, on_final_result, confidence_threshold
            )
            
        except Exception as e:
            logger.error(f"❌ Streaming transcription error: {e}")
            # Fallback to batch method on streaming failure
            logger.info("🔄 Falling back to batch transcription")
            return await self.transcribe_audio_bytes(audio_chunk)
    
    # ===== PHASE 2B: PROGRESSIVE STREAMING METHODS =====
    
    async def start_progressive_stream(
        self,
        on_partial_result: Optional[Callable[[str, float, bool], None]] = None,  # Added 'early_trigger' flag
        on_final_result: Optional[Callable[[str, float], None]] = None,
        confidence_threshold: float = 0.7
    ) -> Optional['ProgressiveStreamHandler']:
        """
        Start a progressive streaming session for real-time transcription.
        
        Returns a stream handler that can accept audio chunks progressively.
        """
        if not self._progressive_streaming:
            return None
            
        try:
            handler = ProgressiveStreamHandler(
                stt_service=self,
                on_partial_result=on_partial_result,
                on_final_result=on_final_result,
                confidence_threshold=confidence_threshold,
                chunk_duration_ms=self._chunk_duration_ms,
                early_processing_threshold=self._early_processing_threshold
            )
            
            await handler.initialize()
            return handler
            
        except Exception as e:
            logger.error(f"❌ Failed to start progressive stream: {e}")
            return None
    
    async def _create_continuous_websocket(self) -> Optional[websockets.WebSocketServerProtocol]:
        """Create a persistent WebSocket connection for progressive streaming"""
        try:
            async with self._websocket_lock:
                if self._continuous_websocket and not self._continuous_websocket.closed:
                    return self._continuous_websocket
                
                # Build WebSocket URL with streaming parameters optimized for progressive chunks
                params = {
                    "model": self.config.get("model", "nova-2"),
                    "language": self.config.get("language", "en-US"),
                    "punctuate": str(self.config.get("punctuate", True)).lower(),
                    "smart_format": str(self.config.get("smart_format", True)).lower(),
                    "interim_results": "true",  # CRITICAL for progressive streaming
                    "utterances": "false",  # Don't auto-close on utterance end
                    "profanity_filter": str(self.config.get("profanity_filter", False)).lower(),
                    "numerals": str(self.config.get("numerals", False)).lower(),
                    "no_delay": "true",  # Minimize latency
                    "endpointing": "100",  # Very short endpointing for progressive chunks
                    "channels": "1",
                    "sample_rate": "16000",
                    "encoding": "linear16"
                }
                
                # Build WebSocket URL
                param_string = "&".join([f"{k}={v}" for k, v in params.items()])
                ws_url = f"{self._streaming_url}?{param_string}"
                
                # Headers for WebSocket connection
                headers = {"Authorization": f"Token {self._api_key}"}
                
                logger.debug(f"🔗 Creating continuous WebSocket: {ws_url[:100]}...")
                
                # Connect to WebSocket with longer keepalive for continuous streaming
                self._continuous_websocket = await websockets.connect(
                    ws_url, 
                    additional_headers=headers,
                    ping_interval=20,  # Keep connection alive
                    ping_timeout=10,
                    close_timeout=5
                )
                
                logger.debug("✅ Continuous WebSocket connected for progressive streaming")
                return self._continuous_websocket
                
        except Exception as e:
            logger.error(f"❌ Failed to create continuous WebSocket: {e}")
            self._continuous_websocket = None
            return None
    
    async def _close_continuous_websocket(self):
        """Close the continuous WebSocket connection"""
        async with self._websocket_lock:
            if self._continuous_websocket and not self._continuous_websocket.closed:
                try:
                    await self._continuous_websocket.close()
                    logger.debug("🔒 Continuous WebSocket closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing continuous WebSocket: {e}")
                finally:
                    self._continuous_websocket = None
    
    async def _stream_transcribe_websocket(
        self,
        audio_data: bytes,
        on_partial_result: Optional[Callable[[str, float], None]],
        on_final_result: Optional[Callable[[str, float], None]],
        confidence_threshold: float
    ) -> Optional[str]:
        """Handle WebSocket streaming transcription"""
        try:
            # Build WebSocket URL with streaming parameters
            params = {
                "model": self.config.get("model", "nova-2"),
                "language": self.config.get("language", "en-US"),
                "punctuate": str(self.config.get("punctuate", True)).lower(),
                "smart_format": str(self.config.get("smart_format", True)).lower(),
                "interim_results": "true",  # ENABLE STREAMING!
                "utterances": "true",
                "profanity_filter": str(self.config.get("profanity_filter", False)).lower(),
                "numerals": str(self.config.get("numerals", False)).lower(),
                "no_delay": "true",
                "endpointing": "300",  # 300ms silence = utterance end
            }
            
            # Build WebSocket URL
            param_string = "&".join([f"{k}={v}" for k, v in params.items()])
            ws_url = f"{self._streaming_url}?{param_string}"
            
            # Headers for WebSocket connection
            headers = {"Authorization": f"Token {self._api_key}"}
            
            logger.debug(f"🔗 Connecting to Deepgram WebSocket: {ws_url[:100]}...")
            
            # Connect to WebSocket and stream audio  
            async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                logger.debug("✅ WebSocket connected, sending audio...")
                
                # Send audio data
                await websocket.send(audio_data)
                
                # Send close message to indicate end of audio
                await websocket.send(json.dumps({"type": "CloseStream"}))
                
                # Process streaming results
                final_transcript = None
                final_confidence = 0.0
                
                async for message in websocket:
                    try:
                        result = json.loads(message)
                        
                        # Handle different message types
                        if result.get("type") == "Results":
                            transcript, confidence, is_final = self._extract_streaming_result(result)
                            
                            if transcript:
                                if is_final:
                                    logger.debug(f"🎯 Final result: '{transcript}' (confidence: {confidence:.2f})")
                                    if confidence >= confidence_threshold:
                                        final_transcript = transcript
                                        final_confidence = confidence
                                    
                                    if on_final_result:
                                        on_final_result(transcript, confidence)
                                        
                                else:
                                    logger.debug(f"🔄 Partial result: '{transcript}' (confidence: {confidence:.2f})")
                                    if on_partial_result:
                                        on_partial_result(transcript, confidence)
                        
                        elif result.get("type") == "Utterance":
                            logger.debug("🔚 Utterance complete")
                            break
                            
                        elif result.get("type") == "SpeechStarted":
                            logger.debug("🗣️ Speech started")
                            
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Invalid JSON from WebSocket: {message}")
                        continue
                    except Exception as e:
                        logger.warning(f"⚠️ Error processing WebSocket message: {e}")
                        continue
                
                return final_transcript
                
        except Exception as e:
            logger.error(f"❌ WebSocket streaming error: {e}")
            raise
    
    def _extract_streaming_result(self, result: dict) -> tuple[Optional[str], float, bool]:
        """Extract transcript, confidence, and finality from streaming result"""
        try:
            channel = result.get("channel", {})
            alternatives = channel.get("alternatives", [])
            
            if not alternatives:
                return None, 0.0, False
                
            alternative = alternatives[0]
            transcript = alternative.get("transcript", "")
            confidence = alternative.get("confidence", 0.0)
            is_final = result.get("is_final", False)
            
            return transcript.strip() if transcript else None, confidence, is_final
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting streaming result: {e}")
            return None, 0.0, False

    # ===== EXISTING METHODS (UNCHANGED) =====

    async def transcribe_stream(self, audio_stream) -> str:
        """
        Legacy method for compatibility - not used in WebSocket context
        """
        logger.warning("⚠️ transcribe_stream called but not implemented for direct usage")
        return ""

    async def transcribe_file(self, audio_file_path: str) -> str:
        """
        Transcribe an audio file

        Args:
            audio_file_path: Path to audio file

        Returns:
            Transcription text
        """
        if not self._initialized:
            await self.initialize()

        try:
            with open(audio_file_path, "rb") as audio_file:
                audio_data = audio_file.read()
                return await self.transcribe_audio_bytes(audio_data) or ""

        except Exception as e:
            logger.error(f"❌ File transcription error: {e}")
            return ""

    # Test method for validation
    async def test_connection(self) -> bool:
        """Test the STT service connection"""
        try:
            await self.initialize()

            # Create a simple test audio (1 second of silence)
            test_audio = self._create_wav_file(b"\x00\x00" * 16000, 16000, 1, 16)

            # Test transcription
            result = await self.transcribe_audio_bytes(test_audio)
            logger.info(f"✅ STT test successful: {result}")
            return True

        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            return False

    # ===== REQUIRED ABSTRACT METHODS =====
    
    @property
    def is_initialized(self) -> bool:
        """Check if the service is initialized"""
        return self._initialized
    
    async def shutdown(self) -> None:
        """Clean up resources"""
        self._api_key = None
        self._initialized = False
        logger.info("🧹 DirectDeepgramSTTService shut down")
        
        # Close continuous WebSocket if active
        if self._continuous_websocket:
            await self._close_continuous_websocket()


class ProgressiveStreamHandler:
    """
    Handles progressive audio streaming for real-time transcription.
    
    This class manages:
    - Continuous WebSocket connection to Deepgram
    - Progressive audio chunk processing  
    - Partial result accumulation
    - Early processing triggers for LLM
    """
    
    def __init__(
        self,
        stt_service: DirectDeepgramSTTService,
        on_partial_result: Optional[Callable[[str, float, bool], None]] = None,
        on_final_result: Optional[Callable[[str, float], None]] = None,
        confidence_threshold: float = 0.7,
        chunk_duration_ms: int = 250,
        early_processing_threshold: float = 0.8
    ):
        self.stt_service = stt_service
        self.on_partial_result = on_partial_result
        self.on_final_result = on_final_result
        self.confidence_threshold = confidence_threshold
        self.chunk_duration_ms = chunk_duration_ms
        self.early_processing_threshold = early_processing_threshold
        
        # Progressive streaming state
        self.websocket = None
        self.active = False
        self.accumulated_transcript = ""
        self.last_confidence = 0.0
        self.chunk_count = 0
        self.early_trigger_sent = False
        
        # Audio buffering for progressive chunks
        self.audio_buffer = bytearray()
        self.chunk_size_bytes = int((16000 * 2 * chunk_duration_ms) / 1000)  # 16kHz, 16-bit, duration
        
        # Background tasks
        self.result_processor_task = None
        
    async def initialize(self) -> bool:
        """Initialize the progressive streaming handler"""
        try:
            # Create continuous WebSocket connection
            self.websocket = await self.stt_service._create_continuous_websocket()
            if not self.websocket:
                return False
                
            self.active = True
            
            # Start result processing task
            self.result_processor_task = asyncio.create_task(self._process_results())
            
            logger.info("🚀 Progressive stream handler initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize progressive stream handler: {e}")
            return False
    
    async def send_audio_chunk(self, audio_data: bytes) -> bool:
        """
        Send progressive audio chunk for real-time transcription.
        
        This method buffers audio and sends chunks at regular intervals.
        """
        if not self.active or not self.websocket:
            return False
            
        try:
            # Add to buffer
            self.audio_buffer.extend(audio_data)
            
            # Send chunk if buffer is large enough
            while len(self.audio_buffer) >= self.chunk_size_bytes:
                chunk = bytes(self.audio_buffer[:self.chunk_size_bytes])
                self.audio_buffer = self.audio_buffer[self.chunk_size_bytes:]
                
                # Send raw audio chunk to WebSocket
                await self.websocket.send(chunk)
                self.chunk_count += 1
                
                logger.debug(f"📤 Sent progressive chunk #{self.chunk_count}: {len(chunk)} bytes")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send audio chunk: {e}")
            await self._handle_error()
            return False
    
    async def finalize_stream(self) -> Optional[str]:
        """
        Finalize the progressive stream and get final transcript.
        """
        if not self.active:
            return self.accumulated_transcript
            
        try:
            # Send any remaining audio in buffer
            if len(self.audio_buffer) > 0:
                await self.websocket.send(bytes(self.audio_buffer))
                logger.debug(f"📤 Sent final chunk: {len(self.audio_buffer)} bytes")
                self.audio_buffer.clear()
            
            # Send close message
            await self.websocket.send(json.dumps({"type": "CloseStream"}))
            
            # Wait a moment for final results
            await asyncio.sleep(0.5)
            
            # Stop processing
            await self.close()
            
            # Return final accumulated transcript
            final_transcript = self.accumulated_transcript.strip()
            if final_transcript and self.on_final_result:
                self.on_final_result(final_transcript, self.last_confidence)
                
            logger.info(f"🎯 Progressive stream finalized: '{final_transcript}'")
            return final_transcript
            
        except Exception as e:
            logger.error(f"❌ Error finalizing progressive stream: {e}")
            await self._handle_error()
            return self.accumulated_transcript
    
    async def close(self):
        """Close the progressive stream handler"""
        self.active = False
        
        # Cancel result processor
        if self.result_processor_task and not self.result_processor_task.done():
            self.result_processor_task.cancel()
            try:
                await self.result_processor_task
            except asyncio.CancelledError:
                pass
        
        # WebSocket will be managed by the main service
        self.websocket = None
        
        logger.debug("🔒 Progressive stream handler closed")
    
    async def _process_results(self):
        """Background task to process WebSocket results"""
        try:
            async for message in self.websocket:
                if not self.active:
                    break
                    
                try:
                    result = json.loads(message)
                    await self._handle_result(result)
                    
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON in progressive stream: {message}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ Error processing progressive result: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Progressive result processing error: {e}")
            await self._handle_error()
    
    async def _handle_result(self, result: dict):
        """Handle individual WebSocket result"""
        try:
            if result.get("type") == "Results":
                transcript, confidence, is_final = self.stt_service._extract_streaming_result(result)
                
                if transcript:
                    # Update accumulated transcript
                    if is_final:
                        # Replace partial results with final
                        self.accumulated_transcript = transcript
                        self.last_confidence = confidence
                        logger.debug(f"🎯 Progressive final: '{transcript}' (confidence: {confidence:.2f})")
                    else:
                        # Update partial result
                        self.accumulated_transcript = transcript
                        self.last_confidence = confidence
                        logger.debug(f"🔄 Progressive partial: '{transcript}' (confidence: {confidence:.2f})")
                    
                    # Check for early processing trigger
                    should_trigger_early = (
                        not self.early_trigger_sent and
                        confidence >= self.early_processing_threshold and
                        len(transcript.strip()) > 10  # At least some meaningful content
                    )
                    
                    if should_trigger_early:
                        self.early_trigger_sent = True
                        logger.info(f"🚀 EARLY TRIGGER: '{transcript}' (confidence: {confidence:.2f})")
                    
                    # Call callback with early trigger flag
                    if self.on_partial_result:
                        self.on_partial_result(transcript, confidence, should_trigger_early)
                        
            elif result.get("type") == "SpeechStarted":
                logger.debug("🗣️ Progressive speech started")
                
            elif result.get("type") == "SpeechEnded":
                logger.debug("🔚 Progressive speech ended")
                
        except Exception as e:
            logger.warning(f"⚠️ Error handling progressive result: {e}")
    
    async def _handle_error(self):
        """Handle errors in progressive streaming"""
        logger.warning("⚠️ Progressive streaming error, attempting recovery...")
        self.active = False
        
        # Try to reconnect WebSocket
        try:
            self.websocket = await self.stt_service._create_continuous_websocket()
            if self.websocket:
                self.active = True
                logger.info("✅ Progressive stream recovered")
            else:
                logger.error("❌ Failed to recover progressive stream")
        except Exception as e:
            logger.error(f"❌ Recovery failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_direct_deepgram())
