import os
from typing import Any, AsyncGenerator, Dict

from livekit.plugins import deepgram

from ..base import BaseSTTService


class DeepgramSTTService(BaseSTTService):
    """Deepgram implementation of the STT service."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._client = None
        self._initialized = False

    def _validate_config(self) -> None:
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set or empty")

    async def initialize(self) -> None:
        if not self._initialized:
            self._client = deepgram.STT(
                model=self.config.get("model", "nova-3"),
                language=self.config.get("language", "multi"),
                interim_results=self.config.get("interim_results", True),
                punctuate=self.config.get("punctuate", True),
                smart_format=self.config.get("smart_format", True),
                no_delay=self.config.get("no_delay", True),
                endpointing_ms=self.config.get("endpointing_ms", 25),
                filler_words=self.config.get("filler_words", True),
                sample_rate=self.config.get("sample_rate", 16000),
                profanity_filter=self.config.get("profanity_filter", False),
                numerals=self.config.get("numerals", False),
            )
            self._initialized = True

    async def shutdown(self) -> None:
        if self._client:
            # Add any necessary cleanup
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        if not self._initialized:
            await self.initialize()

        async for chunk in audio_stream:
            # Implement streaming transcription logic
            # This is a placeholder - actual implementation will depend on Deepgram's API
            yield "Transcribed text"  # Replace with actual transcription

    async def transcribe_file(self, audio_file_path: str) -> str:
        if not self._initialized:
            await self.initialize()

        # Implement file transcription logic
        # This is a placeholder - actual implementation will depend on Deepgram's API
        return "Complete transcription"  # Replace with actual transcription
