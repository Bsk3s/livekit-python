import asyncio
import aiohttp
import logging
from typing import AsyncGenerator, Optional
from livekit import rtc
from livekit.agents import tts
import numpy as np
from dotenv import load_dotenv
import os
import time
import uuid

load_dotenv()
logger = logging.getLogger(__name__)

class LiveKitDeepgramTTS(tts.TTS):
    """Ultra-optimized LiveKit-compatible Deepgram TTS targeting sub-300ms latency"""
    
    VOICE_CONFIGS = {
        "Adina": {"model": "aura-2-luna-en"},
        "Raffa": {"model": "aura-2-orion-en"}
    }
    
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True,  # We support streaming
            ),
            sample_rate=24000,
            num_channels=1,
        )
        
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        self.base_url = "https://api.deepgram.com/v1/speak"
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_character = "Adina"  # Default character
        self._active_streams = set()  # Track active streams for interruption
        self._connection_warmed = False  # Track if connection is pre-warmed
        
        logger.info("🚀 Ultra-optimized LiveKit Deepgram TTS initialized")
    
    def set_character(self, character: str):
        """Set the current character for voice selection"""
        if character in self.VOICE_CONFIGS:
            self._current_character = character
            logger.info(f"🎭 Character set to: {character} (model: {self.VOICE_CONFIGS[character]['model']})")
        else:
            logger.warning(f"Unknown character: {character}, keeping current: {self._current_character}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create optimized HTTP session with connection pooling"""
        if self._session is None or self._session.closed:
            # BLAZING FAST connector for sub-200ms latency
            connector = aiohttp.TCPConnector(
                limit=100,  # MASSIVE connection pool size
                limit_per_host=50,  # MASSIVE connections per host
                ttl_dns_cache=7200,  # 2 hour DNS cache TTL
                use_dns_cache=True,  # Enable DNS caching
                keepalive_timeout=600,  # Keep connections alive 10 minutes
                enable_cleanup_closed=True,  # Clean up closed connections
                force_close=False,  # Reuse connections aggressively
                ssl=False,  # Disable SSL verification for maximum speed
                family=0,  # Use any address family for speed
                local_addr=None,  # No local address binding
                resolver=None,  # Use default resolver
                verify_ssl=False,  # Disable SSL verification for speed
                happy_eyeballs_delay=0,  # No delay for IPv6/IPv4 fallback
                interleave=1,  # Interleave address families for speed
            )
            
            # BLAZING FAST timeout settings
            timeout = aiohttp.ClientTimeout(
                total=2,  # BLAZING FAST total timeout (2 seconds)
                connect=0.3,  # BLAZING FAST connection timeout (300ms)
                sock_read=0.5  # BLAZING FAST socket read timeout (500ms)
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",  # Reuse connections
                    "Accept-Encoding": "gzip, deflate"  # Enable compression
                }
            )
            
            logger.info("Created ultra-optimized HTTP session with connection pooling")
        
        return self._session
    
    async def _warm_connection(self):
        """Pre-warm the connection to eliminate cold start latency"""
        if self._connection_warmed:
            return
            
        try:
            session = await self._get_session()
            # Make a tiny test request to warm up the connection
            test_params = {
                "model": "aura-2-luna-en",
                "encoding": "linear16",
                "sample_rate": 24000,
                "container": "none",
            }
            test_payload = {"text": "Hi"}  # Minimal text for warming
            
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in test_params.items()])
            
            async with session.post(url, json=test_payload) as response:
                # Just read a tiny bit to establish connection
                async for chunk in response.content.iter_chunked(100):
                    break  # Only need first tiny chunk
            
            self._connection_warmed = True
            logger.info("🔥 Connection pre-warmed for ultra-fast responses")
            
        except Exception as e:
            logger.warning(f"⚠️ Connection warming failed: {e}")
            # Don't fail if warming doesn't work
    
    def synthesize(self, text: str) -> "ChunkedStream":
        """Synthesize text to audio stream (LiveKit TTS interface)"""
        return ChunkedStream(self, text, self._current_character)
    
    def stream(self, text: str) -> "ChunkedStream":
        """Stream text to audio (LiveKit streaming TTS interface)"""
        logger.info(f"🎤 TTS.stream() called with text: '{text[:50]}...'")
        return ChunkedStream(self, text, self._current_character)
    
    async def interrupt_all_streams(self):
        """Interrupt all active TTS streams"""
        logger.info(f"🛑 Interrupting {len(self._active_streams)} active TTS streams")
        # Clear the active streams set (stream IDs, not objects)
        self._active_streams.clear()
    
    async def _synthesize_streaming(self, text: str, character: str, stream_id: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Ultra-optimized streaming synthesis targeting sub-300ms first chunk"""
        if not text.strip():
            logger.warning("Empty text provided for TTS")
            return
        
        # Pre-warm connection for ultra-fast response
        await self._warm_connection()
        
        config = self.VOICE_CONFIGS[character]
        session = await self._get_session()
        
        start_time = time.time()
        first_chunk_yielded = False
        chunk_count = 0
        total_audio_duration = 0.0
        
        logger.info(f"🎤 Starting ultra-optimized Deepgram TTS for {character}: '{text[:50]}...'")
        
        # Ultra-optimized parameters for fastest response
        params = {
            "model": config["model"],
            "encoding": "linear16",
            "sample_rate": 24000,
            "container": "none",  # Raw audio stream for fastest delivery
            "filler_injection": "false",  # Disable fillers for speed
            "smart_format": "false"  # Disable smart formatting for speed
        }
        
        payload = {"text": text}
        
        try:
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            # Use pre-configured session with optimized headers
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Deepgram API error {response.status}: {error_text}")
                    raise Exception(f"Deepgram API error {response.status}: {error_text}")
                
                # BLAZING FAST chunks for INSTANT streaming (sub-200ms target)
                chunk_size = 128  # BLAZING FAST chunks (128 bytes) for INSTANT response
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    # Check for interruption
                    if stream_id not in self._active_streams:
                        logger.info(f"🛑 Stream {stream_id} interrupted, stopping TTS")
                        break
                    
                    if chunk:
                        chunk_count += 1
                        
                        # Log first chunk latency (targeting sub-300ms)
                        if not first_chunk_yielded:
                            first_chunk_latency = (time.time() - start_time) * 1000
                            logger.info(f"🚀 ULTRA-FAST FIRST CHUNK for {character}: {first_chunk_latency:.0f}ms")
                            first_chunk_yielded = True
                            
                            # Import timestamp logger from agent
                            try:
                                from agents.spiritual_session import timestamp_logger
                                timestamp_logger.mark_tts_first_chunk()
                            except ImportError:
                                pass  # Fallback if not available
                        
                        # Convert to AudioFrame and yield immediately
                        audio_frame = self._create_audio_frame(chunk)
                        total_audio_duration += audio_frame.duration
                        yield audio_frame
                        
                        # Log progress every 20 chunks (less logging for speed)
                        if chunk_count % 20 == 0:
                            logger.debug(f"🎵 Streamed {chunk_count} chunks, {total_audio_duration:.1f}s audio")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ Ultra-optimized TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total, {total_audio_duration:.1f}s audio")
            
        except Exception as e:
            logger.error(f"Ultra-optimized TTS error for {character}: {e}")
            raise
        finally:
            # Remove from active streams
            self._active_streams.discard(stream_id)
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert audio bytes to LiveKit AudioFrame with minimal processing"""
        # Convert bytes to 16-bit signed integers (optimized)
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,  # Deepgram standard rate
            num_channels=1,     # Mono audio
            samples_per_channel=len(audio_data)
        )
    
    async def aclose(self):
        """Clean up resources and interrupt active streams"""
        # Interrupt all active streams
        await self.interrupt_all_streams()
        
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Closed ultra-optimized Deepgram TTS HTTP session")

