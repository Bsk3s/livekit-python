from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
from google.generativeai import types
import asyncio
import logging
from typing import AsyncGenerator
import numpy as np
from livekit import rtc
import os

logger = logging.getLogger(__name__)

class GeminiTTSService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable required")
        self.client = genai.Client(api_key=api_key)
        self.voice_configs = {
            "adina": {
                "voice_name": "Autonoe",
                "style_prompt": "Speak with warmth, compassion, and gentle wisdom. Use a nurturing tone that feels like a caring spiritual mentor."
            },
            "raffa": {
                "voice_name": "Alnilam",
                "style_prompt": "Speak with gentle authority and paternal wisdom. Use a warm but strong tone that conveys spiritual guidance and strength."
            }
        }
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        voice_config = self.voice_configs.get(character, self.voice_configs["adina"])
        styled_text = f"{voice_config['style_prompt']}: {text}"
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-tts",
                contents=styled_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_config["voice_name"]
                            )
                        )
                    )
                )
            )
            for chunk in response:
                if hasattr(chunk, 'data') and chunk.data:
                    audio_frame = self._bytes_to_audio_frame(chunk.data)
                    yield audio_frame
        except Exception as e:
            logger.error(f"Gemini TTS streaming error: {e}")
            raise
    def _bytes_to_audio_frame(self, audio_bytes: bytes) -> rtc.AudioFrame:
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        frame = rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=len(audio_data)
        )
        return frame

# Test function for manual verification
async def test_gemini_tts():
    tts = GeminiTTSService()
    test_text = "Hello, I am Adina, your spiritual guide. How can I help you today?"
    print("Testing Gemini TTS streaming...")
    chunk_count = 0
    try:
        async for audio_frame in tts.synthesize_streaming(test_text, "adina"):
            chunk_count += 1
            print(f"Received audio frame {chunk_count}: {audio_frame.samples_per_channel} samples")
            if chunk_count >= 5:
                break
        print(f"✅ Successfully received {chunk_count} audio frames")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini_tts()) 