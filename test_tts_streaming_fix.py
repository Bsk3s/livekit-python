#!/usr/bin/env python3
"""
Quick test to verify TTS streaming interface is working
"""
import asyncio
import sys
import os

# Add the python-voice-agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python-voice-agent'))

from app.services.livekit_deepgram_tts import LiveKitDeepgramTTS

async def test_tts_streaming():
    """Test that TTS streaming interface works correctly"""
    print("🧪 Testing TTS streaming interface...")
    
    try:
        # Create TTS instance
        tts = LiveKitDeepgramTTS()
        print(f"✅ TTS instance created, supports_streaming: {tts.supports_streaming}")
        
        # Test the stream() method (what LiveKit actually calls)
        print("🎤 Testing stream() method...")
        stream = await tts.stream("Hello, this is a test.")
        print(f"✅ stream() returned: {type(stream)}")
        
        # Test that we can iterate over the stream
        print("🔄 Testing stream iteration...")
        chunk_count = 0
        async with stream as s:
            async for audio_chunk in s:
                chunk_count += 1
                print(f"📦 Received audio chunk {chunk_count}: {len(audio_chunk.frame.data)} samples")
                if chunk_count >= 3:  # Just test first few chunks
                    break
        
        print(f"✅ Successfully streamed {chunk_count} audio chunks!")
        print("🎉 TTS streaming interface is working correctly!")
        
    except Exception as e:
        print(f"❌ TTS streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tts_streaming())
    if success:
        print("\n🚀 TTS streaming fix is ready! The agent should now work.")
    else:
        print("\n💥 TTS streaming still has issues.") 