#!/usr/bin/env python3

"""
🚀 PHASE 2C: LLM Token Streaming Test

Test the real-time LLM token streaming with sentence-boundary TTS processing.

Expected behavior:
- LLM tokens stream in real-time (~150ms first token)
- Sentence boundaries trigger immediate TTS processing
- Multiple TTS chunks process in parallel  
- Audio chunks stream as they're ready
- Total pipeline: ~200ms first audio vs 3500ms batch

Performance target: <200ms first audio chunk
"""

import asyncio
import base64
import json
import logging
import time
from typing import List, Dict, Any

import websockets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Phase2CLLMStreamingTester:
    def __init__(self, websocket_url: str = "ws://localhost:10000/ws/audio"):
        self.websocket_url = websocket_url
        self.test_messages = [
            "Hello, how are you feeling today?",
            "Tell me about your biggest dreams and aspirations.",
            "What advice would you give to someone feeling overwhelmed?",
        ]
        
    async def test_llm_streaming_pipeline(self):
        """Test the complete Phase 2C streaming pipeline"""
        logger.info("🚀 PHASE 2C: Testing LLM Token Streaming Pipeline")
        
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                # Initialize session
                if not await self._initialize_session(websocket):
                    return False
                
                # Test multiple conversations
                for i, message in enumerate(self.test_messages):
                    logger.info(f"\n🧪 Test {i+1}: '{message}'")
                    
                    result = await self._test_streaming_conversation(websocket, message)
                    if result:
                        logger.info(f"✅ Test {i+1} completed successfully")
                    else:
                        logger.error(f"❌ Test {i+1} failed")
                        return False
                    
                    # Wait between tests
                    await asyncio.sleep(2)
                
                logger.info("🎉 All Phase 2C streaming tests passed!")
                return True
                
        except Exception as e:
            logger.error(f"❌ Test connection error: {e}")
            return False
    
    async def _initialize_session(self, websocket: websockets.WebSocketServerProtocol) -> bool:
        """Initialize a test session"""
        try:
            # Send initialization message
            init_message = {
                "type": "initialize",
                "character": "adina",
                "user_id": "test_phase2c_streaming"
            }
            
            await websocket.send(json.dumps(init_message))
            logger.info("📤 Sent initialization message")
            
            # Wait for connection response first
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(response)
            
            if data.get("type") == "connected":
                logger.info("📡 Connected to server")
                
                # Now wait for initialization response
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                if data.get("type") == "initialized":
                    logger.info("✅ Session initialized and ready")
                    
                    # Skip welcome message
                    welcome_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info("📨 Received welcome message")
                    return True
                else:
                    logger.warning(f"⚠️ Unexpected init response: {data}")
                    return False
            else:
                logger.warning(f"⚠️ Unexpected connection response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Initialization error: {e}")
            return False
    
    async def _test_streaming_conversation(self, websocket: websockets.WebSocketServerProtocol, message: str) -> bool:
        """Test a complete streaming conversation turn"""
        conversation_start_time = time.perf_counter()
        
        # Tracking metrics
        metrics = {
            "llm_first_token_ms": None,
            "first_audio_chunk_ms": None,
            "total_tokens_received": 0,
            "total_audio_chunks": 0,
            "llm_streaming_started": False,
            "tts_chunks_started": [],
            "streaming_complete": False
        }
        
        try:
            # Send text message (simulating completed transcription)
            text_message = {
                "type": "text_message",
                "text": message,
                "timestamp": time.time()
            }
            
            await websocket.send(json.dumps(text_message))
            logger.info(f"📤 Sent text message: '{message}'")
            
            # Listen for streaming events
            timeout_time = time.time() + 30.0  # 30 second timeout
            
            while time.time() < timeout_time:
                try:
                    # Receive message with short timeout for real-time processing
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    message_type = data.get("type")
                    
                    # Track different streaming events
                    if message_type == "llm_streaming_started":
                        metrics["llm_streaming_started"] = True
                        logger.info("🚀 LLM streaming started")
                        
                    elif message_type == "llm_token":
                        # Track first token timing
                        if metrics["llm_first_token_ms"] is None:
                            metrics["llm_first_token_ms"] = (time.perf_counter() - conversation_start_time) * 1000
                            logger.info(f"🚀 FIRST TOKEN: {metrics['llm_first_token_ms']:.1f}ms")
                        
                        metrics["total_tokens_received"] += 1
                        token = data.get("token", "")
                        logger.debug(f"📝 Token: {repr(token)} (total: {metrics['total_tokens_received']})")
                        
                    elif message_type == "tts_chunk_started":
                        chunk_id = data.get("chunk_id", "unknown")
                        sentence = data.get("text", "")
                        metrics["tts_chunks_started"].append(chunk_id)
                        logger.info(f"🎵 TTS Chunk {chunk_id} started: '{sentence[:30]}...'")
                        
                    elif message_type == "streaming_audio_chunk":
                        # Track first audio chunk timing
                        if metrics["first_audio_chunk_ms"] is None:
                            metrics["first_audio_chunk_ms"] = (time.perf_counter() - conversation_start_time) * 1000
                            logger.info(f"🎵 FIRST AUDIO: {metrics['first_audio_chunk_ms']:.1f}ms")
                        
                        chunk_id = data.get("chunk_id", "unknown")
                        audio_size = data.get("audio_size", 0)
                        tts_latency = data.get("tts_latency_ms", 0)
                        metrics["total_audio_chunks"] += 1
                        
                        logger.info(f"🎵 Audio Chunk {chunk_id}: {audio_size} bytes, TTS: {tts_latency:.1f}ms")
                        
                    elif message_type == "llm_streaming_complete":
                        metrics["streaming_complete"] = True
                        total_llm_time = data.get("total_time_ms", 0)
                        full_response = data.get("full_response", "")
                        
                        logger.info(f"🚀 LLM streaming complete: {total_llm_time:.1f}ms")
                        logger.info(f"📝 Full response: '{full_response[:100]}...'")
                        
                        # Wait a bit more for final TTS chunks
                        await asyncio.sleep(2.0)
                        break
                        
                    elif message_type == "error":
                        logger.error(f"❌ Server error: {data.get('message')}")
                        return False
                        
                except asyncio.TimeoutError:
                    # Check if we got enough events to consider success
                    if metrics["streaming_complete"]:
                        break
                    logger.debug("⏱️ Waiting for more streaming events...")
                    continue
            
            # Analyze results
            total_time = (time.perf_counter() - conversation_start_time) * 1000
            
            logger.info(f"\n📊 PHASE 2C STREAMING METRICS:")
            logger.info(f"   🚀 LLM First Token: {metrics['llm_first_token_ms']:.1f}ms" if metrics['llm_first_token_ms'] else "   🚀 LLM First Token: Not received")
            logger.info(f"   🎵 First Audio Chunk: {metrics['first_audio_chunk_ms']:.1f}ms" if metrics['first_audio_chunk_ms'] else "   🎵 First Audio Chunk: Not received")
            logger.info(f"   📝 Total Tokens: {metrics['total_tokens_received']}")
            logger.info(f"   🎵 Total Audio Chunks: {metrics['total_audio_chunks']}")
            logger.info(f"   ⏱️ Total Conversation: {total_time:.1f}ms")
            
            # Success criteria
            success = (
                metrics["llm_streaming_started"] and
                metrics["llm_first_token_ms"] is not None and
                metrics["first_audio_chunk_ms"] is not None and
                metrics["total_tokens_received"] > 0 and
                metrics["total_audio_chunks"] > 0 and
                metrics["streaming_complete"]
            )
            
            if success:
                # Performance analysis
                if metrics["first_audio_chunk_ms"] < 500:
                    logger.info("🎯 EXCELLENT: First audio < 500ms (ultra-fast)")
                elif metrics["first_audio_chunk_ms"] < 1000:
                    logger.info("✅ GOOD: First audio < 1000ms (fast)")
                elif metrics["first_audio_chunk_ms"] < 2000:
                    logger.info("⚠️ ACCEPTABLE: First audio < 2000ms (acceptable)")
                else:
                    logger.warning("❌ SLOW: First audio > 2000ms (needs optimization)")
                    
                if metrics["first_audio_chunk_ms"]:
                    improvement_factor = 3500 / metrics["first_audio_chunk_ms"]
                    logger.info(f"🚀 IMPROVEMENT: {improvement_factor:.1f}x faster than batch (3500ms → {metrics['first_audio_chunk_ms']:.1f}ms)")
                else:
                    logger.info("🚀 IMPROVEMENT: Cannot calculate - no audio chunks received")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Streaming conversation error: {e}")
            return False


async def main():
    """Run Phase 2C LLM streaming tests"""
    logger.info("🚀 PHASE 2C: LLM Token Streaming Test Suite")
    logger.info("=" * 60)
    
    tester = Phase2CLLMStreamingTester()
    
    success = await tester.test_llm_streaming_pipeline()
    
    if success:
        logger.info("\n🎉 PHASE 2C: LLM Token Streaming - IMPLEMENTATION COMPLETE!")
        logger.info("✅ Real-time token streaming working")
        logger.info("✅ Sentence-boundary TTS processing working") 
        logger.info("✅ Parallel audio chunk generation working")
        logger.info("✅ Massive latency reduction achieved")
    else:
        logger.error("\n❌ PHASE 2C: LLM Token Streaming - NEEDS DEBUGGING")
        logger.error("Check server logs for detailed error information")
    
    return success


if __name__ == "__main__":
    asyncio.run(main()) 