#!/usr/bin/env python3
"""
Test script for streaming Deepgram STT implementation
This will test the WebSocket connection and latency performance
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent / "python-voice-agent"
sys.path.insert(0, str(project_root))

from spiritual_voice_agent.services.stt.implementations.streaming_deepgram import StreamingDeepgramSTTService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_streaming_connection():
    """Test WebSocket connection and basic functionality"""
    logger.info("🧪 Testing Streaming Deepgram Connection...")
    
    # Check API key
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("❌ DEEPGRAM_API_KEY not set")
        return False
    
    logger.info(f"🔑 API Key found: {api_key[:8]}...")
    
    # Create service
    service = StreamingDeepgramSTTService({
        "model": "nova-2",
        "language": "en-US"
    })
    
    # Track transcription results
    transcriptions = []
    latencies = []
    
    async def transcription_handler(text: str, is_final: bool, confidence: float, latency_ms: float):
        status = "FINAL" if is_final else "interim"
        logger.info(f"📝 {status}: '{text}' (confidence: {confidence:.2f}, latency: {latency_ms:.1f}ms)")
        
        if is_final:
            transcriptions.append(text)
            if latency_ms:
                latencies.append(latency_ms)
    
    try:
        # Set callback and initialize
        service.set_transcription_callback(transcription_handler)
        await service.initialize()
        
        if not service.is_connected:
            logger.error("❌ Failed to connect to Deepgram WebSocket")
            return False
            
        logger.info("✅ WebSocket connected successfully")
        
        # Test with silent audio first
        logger.info("🎤 Testing with silent audio...")
        silent_audio = b"\x00\x00" * 8000  # 0.5 seconds of silence
        await service.send_audio_chunk(silent_audio)
        await asyncio.sleep(1)
        
        # Test with synthetic audio pattern
        logger.info("🎤 Testing with synthetic audio pattern...")
        # Create a simple tone pattern (not real speech, but will test pipeline)
        test_audio = bytearray()
        for i in range(16000):  # 1 second at 16kHz
            # Simple sine wave pattern
            sample = int(1000 * (i % 100) / 100)  # Simple repeating pattern
            test_audio.extend(sample.to_bytes(2, 'little', signed=True))
        
        # Send in chunks to simulate real audio streaming
        chunk_size = 1600  # 0.1 second chunks
        for i in range(0, len(test_audio), chunk_size):
            chunk = test_audio[i:i + chunk_size]
            await service.send_audio_chunk(chunk)
            await asyncio.sleep(0.1)  # Real-time simulation
            
        # Wait for any final results
        logger.info("⏳ Waiting for final results...")
        await asyncio.sleep(3)
        
        # Performance summary
        logger.info("📊 TEST RESULTS:")
        logger.info(f"   Transcriptions received: {len(transcriptions)}")
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            logger.info(f"   Average latency: {avg_latency:.1f}ms")
            logger.info(f"   Min latency: {min_latency:.1f}ms")
            logger.info(f"   Max latency: {max_latency:.1f}ms")
            
            if avg_latency < 200:
                logger.info("🎯 ✅ EXCELLENT: Sub-200ms average latency achieved!")
            elif avg_latency < 500:
                logger.info("🎯 ✅ GOOD: Sub-500ms average latency achieved!")
            else:
                logger.info("🎯 ⚠️ SLOW: Latency above 500ms - check network/config")
        else:
            logger.info("   No latency data available")
            
        await service.shutdown()
        
        if service.is_connected:
            logger.error("❌ Service still connected after shutdown")
            return False
            
        logger.info("✅ Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_latency_benchmark():
    """Benchmark latency with multiple runs"""
    logger.info("🏃 Running latency benchmark...")
    
    service = StreamingDeepgramSTTService({
        "model": "nova-2", 
        "language": "en-US"
    })
    
    latencies = []
    
    async def benchmark_handler(text: str, is_final: bool, confidence: float, latency_ms: float):
        if is_final and latency_ms:
            latencies.append(latency_ms)
            logger.info(f"📊 Run {len(latencies)}: {latency_ms:.1f}ms - '{text}'")
    
    try:
        service.set_transcription_callback(benchmark_handler)
        await service.initialize()
        
        # Run 5 benchmark tests
        test_audio = b"\x01\x02" * 8000  # 0.5 second test pattern
        
        for run in range(5):
            logger.info(f"🏃 Benchmark run {run + 1}/5")
            await service.send_audio_chunk(test_audio)
            await asyncio.sleep(2)  # Wait between runs
            
        await service.shutdown()
        
        if latencies:
            avg = sum(latencies) / len(latencies)
            logger.info(f"📊 BENCHMARK RESULTS:")
            logger.info(f"   Runs: {len(latencies)}")
            logger.info(f"   Average: {avg:.1f}ms")
            logger.info(f"   Best: {min(latencies):.1f}ms")
            logger.info(f"   Worst: {max(latencies):.1f}ms")
            
            return avg < 200  # Success if under 200ms average
        else:
            logger.warning("⚠️ No benchmark data collected")
            return False
            
    except Exception as e:
        logger.error(f"❌ Benchmark failed: {e}")
        return False


async def main():
    """Run all tests"""
    logger.info("🚀 Starting Deepgram Streaming STT Tests")
    
    # Test 1: Basic connection
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Basic WebSocket Connection")
    logger.info("="*50)
    
    connection_success = await test_streaming_connection()
    
    if not connection_success:
        logger.error("❌ Basic connection test failed - stopping here")
        return False
    
    # Test 2: Latency benchmark
    logger.info("\n" + "="*50)
    logger.info("TEST 2: Latency Benchmark")
    logger.info("="*50)
    
    benchmark_success = await test_latency_benchmark()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("FINAL RESULTS")
    logger.info("="*50)
    
    if connection_success and benchmark_success:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("✅ Streaming Deepgram is ready for production")
        logger.info("🎯 Expected latency: <200ms (excellent for real-time)")
        return True
    else:
        logger.error("❌ Some tests failed")
        logger.error("💡 Try checking:")
        logger.error("   - DEEPGRAM_API_KEY is valid")
        logger.error("   - Internet connection is stable")
        logger.error("   - WebSocket not blocked by firewall")
        return False


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)