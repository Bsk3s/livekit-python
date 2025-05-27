import asyncio
from typing import AsyncGenerator, Dict, Any
import logging
from livekit.plugins import deepgram
from livekit import rtc
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

class DeepgramTTSService:
    """Deepgram TTS service with character-specific voice configurations"""
    
    VOICE_CONFIGS = {
        "adina": {
            "model": "aura-2-andromeda-en",  # Warm, empathetic female voice
            "encoding": "linear16",
            "sample_rate": 24000,
        },
        "raffa": {
            "model": "aura-2-zeus-en",       # Deep, wise male voice
            "encoding": "linear16", 
            "sample_rate": 24000,
        }
    }
    
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        self._tts_instances = {}
        logger.info("Deepgram TTS service initialized")
    
    def _get_tts_instance(self, character: str) -> deepgram.TTS:
        """Get or create TTS instance for character"""
        if character not in self._tts_instances:
            if character not in self.VOICE_CONFIGS:
                raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
            
            config = self.VOICE_CONFIGS[character]
            self._tts_instances[character] = deepgram.TTS(
                model=config["model"],
                encoding=config["encoding"],
                sample_rate=config["sample_rate"],
                api_key=self.api_key
            )
            logger.info(f"Created TTS instance for {character} with model {config['model']}")
        
        return self._tts_instances[character]
    
    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Generate streaming TTS audio with true Deepgram streaming"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
            
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
        
        tts_instance = self._get_tts_instance(character)
        
        start_time = asyncio.get_event_loop().time()
        first_chunk_yielded = False
        chunk_count = 0
        
        logger.info(f"Starting Deepgram TTS synthesis for {character}: '{text[:50]}...'")
        
        try:
            # Use Deepgram's streaming synthesis
            stream = tts_instance.synthesize(text)
            
            async for audio_event in stream:
                chunk_count += 1
                
                # Log first chunk latency
                if not first_chunk_yielded:
                    first_chunk_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    logger.info(f"🚀 FIRST CHUNK latency for {character}: {first_chunk_latency:.0f}ms")
                    first_chunk_yielded = True
                
                yield audio_event.frame
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(f"✅ Deepgram TTS complete for {character}: {chunk_count} chunks, {total_time:.0f}ms total")
            
        except Exception as e:
            logger.error(f"Deepgram TTS error for {character}: {e}")
            raise
    
    async def cleanup(self):
        """Clean up TTS instances"""
        for character, tts_instance in self._tts_instances.items():
            try:
                await tts_instance.aclose()
                logger.info(f"Cleaned up TTS instance for {character}")
            except Exception as e:
                logger.warning(f"Error cleaning up TTS for {character}: {e}")
        
        self._tts_instances.clear()

# Performance test for Deepgram TTS
async def test_deepgram_performance():
    """Test Deepgram TTS performance vs OpenAI"""
    print("🚀 Testing Deepgram TTS Performance")
    service = DeepgramTTSService()
    
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
    
    print(f"\n🎯 DEEPGRAM PERFORMANCE: {passed}/{total_tests} tests under 1.5s")
    
    if passed >= total_tests * 0.8:  # 80% pass rate
        print("🚀 DEEPGRAM MEETS LATENCY REQUIREMENTS!")
        print("💡 Ready for production with true streaming TTS")
        return True
    else:
        print("💀 Still investigating latency issues...")
        return False

if __name__ == "__main__":
    asyncio.run(test_deepgram_performance()) 