import pytest
import asyncio
import time
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-voice-agent', 'app'))

from services.livekit_deepgram_tts import LiveKitDeepgramTTS

@pytest.mark.asyncio
async def test_first_chunk_latency():
    """Test that first TTS chunk arrives within 250ms"""
    tts = LiveKitDeepgramTTS()
    
    started = time.perf_counter()
    
    # Test with async context manager
    async with tts.stream("Hello, this is a test") as stream:
        chunk = await stream.__anext__()   # first PCM frame
        
    first_ms = (time.perf_counter() - started) * 1000
    
    print(f"🚀 First chunk latency: {first_ms:.0f}ms")
    assert first_ms < 250, f"First chunk too slow: {first_ms:.0f} ms (target: <250ms)"
    
    # Clean up
    await tts.aclose()

@pytest.mark.asyncio 
async def test_streaming_works():
    """Test that streaming produces multiple chunks"""
    tts = LiveKitDeepgramTTS()
    
    chunk_count = 0
    async with tts.stream("Hello world, this is a longer test message") as stream:
        async for chunk in stream:
            chunk_count += 1
            if chunk_count >= 3:  # Test first few chunks
                break
    
    assert chunk_count >= 3, f"Expected at least 3 chunks, got {chunk_count}"
    
    # Clean up
    await tts.aclose()

if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_first_chunk_latency())
    asyncio.run(test_streaming_works())
    print("✅ All TTS latency tests passed!") 