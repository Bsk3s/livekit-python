import asyncio
import aiohttp
import json
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
        "adina": {
            "model": "aura-2-luna-en",  # Gentle, soothing female - more conversational
        },
        "raffa": {
            "model": "aura-2-orion-en",  # Warm, approachable male - friendly mentor
        }
    }
    
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        self.base_url = "https://api.deepgram.com/v1/speak"
        self._session = None
        logger.info("Deepgram TTS Direct service initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Generate streaming TTS audio using Deepgram REST API"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
        
        config = self.VOICE_CONFIGS[character]
        session = await self._get_session()
        
        start_time = asyncio.get_event_loop().time()
        first_chunk_yielded = False
        chunk_count = 0
        
        logger.info(f"Starting Deepgram TTS synthesis for {character}: '{text[:50]}...'")
        
        # Prepare request
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        params = {
            "model": config["model"],
            "encoding": "linear16",
            "sample_rate": 24000,
            "container": "none"  # Raw audio stream
        }
        
        payload = {"text": text}
        
        try:
            url = f"{self.base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Deepgram API error {response.status}: {error_text}")
                
                # Stream the audio response
                chunk_size = 4096  # 4KB chunks for streaming
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    if chunk:
                        chunk_count += 1
                        
                        # Log first chunk latency
                        if not first_chunk_yielded:
                            first_chunk_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                            logger.info(f"🚀 FIRST CHUNK latency for {character}: {first_chunk_latency:.0f}ms")
                            first_chunk_yielded = True
                        
                        # Convert to AudioFrame
                        audio_frame = self._create_audio_frame(chunk)
                        yield audio_frame
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(f"✅ Deepgram TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total")
            
        except Exception as e:
            logger.error(f"Deepgram TTS error for {character}: {e}")
            raise
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert audio bytes to LiveKit AudioFrame"""
        # Convert bytes to 16-bit signed integers
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,  # Deepgram standard rate
            num_channels=1,     # Mono audio
            samples_per_channel=len(audio_data)
        )
    
    async def cleanup(self):
        """Clean up HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Closed HTTP session")

# Performance test for Direct Deepgram TTS
async def test_deepgram_direct_performance():
    """Test Direct Deepgram TTS performance"""
    print("🚀 Testing DIRECT Deepgram TTS Performance")
    service = DeepgramTTSDirect()
    
    test_cases = [
        ("short", "Hello, I'm here to guide you."),
        ("medium", "Welcome to our spiritual guidance session. I'm here to provide you with compassionate support."),
        ("long", "In this moment of connection, I want you to know that you are not alone on your spiritual journey. Together we can explore the depths of your soul and find the peace you seek.")
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
                    if chunk_count >= 5:  # Test first few chunks
                        break
                
                total_time = (asyncio.get_event_loop().time() - start) * 1000
                
                # Target: <1500ms first chunk
                status = "🎯 TARGET MET!" if first_chunk_time and first_chunk_time < 1500 else "❌ Too slow"
                
                result = {
                    "test": test_name,
                    "character": character,
                    "first_chunk_ms": first_chunk_time,
                    "total_ms": total_time,
                    "chunks": chunk_count,
                    "status": status
                }
                results.append(result)
                print(f"{character}: {status} - First: {first_chunk_time:.0f}ms, Total: {total_time:.0f}ms")
                
            except Exception as e:
                print(f"{character}: ❌ ERROR - {e}")
                results.append({
                    "test": test_name,
                    "character": character,
                    "error": str(e),
                    "status": "❌ ERROR"
                })
    
    # Cleanup
    await service.cleanup()
    
    # Summary
    passed = sum(1 for r in results if "TARGET MET" in r.get("status", ""))
    total_tests = len([r for r in results if "error" not in r])
    
    print(f"\n🎯 DEEPGRAM DIRECT PERFORMANCE: {passed}/{total_tests} tests under 1.5s")
    
    if passed >= total_tests * 0.8:  # 80% pass rate
        print("🚀 DEEPGRAM DIRECT MEETS LATENCY REQUIREMENTS!")
        print("💡 Ready for production with true streaming TTS")
        print("💰 Cost: ~$0.0048/minute vs OpenAI's ~$15/1M chars")
        return True
    else:
        print("💀 Still investigating latency issues...")
        return False

if __name__ == "__main__":
    asyncio.run(test_deepgram_direct_performance()) 