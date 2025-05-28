#!/usr/bin/env python3
"""
Test script for Render deployment of Spiritual Guidance Voice Agent API
"""

import requests
import json
import time
from datetime import datetime

# Possible Render URLs to test
POSSIBLE_URLS = [
    "https://spiritual-token-api.onrender.com",
    "https://spiritual-token-api-latest.onrender.com", 
    "https://spiritual-guidance-api.onrender.com",
    "https://heavenly-hub-api.onrender.com",
    # Add your actual Render URL here when you find it
]

def test_endpoint(base_url: str, endpoint: str = "/"):
    """Test a specific endpoint"""
    try:
        url = f"{base_url}{endpoint}"
        print(f"🔍 Testing: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ SUCCESS: {url}")
            print(f"   Status: {response.status_code}")
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
            except:
                print(f"   Response: {response.text[:200]}...")
            return True
        else:
            print(f"❌ FAILED: {url} - Status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {url} - {str(e)}")
        return False

def test_token_generation(base_url: str):
    """Test token generation endpoint"""
    try:
        url = f"{base_url}/api/spiritual-token"
        payload = {
            "character": "adina",
            "user_id": "test-user-123"
        }
        
        print(f"🔍 Testing token generation: {url}")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ TOKEN SUCCESS: {url}")
            data = response.json()
            print(f"   Token generated for character: {data.get('character', 'unknown')}")
            print(f"   Room: {data.get('room_name', 'unknown')}")
            return True
        else:
            print(f"❌ TOKEN FAILED: {url} - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ TOKEN ERROR: {url} - {str(e)}")
        return False

def main():
    """Main test function"""
    print("🌟 Testing Render Deployment of Spiritual Guidance Voice Agent API")
    print(f"🕐 Test started at: {datetime.now().isoformat()}")
    print("=" * 70)
    
    working_urls = []
    
    # Test all possible URLs
    for base_url in POSSIBLE_URLS:
        print(f"\n🔗 Testing base URL: {base_url}")
        print("-" * 50)
        
        # Test root endpoint
        if test_endpoint(base_url, "/"):
            working_urls.append(base_url)
            
            # Test health endpoint
            test_endpoint(base_url, "/health")
            
            # Test docs endpoint
            test_endpoint(base_url, "/docs")
            
            # Test token generation
            test_token_generation(base_url)
    
    print("\n" + "=" * 70)
    print("📊 DEPLOYMENT TEST SUMMARY")
    print("=" * 70)
    
    if working_urls:
        print(f"✅ Found {len(working_urls)} working URL(s):")
        for url in working_urls:
            print(f"   🔗 {url}")
        
        print(f"\n🎯 Your API is successfully deployed!")
        print(f"📖 API Documentation: {working_urls[0]}/docs")
        print(f"🏥 Health Check: {working_urls[0]}/health")
        print(f"🎭 Token Generation: {working_urls[0]}/api/spiritual-token")
        
        print(f"\n📱 For mobile testing, use this base URL:")
        print(f"   {working_urls[0]}")
        
    else:
        print("❌ No working URLs found!")
        print("\n🔍 Troubleshooting steps:")
        print("1. Check your Render dashboard for the actual service URL")
        print("2. Verify the service is running and not crashed")
        print("3. Check environment variables are set correctly")
        print("4. Review deployment logs for errors")
        
        print(f"\n💡 Manual URL check:")
        print(f"   Go to your Render dashboard and find the actual URL")
        print(f"   Then test manually: curl https://YOUR-ACTUAL-URL.onrender.com/health")

if __name__ == "__main__":
    main() 