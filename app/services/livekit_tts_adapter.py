from livekit.agents import tts
from .openai_tts_service import OpenAITTSService
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LiveKitOpenAIAdapter(tts.TTS):
    """LiveKit adapter for OpenAI TTS"""
    
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True)
        )
        self.openai_tts = OpenAITTSService()
        self._character = "adina"  # Default character
        logger.info("Initialized LiveKit OpenAI TTS adapter")
    
    def set_character(self, character: str):
        """Set which spiritual guide is speaking"""
        if character not in ["adina", "raffa"]:
            raise ValueError(f"Invalid character: {character}. Must be 'adina' or 'raffa'")
        
        self._character = character
        logger.info(f"TTS character set to: {character}")
    
    def synthesize(self, text: str) -> "OpenAISynthesizeStream":
        """Create synthesis stream for LiveKit"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        logger.info(f"Starting synthesis for {self._character}")
        return OpenAISynthesizeStream(
            text=text,
            character=self._character,
            openai_tts=self.openai_tts
        )

class OpenAISynthesizeStream(tts.SynthesizeStream):
    """Streaming synthesis implementation"""
    
    def __init__(self, text: str, character: str, openai_tts: OpenAITTSService):
        super().__init__()
        self.text = text
        self.character = character
        self.openai_tts = openai_tts
        self._stream: Optional[AsyncGenerator] = None
        self._started = False
        logger.debug(f"Initialized synthesis stream for {character}")
    
    async def __aenter__(self):
        """Start the synthesis stream"""
        if self._started:
            raise RuntimeError("Stream already started")
            
        logger.info(f"Starting TTS synthesis: {self.character} speaking")
        self._stream = self.openai_tts.synthesize_streaming(self.text, self.character)
        self._started = True
        return self
    
    async def __anext__(self):
        """Get next audio frame"""
        if not self._started:
            raise RuntimeError("Stream not started. Use 'async with' context manager")
            
        if self._stream is None:
            raise StopAsyncIteration
        
        try:
            audio_frame = await self._stream.__anext__()
            return audio_frame
        except StopAsyncIteration:
            logger.info(f"TTS synthesis complete for {self.character}")
            raise
        except Exception as e:
            logger.error(f"Error in synthesis stream: {e}")
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up stream resources"""
        self._stream = None
        self._started = False
        if exc_type is not None:
            logger.error(f"Stream exited with error: {exc_val}")
        else:
            logger.debug("Stream closed successfully") 