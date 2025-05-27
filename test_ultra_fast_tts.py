#!/usr/bin/env python3
"""
Ultra-Fast TTS Performance Test
Targeting sub-300ms first chunk latency
"""

import asyncio
import sys
import time
import logging
from dotenv import load_dotenv

# Add app directory to path
sys.path.append('python-voice-agent/app')

from services.livekit_deepgram_tts import LiveKitDeepgramTTS

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_ultra_fast_latency():
    """Test ultra-optimized TTS for sub-300ms latency"""
    
    print("🚀 Ultra-Fast TTS Latency Test")
    print("Target: Sub-300ms first chunk latency")
    print("=" * 50)
    
    tts = LiveKitDeepgramTTS()
    
    # Test phrases of different lengths
    test_phrases = [
        "Hello there!",  # Short phrase
        "I understand your concerns and I'm here to help you.",  # Medium phrase
        "Let's take a moment to breathe together and find some peace in this moment of uncertainty.",  # Longer phrase
    ]
    
    results = []
    
    for character in ["adina", "raffa"]:
        print(f"\n🎭 Testing {character.title()}:")
        print("-" * 30)
        
        tts.set_character(character)
        character_results = []
        
        for i, phrase in enumerate(test_phrases, 1):
            print(f"\n📝 Test {i}: '{phrase[:30]}...'")
            
            # Run multiple iterations for accuracy
            latencies = []
            
            for iteration in range(3):  # 3 iterations per phrase
                start_time = time.time()
                stream = tts.synthesize(phrase)
                
                first_chunk_received = False
                chunk_count = 0
                
                async for synthesized_audio in stream:
                    chunk_count += 1
                    
                    if not first_chunk_received:
                        first_chunk_latency = (time.time() - start_time) * 1000
                        latencies.append(first_chunk_latency)
                        first_chunk_received = True
                        print(f"   Iteration {iteration + 1}: {first_chunk_latency:.0f}ms")
                    
                    if chunk_count >= 2:  # Test first couple chunks
                        break
                
                # Small delay between iterations
                await asyncio.sleep(0.1)
            
            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            character_results.append({
                'phrase': phrase,
                'avg': avg_latency,
                'min': min_latency,
                'max': max_latency,
                'sub_300': avg_latency < 300
            })
            
            status = "✅" if avg_latency < 300 else "⚠️"
            print(f"   {status} Average: {avg_latency:.0f}ms (min: {min_latency:.0f}ms, max: {max_latency:.0f}ms)")
        
        results.append({
            'character': character,
            'results': character_results
        })
    
    await tts.aclose()
    
    # Summary Report
    print("\n📊 Ultra-Fast Latency Summary:")
    print("=" * 40)
    
    total_tests = 0
    sub_300_count = 0
    all_latencies = []
    
    for character_data in results:
        character = character_data['character']
        print(f"\n🎭 {character.title()}:")
        
        for result in character_data['results']:
            total_tests += 1
            if result['sub_300']:
                sub_300_count += 1
            all_latencies.append(result['avg'])
            
            status = "✅" if result['sub_300'] else "❌"
            print(f"   {status} {result['avg']:.0f}ms - '{result['phrase'][:25]}...'")
    
    # Overall statistics
    overall_avg = sum(all_latencies) / len(all_latencies)
    overall_min = min(all_latencies)
    overall_max = max(all_latencies)
    success_rate = (sub_300_count / total_tests) * 100
    
    print(f"\n🎯 Overall Performance:")
    print(f"   Average Latency: {overall_avg:.0f}ms")
    print(f"   Best Performance: {overall_min:.0f}ms")
    print(f"   Worst Performance: {overall_max:.0f}ms")
    print(f"   Sub-300ms Success Rate: {success_rate:.1f}% ({sub_300_count}/{total_tests})")
    
    # Performance verdict
    if overall_avg < 300:
        print(f"\n🎉 SUCCESS: Average latency {overall_avg:.0f}ms < 300ms target!")
        if success_rate >= 80:
            print("🚀 EXCELLENT: 80%+ tests achieved sub-300ms!")
        else:
            print("✅ GOOD: Average under 300ms but some outliers")
    else:
        print(f"\n⚠️ NEEDS IMPROVEMENT: Average {overall_avg:.0f}ms > 300ms target")
        print("💡 Consider further optimizations")
    
    # Optimization suggestions
    if overall_avg >= 300 or success_rate < 80:
        print("\n💡 Optimization Suggestions:")
        print("   • Use shorter test phrases")
        print("   • Check network latency to Deepgram")
        print("   • Consider edge/regional Deepgram endpoints")
        print("   • Optimize chunk size further")
        print("   • Pre-warm HTTP connections")
    
    return overall_avg < 300 and success_rate >= 80

if __name__ == "__main__":
    try:
        result = asyncio.run(test_ultra_fast_latency())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test error: {e}")
        sys.exit(1) 