from livekit.agents import tts
from .gemini_tts_service import StreamingGeminiTTS
import logging

logger = logging.getLogger(__name__)

class LiveKitGeminiTTSAdapter(tts.TTS):
    """Adapter to integrate streaming Gemini TTS with LiveKit"""
    def __init__(self, api_key: str):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True)
        )
        self.gemini_tts = StreamingGeminiTTS(api_key)
        self._voice_config = None
    def set_voice_config(self, voice_config: dict):
        self._voice_config = voice_config
    def synthesize(self, text: str) -> tts.SynthesizeStream:
        return GeminiSynthesizeStream(
            text=text,
            gemini_tts=self.gemini_tts,
            voice_config=self._voice_config
        )

class GeminiSynthesizeStream(tts.SynthesizeStream):
    """Streaming implementation for Gemini TTS"""
    def __init__(self, text: str, gemini_tts: StreamingGeminiTTS, voice_config: dict):
        super().__init__()
        self.text = text
        self.gemini_tts = gemini_tts
        self.voice_config = voice_config
        self._stream = None
        self._stream_iter = None
    def __aiter__(self):
        self._stream = self.gemini_tts.synthesize_streaming(
            self.text, self.voice_config
        )
        self._stream_iter = self._stream.__aiter__()
        return self
    async def __anext__(self):
        return await self._stream_iter.__anext__() 