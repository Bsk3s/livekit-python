from abc import abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

from ...services.base_service import BaseService


class BaseTTSService(BaseService):
    """Base class for Text-to-Speech services."""

    @abstractmethod
    async def synthesize(
        self, text: str, voice_id: Optional[str] = None, speed: float = 1.0
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Optional voice identifier
            speed: Speech rate multiplier

        Yields:
            Audio chunks
        """
        pass

    @abstractmethod
    async def synthesize_to_file(
        self, text: str, output_path: str, voice_id: Optional[str] = None, speed: float = 1.0
    ) -> str:
        """Synthesize text to speech and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice_id: Optional voice identifier
            speed: Speech rate multiplier

        Returns:
            Path to generated audio file
        """
        pass

    @property
    def service_name(self) -> str:
        return "TTS"
