import os
import aiohttp
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from ..base import BaseSTTService

logger = logging.getLogger(__name__)


class DeepgramSTTService(BaseSTTService):
    """Real Deepgram implementation using HTTP API for reliable transcription."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._api_key = None
        self._initialized = False
        self._base_url = "https://api.deepgram.com/v1"
        self._session_timeout = 30.0

    def _validate_config(self) -> None:
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set or empty")
        self._api_key = api_key
        logger.info(f"🔑 Deepgram API key validated: {self._api_key[:8]}...")

    async def initialize(self) -> None:
        if not self._initialized:
            try:
                self._validate_config()
                # Test connection with a minimal request
                await self._test_connection()
                self._initialized = True
                logger.info("✅ DeepgramSTTService initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize DeepgramSTTService: {e}")
                raise

    async def _test_connection(self) -> None:
        """Test the Deepgram connection with a minimal request"""
        try:
            # Create minimal silent audio sample for testing
            silence_samples = int(16000 * 0.1)  # 0.1 second at 16kHz
            silence_bytes = b"\x00\x00" * silence_samples  # 16-bit silence
            wav_data = self._create_wav_file(silence_bytes, 16000, 1, 16)
            
            # Test with Deepgram API
            result = await self._transcribe_with_api(wav_data)
            logger.info("🔗 Deepgram connection test successful")
        except Exception as e:
            logger.warning(f"⚠️ Connection test failed (may be normal): {e}")

    def _create_wav_file(self, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
        """Create a WAV file from PCM data"""
        import struct
        
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        data_size = len(pcm_data)
        file_size = 36 + data_size

        wav_header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", file_size, b"WAVE", b"fmt ", 16, 1, channels,
            sample_rate, byte_rate, block_align, bits_per_sample,
            b"data", data_size,
        )
        return wav_header + pcm_data

    async def shutdown(self) -> None:
        self._api_key = None
        self._initialized = False
        logger.info("🧹 DeepgramSTTService shut down")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

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

                except Exception as api_error:
                    logger.error(f"❌ HTTP API error: {api_error}")
                    return None

        except Exception as e:
            logger.error(f"❌ Failed to call Deepgram API: {e}")
            return None

    def _extract_transcript_from_json(self, response_data: dict) -> Optional[str]:
        """Extract transcript from Deepgram JSON response"""
        try:
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

    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        """Stream transcription - for now accumulate and transcribe as batch"""
        if not self._initialized:
            await self.initialize()

        # Accumulate audio chunks
        audio_chunks = []
        async for chunk in audio_stream:
            audio_chunks.append(chunk)
        
        # Combine chunks and transcribe
        if audio_chunks:
            combined_audio = b"".join(audio_chunks)
            # Ensure WAV format
            if not combined_audio.startswith(b"RIFF"):
                combined_audio = self._create_wav_file(combined_audio, 16000, 1, 16)
            
            result = await self._transcribe_with_api(combined_audio)
            if result:
                yield result

    async def transcribe_file(self, audio_file_path: str) -> str:
        """Transcribe an audio file"""
        if not self._initialized:
            await self.initialize()

        try:
            with open(audio_file_path, "rb") as audio_file:
                audio_data = audio_file.read()
                result = await self._transcribe_with_api(audio_data)
                return result or ""
        except Exception as e:
            logger.error(f"❌ File transcription error: {e}")
            return ""

    async def transcribe_audio_bytes(self, audio_data: bytes) -> Optional[str]:
        """Transcribe raw audio bytes using real Deepgram API"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"🎤 STT DEBUG: Processing {len(audio_data)} bytes of audio")
            
            # Ensure we have proper WAV format
            if not audio_data.startswith(b"RIFF"):
                logger.info("🔧 Converting PCM to WAV format")
                # Assume 16kHz, 16-bit, mono PCM
                audio_data = self._create_wav_file(audio_data, 16000, 1, 16)
                logger.info(f"🔧 Converted to WAV: {len(audio_data)} bytes")

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
            return None
