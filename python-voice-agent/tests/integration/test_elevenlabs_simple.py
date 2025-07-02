#!/usr/bin/env python3
"""
🎙️ SIMPLE ELEVENLABS TTS TEST
Test ElevenLabs TTS configuration without complex dependencies
"""

import os
import sys

def test_elevenlabs_simple():
    """Simple test of ElevenLabs TTS configuration"""
    
    print("🎙️ SIMPLE ELEVENLABS TTS TEST")
    print("=" * 50)
    
    # Test 1: Check environment variables
    print("\n1️⃣ ENVIRONMENT VARIABLES")
    print("-" * 30)
    
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if elevenlabs_key:
        print(f"✅ ELEVENLABS_API_KEY: Set ({'*' * 20}{elevenlabs_key[-4:] if len(elevenlabs_key) > 4 else '****'})")
    else:
        print("❌ ELEVENLABS_API_KEY: Not set")
    
    if openai_key:
        print(f"✅ OPENAI_API_KEY: Set ({'*' * 20}{openai_key[-4:] if len(openai_key) > 4 else '****'})")
    else:
        print("❌ OPENAI_API_KEY: Not set")
    
    # Test 2: Check TTS configuration logic
    print("\n2️⃣ TTS CONFIGURATION LOGIC")
    print("-" * 30)
    
    # Character configurations for ElevenLabs
    VOICE_CONFIGS = {
        "Adina": {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - warm, empathetic female
            "model": "eleven_turbo_v2_5",
        },
        "Raffa": {
            "voice_id": "29vD33N1CtxCmqQRPOHJ",  # Drew - warm, wise male
            "model": "eleven_turbo_v2_5", 
        }
    }
    
    CHARACTER_MAP = {
        "adina": "Adina",
        "raffa": "Raffa",
        "Adina": "Adina",
        "Raffa": "Raffa"
    }
    
    print("✅ ElevenLabs voice configurations:")
    for char_name, config_key in CHARACTER_MAP.items():
        if config_key in VOICE_CONFIGS:
            voice_config = VOICE_CONFIGS[config_key]
            print(f"   🎭 {char_name} → {config_key}")
            print(f"      Voice ID: {voice_config['voice_id']}")
            print(f"      Model: {voice_config['model']}")
    
    # Test 3: OpenAI TTS fallback configuration
    print("\n3️⃣ OPENAI TTS FALLBACK CONFIGURATION")
    print("-" * 30)
    
    openai_voices = {
        "adina": "nova",  # Warm, feminine voice
        "raffa": "onyx",  # Deep, masculine voice
        "default": "alloy"  # Default voice
    }
    
    print("✅ OpenAI TTS-1 HD fallback voices:")
    for character, voice in openai_voices.items():
        print(f"   🎭 {character}: {voice}")
    print("   📝 Model: tts-1-hd (high definition)")
    
    # Test 4: Configuration summary
    print("\n4️⃣ CONFIGURATION SUMMARY")
    print("-" * 30)
    
    if elevenlabs_key and openai_key:
        print("✅ OPTIMAL CONFIGURATION")
        print("   🎙️ Primary: ElevenLabs streaming TTS")
        print("   🛡️ Fallback: OpenAI TTS-1 HD")
        print("   🚀 Result: Natural voice with reliable fallback")
        print("   📋 Flow: ElevenLabs → OpenAI TTS-1 HD → Basic OpenAI")
    elif openai_key:
        print("⚠️ FALLBACK ONLY CONFIGURATION")
        print("   🛡️ Using: OpenAI TTS-1 HD only")
        print("   📝 Note: Add ELEVENLABS_API_KEY for natural voice")
        print("   📋 Flow: OpenAI TTS-1 HD → Basic OpenAI")
    else:
        print("❌ INCOMPLETE CONFIGURATION")
        print("   📝 Need: ELEVENLABS_API_KEY and OPENAI_API_KEY")
        print("   🚨 Warning: TTS will fail without API keys")
    
    # Test 5: Deployment instructions
    print("\n5️⃣ DEPLOYMENT INSTRUCTIONS")
    print("-" * 30)
    
    if not elevenlabs_key:
        print("📝 TO ENABLE ELEVENLABS:")
        print("   1. Get API key from: https://elevenlabs.io/")
        print("   2. Add to Render environment variables:")
        print("      ELEVENLABS_API_KEY=your_api_key_here")
    
    if not openai_key:
        print("📝 TO ENABLE OPENAI FALLBACK:")
        print("   1. Get API key from: https://platform.openai.com/")
        print("   2. Add to Render environment variables:")
        print("      OPENAI_API_KEY=your_api_key_here")
    
    print("\n" + "=" * 50)
    print("🎙️ Simple ElevenLabs TTS test complete!")
    
    return elevenlabs_key is not None, openai_key is not None

if __name__ == "__main__":
    has_elevenlabs, has_openai = test_elevenlabs_simple()
    
    if has_elevenlabs and has_openai:
        print("\n🎉 READY TO DEPLOY: All TTS services configured!")
    elif has_openai:
        print("\n⚠️ PARTIAL: OpenAI TTS ready, add ElevenLabs for best quality")
    else:
        print("\n❌ NOT READY: Missing API keys for TTS services") 