#!/usr/bin/env python3
import os
import sys
import subprocess
import json

print("🔍 DEBUGGING TOKEN CREDENTIALS MISMATCH")
print("=" * 50)

# Test 1: Get token from backend using curl
print("📡 Getting token from backend...")
try:
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', 
        'https://heavenly-new.onrender.com/api/generate-token',
        '-H', 'Content-Type: application/json',
        '-d', '{"room": "test-room", "identity": "test-user", "character": "adina"}'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        token = data['token']
        print(f"✅ Token received: {token[:30]}...")
        
        # Decode token to see credentials (base64 decode the payload)
        import base64
        import json
        
        # JWT has 3 parts: header.payload.signature
        parts = token.split('.')
        if len(parts) == 3:
            # Decode payload (add padding if needed)
            payload_b64 = parts[1]
            # Add padding if needed
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            
            print("\n🔍 TOKEN ANALYSIS:")
            print(f"API Key (iss): {payload.get('iss', 'NOT_SET')}")
            print(f"Subject: {payload.get('sub', 'NOT_SET')}")
            print(f"Room: {payload.get('room', 'NOT_SET')}")
            
            print("\n🎯 CREDENTIAL COMPARISON:")
            expected_key = "APIjsXZYsEhhs8h"
            actual_key = payload.get('iss', 'NOT_SET')
            print(f"Expected: {expected_key}")
            print(f"Actual:   {actual_key}")
            
            if actual_key == expected_key:
                print("✅ CREDENTIALS MATCH!")
                print("❓ The issue might be elsewhere...")
            else:
                print("❌ CREDENTIALS MISMATCH!")
                print("🔧 This is the problem - backend using wrong credentials!")
                
        else:
            print("❌ Invalid JWT format")
            
    else:
        print(f"❌ Failed to get token: {result.stderr}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 50)
print("🎯 EXPECTED LIVEKIT CREDENTIALS:")
print("LIVEKIT_URL=wss://hb-j73yzwmu.livekit.cloud")
print("LIVEKIT_API_KEY=APIjsXZYsEhhs8h") 
print("LIVEKIT_API_SECRET=h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM") 