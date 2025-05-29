#!/usr/bin/env python3
"""
Test script to validate LiveKit token generation with correct credentials
"""

import os
import sys
from datetime import timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livekit import api

# Correct LiveKit credentials from webrtc_client.py
CORRECT_API_KEY = "APIjsXZYsEhhs8h"
CORRECT_API_SECRET = "h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM"
CORRECT_LIVEKIT_URL = "wss://hb-j73yzwmu.livekit.cloud"

def test_token_generation():
    """Test token generation with correct credentials"""
    try:
        print("🧪 Testing LiveKit token generation...")
        print(f"📡 LiveKit URL: {CORRECT_LIVEKIT_URL}")
        print(f"🔑 API Key: {CORRECT_API_KEY}")
        print(f"🔐 API Secret: {CORRECT_API_SECRET[:10]}...")
        
        # Create video grants
        grants = api.VideoGrants(
            room_join=True,
            room="spiritual-adina-test",
            room_create=True,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
            can_update_own_metadata=True
        )
        
        # Create access token
        token = api.AccessToken(api_key=CORRECT_API_KEY, api_secret=CORRECT_API_SECRET)
        token.grants = grants
        token.identity = "user_test-user"
        token.name = "Test User"
        token.ttl = timedelta(minutes=30)
        
        # Generate JWT
        jwt_token = token.to_jwt()
        print(f"✅ Token generated successfully!")
        print(f"🎫 Token: {jwt_token[:50]}...")
        
        # Test decoding
        decoded = api.AccessToken.from_jwt(jwt_token, CORRECT_API_SECRET)
        print(f"✅ Token decoded successfully!")
        print(f"👤 Identity: {decoded.identity}")
        print(f"🏠 Room: {decoded.grants.room}")
        print(f"📝 Can publish: {decoded.grants.can_publish}")
        print(f"📺 Can subscribe: {decoded.grants.can_subscribe}")
        
        return jwt_token
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_current_env_vars():
    """Test with current environment variables"""
    try:
        print("\n🔍 Testing current environment variables...")
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        livekit_url = os.getenv("LIVEKIT_URL")
        
        print(f"📡 LIVEKIT_URL: {livekit_url or 'Not set'}")
        print(f"🔑 LIVEKIT_API_KEY: {api_key[:10] + '...' if api_key else 'Not set'}")
        print(f"🔐 LIVEKIT_API_SECRET: {api_secret[:10] + '...' if api_secret else 'Not set'}")
        
        if not api_key or not api_secret:
            print("⚠️ Environment variables not set locally")
            return None
            
        # Test with env vars
        grants = api.VideoGrants(
            room_join=True,
            room="spiritual-adina-test",
            can_publish=True,
            can_subscribe=True
        )
        
        token = api.AccessToken(api_key=api_key, api_secret=api_secret)
        token.grants = grants
        token.identity = "user_test-user"
        token.ttl = timedelta(minutes=30)
        
        jwt_token = token.to_jwt()
        print(f"✅ Token with env vars generated successfully!")
        print(f"🎫 Token: {jwt_token[:50]}...")
        
        return jwt_token
        
    except Exception as e:
        print(f"❌ Error with env vars: {e}")
        return None

if __name__ == "__main__":
    print("🌟 LiveKit Token Validation Test")
    print("=" * 50)
    
    # Test with correct credentials
    correct_token = test_token_generation()
    
    # Test with environment variables
    env_token = test_current_env_vars()
    
    print("\n📊 Summary:")
    print(f"✅ Correct credentials token: {'Generated' if correct_token else 'Failed'}")
    print(f"⚠️ Environment variables token: {'Generated' if env_token else 'Failed/Not set'}")
    
    if correct_token:
        print(f"\n🎯 Use these credentials on Render:")
        print(f"LIVEKIT_URL={CORRECT_LIVEKIT_URL}")
        print(f"LIVEKIT_API_KEY={CORRECT_API_KEY}")
        print(f"LIVEKIT_API_SECRET={CORRECT_API_SECRET}") 