class ChunkedStream(tts.SynthesizeStream):
    """Ultra-optimized LiveKit TTS stream with interruption support"""
    
    def __init__(self, tts_instance: LiveKitDeepgramTTS, text: str, character: str):
        super().__init__()  # Initialize parent SynthesizeStream
        self._tts = tts_instance
        self._text = text
        self._character = character
        self._stream = None
        self._stream_id = f"tts_{int(time.time() * 1000)}"  # Unique stream ID
        self._interrupted = False
        
        # Add to active streams for interruption tracking
        self._tts._active_streams.add(self._stream_id)
    
    def interrupt(self):
        """Interrupt this specific stream"""
        self._interrupted = True
        self._tts._active_streams.discard(self._stream_id)
        logger.info(f"🛑 Stream {self._stream_id} marked for interruption")
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> tts.SynthesizedAudio:
        if self._interrupted:
            raise StopAsyncIteration
        
        if self._stream is None:
            self._stream = self._tts._synthesize_streaming(self._text, self._character, self._stream_id)
        
        try:
            audio_frame = await self._stream.__anext__()
            return tts.SynthesizedAudio(
                frame=audio_frame,
                request_id=self._stream_id,
            )
        except StopAsyncIteration:
            # Clean up when stream ends
            self._tts._active_streams.discard(self._stream_id)
            raise StopAsyncIteration
    
    async def aclose(self):
        """Close the stream and clean up"""
        self.interrupt()
        if self._stream:
            try:
                await self._stream.aclose()
            except:
                pass 