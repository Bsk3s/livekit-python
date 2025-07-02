from dotenv import load_dotenv
load_dotenv()
import aiohttp
import asyncio
import json
import base64
import os
from typing import AsyncGenerator
import numpy as np
from livekit import rtc
import logging

logger = logging.getLogger(__name__)

class GeminiStreamingTTSService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable required")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.voice_configs = {
            "adina": {
                "voice_name": "Autonoe",
                "style": "Speak with warmth and compassion"
            },
            "raffa": {
                "voice_name": "Alnilam",
                "style": "Speak with gentle authority"
            }
        }
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        voice_config = self.voice_configs.get(character, self.voice_configs["adina"])
        styled_text = f"{voice_config['style']}: {text}"
        payload = {
            "contents": [{
                "parts": [{"text": styled_text}]
            }],
            "generationConfig": {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": voice_config["voice_name"]
                        }
                    }
                }
            }
        }
        url = f"{self.base_url}/models/gemini-2.5-flash-tts:streamGenerateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
            "Accept": "text/event-stream"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Streaming TTS failed: {response.status} - {error_text}")
                        raise Exception(f"STREAMING MANDATORY - API failed: {response.status}")
                    content_type = response.headers.get('content-type', '')
                    if 'stream' not in content_type.lower():
                        raise Exception("STREAMING MANDATORY - Got non-streaming response")
                    logger.info("✅ Confirmed streaming TTS response")
                    first_chunk_received = False
                    chunk_count = 0
                    async for line in response.content:
                        if line:
                            audio_frame = await self._process_streaming_line(line)
                            if audio_frame:
                                chunk_count += 1
                                if not first_chunk_received:
                                    logger.info(f"🎵 First audio chunk received! Latency optimized.")
                                    first_chunk_received = True
                                yield audio_frame
                    if chunk_count == 0:
                        raise Exception("STREAMING MANDATORY - No audio chunks received")
                    logger.info(f"✅ Streaming complete: {chunk_count} audio chunks")
        except Exception as e:
            logger.error(f"Streaming TTS failed: {e}")
            raise Exception(f"STREAMING TTS FAILED: {e}")
    async def _process_streaming_line(self, line: bytes) -> rtc.AudioFrame:
        try:
            line_str = line.decode('utf-8').strip()
            if not line_str or not line_str.startswith('data:'):
                return None
            json_str = line_str[5:].strip()
            if json_str == '[DONE]':
                return None
            data = json.loads(json_str)
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inline_data" in part and "data" in part["inline_data"]:
                            audio_b64 = part["inline_data"]["data"]
                            audio_bytes = base64.b64decode(audio_b64)
                            return self._bytes_to_audio_frame(audio_bytes)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            logger.debug(f"Chunk parsing error (expected during streaming): {e}")
            return None
    def _bytes_to_audio_frame(self, audio_bytes: bytes) -> rtc.AudioFrame:
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=len(audio_data)
        )

# MANDATORY streaming test
async def test_streaming_only():
    print("🧪 Testing MANDATORY streaming TTS...")
    try:
        service = GeminiStreamingTTSService()
        test_text = "Hello, this is a streaming test for spiritual guidance."
        print(f"📝 Text: '{test_text}'")
        print(f"🎤 Voice: Autonoe (streaming required)")
        first_chunk_time = None
        chunk_count = 0
        start_time = asyncio.get_event_loop().time()
        async for audio_frame in service.synthesize_streaming(test_text, "adina"):
            chunk_count += 1
            if chunk_count == 1:
                first_chunk_time = asyncio.get_event_loop().time() - start_time
                print(f"⚡ FIRST CHUNK: {first_chunk_time*1000:.0f}ms (streaming confirmed!)")
            print(f"🎵 Chunk {chunk_count}: {audio_frame.samples_per_channel} samples")
            if chunk_count >= 3:
                break
        if chunk_count > 0 and first_chunk_time:
            print(f"✅ STREAMING SUCCESS!")
            print(f"   • First chunk: {first_chunk_time*1000:.0f}ms")
            print(f"   • Total chunks: {chunk_count}")
            print(f"   • Streaming confirmed: TRUE")
            return True
        else:
            print("❌ STREAMING FAILED - No chunks received")
            return False
    except Exception as e:
        print(f"❌ STREAMING FAILED: {e}")
        return False

async def list_gemini_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY environment variable required")
        return
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": api_key}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to list models: {response.status}")
                print(await response.text())
                return
            data = await response.json()
            print("\nAvailable Gemini Models:")
            for model in data.get("models", []):
                print(f"- {model.get('name')}")
                if 'supportedGenerationMethods' in model:
                    print(f"  Supported methods: {model['supportedGenerationMethods']}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list-models":
        asyncio.run(list_gemini_models())
    else:
        success = asyncio.run(test_streaming_only())
        if not success:
            print("\n💀 STREAMING IS MANDATORY - Cannot proceed without streaming TTS")
            exit(1)
        else:
            print("\n🚀 Ready for production streaming TTS!") 