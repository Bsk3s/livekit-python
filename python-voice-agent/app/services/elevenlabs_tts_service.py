import asyncio
import aiohttp
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from livekit import rtc
from livekit.agents import tts
import numpy as np
from dotenv import load_dotenv
import os
import time
import json

load_dotenv()
logger = logging.getLogger(__name__)

class ElevenLabsTTS(tts.TTS):
    """ElevenLabs streaming TTS service with character-specific voices"""
    
    # Declare streaming support for LiveKit
    supports_streaming = True
    
    # Character-specific voice configurations - using .env file voice IDs
    VOICE_CONFIGS = {
        "Adina": {
            "voice_id": os.getenv("ADINA_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),  # From .env or Rachel fallback
            "model": "eleven_turbo_v2_5",
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True
        },
        "Raffa": {
            "voice_id": os.getenv("RAFFA_VOICE_ID", "29vD33N1CtxCmqQRPOHJ"),  # From .env or Drew fallback
            "model": "eleven_turbo_v2_5", 
            "stability": 0.6,
            "similarity_boost": 0.7,
            "style": 0.3,
            "use_speaker_boost": True
        }
    }
    
    # Case-insensitive mapping from frontend names to config keys
    CHARACTER_MAP = {
        "adina": "Adina",
        "raffa": "Raffa",
        "Adina": "Adina",
        "Raffa": "Raffa"
    }
    
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True,
            ),
            sample_rate=24000,
            num_channels=1,
        )
        
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is required")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_character = "Adina"  # Default character
        self._active_streams = set()  # Track active streams for interruption
        
        # Log voice configuration
        logger.info("🎙️ ElevenLabs streaming TTS initialized")
        for char, config in self.VOICE_CONFIGS.items():
            logger.info(f"   🎭 {char}: {config['voice_id']}")

    def set_character(self, character: str):
        """Set the current character for voice selection (case-insensitive)"""
        mapped_character = self.CHARACTER_MAP.get(character)
        
        if mapped_character and mapped_character in self.VOICE_CONFIGS:
            self._current_character = mapped_character
            voice_id = self.VOICE_CONFIGS[mapped_character]['voice_id']
            logger.info(f"🎭 Character set to: {character} → {mapped_character} (voice: {voice_id})")
        else:
            logger.warning(f"Unknown character: {character}, keeping current: {self._current_character}")
            logger.info(f"Available characters: {list(self.CHARACTER_MAP.keys())}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create optimized HTTP session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=50,
                limit_per_host=25,
                ttl_dns_cache=3600,
                use_dns_cache=True,
                keepalive_timeout=300,
                enable_cleanup_closed=True,
            )
            
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=5,
                sock_read=10
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/wav"  # Request WAV format for easier processing
                }
            )
            
            logger.info("Created ElevenLabs HTTP session")
        
        return self._session
    
    def synthesize(self, text: str) -> "ElevenLabsStream":
        """Synthesize text to audio stream (LiveKit TTS interface)"""
        return ElevenLabsStream(self, text, self._current_character)
    
    async def stream(self, text: str, **kwargs) -> "ElevenLabsStream":
        """Stream text to audio (PRIMARY LiveKit streaming TTS interface)"""
        logger.info(f"🎙️ ElevenLabs TTS.stream() called with text: '{text[:50]}...'")
        logger.info(f"🎙️ Character: {self._current_character}")
        return ElevenLabsStream(self, text, self._current_character)
    
    async def _synthesize_streaming(self, text: str, character: str, stream_id: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Stream synthesis using ElevenLabs streaming API"""
        if not text.strip():
            logger.warning("Empty text provided for ElevenLabs TTS")
            return
        
        config = self.VOICE_CONFIGS[character]
        session = await self._get_session()
        
        start_time = time.time()
        first_chunk_yielded = False
        chunk_count = 0
        
        logger.info(f"🎙️ Starting ElevenLabs TTS for {character}: '{text[:50]}...'")
        
        # ElevenLabs streaming endpoint
        url = f"{self.base_url}/text-to-speech/{config['voice_id']}/stream"
        
        payload = {
            "text": text,
            "model_id": config["model"],
            "voice_settings": {
                "stability": config["stability"],
                "similarity_boost": config["similarity_boost"],
                "style": config.get("style", 0.0),
                "use_speaker_boost": config.get("use_speaker_boost", True)
            },
            "output_format": "pcm_24000"  # Use PCM format for direct audio processing
        }
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ElevenLabs API error {response.status}: {error_text}")
                    raise Exception(f"ElevenLabs API error {response.status}: {error_text}")
                
                # Stream the audio response in chunks
                chunk_size = 4800  # 4800 bytes = 0.1 seconds of 24kHz 16-bit mono audio
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    # Check for interruption
                    if stream_id not in self._active_streams:
                        logger.info(f"🛑 ElevenLabs stream {stream_id} interrupted")
                        break
                    
                    if chunk:
                        chunk_count += 1
                        
                        # Log first chunk latency
                        if not first_chunk_yielded:
                            first_chunk_latency = (time.time() - start_time) * 1000
                            logger.info(f"🚀 ElevenLabs FIRST CHUNK for {character}: {first_chunk_latency:.0f}ms")
                            first_chunk_yielded = True
                        
                        # Convert PCM chunk to AudioFrame
                        audio_frame = self._pcm_to_audio_frame(chunk)
                        if audio_frame:
                            yield audio_frame
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ ElevenLabs TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total")
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS error for {character}: {e}")
            raise
        finally:
            # Remove from active streams
            self._active_streams.discard(stream_id)
    
    def _pcm_to_audio_frame(self, pcm_chunk: bytes) -> Optional[rtc.AudioFrame]:
        """Convert PCM chunk to AudioFrame"""
        try:
            # Ensure we have valid audio data
            if len(pcm_chunk) < 2:  # Need at least 2 bytes for 16-bit sample
                return None
            
            # Convert bytes to 16-bit signed integers (PCM format)
            audio_data = np.frombuffer(pcm_chunk, dtype=np.int16)
            
            # Ensure we have valid audio data
            if len(audio_data) == 0:
                return None
            
            return rtc.AudioFrame(
                data=audio_data,
                sample_rate=24000,  # ElevenLabs PCM sample rate
                num_channels=1,     # Mono audio
                samples_per_channel=len(audio_data)
            )
            
        except Exception as e:
            logger.debug(f"Error converting PCM chunk: {e}")
            return None
    
    async def aclose(self):
        """Clean up resources"""
        # Clear active streams
        self._active_streams.clear()
        
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Closed ElevenLabs TTS HTTP session")


class ElevenLabsStream:
    """ElevenLabs TTS stream with interruption support"""
    
    def __init__(self, tts_instance: ElevenLabsTTS, text: str, character: str):
        self._tts = tts_instance
        self._text = text
        self._character = character
        self._stream = None
        self._stream_id = f"elevenlabs_{int(time.time() * 1000)}"
        self._interrupted = False
        
        # Add to active streams for interruption tracking
        self._tts._active_streams.add(self._stream_id)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
    
    def interrupt(self):
        """Interrupt this specific stream"""
        self._interrupted = True
        self._tts._active_streams.discard(self._stream_id)
        logger.info(f"🛑 ElevenLabs stream {self._stream_id} interrupted")
    
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

# Verification logging
logger.info("✅ Loaded ElevenLabs TTS class: %r", ElevenLabsTTS)
logger.info("✅ ElevenLabs TTS supports_streaming: %s", getattr(ElevenLabsTTS, 'supports_streaming', 'NOT_SET')) 