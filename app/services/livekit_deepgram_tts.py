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

load_dotenv()
logger = logging.getLogger(__name__)

class LiveKitDeepgramTTS(tts.TTS):
    """Enhanced LiveKit-compatible Deepgram TTS with early playback and interruption handling"""
    
    VOICE_CONFIGS = {
        "adina": {
            "model": "aura-2-luna-en",  # Gentle, soothing female - conversational
            "description": "Compassionate spiritual guide"
        },
        "raffa": {
            "model": "aura-2-orion-en",  # Warm, approachable male - friendly mentor
            "description": "Wise spiritual mentor"
        }
    }
    
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True,
            ),
            sample_rate=24000,
            num_channels=1,
        )
        
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        self.base_url = "https://api.deepgram.com/v1/speak"
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_character = "adina"  # Default character
        self._active_streams = set()  # Track active streams for interruption
        
        logger.info("Enhanced LiveKit Deepgram TTS initialized with streaming support")
    
    def set_character(self, character: str):
        """Set the character voice for TTS"""
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
        
        self._current_character = character
        config = self.VOICE_CONFIGS[character]
        logger.info(f"Set TTS character to {character} ({config['description']}) - Model: {config['model']}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def synthesize(self, text: str) -> "ChunkedStream":
        """Synthesize text to audio stream (LiveKit TTS interface)"""
        return ChunkedStream(self, text, self._current_character)
    
    async def interrupt_all_streams(self):
        """Interrupt all active TTS streams"""
        logger.info(f"🛑 Interrupting {len(self._active_streams)} active TTS streams")
        for stream in list(self._active_streams):
            stream.interrupt()
    
    async def _synthesize_streaming(self, text: str, character: str, stream_id: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Enhanced streaming synthesis with early playback and interruption support"""
        if not text.strip():
            logger.warning("Empty text provided for TTS")
            return
        
        config = self.VOICE_CONFIGS[character]
        session = await self._get_session()
        
        start_time = time.time()
        first_chunk_yielded = False
        chunk_count = 0
        total_audio_duration = 0.0
        
        logger.info(f"🎤 Starting enhanced Deepgram TTS for {character}: '{text[:50]}...'")
        
        # Prepare request with optimized settings for streaming
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        params = {
            "model": config["model"],
            "encoding": "linear16",
            "sample_rate": 24000,
            "container": "none"  # Raw audio stream for fastest delivery
        }
        
        payload = {"text": text}
        
        try:
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Deepgram API error {response.status}: {error_text}")
                    raise Exception(f"Deepgram API error {response.status}: {error_text}")
                
                # Stream audio with small chunks for immediate playback
                chunk_size = 2048  # Smaller chunks for faster initial response
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    # Check for interruption
                    if stream_id not in self._active_streams:
                        logger.info(f"🛑 Stream {stream_id} interrupted, stopping TTS")
                        break
                    
                    if chunk:
                        chunk_count += 1
                        
                        # Log first chunk latency (early playback start)
                        if not first_chunk_yielded:
                            first_chunk_latency = (time.time() - start_time) * 1000
                            logger.info(f"🚀 EARLY PLAYBACK START for {character}: {first_chunk_latency:.0f}ms")
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
                        
                        # Log progress every 10 chunks
                        if chunk_count % 10 == 0:
                            logger.debug(f"🎵 Streamed {chunk_count} chunks, {total_audio_duration:.1f}s audio")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ Enhanced TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total, {total_audio_duration:.1f}s audio")
            
        except Exception as e:
            logger.error(f"Enhanced TTS error for {character}: {e}")
            raise
        finally:
            # Remove from active streams
            self._active_streams.discard(stream_id)
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert audio bytes to LiveKit AudioFrame with optimized settings"""
        # Convert bytes to 16-bit signed integers
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
            logger.info("Closed enhanced Deepgram TTS HTTP session")

class ChunkedStream:
    """Enhanced LiveKit TTS stream with interruption support"""
    
    def __init__(self, tts_instance: LiveKitDeepgramTTS, text: str, character: str):
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