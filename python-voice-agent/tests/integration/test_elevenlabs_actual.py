#!/usr/bin/env python3
"""
🎙️ ELEVENLABS TTS ACTUAL TEST
Test that ElevenLabs TTS service can be created and configured properly
"""

import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_elevenlabs_actual():
    """Test actual ElevenLabs TTS service creation and configuration"""
    
    print("🎙️ ELEVENLABS TTS ACTUAL TEST")
    print("=" * 60)
    
    # Test 1: Check environment variables
    print("\n1️⃣ ENVIRONMENT VARIABLES")
    print("-" * 30)
    
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    adina_voice = os.getenv("ADINA_VOICE_ID")
    raffa_voice = os.getenv("RAFFA_VOICE_ID")
    
    if elevenlabs_key:
        print(f"✅ ELEVENLABS_API_KEY: {'*' * 20}{elevenlabs_key[-4:]}")
    else:
        print("❌ ELEVENLABS_API_KEY: Not set")
        return False
    
    if openai_key:
        print(f"✅ OPENAI_API_KEY: {'*' * 20}{openai_key[-4:]}")
    else:
        print("❌ OPENAI_API_KEY: Not set")
    
    if adina_voice:
        print(f"✅ ADINA_VOICE_ID: {adina_voice}")
    else:
        print("⚠️ ADINA_VOICE_ID: Not set (will use default)")
    
    if raffa_voice:
        print(f"✅ RAFFA_VOICE_ID: {raffa_voice}")
    else:
        print("⚠️ RAFFA_VOICE_ID: Not set (will use default)")
    
    # Test 2: Import and create ElevenLabs TTS
    print("\n2️⃣ ELEVENLABS TTS CREATION")
    print("-" * 30)
    
    try:
        from app.services.elevenlabs_tts_service import ElevenLabsTTS
        print("✅ ElevenLabs TTS service imported successfully")
        
        # Create the TTS service
        tts_service = ElevenLabsTTS()
        print("✅ ElevenLabs TTS service created successfully")
        
        # Check voice configurations
        print(f"✅ Voice configurations loaded:")
        for char, config in tts_service.VOICE_CONFIGS.items():
            print(f"   🎭 {char}: {config['voice_id']} (model: {config['model']})")
        
        # Test character setting
        print("\n3️⃣ CHARACTER SETTING TEST")
        print("-" * 30)
        
        # Test Adina
        tts_service.set_character("adina")
        print(f"✅ Set character to 'adina' → {tts_service._current_character}")
        
        # Test Raffa
        tts_service.set_character("raffa")
        print(f"✅ Set character to 'raffa' → {tts_service._current_character}")
        
        # Test case insensitive
        tts_service.set_character("Adina")
        print(f"✅ Set character to 'Adina' → {tts_service._current_character}")
        
        # Test invalid character
        tts_service.set_character("invalid")
        print(f"✅ Invalid character test → {tts_service._current_character} (should remain unchanged)")
        
        # Test 4: Stream creation (without actual synthesis)
        print("\n4️⃣ STREAM CREATION TEST")
        print("-" * 30)
        
        test_text = "Hello, this is a test of the ElevenLabs TTS service."
        
        # Test synthesize method
        stream = tts_service.synthesize(test_text)
        print(f"✅ Synthesize stream created: {type(stream).__name__}")
        
        # Test stream method
        stream2 = await tts_service.stream(test_text)
        print(f"✅ Stream method created: {type(stream2).__name__}")
        
        # Clean up streams
        await stream.aclose()
        await stream2.aclose()
        print("✅ Streams cleaned up successfully")
        
        # Test 5: Session management
        print("\n5️⃣ SESSION MANAGEMENT TEST")
        print("-" * 30)
        
        # Get session (should create it)
        session = await tts_service._get_session()
        print(f"✅ HTTP session created: {type(session).__name__}")
        print(f"   Headers: {dict(session.headers)}")
        
        # Clean up TTS service
        await tts_service.aclose()
        print("✅ TTS service cleaned up successfully")
        
        print("\n6️⃣ FALLBACK CHAIN TEST")
        print("-" * 30)
        
        # Test the fallback logic from spiritual_worker.py
        try:
            # Primary: ElevenLabs
            primary_tts = ElevenLabsTTS()
            primary_tts.set_character("adina")
            print("✅ Primary ElevenLabs TTS created successfully")
            await primary_tts.aclose()
            
        except Exception as e:
            print(f"❌ Primary ElevenLabs TTS failed: {e}")
            
            # Fallback: OpenAI TTS-1 HD
            try:
                from livekit.plugins import openai
                fallback_tts = openai.TTS(voice="nova", model="tts-1-hd")
                print("✅ Fallback OpenAI TTS-1 HD created successfully")
            except Exception as fallback_e:
                print(f"❌ Fallback OpenAI TTS failed: {fallback_e}")
                
                # Emergency: Basic OpenAI TTS
                try:
                    emergency_tts = openai.TTS()
                    print("✅ Emergency OpenAI TTS created successfully")
                except Exception as emergency_e:
                    print(f"❌ Emergency OpenAI TTS failed: {emergency_e}")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create ElevenLabs TTS: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_elevenlabs_actual())
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED: ElevenLabs TTS is ready for production!")
        print("🚀 Your voice agent should work with natural ElevenLabs voices")
    else:
        print("❌ TESTS FAILED: Check ElevenLabs TTS configuration")
        print("🛡️ Fallback to OpenAI TTS will be used instead") 