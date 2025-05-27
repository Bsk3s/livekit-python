import asyncio
import aiohttp
from typing import AsyncGenerator
import logging
from livekit import rtc
import numpy as np
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)

class DeepgramTTSDirect:
    """Direct Deepgram TTS implementation using REST API"""
    
    VOICE_CONFIGS = {
        "adina": {"model": "aura-2-luna-en"},  # Gentle, soothing - conversational
        "raffa": {"model": "aura-2-orion-en"}  # Warm, approachable - friendly
    }
    
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        self.base_url = "https://api.deepgram.com/v1/speak"
        self._session = None
    
    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        if not text.strip():
            raise ValueError("Text cannot be empty")
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}")
        
        config = self.VOICE_CONFIGS[character]
        session = await self._get_session()
        start_time = asyncio.get_event_loop().time()
        first_chunk_yielded = False
        chunk_count = 0
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        params = {
            "model": config["model"],
            "encoding": "linear16",
            "sample_rate": 24000,
            "container": "none"
        }
        
        payload = {"text": text}
        
        try:
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Deepgram API error {response.status}: {error_text}")
                
                chunk_size = 4096
                async for chunk in response.content.iter_chunked(chunk_size):
                    if chunk:
                        chunk_count += 1
                        if not first_chunk_yielded:
                            first_chunk_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                            print(f"🚀 FIRST CHUNK latency for {character}: {first_chunk_latency:.0f}ms")
                            first_chunk_yielded = True
                        
                        audio_data = np.frombuffer(chunk, dtype=np.int16)
                        audio_frame = rtc.AudioFrame(
                            data=audio_data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=len(audio_data)
                        )
                        yield audio_frame
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            print(f"✅ Complete: {total_time:.0f}ms total for {character}")
            
        except Exception as e:
            print(f"❌ Error for {character}: {e}")
            raise
    
    async def cleanup(self):
        if self._session and not self._session.closed:
            await self._session.close()

async def test_deepgram_direct():
    print("🚀 Testing DIRECT Deepgram TTS Performance")
    service = DeepgramTTSDirect()
    
    test_cases = [
        ("short", "Hello, I'm here to guide you."),
        ("medium", "Welcome to our spiritual guidance session. I'm here to provide support."),
    ]
    
    results = []
    for test_name, test_text in test_cases:
        print(f"\n=== Testing {test_name} text ({len(test_text)} chars) ===")
        
        for character in ["adina", "raffa"]:
            try:
                start = asyncio.get_event_loop().time()
                first_chunk_time = None
                chunk_count = 0
                
                async for audio_frame in service.synthesize_streaming(test_text, character):
                    chunk_count += 1
                    if chunk_count == 1:
                        first_chunk_time = (asyncio.get_event_loop().time() - start) * 1000
                    if chunk_count >= 3:
                        break
                
                total_time = (asyncio.get_event_loop().time() - start) * 1000
                status = "🎯 TARGET MET!" if first_chunk_time and first_chunk_time < 1500 else "❌ Too slow"
                
                results.append({
                    "test": test_name,
                    "character": character,
                    "first_chunk_ms": first_chunk_time,
                    "status": status
                })
                print(f"{character}: {status} - First: {first_chunk_time:.0f}ms")
                
            except Exception as e:
                print(f"{character}: ❌ ERROR - {e}")
                results.append({"test": test_name, "character": character, "status": "❌ ERROR"})
    
    await service.cleanup()
    
    passed = sum(1 for r in results if "TARGET MET" in r.get("status", ""))
    total_tests = len([r for r in results if "error" not in r.get("status", "")])
    
    print(f"\n🎯 DEEPGRAM DIRECT PERFORMANCE: {passed}/{total_tests} tests under 1.5s")
    
    if passed >= total_tests * 0.8:
        print("🚀 DEEPGRAM DIRECT MEETS LATENCY REQUIREMENTS!")
        print("💡 Ready for production with true streaming TTS")
        return True
    else:
        print("💀 Still investigating latency issues...")
        return False

if __name__ == "__main__":
    asyncio.run(test_deepgram_direct()) 