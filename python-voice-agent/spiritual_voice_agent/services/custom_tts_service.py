#!/usr/bin/env python3
"""
Custom TTS Service Template
Easy-to-modify template for plugging in your own TTS model
"""

import asyncio
import io
import logging
from typing import AsyncGenerator, Optional

import numpy as np
from livekit import rtc
from livekit.agents import tts

from spiritual_voice_agent.services.tts.implementations.kokoro.kokoro import KokoroTTS

logger = logging.getLogger(__name__)


class WAVTTSService(tts.TTS):
    """
    WAV TTS Service - Uses direct OpenAI API for WAV output (iOS compatible)
    Implements LiveKit TTS interface for compatibility
    """

    def __init__(self, character: str = "adina"):
        """Initialize WAV TTS service"""
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=16000,  # Standard sample rate for voice
            num_channels=1,  # Mono audio
        )

        self.character = character

        # Character-specific voice mapping
        voice_map = {
            "adina": "nova",  # Warm, feminine
            "raffa": "onyx",  # Deep, masculine
            "default": "alloy",  # Neutral
        }

        self.voice = voice_map.get(character.lower(), "alloy")

        logger.info(f"🎙️ WAV TTS initialized for character: {character} (voice: {self.voice})")

    async def synthesize(self, text: str) -> "tts.ChunkedStream":
        """
        Synthesize text to WAV audio using direct OpenAI API (iOS compatible)
        """
        logger.info(f"🎤 WAV TTS synthesis: '{text[:50]}...'")

        try:
            # Use direct OpenAI API for WAV output (iOS compatible)
            import openai

            response = await openai.AsyncOpenAI().audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text,
                response_format="wav",  # Changed from mp3 to wav for iOS compatibility
            )

            audio_data = await response.aread()
            logger.info(f"🎵 WAV TTS generated: {len(audio_data)} bytes")

            # Store the WAV data for retrieval
            self._last_wav_data = audio_data

            # Return a simple stream that yields the WAV data
            return tts.ChunkedStream(self._wav_to_audio_frames(audio_data))

        except Exception as e:
            logger.error(f"❌ WAV TTS synthesis failed: {e}")
            # Return silence as fallback
            return tts.ChunkedStream(self._create_silence_stream())

    def _wav_to_audio_frames(self, wav_data: bytes) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Convert WAV data to LiveKit audio frames"""

        async def frame_generator():
            # Store the WAV data for external access
            self._last_wav_data = wav_data

            # Create a simple audio frame that represents the WAV data
            # This is a placeholder - the actual WAV data is stored in _last_wav_data
            dummy_audio = np.zeros(1600, dtype=np.int16)  # 100ms at 16kHz

            frame = rtc.AudioFrame(
                data=dummy_audio,
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(dummy_audio),
            )

            yield frame

            # Small delay for natural streaming
            await asyncio.sleep(0.01)

        return frame_generator()

    def get_last_wav_data(self) -> bytes:
        """Get the last generated WAV data"""
        return getattr(self, "_last_wav_data", b"")

    def _create_silence_stream(self) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Create silence stream for error fallback"""

        async def silence_generator():
            # 1 second of silence
            samples = 16000  # 1 second at 16kHz
            silence = np.zeros(samples, dtype=np.int16)

            frame = rtc.AudioFrame(
                data=silence,
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(silence),
            )

            yield frame

        return silence_generator()


