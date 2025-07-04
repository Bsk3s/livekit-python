import asyncio
import logging
import os
# from services.openai_tts_service import OpenAITTSService  # Service moved to archived
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def check_api_keys():
    """Check if required API keys are set"""
    required_keys = ["OPENAI_API_KEY"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        print("\n❌ Missing required API keys:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nPlease set these environment variables before running the tests.")
        return False
    return True

async def test_latency():
    """Test latency for both voices"""
    print("\n=== Testing Voice Latency ===")
    tts_service = OpenAITTSService()
    test_text = "This is a latency test for spiritual guidance."
    
    latencies = []
    for character in ["adina", "raffa"]:
        print(f"\nTesting {character} latency...")
        character_latencies = []
        
        for run in range(3):  # 3 runs per character
            try:
                start = asyncio.get_event_loop().time()
                async for _ in tts_service.synthesize_streaming(test_text, character):
                    if character_latencies:  # First chunk only
                        break
                    latency = (asyncio.get_event_loop().time() - start) * 1000
                    character_latencies.append(latency)
                    print(f"Run {run + 1}: {latency:.0f}ms")
                    
            except Exception as e:
                print(f"Run {run + 1} failed: {e}")
                continue
                
        if character_latencies:
            avg_latency = sum(character_latencies) / len(character_latencies)
            print(f"\n{character} average latency: {avg_latency:.0f}ms")
            latencies.append((character, avg_latency))
    
    return latencies

async def test_error_recovery():
    """Test error handling and recovery"""
    print("\n=== Testing Error Recovery ===")
    tts_service = OpenAITTSService()
    
    # Test cases
    test_cases = [
        ("empty_text", "", "adina", ValueError),
        ("invalid_character", "Test message", "invalid", ValueError),
        ("long_text", "Test " * 1000, "adina", None),  # Should succeed
    ]
    
    results = []
    for name, text, character, expected_error in test_cases:
        print(f"\nTesting {name}...")
        try:
            async for _ in tts_service.synthesize_streaming(text, character):
                break
                
            if expected_error is None:
                print("✅ PASS - Expected success")
                results.append((name, True))
            else:
                print("❌ FAIL - Expected error but got success")
                results.append((name, False))
                
        except Exception as e:
            if expected_error and isinstance(e, expected_error):
                print(f"✅ PASS - Caught expected error: {e}")
                results.append((name, True))
            else:
                print(f"❌ FAIL - Unexpected error: {e}")
                results.append((name, False))
    
    return results

async def test_spiritual_voices():
    """Test both voices with spiritual content"""
    print("\n=== Testing Spiritual Voices ===")
    tts_service = OpenAITTSService()
    
    test_messages = {
        "adina": "Hello, I'm Adina, and I'm here to provide you with spiritual comfort and support. How can I help guide you today?",
        "raffa": "Peace be with you. I'm Raffa, your spiritual guide. I'm here to offer biblical wisdom and help you grow in your faith journey."
    }
    
    results = []
    for character, message in test_messages.items():
        print(f"\nTesting {character} voice...")
        try:
            chunk_count = 0
            start_time = asyncio.get_event_loop().time()
            
            async for audio_frame in tts_service.synthesize_streaming(message, character):
                chunk_count += 1
                
                if chunk_count == 1:
                    first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    print(f"✅ First chunk: {first_chunk_time:.0f}ms")
                
                # Test with first few chunks
                if chunk_count >= 5:
                    break
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            print(f"✅ Complete: {chunk_count} chunks, {total_time:.0f}ms total")
            results.append((character, True))
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append((character, False))
    
    return results

async def main():
    """Run all tests"""
    print("Starting voice pipeline tests...")
    
    # Check API keys first
    if not check_api_keys():
        return
    
    # Test latency
    latencies = await test_latency()
    print("\nLatency Summary:")
    for character, latency in latencies:
        print(f"{character}: {latency:.0f}ms")
    
    # Test error recovery
    error_results = await test_error_recovery()
    print("\nError Recovery Summary:")
    for name, passed in error_results:
        print(f"{name}: {'✅ PASS' if passed else '❌ FAIL'}")
    
    # Test spiritual voices
    voice_results = await test_spiritual_voices()
    print("\nVoice Test Summary:")
    for character, passed in voice_results:
        print(f"{character}: {'✅ PASS' if passed else '❌ FAIL'}")
    
    # Overall results
    total_tests = len(error_results) + len(voice_results)
    passed_tests = sum(1 for _, passed in error_results + voice_results if passed)
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")

if __name__ == "__main__":
    asyncio.run(main())

print('test file created') 