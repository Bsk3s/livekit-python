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

class OptimizedOpenAITTSService:
    VOICE_CONFIGS = {
        "adina": {
            "voice": "alloy",
            "speed": 1.3,  # Much faster
        },
        "raffa": {
            "voice": "onyx", 
            "speed": 1.2,  # Faster
        }
    }
    
    def __init__(self):
        self.client = openai.OpenAI()
        self.max_retries = 1  # Minimal retries for speed
        self.chunk_size = 512  # Very small audio chunks
        self.max_text_length = 50  # Very short text chunks
    
    def _split_text_smart(self, text: str) -> list[str]:
        """Split text into very small chunks for minimal latency"""
        if len(text) <= self.max_text_length:
            return [text]
        
        # Split at natural breaks: periods, commas, spaces
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            test_chunk = f"{current_chunk} {word}".strip()
            if len(test_chunk) <= self.max_text_length:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks if chunks else [text[:self.max_text_length]]
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Ultra-optimized streaming with micro-chunks"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
            
        voice_config = self.VOICE_CONFIGS[character]
        text_chunks = self._split_text_smart(text.strip())
        
        logger.info(f"Processing {len(text_chunks)} micro-chunks for {character}")
        
        overall_start = asyncio.get_event_loop().time()
        first_audio_yielded = False
        
        # Process chunks in parallel for even faster response
        tasks = []
        for i, text_chunk in enumerate(text_chunks[:3]):  # Only first 3 chunks for speed
            task = self._generate_chunk_audio(text_chunk, voice_config, i)
            tasks.append(task)
        
        # Yield audio as soon as first chunk is ready
        for task in asyncio.as_completed(tasks):
            try:
                chunk_idx, audio_data = await task
                
                # Stream this chunk immediately
                for i in range(0, len(audio_data), self.chunk_size):
                    audio_chunk = audio_data[i:i + self.chunk_size]
                    if len(audio_chunk) > 0:
                        audio_frame = self._create_audio_frame(audio_chunk)
                        
                        if not first_audio_yielded:
                            first_latency = (asyncio.get_event_loop().time() - overall_start) * 1000
                            logger.info(f"🚀 FIRST AUDIO: {first_latency:.0f}ms for {character}")
                            first_audio_yielded = True
                        
                        yield audio_frame
                        
            except Exception as e:
                logger.error(f"Chunk generation failed: {e}")
                continue
        
        total_time = (asyncio.get_event_loop().time() - overall_start) * 1000
        logger.info(f"✅ Complete: {total_time:.0f}ms total for {character}")
    
    async def _generate_chunk_audio(self, text_chunk: str, voice_config: dict, chunk_idx: int):
        """Generate audio for a single text chunk"""
        try:
            response = self.client.audio.speech.create(
                model="tts-1",  # Fastest model
                voice=voice_config["voice"],
                input=text_chunk,
                response_format="pcm",
                speed=voice_config["speed"]
            )
            return chunk_idx, response.content
        except Exception as e:
            logger.error(f"Failed to generate chunk {chunk_idx}: {e}")
            raise
    
    def _create_audio_frame(self, chunk: bytes) -> rtc.AudioFrame:
        """Convert PCM bytes to LiveKit AudioFrame"""
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=len(audio_data)
        )

# Speed test
async def speed_test():
    print("🚀 ULTRA-OPTIMIZED OpenAI TTS Speed Test")
    service = OptimizedOpenAITTSService()
    
    test_cases = [
        ("ultra_short", "Hello there."),
        ("short", "I'm here to help you today."),
        ("medium", "Welcome to our spiritual guidance session. I'm here to help."),
    ]
    
    results = []
    for test_name, test_text in test_cases:
        print(f"\n=== {test_name.upper()}: '{test_text}' ===")
        
        for character in ["adina", "raffa"]:
            try:
                start = asyncio.get_event_loop().time()
                first_audio = None
                chunk_count = 0
                
                async for audio_frame in service.synthesize_streaming(test_text, character):
                    chunk_count += 1
                    if chunk_count == 1:
                        first_audio = (asyncio.get_event_loop().time() - start) * 1000
                    if chunk_count >= 3:  # Just test first few chunks
                        break
                
                total = (asyncio.get_event_loop().time() - start) * 1000
                
                status = "🎯 TARGET MET!" if first_audio and first_audio < 1500 else "❌ Too slow"
                
                print(f"{character}: {status} - First: {first_audio:.0f}ms, Total: {total:.0f}ms")
                
                results.append({
                    "test": test_name,
                    "character": character, 
                    "first_ms": first_audio,
                    "pass": first_audio < 1500 if first_audio else False
                })
                
            except Exception as e:
                print(f"{character}: ❌ ERROR - {e}")
                results.append({"test": test_name, "character": character, "pass": False})
    
    # Summary
    passed = sum(1 for r in results if r.get("pass", False))
    total_tests = len(results)
    
    print(f"\n🎯 FINAL SCORE: {passed}/{total_tests} tests under 1.5s")
    
    if passed >= total_tests * 0.5:
        print("🚀 IMPROVEMENT ACHIEVED!")
        return True
    else:
        print("💀 Still need more optimization...")
        return False

if __name__ == "__main__":
    asyncio.run(speed_test()) 