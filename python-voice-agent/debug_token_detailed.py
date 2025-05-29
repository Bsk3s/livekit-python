#!/usr/bin/env python3
import subprocess
import json
import base64

print("🔍 DETAILED TOKEN ANALYSIS")
print("=" * 60)

# Get token from backend
print("📡 Getting token from backend...")
result = subprocess.run([
    'curl', '-s', '-X', 'POST', 
    'https://heavenly-new.onrender.com/api/generate-token',
    '-H', 'Content-Type: application/json',
    '-d', '{"room": "spiritual-adina-test", "identity": "test-user", "character": "adina"}'
], capture_output=True, text=True)

if result.returncode == 0:
    data = json.loads(result.stdout)
    token = data['token']
    room_name = data['room']
    ws_url = data['wsUrl']
    
    print(f"✅ Backend Response:")
    print(f"   Room: {room_name}")
    print(f"   WebSocket URL: {ws_url}")
    print(f"   Token: {token[:40]}...")
    
    # Decode JWT
    parts = token.split('.')
    
    # Decode header
    header_b64 = parts[0] + '=' * (4 - len(parts[0]) % 4)
    header = json.loads(base64.urlsafe_b64decode(header_b64))
    
    # Decode payload
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    print(f"\n🔍 JWT HEADER:")
    for key, value in header.items():
        print(f"   {key}: {value}")
    
    print(f"\n🔍 JWT PAYLOAD:")
    for key, value in payload.items():
        print(f"   {key}: {value}")
    
    # Analyze video grants (using camelCase field names)
    video_grants = payload.get('video', {})
    print(f"\n🎯 PERMISSION ANALYSIS:")
    
    # Check camelCase field names as they appear in JWT
    camel_case_grants = {
        'roomJoin': 'room_join',
        'canPublish': 'can_publish', 
        'canSubscribe': 'can_subscribe',
        'canPublishData': 'can_publish_data',
        'roomCreate': 'room_create'
    }
    
    for camel_field, snake_field in camel_case_grants.items():
        value = video_grants.get(camel_field, "❌ MISSING")
        status = "✅" if value == True else "❌"
        print(f"   {snake_field}: {value} {status}")
    
    # Room analysis
    print(f"\n🏠 ROOM ANALYSIS:")
    print(f"   Backend returned room: {room_name}")
    token_room = video_grants.get('room', 'NOT_SET')
    print(f"   Token contains room: {token_room}")
    room_match = "✅" if token_room == room_name else "❌"
    print(f"   Room match: {room_match}")
    
    # Identity analysis
    print(f"\n👤 IDENTITY ANALYSIS:")
    identity = payload.get('sub', 'NOT_SET')
    print(f"   Token identity: {identity}")
    print(f"   Expected format: user_[identity]")
    
    # Final diagnosis
    print(f"\n🔧 DIAGNOSIS:")
    if video_grants and video_grants.get('roomJoin') and video_grants.get('room'):
        print("✅ SUCCESS: Token contains proper video grants!")
        print("✅ This should resolve the 401 permission errors!")
        print("✅ The iOS app should now be able to connect!")
    else:
        print("❌ PROBLEM: Token missing room information!")
        print("   This causes 401 'no permissions to access the room'")
        print("   Fix: Ensure token includes room in grants")
        
else:
    print(f"❌ Failed to get token: {result.stderr}") 