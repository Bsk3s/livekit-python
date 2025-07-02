from livekit.agents import tts
from .gemini_tts_service import GeminiTTSService
import logging

logger = logging.getLogger(__name__)

class LiveKitGeminiTTSAdapter(tts.TTS):
    """LiveKit adapter for Gemini TTS"""
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True)
        )
        self.gemini_tts = GeminiTTSService()
        self._character = "adina"  # default
    def set_character(self, character: str):
        self._character = character
    def synthesize(self, text: str) -> tts.SynthesizeStream:
        return GeminiSynthesizeStream(
            text=text,
            character=self._character,
            gemini_tts=self.gemini_tts
        )

class GeminiSynthesizeStream(tts.SynthesizeStream):
    """Streaming implementation for Gemini TTS"""
    def __init__(self, text: str, character: str, gemini_tts: GeminiTTSService):
        super().__init__()
        self.text = text
        self.character = character
        self.gemini_tts = gemini_tts
        self._stream = None
    async def __aenter__(self):
        self._stream = self.gemini_tts.synthesize_streaming(self.text, self.character)
        return self
    async def __anext__(self):
        if self._stream is None:
            raise StopAsyncIteration
        try:
            return await self._stream.__anext__()
        except StopAsyncIteration:
            raise 