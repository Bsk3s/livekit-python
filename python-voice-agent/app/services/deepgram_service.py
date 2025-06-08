from livekit.plugins import deepgram, openai
from livekit.agents import stt
import os
import logging
import asyncio
import time
import websockets

logger = logging.getLogger(__name__)

class RateLimitedDeepgramSTT(stt.STT):
    """Deepgram STT with rate limiting and retry logic to prevent 429 errors"""
    
    def __init__(self):
        # Initialize with Deepgram STT capabilities
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=True,
                interim_results=True,
            )
        )
        
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        # Rate limiting state
        self._connection_count = 0
        self._last_connection_time = 0
        self._retry_count = 0
        self._rate_limit_delay = 2.0  # Minimum seconds between connections
        self._active_connections = set()
        
        # Deepgram STT configuration
        self._config = {
            "model": "nova-3",
            "language": "multi",
            "interim_results": True,
            "punctuate": True,
            "smart_format": True,
            "no_delay": True,
            "endpointing": 25,
            "filler_words": True,
            "sample_rate": 16000,
            "profanity_filter": False,
            "numerals": False,
        }
        
        logger.info("🚀 Rate-limited Deepgram STT initialized")
    
    async def _check_rate_limit(self):
        """Implement rate limiting to prevent 429 errors"""
        current_time = time.time()
        time_since_last = current_time - self._last_connection_time
        
        # Minimum delay between connections to prevent spam
        if time_since_last < self._rate_limit_delay:
            wait_time = self._rate_limit_delay - time_since_last
            logger.info(f"⏳ STT Rate limiting: waiting {wait_time:.1f}s before next connection")
            await asyncio.sleep(wait_time)
        
        self._last_connection_time = time.time()
        self._connection_count += 1
    
    async def _exponential_backoff(self):
        """Implement exponential backoff for retries"""
        if self._retry_count > 0:
            backoff_time = min(2 ** self._retry_count, 30)  # Max 30 seconds
            logger.info(f"🔄 STT Retry #{self._retry_count}: backing off for {backoff_time}s")
            await asyncio.sleep(backoff_time)
        self._retry_count += 1
    
    def recognize(self, *, buffer, language=None):
        """Create a recognition stream with rate limiting"""
        return RateLimitedSTTStream(self, buffer, language)
    
    async def aclose(self):
        """Clean up all connections and reset state"""
        logger.info("🧹 Cleaning up Rate-limited Deepgram STT service")
        
        # Close all active connections
        for connection in list(self._active_connections):
            try:
                await connection.close()
                logger.debug("🔌 Closed STT WebSocket connection")
            except Exception as e:
                logger.warning(f"⚠️ Error closing STT WebSocket: {e}")
        
        # Reset all state
        self._active_connections.clear()
        self._connection_count = 0
        self._retry_count = 0
        self._last_connection_time = 0
        
        logger.info("✅ Rate-limited Deepgram STT service cleaned up")


