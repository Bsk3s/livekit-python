from dotenv import load_dotenv
load_dotenv()
import aiohttp
import asyncio
import json
import base64
import os
from typing import AsyncGenerator, Optional
import numpy as np
from livekit import rtc
import logging

logger = logging.getLogger(__name__)

class StreamingGeminiTTSService:
    MODELS = {
        "flash": "gemini-2.5-flash-preview-tts",
        "pro": "gemini-2.5-pro-preview-tts"
    }
    VOICE_CONFIGS = {
        "adina": {
            "voice_name": "Autonoe",
            "style_prompt": "Speak with warmth and compassion as a spiritual guide"
        },
        "raffa": {
            "voice_name": "Alnilam",
            "style_prompt": "Speak with gentle authority as a spiritual mentor"
        }
    }
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable required")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=2)
    async def synthesize_streaming(self, text: str, character: str, model_type: str = "flash") -> AsyncGenerator[rtc.AudioFrame, None]:
        if model_type not in self.MODELS:
            raise ValueError(f"Invalid model_type: {model_type}. Must be: {list(self.MODELS.keys())}")
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be: {list(self.VOICE_CONFIGS.keys())}")
        model_name = self.MODELS[model_type]
        voice_config = self.VOICE_CONFIGS[character]
        styled_text = f"{voice_config['style_prompt']}: {text}"
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
        url = f"{self.base_url}/models/{model_name}:streamGenerateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }
        logger.info(f"Initiating streaming TTS: model={model_name}, character={character}")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    await self._validate_streaming_response(response)
                    chunk_count = 0
                    start_time = asyncio.get_event_loop().time()
                    async for line in response.content:
                        audio_frame = await self._process_chunk(line)
                        if audio_frame:
                            chunk_count += 1
                            if chunk_count == 1:
                                first_chunk_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                                logger.info(f"First audio chunk received: {first_chunk_latency:.0f}ms")
                            yield audio_frame
                    if chunk_count == 0:
                        raise Exception("No audio chunks received from streaming response")
                    total_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    logger.info(f"Streaming completed: {chunk_count} chunks, {total_latency:.0f}ms total")
        except asyncio.TimeoutError as e:
            logger.error(f"Streaming timeout: {e}")
            raise Exception("TTS streaming timeout - API response too slow for real-time requirements")
        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            raise
    async def _validate_streaming_response(self, response: aiohttp.ClientResponse) -> None:
        if response.status != 200:
            error_text = await response.text()
            logger.error(f"API error {response.status}: {error_text}")
            raise Exception(f"TTS API failed: HTTP {response.status}")
        content_type = response.headers.get('content-type', '')
        if 'stream' not in content_type.lower() and 'event-stream' not in content_type.lower():
            logger.error(f"Non-streaming response type: {content_type}")
            raise Exception(f"Streaming required but got: {content_type}")
        logger.debug(f"Validated streaming response: {content_type}")
    async def _process_chunk(self, chunk: bytes) -> Optional[rtc.AudioFrame]:
        try:
            chunk_str = chunk.decode('utf-8', errors='ignore').strip()
            if not chunk_str:
                return None
            if chunk_str.startswith('data: '):
                json_str = chunk_str[6:].strip()
                if json_str == '[DONE]':
                    return None
                return self._extract_audio_from_json(json_str)
            elif chunk_str.startswith('{'):
                return self._extract_audio_from_json(chunk_str)
            return None
        except Exception as e:
            logger.debug(f"Chunk processing error: {e}")
            return None
    def _extract_audio_from_json(self, json_str: str) -> Optional[rtc.AudioFrame]:
        try:
            data = json.loads(json_str)
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                inline_data = part.get("inline_data", {})
                if "data" in inline_data:
                    audio_b64 = inline_data["data"]
                    audio_bytes = base64.b64decode(audio_b64)
                    return self._create_audio_frame(audio_bytes)
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"JSON processing error: {e}")
            return None
    def _create_audio_frame(self, audio_bytes: bytes) -> rtc.AudioFrame:
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=len(audio_data)
        )

# Performance validation test
async def validate_streaming_performance():
    print("Validating streaming TTS performance...")
    service = StreamingGeminiTTSService()
    test_text = "This is a performance validation test for real-time spiritual guidance."
    test_cases = [
        ("flash", "adina"),
        ("flash", "raffa"),
        ("pro", "adina"),
        ("pro", "raffa")
    ]
    results = []
    for model_type, character in test_cases:
        print(f"\nTesting {model_type}/{character}...")
        try:
            start_time = asyncio.get_event_loop().time()
            first_chunk_time = None
            chunk_count = 0
            async for audio_frame in service.synthesize_streaming(test_text, character, model_type):
                chunk_count += 1
                if chunk_count == 1:
                    first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                if chunk_count >= 3:
                    break
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            if first_chunk_time and first_chunk_time < 1000:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
            result = {
                "model": model_type,
                "character": character,
                "first_chunk_ms": first_chunk_time,
                "total_ms": total_time,
                "chunks": chunk_count,
                "status": status
            }
            results.append(result)
            print(f"{status} - First chunk: {first_chunk_time:.0f}ms, Total: {total_time:.0f}ms")
        except Exception as e:
            print(f"❌ FAIL - {e}")
            results.append({
                "model": model_type,
                "character": character,
                "error": str(e),
                "status": "❌ FAIL"
            })
    passing = sum(1 for r in results if r["status"] == "✅ PASS")
    total = len(results)
    print(f"\nPerformance validation: {passing}/{total} passed")
    if passing == total:
        print("🚀 All configurations meet real-time requirements")
        return True
    else:
        print("💀 Performance requirements not met")
        return False

if __name__ == "__main__":
    asyncio.run(validate_streaming_performance()) 