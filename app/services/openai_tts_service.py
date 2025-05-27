import openai
import asyncio
from typing import AsyncGenerator
import numpy as np
from livekit import rtc
import logging
from dotenv import load_dotenv
import re

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAITTSService:
    VOICE_CONFIGS = {
        "adina": {
            "voice": "alloy",
            "speed": 1.2,  # Faster for responsiveness
            "style_prompt": "Speaking as a compassionate spiritual guide"
        },
        "raffa": {
            "voice": "onyx",
            "speed": 1.1,  # Slightly faster
            "style_prompt": "Speaking as a wise spiritual mentor"
        }
    }
    
    def __init__(self):
        self.client = openai.OpenAI()
        self.max_retries = 2
        self.chunk_size = 1024  # Smaller audio chunks
        self.max_text_length = 100  # Max characters per TTS request
    
    def _split_text_intelligently(self, text: str) -> list[str]:
        """Split text into smaller chunks at natural break points"""
        if len(text) <= self.max_text_length:
            return [text]
        
        # Split at sentence boundaries first
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed limit, save current chunk
            if len(current_chunk) + len(sentence) + 1 > self.max_text_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text[:self.max_text_length]]
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Generate streaming TTS audio with text chunking for lower latency"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
            
        voice_config = self.VOICE_CONFIGS[character]
        
        # Split text into smaller chunks for faster processing
        text_chunks = self._split_text_intelligently(text.strip())
        logger.info(f"Split text into {len(text_chunks)} chunks for {character}")
        
        overall_start = asyncio.get_event_loop().time()
        total_audio_chunks = 0
        first_chunk_yielded = False
        
        for chunk_idx, text_chunk in enumerate(text_chunks):
            chunk_start = asyncio.get_event_loop().time()
            
            for attempt in range(self.max_retries):
                try:
                    # Use fastest settings
                    response = self.client.audio.speech.create(
                        model="tts-1",  # Fastest model
                        voice=voice_config["voice"],
                        input=text_chunk,  # Small text chunk
                        response_format="pcm",
                        speed=voice_config["speed"]
                    )
                    
                    audio_data = response.content
                    
                    # Stream this chunk's audio immediately
                    for i in range(0, len(audio_data), self.chunk_size):
                        audio_chunk = audio_data[i:i + self.chunk_size]
                        if len(audio_chunk) > 0:
                            audio_frame = self._create_audio_frame(audio_chunk)
                            total_audio_chunks += 1
                            
                            # Log first chunk latency
                            if not first_chunk_yielded:
                                first_chunk_latency = (asyncio.get_event_loop().time() - overall_start) * 1000
                                logger.info(f"FIRST CHUNK latency for {character}: {first_chunk_latency:.0f}ms")
                                first_chunk_yielded = True
                            
                            yield audio_frame
                    
                    # Log chunk completion
                    chunk_time = (asyncio.get_event_loop().time() - chunk_start) * 1000
                    logger.info(f"Chunk {chunk_idx + 1}/{len(text_chunks)} completed in {chunk_time:.0f}ms")
                    break
                        
                except openai.RateLimitError as e:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(0.5)  # Very short wait
                        continue
                    logger.error(f"Rate limit exceeded")
                    raise
                    
                except Exception as e:
                    logger.error(f"OpenAI TTS error on chunk {chunk_idx}: {e}")
                    raise
        
        total_time = (asyncio.get_event_loop().time() - overall_start) * 1000
        logger.info(f"TTS complete for {character}: {total_audio_chunks} audio chunks, {total_time:.0f}ms total")
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert PCM bytes to LiveKit AudioFrame"""
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=len(audio_data)
        )

# Performance validation test
async def validate_streaming_performance():
    print("Validating OPTIMIZED OpenAI TTS performance with text chunking...")
    service = OpenAITTSService()
    
    # Test with different text lengths
    test_cases = [
        ("short", "Hello, I'm here to help you today."),
        ("medium", "This is a performance validation test for real-time spiritual guidance. I'm here to provide comfort and support."),
        ("long", "Welcome to our spiritual guidance session. I'm here to provide you with compassionate support and wisdom. Together we can explore your spiritual journey and find the answers you seek. Let me help guide you through this process with care and understanding.")
    ]
    
    results = []
    for test_name, test_text in test_cases:
        print(f"\n=== Testing {test_name} text ({len(test_text)} chars) ===")
        
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
                    if chunk_count >= 5:  # Test first few chunks
                        break
                        
                total_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if first_chunk_time and first_chunk_time < 1500:
                    status = "✅ PASS"
                else:
                    status = "❌ FAIL"
                    
                result = {
                    "test": test_name,
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
                    "test": test_name,
                    "character": character,
                    "error": str(e),
                    "status": "❌ FAIL"
                })
    
    passing = sum(1 for r in results if r["status"] == "✅ PASS")
    total = len(results)
    print(f"\n🎯 Performance Summary: {passing}/{total} tests passed")
    
    if passing >= total * 0.7:  # 70% pass rate
        print("🚀 Chunking strategy shows improvement!")
        return True
    else:
        print("💀 Still need more optimization")
        return False

if __name__ == "__main__":
    asyncio.run(validate_streaming_performance()) 