class CustomTTSService(tts.TTS):
    """
    Custom TTS Service - Replace this with your own model
    Implements LiveKit TTS interface for easy swapping
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        voice_config: Optional[dict] = None,
        sample_rate: int = 24000,
    ):
        """Initialize your custom TTS model here"""
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True  # Set to False if your model doesn't support streaming
            )
        )

        self.model_path = model_path
        self.voice_config = voice_config or {}
        self.sample_rate = sample_rate

        # TODO: Initialize your model here
        # self.model = load_your_model(model_path)

        logger.info(f"🎙️ Custom TTS initialized (sample_rate: {sample_rate}Hz)")

    async def synthesize(self, text: str) -> "tts.ChunkedStream":
        """
        Main synthesis method - implement your TTS model here
        """
        logger.info(f"🎤 Custom TTS synthesis: '{text[:50]}...'")

        try:
            # TODO: Replace this with your actual TTS model inference
            audio_data = await self._generate_audio_with_your_model(text)

            # Convert to LiveKit audio frames
            return tts.ChunkedStream(self._convert_to_audio_frames(audio_data))

        except Exception as e:
            logger.error(f"❌ Custom TTS synthesis failed: {e}")
            # Return silence as fallback
            return tts.ChunkedStream(self._create_silence_stream())

    async def _generate_audio_with_your_model(self, text: str) -> np.ndarray:
        """
        🔧 REPLACE THIS: Your actual TTS model inference
        """
        # TODO: Replace with your model's inference code
        # Examples of what you might do here:

        # Option 1: Local model (e.g., Coqui TTS, Tortoise, etc.)
        # audio = your_model.tts(text)

        # Option 2: API call to your hosted model
        # audio = await your_api_client.synthesize(text)

        # Option 3: External service
        # audio = await external_service.generate(text)

        # For demo purposes, creating a simple tone
        # REMOVE THIS and replace with your model
        duration = len(text) * 0.1  # Rough duration estimate
        samples = int(self.sample_rate * duration)

        # Generate simple sine wave as placeholder
        t = np.linspace(0, duration, samples)
        frequency = 440  # A4 note
        audio_data = (np.sin(2 * np.pi * frequency * t) * 0.3).astype(np.float32)

        logger.info(f"🎵 Generated {duration:.1f}s of audio ({samples} samples)")
        return audio_data

    def _convert_to_audio_frames(
        self, audio_data: np.ndarray
    ) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Convert your audio data to LiveKit audio frames"""

        async def frame_generator():
            # Convert to int16 format
            if audio_data.dtype != np.int16:
                # Normalize to int16 range
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data

            # Split into chunks for streaming
            chunk_size = self.sample_rate // 10  # 100ms chunks

            for i in range(0, len(audio_int16), chunk_size):
                chunk = audio_int16[i : i + chunk_size]

                # Create LiveKit AudioFrame
                frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=self.sample_rate,
                    num_channels=1,
                    samples_per_channel=len(chunk),
                )

                yield frame

                # Small delay for natural streaming
                await asyncio.sleep(0.01)

        return frame_generator()

    def _create_silence_stream(self) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Create silence stream for error fallback"""

        async def silence_generator():
            # 1 second of silence
            samples = self.sample_rate
            silence = np.zeros(samples, dtype=np.int16)

            frame = rtc.AudioFrame(
                data=silence,
                sample_rate=self.sample_rate,
                num_channels=1,
                samples_per_channel=len(silence),
            )

            yield frame

        return silence_generator()


# Character-specific configurations
CHARACTER_VOICE_CONFIGS = {
    "adina": {"voice_id": "compassionate_female", "speed": 1.0, "pitch": 1.1, "warmth": 0.8},
    "raffa": {"voice_id": "wise_male", "speed": 0.95, "pitch": 0.9, "authority": 0.7},
}


def create_custom_tts(character: str = "default") -> CustomTTSService:
    """Factory function to create character-specific TTS"""
    voice_config = CHARACTER_VOICE_CONFIGS.get(character, {})

    return CustomTTSService(
        model_path="path/to/your/model", voice_config=voice_config  # TODO: Set your model path
    )


def create_wav_tts(character: str = "default") -> WAVTTSService:
    """Factory function to create WAV TTS service"""
    return WAVTTSService(character)


def create_kokoro_tts(character: str = "default"):
    """Factory function to create WAV TTS service"""
    voice_mapping = {
        "adina": "af_heart",
        "rafa": "am_fenrir",
    }
    return KokoroTTS(voice_mapping[character])
