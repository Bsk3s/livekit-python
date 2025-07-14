# Add future import for Python typing compatibility
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import aiohttp

from spiritual_voice_agent.services.stt.base import BaseSTTService

logger = logging.getLogger(__name__)


class DirectDeepgramSTTService(BaseSTTService):
    """Direct Deepgram implementation using HTTP API to avoid SDK typing issues."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._api_key = None
        self._initialized = False
        self._session_timeout = 30.0  # 30 second timeout for API calls
        self._base_url = "https://api.deepgram.com/v1"

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
        """Create a proper WAV file from PCM data"""
        import struct

        # Calculate values
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8

        # WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + len(pcm_data),  # ChunkSize
            b"WAVE",
            b"fmt ",
            16,  # Subchunk1Size
            1,  # AudioFormat (PCM)
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            len(pcm_data),
        )

        return header + pcm_data

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

            # Navigate JSON response structure
            if "results" not in response_data:
                logger.debug("⚠️ No 'results' in response")
                return None

            results = response_data["results"]
            logger.debug(f"🔍 Results structure: {results}")

            if "channels" not in results or not results["channels"]:
                logger.debug("⚠️ No 'channels' in results")
                return None

            channel = results["channels"][0]
            logger.debug(f"🔍 Channel structure: {channel}")

            if "alternatives" not in channel or not channel["alternatives"]:
                logger.debug("⚠️ No 'alternatives' in channel")
                return None

            alternative = channel["alternatives"][0]
            logger.debug(f"🔍 Alternative structure: {alternative}")

            if "transcript" not in alternative:
                logger.debug("⚠️ No 'transcript' in alternative")
                return None

            transcript = alternative["transcript"]
            logger.debug(f"🔍 Raw transcript: {repr(transcript)}")

            if transcript and isinstance(transcript, str):
                transcript = transcript.strip()
                if len(transcript) > 0:
                    logger.debug(f"📝 Extracted transcript: '{transcript}'")
                    return transcript

            logger.debug("🔇 Empty or invalid transcript")
            return None

        except Exception as e:
            logger.error(f"❌ Error extracting transcript from JSON: {e}")
            logger.error(f"❌ Response data type: {type(response_data)}")
            logger.error(f"❌ Response data: {response_data}")
            return None

    async def shutdown(self) -> None:
        """Clean up resources"""
        self._api_key = None
        self._initialized = False
        logger.info("🧹 DirectDeepgramSTTService shut down")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def transcribe_audio_bytes(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe raw audio bytes using Deepgram HTTP API

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


# Test function for validation
async def test_direct_deepgram():
    """Test the DirectDeepgramSTTService"""
    logger.info("🧪 Testing DirectDeepgramSTTService...")

    service = DirectDeepgramSTTService(
        {
            "model": "nova-2",
            "language": "en-US",
            "punctuate": True,
        }
    )

    try:
        await service.initialize()
        logger.info("✅ Service initialization successful")

        # Test with minimal audio data
        test_audio = b"\x00\x00" * 8000  # 0.5 seconds of silence
        result = await service.transcribe_audio_bytes(test_audio)

        if result is None:
            logger.info("✅ Correctly returned None for silence")
        else:
            logger.info(f"📝 Transcription result: '{result}'")

        await service.shutdown()
        logger.info("✅ Service shutdown successful")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_direct_deepgram())
