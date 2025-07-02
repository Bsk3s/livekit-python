#!/usr/bin/env python3

import asyncio
import time
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def test_openai_tts_latency():
    """Test OpenAI TTS latency with different models and settings"""
    print("🚀 Testing OpenAI TTS Latency")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment")
        return False
    
    client = AsyncOpenAI(api_key=api_key)
    
    # Test cases
    test_cases = [
        ("short", "Hello, I'm here to guide you."),
        ("medium", "Welcome to our spiritual guidance session. I'm here to provide you with compassionate support."),
        ("long", "In this moment of connection, I want you to know that you are not alone on your spiritual journey. Together we can explore the depths of your soul and find the peace you seek.")
    ]
    
    # Test configurations
    configs = [
        {"model": "tts-1", "voice": "alloy", "name": "TTS-1 (Fast)"},
        {"model": "tts-1-hd", "voice": "alloy", "name": "TTS-1-HD (Quality)"},
        {"model": "tts-1", "voice": "onyx", "name": "TTS-1 Onyx (Male)"},
    ]
    
    results = []
    
    for config in configs:
        print(f"\n=== Testing {config['name']} ===")
        
        for test_name, test_text in test_cases:
            print(f"\n--- {test_name} text ({len(test_text)} chars) ---")
            
            try:
                start_time = time.perf_counter()
                
                # Test with streaming
                response = await client.audio.speech.create(
                    model=config["model"],
                    voice=config["voice"],
                    input=test_text,
                    response_format="pcm",
                    speed=1.0
                )
                
                # Measure first chunk
                first_chunk_time = None
                chunk_count = 0
                total_bytes = 0
                
                async for chunk in response.iter_bytes(chunk_size=4096):
                    chunk_count += 1
                    total_bytes += len(chunk)
                    
                    if chunk_count == 1:
                        first_chunk_time = (time.perf_counter() - start_time) * 1000
                        print(f"🚀 FIRST CHUNK: {first_chunk_time:.0f}ms")
                    
                    if chunk_count >= 5:  # Test first few chunks
                        break
                
                total_time = (time.perf_counter() - start_time) * 1000
                
                # Check if meets target
                status = "🎯 TARGET MET!" if first_chunk_time and first_chunk_time < 1500 else "❌ Too slow"
                
                result = {
                    "config": config["name"],
                    "test": test_name,
                    "first_chunk_ms": first_chunk_time,
                    "total_ms": total_time,
                    "chunks": chunk_count,
                    "bytes": total_bytes,
                    "status": status
                }
                results.append(result)
                
                print(f"   {status}")
                print(f"   First chunk: {first_chunk_time:.0f}ms")
                print(f"   Total time: {total_time:.0f}ms")
                print(f"   Chunks: {chunk_count}, Bytes: {total_bytes}")
                
            except Exception as e:
                print(f"❌ ERROR: {e}")
                results.append({
                    "config": config["name"],
                    "test": test_name,
                    "error": str(e),
                    "status": "❌ ERROR"
                })
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 OPENAI TTS LATENCY SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results if "TARGET MET" in r.get("status", ""))
    total_tests = len([r for r in results if "error" not in r])
    
    print(f"🎯 Tests under 1.5s: {passed}/{total_tests}")
    
    # Show averages by model
    for config in configs:
        config_results = [r for r in results if r.get("config") == config["name"] and "first_chunk_ms" in r]
        if config_results:
            avg_latency = sum(r["first_chunk_ms"] for r in config_results) / len(config_results)
            print(f"📈 {config['name']} average: {avg_latency:.0f}ms")
    
    print(f"\n🔥 COMPARISON WITH DEEPGRAM:")
    print(f"   Deepgram Aura-2: ~330ms ✅")
    print(f"   OpenAI Best: {min(r.get('first_chunk_ms', 9999) for r in results if 'first_chunk_ms' in r):.0f}ms")
    
    if passed >= total_tests * 0.8:
        print("\n🚀 OpenAI TTS meets latency requirements!")
        return True
    else:
        print("\n💀 OpenAI TTS too slow for real-time use")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_openai_tts_latency()) 