class RateLimitedSTTStream:
    """STT stream with rate limiting and retry logic"""
    
    def __init__(self, stt_instance, buffer, language):
        self._stt = stt_instance
        self._buffer = buffer
        self._language = language or "multi"
        self._websocket = None
        self._stream_id = f"stt_{int(time.time() * 1000)}"
        self._interrupted = False
        
    async def __aenter__(self):
        """Start the STT stream with rate limiting"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting to prevent 429 errors
                await self._stt._check_rate_limit()
                
                # Apply exponential backoff if this is a retry
                if attempt > 0:
                    await self._stt._exponential_backoff()
                
                # Build WebSocket URL with parameters
                params = []
                for key, value in self._stt._config.items():
                    params.append(f"{key}={value}")
                
                url = f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"
                
                # WebSocket headers for authentication
                headers = {
                    "Authorization": f"Token {self._stt.api_key}"
                }
                
                # Connect to Deepgram WebSocket STT endpoint
                self._websocket = await websockets.connect(url, extra_headers=headers)
                self._stt._active_connections.add(self._websocket)
                logger.info(f"✅ STT WebSocket connection established (attempt {attempt + 1})")
                
                # Reset retry count on successful connection
                self._stt._retry_count = 0
                
                return self
                
            except websockets.exceptions.InvalidStatusCode as e:
                if e.status_code == 429:
                    logger.warning(f"⚠️ STT Rate limited (429) on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        # Exponential backoff for rate limiting
                        backoff_time = min(2 ** (attempt + 1), 30)
                        logger.info(f"⏳ STT Backing off for {backoff_time}s due to rate limiting")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        logger.error("❌ STT Max retries exceeded due to rate limiting")
                        raise Exception("Deepgram STT API rate limit exceeded - consider upgrading your plan")
                else:
                    logger.error(f"❌ STT WebSocket connection failed with status {e.status_code}: {e}")
                    raise
            
            except Exception as e:
                logger.error(f"❌ STT WebSocket connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 STT Retrying in {2 ** attempt}s...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("❌ STT Max retries exceeded for WebSocket connection")
                    raise
        
        raise Exception("Failed to establish STT WebSocket connection after all retries")
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the STT stream"""
        if self._websocket:
            try:
                self._stt._active_connections.discard(self._websocket)
                await self._websocket.close()
                logger.debug(f"🔌 STT WebSocket stream {self._stream_id} closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing STT WebSocket: {e}")
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        """Get next STT result"""
        if self._interrupted or not self._websocket:
            raise StopAsyncIteration
        
        try:
            # Send audio data to WebSocket
            if self._buffer:
                await self._websocket.send(self._buffer)
            
            # Receive transcription results
            async for message in self._websocket:
                # Process Deepgram response
                import json
                try:
                    data = json.loads(message)
                    if data.get("type") == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [])
                        if alternatives:
                            transcript = alternatives[0].get("transcript", "")
                            confidence = alternatives[0].get("confidence", 0.0)
                            is_final = channel.get("is_final", False)
                            
                            return stt.SpeechEvent(
                                type=stt.SpeechEventType.FINAL_TRANSCRIPT if is_final else stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                alternatives=[
                                    stt.SpeechData(
                                        text=transcript,
                                        confidence=confidence,
                                        language=self._language
                                    )
                                ]
                            )
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON from STT WebSocket: {message}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error processing STT message: {e}")
                    continue
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 STT WebSocket connection closed")
            raise StopAsyncIteration
        except Exception as e:
            logger.error(f"❌ STT WebSocket error: {e}")
            raise StopAsyncIteration


def create_deepgram_stt():
    """Create standard Deepgram STT (legacy)"""
    if not os.getenv("DEEPGRAM_API_KEY"):
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")
    
    try:
        return deepgram.STT(
            model="nova-3",
            language="multi",
            interim_results=True,
            punctuate=True,
            smart_format=True,
            no_delay=True,
            endpointing_ms=25,
            filler_words=True,
            sample_rate=16000,
            profanity_filter=False,
            numerals=False,
        )
    except Exception as e:
        logger.error(f"❌ Failed to create Deepgram STT: {e}")
        raise

def create_rate_limited_deepgram_stt():
    """Create rate-limited Deepgram STT to prevent 429 errors"""
    try:
        stt_service = RateLimitedDeepgramSTT()
        logger.info("✅ STT: Rate-limited Deepgram Nova-3 (prevents 429 errors)")
        return stt_service
    except Exception as e:
        logger.error(f"❌ Failed to create rate-limited Deepgram STT: {e}")
        raise

def create_openai_whisper_stt():
    """Create OpenAI Whisper STT as fallback"""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    try:
        return openai.STT(
            model="whisper-1",
            language="en",
        )
    except Exception as e:
        logger.error(f"❌ Failed to create OpenAI Whisper STT: {e}")
        raise

def create_stt_with_fallback():
    """Create STT service with rate limiting and automatic fallback"""
    try:
        # Use standard LiveKit Deepgram STT plugin (most reliable)
        logger.info("🎧 Creating Deepgram STT service...")
        return create_deepgram_stt()
    except Exception as e:
        logger.warning(f"⚠️ Deepgram STT failed, falling back to OpenAI Whisper: {e}")
        try:
            # Fallback to OpenAI Whisper
            stt_service = create_openai_whisper_stt()
            logger.info("✅ STT: OpenAI Whisper (fallback)")
            return stt_service
        except Exception as fallback_e:
            logger.error(f"❌ Both STT services failed: {fallback_e}")
            raise Exception("All STT services unavailable") 