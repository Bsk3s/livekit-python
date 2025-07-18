import io
import logging

logger = logging.getLogger(__name__)


from uuid import uuid4

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline
from livekit.agents import tts
from livekit.agents.tts import ChunkedStream, TTSCapabilities


class KokoroTTS(tts.TTS):
    def __init__(self, voice="af_heart", **kwargs):
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
            **kwargs,
        )
        self.voice = voice
        self.model = self._load_custom_model()
        self.lang = "en-us"
        self.speed = 1.1

    async def asynthesize(self, text: str):
        try:
            generator = self.model(text)
            for i, (gs, ps, audio) in enumerate(generator):
                if i == 0:
                    yield self._tensor_to_bytes(audio)

        except Exception as e:
            print(f"Error synthesizing speech: {e}")
            raise e

    def synthesize(self, text: str, *, conn_options=None) -> ChunkedStream:
        logger.info(f"🎵 Generating welcome WAV: with Kokoro")
        return KokoroChunkedStream(self, text, conn_options)

    def _generate_audio_sync(self, text: str) -> bytes:
        samples, sample_rate = self.model(text)
        return self._tensor_to_bytes(samples, sample_rate)

    def _tensor_to_ndarray(
        self, audio_tensor: torch.Tensor, sample_rate: int = 24000
    ) -> np.ndarray:
        # Move to CPU and convert to numpy
        audio_array = audio_tensor.cpu().detach().numpy().astype(np.float32)

        # Squeeze to remove extra dimensions
        audio_array = audio_array.squeeze()

        # Normalize to [-1, 1] range if needed
        max_val = np.max(np.abs(audio_array))
        if max_val > 1.0:
            audio_array = audio_array / max_val

        # Convert to WAV bytes
        buffer = io.BytesIO()
        sf.write(buffer, audio_array, sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer.read()

    def _load_custom_model(self):
        self.base_model = KPipeline(lang_code="a")

        def call_model(text):
            return self.base_model(text, self.voice, speed=self.speed)

        return call_model


class KokoroChunkedStream(ChunkedStream):
    def __init__(self, tts_instance, text, conn_options=None):
        super().__init__(tts=tts_instance, input_text=text, conn_options=conn_options)

    async def _run(self, output_emitter=None):
        try:
            output_emitter.initialize(
                request_id=str(uuid4), sample_rate=24000, num_channels=1, mime_type=""
            )
            generator = self._tts.model(self._input_text, voice=self._tts.voice)
            for i, (gs, ps, audio) in enumerate(generator):
                audio_bytes = self._tts._tensor_to_bytes(audio)
                output_emitter.push(audio_bytes)
            output_emitter.end_input()
            output_emitter.aclose()

        except Exception as e:
            print(f"Synthesis error: {e}")
            raise e
