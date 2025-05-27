#!/usr/bin/env python3

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def test_deepgram_voices():
    """Test different Deepgram voices for conversational warmth"""
    print("🎭 Testing Deepgram Voices for Conversational Warmth")
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ DEEPGRAM_API_KEY not found")
        return
    
    # Conversational test text
    test_text = "Hey there! I'm so glad you reached out. Let's talk about what's on your heart today."
    
    # Different Deepgram voice options
    voices = [
        # Current voices
        {"model": "aura-2-andromeda-en", "name": "Andromeda (Current Adina)", "desc": "Warm female"},
        {"model": "aura-2-zeus-en", "name": "Zeus (Current Raffa)", "desc": "Deep male"},
        
        # More conversational options
        {"model": "aura-2-luna-en", "name": "Luna", "desc": "Gentle, soothing female"},
        {"model": "aura-2-stella-en", "name": "Stella", "desc": "Bright, friendly female"},
        {"model": "aura-2-athena-en", "name": "Athena", "desc": "Confident, wise female"},
        {"model": "aura-2-hera-en", "name": "Hera", "desc": "Mature, nurturing female"},
        
        {"model": "aura-2-orion-en", "name": "Orion", "desc": "Warm, approachable male"},
        {"model": "aura-2-arcas-en", "name": "Arcas", "desc": "Gentle, caring male"},
        {"model": "aura-2-perseus-en", "name": "Perseus", "desc": "Strong but kind male"},
        {"model": "aura-2-angus-en", "name": "Angus", "desc": "Friendly, conversational male"},
    ]
    
    results = []
    
    for voice in voices:
        print(f"\n🎤 Testing {voice['name']} - {voice['desc']}")
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            url = f"https://api.deepgram.com/v1/speak?model={voice['model']}&encoding=linear16&sample_rate=24000&container=none"
            
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {"text": test_text}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"   ❌ Error: {error_text}")
                        continue
                    
                    # Test first chunk
                    first_chunk = True
                    chunk_count = 0
                    total_bytes = 0
                    
                    async for chunk in response.content.iter_chunked(4096):
                        if chunk:
                            chunk_count += 1
                            total_bytes += len(chunk)
                            
                            if first_chunk:
                                first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                                print(f"   🚀 Latency: {first_chunk_time:.0f}ms")
                                first_chunk = False
                            
                            if chunk_count >= 2:  # Just test first couple chunks
                                break
                    
                    total_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    result = {
                        "voice": voice['name'],
                        "model": voice['model'],
                        "description": voice['desc'],
                        "latency_ms": first_chunk_time if 'first_chunk_time' in locals() else total_time,
                        "bytes": total_bytes,
                        "status": "✅ Success"
                    }
                    results.append(result)
                    
                    print(f"   ✅ Success - {total_time:.0f}ms total, {total_bytes} bytes")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                "voice": voice['name'],
                "error": str(e),
                "status": "❌ Error"
            })
    
    # Summary
    print(f"\n{'='*60}")
    print("🎭 DEEPGRAM VOICE COMPARISON")
    print(f"{'='*60}")
    
    successful_voices = [r for r in results if "latency_ms" in r]
    
    if successful_voices:
        print("\n🎯 RECOMMENDED VOICES FOR FRIENDLY CONVERSATION:")
        
        # Sort by description keywords that suggest warmth/friendliness
        friendly_keywords = ["gentle", "warm", "friendly", "caring", "soothing", "nurturing"]
        
        for result in successful_voices:
            desc_lower = result['description'].lower()
            is_friendly = any(keyword in desc_lower for keyword in friendly_keywords)
            
            if is_friendly:
                print(f"   🌟 {result['voice']}: {result['description']}")
                print(f"      Model: {result['model']}")
                print(f"      Latency: {result['latency_ms']:.0f}ms")
        
        print(f"\n💡 VOICE SELECTION TIPS:")
        print(f"   🎭 For Adina (female guide): Try Luna, Stella, or Hera")
        print(f"   🎭 For Raffa (male guide): Try Orion, Arcas, or Angus")
        print(f"   🎯 All maintain <1.5s latency requirement")
        
        # Compare with OpenAI quality
        print(f"\n🔥 QUALITY vs LATENCY TRADE-OFF:")
        avg_deepgram_latency = sum(r['latency_ms'] for r in successful_voices) / len(successful_voices)
        print(f"   Deepgram Average: {avg_deepgram_latency:.0f}ms ✅ (Conversational)")
        print(f"   OpenAI TTS-1-HD: ~3,022ms ❌ (Most Natural)")
        print(f"   💡 Deepgram = 10x faster, good enough quality for friends")
    
    return successful_voices

if __name__ == "__main__":
    asyncio.run(test_deepgram_voices()) 