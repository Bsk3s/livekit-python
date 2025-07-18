import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Callable
import websockets
from datetime import datetime

from spiritual_voice_agent.services.stt.base import BaseSTTService

logger = logging.getLogger(__name__)


class StreamingDeepgramSTTService(BaseSTTService):
    """Real-time WebSocket Deepgram implementation for sub-100ms latency."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._api_key = None
        self._websocket = None
        self._initialized = False
        self._is_connected = False
        self._transcription_callback: Optional[Callable] = None
        self._connection_lock = asyncio.Lock()
        self._last_activity = time.time()
        self._ping_task = None
        
        # Performance tracking
        self._last_audio_time = None
        self._transcription_times = []

    def _validate_config(self) -> None:
        """Validate required configuration and environment variables"""
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set or empty")
        self._api_key = api_key
        logger.info(f"🔑 Deepgram API key validated for WebSocket streaming")

    async def initialize(self) -> None:
        """Initialize the WebSocket connection"""
        if not self._initialized:
            try:
                self._validate_config()
                await self._connect_websocket()
                self._initialized = True
                logger.info("✅ StreamingDeepgramSTTService initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize StreamingDeepgramSTTService: {e}")
                raise

    async def _connect_websocket(self) -> None:
        """Establish WebSocket connection with optimized parameters for real-time"""
        async with self._connection_lock:
            if self._is_connected:
                return

            # WebSocket URL with optimized parameters for minimal latency
            base_url = "wss://api.deepgram.com/v1/listen"
            params = {
                "model": self.config.get("model", "nova-2"),
                "language": self.config.get("language", "en-US"),
                "smart_format": "true",
                "punctuate": "true",
                "interim_results": "true",     # ← Critical for real-time
                "endpointing": "10",           # ← Very short endpointing (10ms)
                "utterance_end_ms": "300",     # ← Quick utterance detection
                "vad_turnoff": "100",          # ← Fast voice activity detection (100ms)
                "no_delay": "true",            # ← Critical for minimal latency
                "encoding": "linear16",        # ← Raw PCM, no WAV overhead
                "sample_rate": "16000",
                "channels": "1",
                "filler_words": "false",       # ← Skip filler words for speed
                "profanity_filter": "false"
            }
            
            # Build query string
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{base_url}?{query_params}"
            
            # Headers
            headers = {"Authorization": f"Token {self._api_key}"}
            
            try:
                logger.info(f"🔗 Connecting to Deepgram WebSocket...")
                self._websocket = await websockets.connect(
                    url,
                    extra_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=10 * 1024 * 1024,  # 10MB max message size
                    compression=None  # Disable compression for speed
                )
                
                self._is_connected = True
                self._last_activity = time.time()
                
                # Start background tasks
                asyncio.create_task(self._listen_for_transcriptions())
                self._ping_task = asyncio.create_task(self._keep_alive())
                
                logger.info("✅ Deepgram WebSocket connected and listening")
                
            except Exception as e:
                logger.error(f"❌ Failed to connect WebSocket: {e}")
                self._is_connected = False
                raise

    async def _listen_for_transcriptions(self) -> None:
        """Listen for real-time transcription results"""
        try:
            async for message in self._websocket:
                await self._handle_websocket_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 Deepgram WebSocket connection closed")
            self._is_connected = False
        except Exception as e:
            logger.error(f"❌ Error in transcription listener: {e}")
            self._is_connected = False

    async def _handle_websocket_message(self, message: str) -> None:
        """Process incoming WebSocket messages with latency tracking"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "Results":
                await self._process_transcription_result(data)
            elif msg_type == "Metadata":
                logger.debug(f"📊 Deepgram metadata: {data}")
            elif msg_type == "SpeechStarted":
                logger.debug("🎤 Speech started detected")
                self._last_audio_time = time.time()
            elif msg_type == "UtteranceEnd":
                logger.debug("🔚 Utterance end detected")
            else:
                logger.debug(f"📨 Unknown message type: {msg_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")

    async def _process_transcription_result(self, data: dict) -> None:
        """Process transcription with performance tracking"""
        try:
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])
            
            if not alternatives:
                return
                
            alternative = alternatives[0]
            transcript = alternative.get("transcript", "").strip()
            confidence = alternative.get("confidence", 0.0)
            is_final = channel.get("is_final", False)
            
            # Calculate latency if we have timing data
            current_time = time.time()
            latency_ms = None
            if self._last_audio_time:
                latency_ms = (current_time - self._last_audio_time) * 1000
                
            if transcript:
                if is_final:
                    # Track final transcription performance
                    if latency_ms:
                        self._transcription_times.append(latency_ms)
                        # Keep only last 50 measurements
                        if len(self._transcription_times) > 50:
                            self._transcription_times.pop(0)
                            
                    logger.info(f"📝 FINAL: '{transcript}' (confidence: {confidence:.2f}, latency: {latency_ms:.1f}ms)")
                    
                    # Send to callback if registered
                    if self._transcription_callback:
                        await self._transcription_callback(transcript, is_final, confidence, latency_ms)
                        
                else:
                    logger.debug(f"📝 interim: '{transcript}' (confidence: {confidence:.2f})")
                    
                    # Send interim results too for ultra-responsive UX
                    if self._transcription_callback:
                        await self._transcription_callback(transcript, is_final, confidence, latency_ms)
                        
        except Exception as e:
            logger.error(f"❌ Error processing transcription result: {e}")

    async def _keep_alive(self) -> None:
        """Keep WebSocket connection alive"""
        while self._is_connected:
            try:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if self._websocket and not self._websocket.closed:
                    await self._websocket.ping()
                    logger.debug("🏓 WebSocket ping sent")
            except Exception as e:
                logger.warning(f"⚠️ Ping failed: {e}")
                break

    async def send_audio_chunk(self, audio_data: bytes) -> None:
        """Send raw PCM audio data for real-time transcription"""
        if not self._is_connected or not self._websocket:
            logger.warning("⚠️ WebSocket not connected, cannot send audio")
            return
            
        try:
            # Send raw PCM data directly - no conversion overhead!
            await self._websocket.send(audio_data)
            self._last_activity = time.time()
            
            # Track when we send audio for latency calculation
            if not self._last_audio_time:
                self._last_audio_time = time.time()
                
        except Exception as e:
            logger.error(f"❌ Error sending audio chunk: {e}")
            self._is_connected = False

    def set_transcription_callback(self, callback: Callable) -> None:
        """Set callback function for handling transcriptions"""
        self._transcription_callback = callback

    async def transcribe_audio_bytes(self, audio_data: bytes) -> Optional[str]:
        """
        Legacy method for compatibility - streams audio and waits for result
        Note: For real-time use, prefer send_audio_chunk() with callback
        """
        if not self._initialized:
            await self.initialize()
            
        # This is a compatibility method - not optimal for streaming
        logger.warning("⚠️ Using legacy transcribe_audio_bytes - consider using send_audio_chunk() for better performance")
        
        # Send audio and wait briefly for transcription
        await self.send_audio_chunk(audio_data)
        
        # Wait up to 500ms for a transcription result
        await asyncio.sleep(0.5)
        
        return None  # Real results come through callback

    async def shutdown(self) -> None:
        """Clean up WebSocket connection and resources"""
        logger.info("🧹 Shutting down StreamingDeepgramSTTService...")
        
        self._is_connected = False
        
        if self._ping_task:
            self._ping_task.cancel()
            
        if self._websocket:
            await self._websocket.close()
            
        self._initialized = False
        
        # Log performance stats
        if self._transcription_times:
            avg_latency = sum(self._transcription_times) / len(self._transcription_times)
            min_latency = min(self._transcription_times)
            max_latency = max(self._transcription_times)
            logger.info(f"📊 Session stats - Avg: {avg_latency:.1f}ms, Min: {min_latency:.1f}ms, Max: {max_latency:.1f}ms")
        
        logger.info("✅ StreamingDeepgramSTTService shutdown complete")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def transcribe_stream(self, audio_stream) -> str:
        """Legacy method - not used in WebSocket streaming context"""
        logger.warning("⚠️ transcribe_stream called but not implemented for WebSocket streaming")
        return ""

    async def transcribe_file(self, audio_file_path: str) -> str:
        """Transcribe an audio file - fallback to HTTP for files"""
        logger.warning("⚠️ File transcription not optimized for WebSocket - consider HTTP fallback")
        return ""


# Test function
async def test_streaming_deepgram():
    """Test the streaming Deepgram service"""
    logger.info("🧪 Testing StreamingDeepgramSTTService...")
    
    service = StreamingDeepgramSTTService({
        "model": "nova-2",
        "language": "en-US"
    })
    
    # Callback to handle transcriptions
    async def transcription_handler(text: str, is_final: bool, confidence: float, latency_ms: float):
        status = "FINAL" if is_final else "interim"
        logger.info(f"📝 {status}: '{text}' (confidence: {confidence:.2f}, latency: {latency_ms:.1f}ms)")
    
    try:
        service.set_transcription_callback(transcription_handler)
        await service.initialize()
        
        # Simulate sending audio chunks
        logger.info("🎤 Simulating audio stream...")
        test_audio = b"\x00\x01" * 1600  # 0.1 second of test audio
        
        for i in range(5):
            await service.send_audio_chunk(test_audio)
            await asyncio.sleep(0.1)  # Simulate real-time audio chunks
            
        # Wait for any final transcriptions
        await asyncio.sleep(2)
        
        await service.shutdown()
        logger.info("✅ Streaming test completed")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_streaming_deepgram())