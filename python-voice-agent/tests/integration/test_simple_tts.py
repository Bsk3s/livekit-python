#!/usr/bin/env python3
"""
Simple TTS test to verify OpenAI TTS is working
"""

import asyncio
import logging
import sys
import os

# Add current directory to path

async def test_openai_tts_direct():
    """Test OpenAI TTS directly"""
    print("🧪 Testing OpenAI TTS directly...")
    
    try:
        import openai
        client = openai.AsyncOpenAI()
        
        response = await client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input="Hello, this is a test."
        )
        
        audio_data = await response.aread()
        print(f"✅ Direct OpenAI TTS: {len(audio_data)} bytes generated")
        
        return True
        
    except Exception as e:
        print(f"❌ Direct OpenAI TTS failed: {e}")
        return False

async def test_livekit_openai_tts():
    """Test LiveKit OpenAI TTS plugin"""
    print("🧪 Testing LiveKit OpenAI TTS plugin...")
    
    try:
        from livekit.plugins import openai as lk_openai
        
        tts_service = lk_openai.TTS(voice="nova", model="tts-1")
        print("✅ LiveKit TTS service created")
        
        # Test synthesis
        frame_count = 0
        async for frame in tts_service.synthesize("Hello, this is a test."):
            frame_count += 1
            print(f"📊 Frame {frame_count}: {type(frame)}")
            if hasattr(frame, 'data'):
                print(f"   📊 Frame data: {len(frame.data)} bytes")
            if frame_count >= 3:  # Just test first few frames
                break
        
        print(f"✅ LiveKit TTS generated {frame_count} frames")
        return True
        
    except Exception as e:
        print(f"❌ LiveKit OpenAI TTS failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_tts_service():
    """Test the TTS service from our WebSocket handler"""
    print("🧪 Testing WebSocket TTS service...")
    
    try:
        from spiritual_voice_agent.services.openai_tts_service import OpenAITTSService
        
        tts_service = OpenAITTSService()
        print("✅ OpenAI TTS service created")
        
        # Test synthesis
        frame_count = 0
        async for frame in tts_service.synthesize_streaming("Hello, this is a test.", "adina"):
            frame_count += 1
            print(f"📊 Frame {frame_count}: {type(frame)}")
            if hasattr(frame, 'data'):
                print(f"   📊 Frame data: {len(frame.data)} bytes")
            if frame_count >= 3:  # Just test first few frames
                break
        
        print(f"✅ WebSocket TTS generated {frame_count} frames")
        return True
        
    except Exception as e:
        print(f"❌ WebSocket TTS failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🔍 TTS Service Diagnosis")
    print("=" * 40)
    
    # Test 1: Direct OpenAI
    success1 = await test_openai_tts_direct()
    print()
    
    # Test 2: LiveKit OpenAI plugin
    success2 = await test_livekit_openai_tts()
    print()
    
    # Test 3: Our WebSocket TTS service
    success3 = await test_websocket_tts_service()
    print()
    
    print("📊 Results:")
    print(f"   Direct OpenAI: {'✅' if success1 else '❌'}")
    print(f"   LiveKit OpenAI: {'✅' if success2 else '❌'}")
    print(f"   WebSocket TTS: {'✅' if success3 else '❌'}")
    
    if not success2:
        print("\n💡 Recommendation: LiveKit OpenAI plugin issue detected")
        print("   The WebSocket handler should use direct OpenAI API as fallback")

if __name__ == "__main__":
    asyncio.run(main()) 