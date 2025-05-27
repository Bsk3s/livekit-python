from typing import AsyncGenerator, Optional
from ...services.base_service import BaseService

class BaseSTTService(BaseService):
    """Base class for Speech-to-Text services."""
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """Transcribe an audio stream to text.
        
        Args:
            audio_stream: Async generator yielding audio chunks
            
        Yields:
            Transcribed text segments
        """
        pass
    
    @abstractmethod
    async def transcribe_file(self, audio_file_path: str) -> str:
        """Transcribe an audio file to text.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Complete transcription
        """
        pass
    
    @property
    def service_name(self) -> str:
        return "STT" 