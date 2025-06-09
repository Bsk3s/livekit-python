#!/usr/bin/env python3
"""
Smoke test for TTS streaming interface
Verifies that LiveKit can properly call the stream() method
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def smoke_test():
    """Test that TTS streaming interface works correctly"""
    print("🧪 Testing TTS streaming interface...")
    
    try:
        # Import the TTS class
        from app.services.livekit_deepgram_tts import LiveKitDeepgramTTS
        print(f"✅ TTS class imported successfully: {LiveKitDeepgramTTS}")
        print(f"✅ supports_streaming: {getattr(LiveKitDeepgramTTS, 'supports_streaming', 'NOT_SET')}")
        
        # Create TTS instance
        tts = LiveKitDeepgramTTS()
        print(f"✅ TTS instance created")
        
        # Test that stream() method exists and is callable
        if hasattr(tts, 'stream') and callable(getattr(tts, 'stream')):
            print("✅ stream() method exists and is callable")
        else:
            print("❌ stream() method missing or not callable")
            return False
            
        # Test the stream() method (what LiveKit actually calls)
        print("🎤 Testing stream() method...")
        stream = await tts.stream("Hello world test")
        print(f"✅ stream() returned: {type(stream)}")
        
        # Test that the stream is iterable
        print("🔄 Testing stream iteration...")
        chunk_count = 0
        async with stream as s:
            async for chunk in s:
                chunk_count += 1
                print(f"📦 Chunk {chunk_count}: {len(chunk.frame.data) if hasattr(chunk, 'frame') else 'unknown'} bytes")
                if chunk_count >= 3:  # Just test first few chunks
                    break
        
        print(f"✅ Stream iteration successful - got {chunk_count} chunks")
        print("🎉 TTS streaming interface test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ TTS streaming test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            await tts.aclose()
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1) 