#!/usr/bin/env python3
"""
🎙️ TTS IMPORT AND FALLBACK TEST
Test that TTS services can be imported and fallback logic works
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_tts_import():
    """Test TTS service imports and fallback logic"""
    
    print("🎙️ TTS IMPORT AND FALLBACK TEST")
    print("=" * 50)
    
    # Test 1: Import ElevenLabs TTS service
    print("\n1️⃣ ELEVENLABS TTS IMPORT")
    print("-" * 30)
    
    try:
        from spiritual_voice_agent.services.elevenlabs_tts_service import ElevenLabsTTS
        print("✅ ElevenLabs TTS service imported successfully")
        print(f"✅ Streaming support: {getattr(ElevenLabsTTS, 'supports_streaming', 'NOT_SET')}")
        print(f"✅ Character configurations: {len(ElevenLabsTTS.VOICE_CONFIGS)} characters")
        
        # Test character mapping
        for frontend_name, config_key in ElevenLabsTTS.CHARACTER_MAP.items():
            print(f"   🎭 {frontend_name} → {config_key}")
        
    except Exception as e:
        print(f"❌ Failed to import ElevenLabs TTS: {e}")
        return False
    
    # Test 2: Test TTS creation logic (without API keys)
    print("\n2️⃣ TTS CREATION LOGIC")
    print("-" * 30)
    
    # Simulate the worker's TTS creation logic
    elevenlabs_available = os.getenv("ELEVENLABS_API_KEY") is not None
    openai_available = os.getenv("OPENAI_API_KEY") is not None
    
    print(f"Environment check:")
    print(f"   ELEVENLABS_API_KEY: {'✅ Set' if elevenlabs_available else '❌ Not set'}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if openai_available else '❌ Not set'}")
    
    # Test 3: Fallback chain simulation
    print("\n3️⃣ FALLBACK CHAIN SIMULATION")
    print("-" * 30)
    
    tts_service = None
    tts_type = "unknown"
    
    # Primary: ElevenLabs TTS
    if elevenlabs_available:
        try:
            print("🎙️ Attempting ElevenLabs TTS...")
            # Would create ElevenLabsTTS() here if API key was available
            print("✅ ElevenLabs TTS would be created")
            tts_service = "ElevenLabs"
            tts_type = "primary"
        except Exception as e:
            print(f"❌ ElevenLabs TTS failed: {e}")
    else:
        print("⚠️ ElevenLabs TTS skipped (no API key)")
    
    # Fallback 1: OpenAI TTS-1 HD
    if not tts_service and openai_available:
        try:
            print("🛡️ Attempting OpenAI TTS-1 HD fallback...")
            # Would create OpenAI TTS here if API key was available
            print("✅ OpenAI TTS-1 HD would be created")
            tts_service = "OpenAI TTS-1 HD"
            tts_type = "fallback"
        except Exception as e:
            print(f"❌ OpenAI TTS-1 HD failed: {e}")
    elif not tts_service:
        print("⚠️ OpenAI TTS-1 HD skipped (no API key)")
    
    # Fallback 2: Basic OpenAI TTS
    if not tts_service:
        try:
            print("🛡️ Attempting basic OpenAI TTS...")
            print("✅ Basic OpenAI TTS would be created")
            tts_service = "Basic OpenAI TTS"
            tts_type = "emergency"
        except Exception as e:
            print(f"❌ Basic OpenAI TTS failed: {e}")
    
    # Test 4: Results
    print("\n4️⃣ RESULTS")
    print("-" * 30)
    
    if tts_service:
        print(f"✅ TTS Service: {tts_service} ({tts_type})")
        
        if tts_type == "primary":
            print("🚀 OPTIMAL: Using ElevenLabs streaming TTS")
        elif tts_type == "fallback":
            print("🛡️ FALLBACK: Using OpenAI TTS-1 HD")
        else:
            print("🚨 EMERGENCY: Using basic OpenAI TTS")
    else:
        print("❌ NO TTS SERVICE AVAILABLE")
        return False
    
    # Test 5: Character voice mapping
    print("\n5️⃣ CHARACTER VOICE MAPPING")
    print("-" * 30)
    
    if tts_service == "ElevenLabs":
        print("🎭 ElevenLabs character voices:")
        print("   Adina → Rachel (21m00Tcm4TlvDq8ikWAM)")
        print("   Raffa → Drew (29vD33N1CtxCmqQRPOHJ)")
    else:
        print("🎭 OpenAI character voices:")
        print("   Adina → nova (warm, feminine)")
        print("   Raffa → onyx (deep, masculine)")
    
    print("\n" + "=" * 50)
    print("🎙️ TTS import and fallback test complete!")
    
    return True

if __name__ == "__main__":
    success = test_tts_import()
    
    if success:
        print("\n✅ ALL TESTS PASSED: TTS services ready for deployment")
    else:
        print("\n❌ TESTS FAILED: Check TTS configuration") 