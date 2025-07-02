#!/usr/bin/env python3
"""
Test script to verify backend is ready for Expo client testing
"""

import asyncio
import aiohttp
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def test_backend_health():
    """Test if the FastAPI backend is running and healthy"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8000/api/health') as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Backend health check passed")
                    print(f"   Status: {data.get('status')}")
                    return True
                else:
                    print(f"❌ Backend health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        return False

async def test_token_generation():
    """Test token generation endpoint"""
    try:
        payload = {
            "room": "spiritual-room-adina",
            "identity": "test-user-123",
            "character": "adina"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'http://localhost:8000/api/generate-token',
                json=payload,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Token generation test passed")
                    print(f"   Room: {data.get('room')}")
                    print(f"   Character: {data.get('character')}")
                    print(f"   WebSocket URL: {data.get('ws_url')}")
                    print(f"   Token length: {len(data.get('token', ''))}")
                    return True
                else:
                    error_data = await response.text()
                    print(f"❌ Token generation failed: {response.status}")
                    print(f"   Error: {error_data}")
                    return False
    except Exception as e:
        print(f"❌ Token generation error: {e}")
        return False

def check_environment():
    """Check required environment variables"""
    required_vars = [
        'LIVEKIT_API_KEY',
        'LIVEKIT_API_SECRET',
        'DEEPGRAM_API_KEY',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def check_livekit_config():
    """Check LiveKit configuration"""
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    ws_url = os.getenv('LIVEKIT_WS_URL', 'ws://localhost:7880')
    
    print("📡 LiveKit Configuration:")
    print(f"   API Key: {api_key[:10]}..." if api_key else "   API Key: Not set")
    print(f"   API Secret: {api_secret[:10]}..." if api_secret else "   API Secret: Not set")
    print(f"   WebSocket URL: {ws_url}")
    
    return bool(api_key and api_secret)

async def main():
    """Run all tests"""
    print("🧪 Testing Expo Backend Readiness")
    print("=" * 40)
    
    # Check environment
    env_ok = check_environment()
    print()
    
    # Check LiveKit config
    livekit_ok = check_livekit_config()
    print()
    
    # Test backend health
    health_ok = await test_backend_health()
    print()
    
    # Test token generation
    token_ok = await test_token_generation()
    print()
    
    # Summary
    print("📋 Test Summary:")
    print(f"   Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"   LiveKit Configuration: {'✅' if livekit_ok else '❌'}")
    print(f"   Backend Health: {'✅' if health_ok else '❌'}")
    print(f"   Token Generation: {'✅' if token_ok else '❌'}")
    print()
    
    if all([env_ok, livekit_ok, health_ok, token_ok]):
        print("🎉 All tests passed! Your backend is ready for Expo testing.")
        print()
        print("Next steps:")
        print("1. Start LiveKit agent: python app/agents/spiritual_session.py dev")
        print("2. Set up Expo client: cd ../expo-client && ./setup.sh")
        print("3. Start Expo: npm start")
        return True
    else:
        print("⚠️  Some tests failed. Please fix the issues above before testing with Expo.")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1) 