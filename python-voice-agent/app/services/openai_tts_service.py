import openai
import asyncio
from typing import AsyncGenerator
import numpy as np
from livekit import rtc
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAITTSService:
    VOICE_CONFIGS = {
        "adina": {
            "voice": "alloy",
            "speed": 0.9,
            "style_prompt": "Speaking as a compassionate spiritual guide"
        },
        "raffa": {
            "voice": "onyx",
            "speed": 0.85,  # Slightly slower for wisdom
            "style_prompt": "Speaking as a wise spiritual mentor"
        }
    }
    
    def __init__(self):
        self.client = openai.OpenAI()
        self.max_retries = 3
        self.chunk_size = 4096  # Optimal chunk size for streaming
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Generate streaming TTS audio for spiritual guidance"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
            
        voice_config = self.VOICE_CONFIGS[character]
        spiritual_context = f"{voice_config['style_prompt']}: {text}"
        
        start_time = asyncio.get_event_loop().time()
        chunk_count = 0
        
        for attempt in range(self.max_retries):
            try:
                # Generate high-quality TTS
                response = self.client.audio.speech.create(
                    model="tts-1-hd",           # Higher quality for spiritual conversations
                    voice=voice_config["voice"],
                    input=spiritual_context,
                    response_format="pcm",      # Raw PCM for LiveKit streaming
                    speed=voice_config["speed"]
                )
                
                # Stream audio in chunks
                audio_data = response.content
                logger.info(f"Generated {len(audio_data)} bytes of audio for {character}")
                
                for i in range(0, len(audio_data), self.chunk_size):
                    chunk = audio_data[i:i + self.chunk_size]
                    if len(chunk) > 0:
                        audio_frame = self._create_audio_frame(chunk)
                        chunk_count += 1
                        
                        if chunk_count == 1:
                            first_chunk_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                            logger.info(f"First chunk latency for {character}: {first_chunk_latency:.0f}ms")
                            
                        yield audio_frame
                        await asyncio.sleep(0.01)  # Small delay for streaming feel
                
                # Success - break retry loop
                break
                    
            except openai.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                raise
                
            except Exception as e:
                logger.error(f"OpenAI TTS error: {e}")
                raise
        
        total_time = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(f"TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total")
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert PCM bytes to LiveKit AudioFrame"""
        # Convert bytes to 16-bit signed integers
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,  # OpenAI TTS standard rate
            num_channels=1,     # Mono audio
            samples_per_channel=len(audio_data)
        )

# Performance validation test
async def validate_streaming_performance():
    print("Validating OpenAI TTS performance...")
    service = OpenAITTSService()
    test_text = "This is a performance validation test for real-time spiritual guidance."
    
    results = []
    for character in ["adina", "raffa"]:
        print(f"\nTesting {character}...")
        try:
            start_time = asyncio.get_event_loop().time()
            first_chunk_time = None
            chunk_count = 0
            
            async for audio_frame in service.synthesize_streaming(test_text, character):
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