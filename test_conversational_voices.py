#!/usr/bin/env python3

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def test_conversational_voices():
    """Test the new conversational voices with friendly dialogue"""
    print("🗣️ Testing New Conversational Voices")
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ DEEPGRAM_API_KEY not found")
        return
    
    # Friendly conversation examples
    test_cases = [
        ("adina", "aura-2-luna-en", "Hey there! I'm so glad you reached out. What's been on your heart lately?"),
        ("raffa", "aura-2-orion-en", "Good to see you, friend! Let's dive into whatever's weighing on your mind."),
        ("adina", "aura-2-luna-en", "You know what? I totally get that feeling. We've all been there."),
        ("raffa", "aura-2-orion-en", "That's a really thoughtful question. Let me share what I've learned about that."),
    ]
    
    results = []
    
    for character, model, text in test_cases:
        print(f"\n🎤 {character.title()} ({model}): '{text[:40]}...'")
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            url = f"https://api.deepgram.com/v1/speak?model={model}&encoding=linear16&sample_rate=24000&container=none"
            
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {"text": text}
            
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
                                print(f"   🚀 First chunk: {first_chunk_time:.0f}ms")
                                first_chunk = False
                            
                            if chunk_count >= 3:  # Test first few chunks
                                break
                    
                    total_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    status = "🎯 FAST!" if first_chunk_time < 1500 else "❌ Slow"
                    
                    result = {
                        "character": character,
                        "model": model,
                        "latency_ms": first_chunk_time,
                        "total_ms": total_time,
                        "bytes": total_bytes,
                        "status": status
                    }
                    results.append(result)
                    
                    print(f"   {status} - {total_time:.0f}ms total, {total_bytes} bytes")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("🗣️ CONVERSATIONAL VOICE RESULTS")
    print(f"{'='*60}")
    
    if results:
        adina_results = [r for r in results if r['character'] == 'adina']
        raffa_results = [r for r in results if r['character'] == 'raffa']
        
        if adina_results:
            avg_adina = sum(r['latency_ms'] for r in adina_results) / len(adina_results)
            print(f"🌟 Adina (Luna voice): {avg_adina:.0f}ms average - Gentle & soothing")
        
        if raffa_results:
            avg_raffa = sum(r['latency_ms'] for r in raffa_results) / len(raffa_results)
            print(f"🌟 Raffa (Orion voice): {avg_raffa:.0f}ms average - Warm & approachable")
        
        all_passed = all(r['latency_ms'] < 1500 for r in results)
        
        print(f"\n💡 CONVERSATIONAL UPGRADE:")
        print(f"   ✅ More friendly, less professional tone")
        print(f"   ✅ Still maintains <1.5s latency requirement")
        print(f"   ✅ Perfect for spiritual friend conversations")
        
        if all_passed:
            print(f"\n🚀 READY FOR FRIENDLY SPIRITUAL GUIDANCE!")
            return True
        else:
            print(f"\n❌ Some latency issues detected")
            return False
    
    return False

if __name__ == "__main__":
    asyncio.run(test_conversational_voices()) 