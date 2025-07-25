import io
import logging
import os
import threading
import time
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline
from livekit.agents import tts
from livekit import rtc

logger = logging.getLogger(__name__)


class KokoroModelSingleton:
    """Singleton to manage Kokoro model instance for memory efficiency"""
    
    _instance = None
    _lock = threading.Lock()
    _model = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._init_model()
                    self._initialized = True
    
    def _init_model(self):
        """Initialize Kokoro model once"""
        try:
            logger.info("🎵 Initializing Kokoro model (one-time startup)")
            self._model = KPipeline(lang_code="a")  # 'a' = American English
            logger.info("✅ Kokoro model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kokoro model: {e}")
            raise

    def create_audio(self, text: str, voice: str, speed: float):
        """Generate audio using the singleton model"""
        if not self._model:
            raise RuntimeError("Kokoro model not initialized")
        
        try:
            # Get generator from Kokoro pipeline
            # Generator yields (gs, ps, audio) tuples per documentation
            audio_gen = self._model(text, voice=voice, speed=speed)
            
            # Collect all audio chunks from generator
            audio_chunks = []
            for gs, ps, audio in audio_gen:
                # audio is already a numpy array per documentation
                audio_chunks.append(audio)
            
            # Concatenate all chunks
            if audio_chunks:
                # Concatenate numpy arrays
                samples = np.concatenate(audio_chunks, axis=0)
                sample_rate = 24000  # Kokoro default sample rate per docs
                return samples, sample_rate
            else:
                raise RuntimeError("No audio generated")
                
        except Exception as e:
            logger.error(f"❌ Kokoro audio generation failed: {e}")
            raise


class KokoroTTS(tts.TTS):
    """Kokoro TTS implementation for LiveKit"""
    
    def __init__(self, voice: str = "af", **kwargs):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=16000,  # Reverted: Keep 16kHz to match frontend expectations
            num_channels=1,
            **kwargs,
        )
        self.voice = voice
        self.lang = "en-us"
        self.speed = 1.1
        
        # Get the singleton instance
        self.model_singleton = KokoroModelSingleton()
        
        logger.info(f"✅ KokoroTTS instance created (voice: {voice})")

    async def synthesize(self, text: str):
        """Generate audio using Kokoro TTS"""
        try:
            logger.info(f"🎵 Generating audio with Kokoro model")
            samples, sample_rate = self.model_singleton.create_audio(
                text, self.voice, self.speed
            )

            # Convert to 16-bit PCM
            if samples.dtype != np.int16:
                samples = (samples * 32767).astype(np.int16)

            logger.info(f"✅ Generated {len(samples)} samples at {sample_rate}Hz")
            
            # Create audio frame
            frame = rtc.AudioFrame(
                data=samples,
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(samples),
            )
            
            # Create a simple async generator that yields the frame
            async def audio_generator():
                yield frame
                logger.info(f"🎵 Audio frame published to LiveKit (size: {len(samples)} samples)")
            
            # FIXED: Wrap in tts.ChunkedStream like working TTS implementations
            return tts.ChunkedStream(audio_generator())

        except Exception as e:
            logger.error(f"❌ Kokoro synthesis failed: {e}")
            # Return empty ChunkedStream on error
            async def empty_generator():
                return
                yield  # unreachable, but makes it a generator
            
            return tts.ChunkedStream(empty_generator())

    def synthesize(self, text: str):
        """Sync version - not implemented for Kokoro"""
        raise NotImplementedError("Use asynthesize() for Kokoro TTS")


def create_kokoro_tts(character: str = "adina") -> KokoroTTS:
    """Factory function to create character-specific Kokoro TTS"""
    
    # Character-specific voice mapping (using official Kokoro voice names from docs)
    voice_map = {
        "adina": "af_heart",  # Female voice for Adina (American Female)
        "raffa": "am_adam",   # Male voice for Raffa (American Male)
    }
    
    voice = voice_map.get(character.lower(), "af_heart")
    logger.info(f"🎵 Creating Kokoro TTS with voice '{voice}' for character '{character}'")
    
    return KokoroTTS(voice=voice)
