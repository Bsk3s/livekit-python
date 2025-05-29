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

from app.services.livekit_token import create_spiritual_access_token

print("🔍 TESTING CORRECTED TOKEN CREATION WITH FLUENT API")
print("=" * 70)

try:
    # Create a token using the corrected backend function
    token = create_spiritual_access_token(
        room='test-room-spiritual',
        user_id='test-user', 
        user_name='Test User',
        character='adina'
    )
    
    print(f"✅ Token created: {token[:40]}...")
    
    # Decode it to see what's in it
    parts = token.split('.')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    print(f"\n🔍 CORRECTED TOKEN PAYLOAD:")
    for key, value in payload.items():
        print(f"   {key}: {value}")
    
    print(f"\n🎯 GRANTS ANALYSIS:")
    video_grants = payload.get('video', {})
    if video_grants:
        print("   ✅ VIDEO GRANTS FOUND!")
        for key, value in video_grants.items():
            print(f"   {key}: {value}")
    else:
        print("   ❌ NO VIDEO GRANTS FOUND")
    
    # Check specific required grants
    required_grants = ['roomJoin', 'canPublish', 'canSubscribe', 'room']
    print(f"\n🔍 REQUIRED GRANTS CHECK:")
    for grant in required_grants:
        value = video_grants.get(grant, "❌ MISSING")
        status = "✅" if value else "❌"
        print(f"   {grant}: {value} {status}")
    
    print(f"\n🎉 CONCLUSION:")
    if video_grants and video_grants.get('roomJoin') and video_grants.get('room'):
        print("   ✅ TOKEN IS PROPERLY FORMATTED WITH GRANTS!")
        print("   ✅ This should resolve the 401 permission errors!")
    else:
        print("   ❌ Token still missing required grants")
    
except Exception as e:
    print(f"❌ Error creating token: {e}")
    import traceback
    traceback.print_exc() 