#!/usr/bin/env python3
import os
import sys
import json
import base64

# Add the correct Python path
sys.path.insert(0, "/Users/administrator/Desktop/Python Livekit/venv/lib/python3.11/site-packages")

# Set the correct credentials
os.environ["LIVEKIT_API_KEY"] = "APIjsXZYsEhhs8h"
os.environ["LIVEKIT_API_SECRET"] = "h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM"

from livekit.api import AccessToken, VideoGrants
from datetime import timedelta

print("🔍 TESTING LOCAL TOKEN CREATION WITH CORRECT CREDENTIALS")
print("=" * 70)

try:
    # Create token manually using the same logic as the backend
    api_key = "APIjsXZYsEhhs8h"
    api_secret = "h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM"
    room = "test-room-spiritual"
    user_id = "test-user"
    user_name = "Test User"
    character = "adina"
    
    # Create video grants with appropriate permissions
    grants = VideoGrants(
        room_join=True,
        room=room,
        room_create=True,  # Allow room creation if it doesn't exist
        can_publish=True,  # User can publish audio
        can_subscribe=True,  # User can receive agent audio
        can_publish_data=True,  # For potential text chat
        can_update_own_metadata=True  # User can update their own metadata
    )
    
    # Create access token with expiration
    token = AccessToken(api_key=api_key, api_secret=api_secret)
    token.grants = grants
    token.identity = f"user_{user_id}"  # Prefix for clarity
    token.name = user_name
    
    # Set token expiration
    token.ttl = timedelta(minutes=30)
    
    jwt_token = token.to_jwt()
    
    print(f"✅ Token created: {jwt_token[:40]}...")
    
    # Decode it to see what's in it
    parts = jwt_token.split('.')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    print(f"\n🔍 LOCAL TOKEN PAYLOAD:")
    for key, value in payload.items():
        print(f"   {key}: {value}")
    
    print(f"\n🎯 GRANTS ANALYSIS:")
    grants_fields = ['room_join', 'can_publish', 'can_subscribe', 'room_create', 'can_publish_data']
    for field in grants_fields:
        value = payload.get(field, "❌ MISSING")
        status = "✅" if value == True else "❌"
        print(f"   {field}: {value} {status}")
    
    room_value = payload.get('room', 'NOT_SET')
    print(f"   room: {room_value} {'✅' if room_value else '❌'}")
    
    print(f"\n🤔 COMPARISON:")
    print("   If local token has grants but backend token doesn't,")
    print("   then the issue is on the Render environment!")
    
except Exception as e:
    print(f"❌ Error creating token: {e}")
    import traceback
    traceback.print_exc() 