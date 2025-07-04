#!/usr/bin/env python3

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add app directory to path

# from services.livekit_deepgram_tts import LiveKitDeepgramTTS  # Service removed

load_dotenv()

async def test_simple_integration():
    """Simple test of Deepgram TTS integration"""
    print("🚀 Testing Simple Deepgram TTS Integration")
    print("=" * 50)
    
    try:
        # Initialize TTS
        tts = LiveKitDeepgramTTS()
        print("✅ TTS initialized")
        
        # Test both characters
        characters = ["adina", "raffa"]
        test_text = "Hello, I'm here to provide spiritual guidance and support."
        
        for character in characters:
            print(f"\n🎭 Testing {character.title()}")
            
            # Set character
            tts.set_character(character)
            
            # Test synthesis
            start_time = asyncio.get_event_loop().time()
            first_chunk_time = None
            chunk_count = 0
            
            async for audio_chunk in tts._synthesize_streaming(test_text, character):
                chunk_count += 1
                if chunk_count == 1:
                    first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                if chunk_count >= 3:  # Test first few chunks
                    break
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Evaluate
            status = "🎯 FAST!" if first_chunk_time < 1500 else "❌ Slow"
            print(f"   {status} - First chunk: {first_chunk_time:.0f}ms, Total: {total_time:.0f}ms")
        
        # Cleanup
        await tts.aclose()
        print("\n✅ Test completed successfully!")
        print("🚀 Deepgram TTS integration is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_integration()) 