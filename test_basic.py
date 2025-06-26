#!/usr/bin/env python3
"""
Basic test for clean LiveKit setup
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test that required environment variables are set"""
    required_vars = [
        'LIVEKIT_URL',
        'LIVEKIT_API_KEY', 
        'LIVEKIT_API_SECRET',
        'OPENAI_API_KEY',
        'DEEPGRAM_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return False
    
    print("✅ All environment variables are set")
    return True

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
        from livekit.plugins import openai, silero
        from app.services.tts_service import TTSService
        from app.services.llm_service import create_gpt4o_mini
        from app.services.deepgram_service import create_deepgram_stt
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

async def test_tts_service():
    """Test TTS service initialization"""
    try:
        from app.services.tts_service import TTSService
        tts = TTSService()
        print("✅ TTS service initialized")
        
        # Test cleanup
        await tts.aclose()
        print("✅ TTS service cleanup successful")
        return True
    except Exception as e:
        print(f"❌ TTS service error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing clean LiveKit setup...")
    
    # Test environment
    env_ok = test_environment()
    
    # Test imports
    imports_ok = test_imports()
    
    # Test TTS service
    tts_ok = asyncio.run(test_tts_service())
    
    # Summary
    if env_ok and imports_ok and tts_ok:
        print("\n🎉 All tests passed! Clean setup is ready.")
        print("\nNext steps:")
        print("1. Run: python agent.py")
        print("2. Implement your custom TTS model")
        print("3. Test with LiveKit agent")
    else:
        print("\n❌ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main() 