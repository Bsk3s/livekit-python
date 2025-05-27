from dotenv import load_dotenv
load_dotenv()
import os
import pytest
from app.services.gemini_tts_service import StreamingGeminiTTS
from app.characters.adina.voice_config import AdinaVoiceConfig

@pytest.mark.asyncio
async def test_gemini_tts_streaming_real():
    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY must be set in the environment."
    tts = StreamingGeminiTTS(api_key)
    text = "Hello, this is Adina. I am here to guide you with warmth and wisdom."
    voice_config = AdinaVoiceConfig.CONFIG
    print("\nStreaming Gemini TTS audio frames:")
    frame_count = 0
    async for frame in tts.synthesize_streaming(text, voice_config):
        print(f"Received audio frame: sample_rate={frame.sample_rate}, samples={frame.samples_per_channel}")
        frame_count += 1
        if frame_count >= 3:
            break  # Limit for test/demo
    assert frame_count > 0, "No audio frames received from Gemini TTS." 