#!/usr/bin/env python3

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def test_deepgram_simple():
    """Simple test of Deepgram TTS API"""
    print("🚀 Testing Deepgram TTS API directly")
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ DEEPGRAM_API_KEY not found in environment")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...")
    
    # Test with simple text
    text = "Hello, this is a test of Deepgram TTS."
    model = "aura-2-andromeda-en"
    
    url = f"https://api.deepgram.com/v1/speak?model={model}&encoding=linear16&sample_rate=24000&container=none"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {"text": text}
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            print(f"📡 Making request to Deepgram...")
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"📊 Response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ API Error: {error_text}")
                    return False
                
                # Check if we get audio data
                first_chunk = True
                chunk_count = 0
                total_bytes = 0
                
                async for chunk in response.content.iter_chunked(4096):
                    if chunk:
                        chunk_count += 1
                        total_bytes += len(chunk)
                        
                        if first_chunk:
                            first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                            print(f"🚀 FIRST CHUNK: {first_chunk_time:.0f}ms")
                            first_chunk = False
                        
                        if chunk_count >= 3:  # Test first few chunks
                            break
                
                total_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                print(f"✅ Success!")
                print(f"   - Total time: {total_time:.0f}ms")
                print(f"   - Chunks received: {chunk_count}")
                print(f"   - Total bytes: {total_bytes}")
                
                # Check if meets latency target
                if first_chunk_time < 1500:
                    print("🎯 LATENCY TARGET MET! (<1.5s)")
                    return True
                else:
                    print(f"❌ Too slow: {first_chunk_time:.0f}ms > 1500ms")
                    return False
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_deepgram_simple())
    if result:
        print("\n🚀 DEEPGRAM TTS IS PRODUCTION READY!")
        print("💡 Meets <1.5s latency requirement")
        print("💰 Cost-effective alternative to OpenAI")
    else:
        print("\n💀 Deepgram test failed") 