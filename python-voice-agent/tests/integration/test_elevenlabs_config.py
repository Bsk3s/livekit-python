#!/usr/bin/env python3
"""
🎙️ ELEVENLABS TTS CONFIGURATION TEST
Test that ElevenLabs TTS is properly configured and OpenAI TTS-1 HD fallback works
"""

import asyncio
import logging
import sys
import os

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

async def test_elevenlabs_config():
    """Test ElevenLabs TTS configuration"""
    
    print("🎙️ ELEVENLABS TTS CONFIGURATION TEST")
    print("=" * 60)
    
    # Test 1: Check environment variables
    print("\n1️⃣ ENVIRONMENT VARIABLES")
    print("-" * 30)
    
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if elevenlabs_key:
        print(f"✅ ELEVENLABS_API_KEY: {'*' * 20}{elevenlabs_key[-4:]}")
    else:
        print("❌ ELEVENLABS_API_KEY: Not set")
    
    if openai_key:
        print(f"✅ OPENAI_API_KEY: {'*' * 20}{openai_key[-4:]}")
    else:
        print("❌ OPENAI_API_KEY: Not set")
    
    # Test 2: Try to import ElevenLabs TTS
    print("\n2️⃣ ELEVENLABS TTS IMPORT")
    print("-" * 30)
    
    try:
        from spiritual_voice_agent.services.elevenlabs_tts_service import ElevenLabsTTS
        print("✅ ElevenLabs TTS service imported successfully")
        
        # Test character configurations
        print(f"✅ Available characters: {list(ElevenLabsTTS.CHARACTER_MAP.keys())}")
        
        for char_name, config_key in ElevenLabsTTS.CHARACTER_MAP.items():
            if config_key in ElevenLabsTTS.VOICE_CONFIGS:
                voice_config = ElevenLabsTTS.VOICE_CONFIGS[config_key]
                print(f"   🎭 {char_name} → {config_key}")
                print(f"      Voice ID: {voice_config['voice_id']}")
                print(f"      Model: {voice_config['model']}")
        
    except Exception as e:
        print(f"❌ Failed to import ElevenLabs TTS: {e}")
    
    # Test 3: Try to create ElevenLabs TTS instance
    print("\n3️⃣ ELEVENLABS TTS CREATION")
    print("-" * 30)
    
    if elevenlabs_key:
        try:
            tts_service = ElevenLabsTTS()
            print("✅ ElevenLabs TTS instance created successfully")
            
            # Test character setting
            tts_service.set_character("adina")
            print(f"✅ Character set to: {tts_service._current_character}")
            
            tts_service.set_character("raffa")
            print(f"✅ Character set to: {tts_service._current_character}")
            
            await tts_service.aclose()
            print("✅ ElevenLabs TTS cleaned up successfully")
            
        except Exception as e:
            print(f"❌ Failed to create ElevenLabs TTS: {e}")
    else:
        print("⚠️ Skipping ElevenLabs TTS creation (no API key)")
    
    # Test 4: Test OpenAI TTS fallback
    print("\n4️⃣ OPENAI TTS-1 HD FALLBACK")
    print("-" * 30)
    
    if openai_key:
        try:
            from livekit.plugins import openai
            
            # Test OpenAI TTS-1 HD creation
            tts_fallback = openai.TTS(
                voice="nova",
                model="tts-1-hd"
            )
            print("✅ OpenAI TTS-1 HD fallback created successfully")
            print("   Voice: nova")
            print("   Model: tts-1-hd (high definition)")
            
        except Exception as e:
            print(f"❌ Failed to create OpenAI TTS fallback: {e}")
    else:
        print("⚠️ Skipping OpenAI TTS test (no API key)")
    
    # Test 5: Configuration summary
    print("\n5️⃣ CONFIGURATION SUMMARY")
    print("-" * 30)
    
    if elevenlabs_key and openai_key:
        print("✅ OPTIMAL: ElevenLabs primary + OpenAI TTS-1 HD fallback")
        print("   🎙️ Primary: ElevenLabs streaming TTS")
        print("   🛡️ Fallback: OpenAI TTS-1 HD")
        print("   🚀 Result: Natural voice with reliable fallback")
    elif openai_key:
        print("⚠️ FALLBACK ONLY: OpenAI TTS-1 HD")
        print("   🛡️ Using: OpenAI TTS-1 HD only")
        print("   📝 Note: Add ELEVENLABS_API_KEY for natural voice")
    else:
        print("❌ INCOMPLETE: Missing API keys")
        print("   📝 Need: ELEVENLABS_API_KEY and OPENAI_API_KEY")
    
    print("\n" + "=" * 60)
    print("🎙️ ElevenLabs TTS configuration test complete!")

if __name__ == "__main__":
    asyncio.run(test_elevenlabs_config()) 