import io
import logging
import os

logger = logging.getLogger(__name__)
from uuid import uuid4

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
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
        self.speed = 1.12

    async def asynthesize(self, text: str) -> bytes:
        try:
            logger.info(f"🎵 Generating welcome WAV: with Kokoro")
            samples, sample_rate = self.model(text)
            return self._array_to_bytes(samples, sample_rate)

        except Exception as e:
            print(f"Synthesis error: {e}")
            raise e

    def synthesize(self, text: str, *, conn_options=None) -> ChunkedStream:
        logger.info(f"🎵 Generating welcome WAV: with Kokoro")
        return KokoroChunkedStream(self, text, conn_options)

    def _generate_audio_sync(self, text: str) -> bytes:
        samples, sample_rate = self.model(text)
        return self._array_to_bytes(samples, sample_rate)

    def _array_to_bytes(self, audio_array: np.ndarray, sample_rate: int = 24000) -> bytes:
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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, "kokoro-v1.0.onnx")
        voices_path = os.path.join(base_dir, "voices-v1.0.bin")

        model = Kokoro(model_path, voices_path)

        def call_model(text):
            return model.create(text, self.voice, speed=self.speed, lang=self.lang)

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
                if i == 0:
                    audio_bytes = self._tts._tensor_to_bytes(audio)
                    output_emitter.push(audio_bytes)
                    break
            output_emitter.end_input()
            output_emitter.aclose()

        except Exception as e:
            print(f"Synthesis error: {e}")
            raise e
            raise e
