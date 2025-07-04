#!/usr/bin/env python3
"""
🎯 Interruption System Validation Test

Tests the new interruption capabilities including:
- VAD detection during AI responses
- TTS cancellation on interruption
- Interruption latency measurement
- State management during interruptions
- Configuration controls

This test builds on the VAD decoupling foundation implemented earlier.
"""

import asyncio
import base64
import json
import time
import websockets
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InterruptionSystemTest:
    def __init__(self, websocket_url: str = "ws://localhost:8000/ws/audio"):
        self.websocket_url = websocket_url
        self.test_results = []
        self.session_id = None
        
        # Test configuration
        self.test_audio_frequency = 1000  # 1kHz test tone
        self.sample_rate = 16000
        self.chunk_size = 1600  # 100ms chunks (0.1 seconds at 16kHz 16-bit)
        
    def generate_high_energy_audio(self, duration_seconds: float = 1.0) -> bytes:
        """Generate high-energy audio for triggering VAD and interruptions"""
        import math
        import struct
        
        num_samples = int(self.sample_rate * duration_seconds)
        audio_data = bytearray()
        
        for i in range(num_samples):
            # Generate loud sine wave (16-bit signed PCM)
            t = i / self.sample_rate
            sample = int(20000 * math.sin(2 * math.pi * self.test_audio_frequency * t))  # High amplitude
            audio_data.extend(struct.pack('<h', sample))  # Little-endian 16-bit
            
        return bytes(audio_data)
    
    def generate_silence(self, duration_seconds: float = 0.5) -> bytes:
        """Generate silence for spacing between tests"""
        num_samples = int(self.sample_rate * duration_seconds)
        return bytes(num_samples * 2)  # 16-bit silence (all zeros)
    
    async def connect_and_initialize(self) -> websockets.WebSocketServerProtocol:
        """Connect to WebSocket and initialize session"""
        logger.info("🔗 Connecting to voice agent WebSocket...")
        websocket = await websockets.connect(self.websocket_url)
        
        # Wait for connection confirmation
        response = await websocket.recv()
        connection_data = json.loads(response)
        self.session_id = connection_data.get("session_id")
        logger.info(f"✅ Connected with session ID: {self.session_id}")
        
        # Initialize session with character
        await websocket.send(json.dumps({
            "type": "initialize",
            "character": "adina",
            "user_id": "interruption_test_user"
        }))
        
        # Wait for initialization response
        init_response = await websocket.recv()
        init_data = json.loads(init_response)
        logger.info(f"✅ Session initialized: {init_data.get('message', 'Unknown')}")
        
        # Wait for welcome message (if any)
        try:
            welcome = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            welcome_data = json.loads(welcome)
            if welcome_data.get("type") == "welcome_message":
                logger.info(f"👋 Welcome: {welcome_data.get('text', 'No text')[:50]}...")
        except asyncio.TimeoutError:
            logger.info("👋 No welcome message received")
        
        return websocket
    
    async def test_interruption_configuration(self, websocket) -> Dict[str, Any]:
        """Test interruption configuration controls"""
        logger.info("\n🎯 Testing Interruption Configuration...")
        
        test_result = {
            "test_name": "interruption_configuration",
            "passed": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Test 1: Configure interruption sensitivity
            logger.info("📝 Configuring interruption sensitivity...")
            await websocket.send(json.dumps({
                "type": "configure_interruption",
                "threshold": 1.2,  # More sensitive
                "cooldown": 0.8    # Shorter cooldown
            }))
            
            config_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            config_data = json.loads(config_response)
            
            if config_data.get("type") == "interruption_configured":
                test_result["details"]["configuration"] = {
                    "threshold": config_data.get("threshold"),
                    "cooldown": config_data.get("cooldown"),
                    "success": True
                }
                logger.info(f"✅ Configured: threshold={config_data.get('threshold')}, cooldown={config_data.get('cooldown')}")
            else:
                test_result["errors"].append("Configuration response not received")
            
            # Test 2: Get interruption stats
            logger.info("📊 Getting interruption stats...")
            await websocket.send(json.dumps({"type": "get_interruption_stats"}))
            
            stats_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            stats_data = json.loads(stats_response)
            
            if stats_data.get("type") == "interruption_stats":
                test_result["details"]["stats"] = {
                    "interruption_enabled": stats_data.get("interruption_enabled"),
                    "interruption_threshold": stats_data.get("interruption_threshold"),
                    "total_interruptions": stats_data.get("total_interruptions", 0),
                    "has_active_tts": stats_data.get("has_active_tts"),
                    "success": True
                }
                logger.info(f"✅ Stats received: enabled={stats_data.get('interruption_enabled')}, interruptions={stats_data.get('total_interruptions', 0)}")
            else:
                test_result["errors"].append("Stats response not received")
            
            # Test 3: Toggle interruption system
            logger.info("🔄 Testing interruption toggle...")
            await websocket.send(json.dumps({
                "type": "enable_interruption",
                "enabled": False
            }))
            
            toggle_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            toggle_data = json.loads(toggle_response)
            
            if toggle_data.get("type") == "interruption_toggled":
                test_result["details"]["toggle"] = {
                    "interruption_enabled": toggle_data.get("interruption_enabled"),
                    "success": True
                }
                logger.info(f"✅ Toggled: enabled={toggle_data.get('interruption_enabled')}")
            else:
                test_result["errors"].append("Toggle response not received")
            
            # Re-enable for subsequent tests
            await websocket.send(json.dumps({
                "type": "enable_interruption",
                "enabled": True
            }))
            await websocket.recv()  # Consume response
            
            test_result["passed"] = len(test_result["errors"]) == 0
            
        except Exception as e:
            test_result["errors"].append(f"Configuration test error: {e}")
            
        return test_result
    
    async def test_interruption_during_response(self, websocket) -> Dict[str, Any]:
        """Test actual interruption during AI response"""
        logger.info("\n🎯 Testing Real Interruption During AI Response...")
        
        test_result = {
            "test_name": "interruption_during_response",
            "passed": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Step 1: Trigger a long AI response
            logger.info("🤖 Triggering long AI response...")
            trigger_text = "Please tell me a very detailed story about your day, include many details and make it long"
            
            await websocket.send(json.dumps({
                "type": "text_message",
                "text": trigger_text
            }))
            
            # Step 2: Wait for AI to start responding
            response_chunks = []
            interruption_time = None
            interruption_detected = False
            
            # Wait for response to start
            for _ in range(10):  # Wait up to 10 messages for response to start
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                if data.get("type") == "response_start":
                    logger.info(f"🎵 AI response started with {data.get('total_chunks', 0)} chunks")
                    test_result["details"]["response_started"] = True
                    break
                elif data.get("type") in ["processing_started", "transcription_complete"]:
                    logger.info(f"📝 {data.get('type')}: {data.get('message', '')}")
                    continue
                else:
                    logger.info(f"📝 Received: {data.get('type')}")
            
            # Step 3: Wait for first audio chunk, then interrupt
            audio_chunks_received = 0
            for _ in range(20):  # Listen for up to 20 messages
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=8.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "audio_chunk":
                        audio_chunks_received += 1
                        response_chunks.append(data)
                        logger.info(f"🎵 Received audio chunk {data.get('chunk_id')}/{data.get('total_chunks')}: '{data.get('text', '')[:30]}...'")
                        
                        # Interrupt after 2 chunks
                        if audio_chunks_received == 2 and not interruption_time:
                            logger.info("🚨 INTERRUPTING AI RESPONSE!")
                            interruption_time = time.time()
                            
                            # Send high-energy audio to trigger interruption
                            interruption_audio = self.generate_high_energy_audio(duration_seconds=1.5)
                            
                            # Send in chunks to simulate real speech
                            for i in range(0, len(interruption_audio), self.chunk_size):
                                chunk = interruption_audio[i:i + self.chunk_size]
                                await websocket.send(chunk)
                                await asyncio.sleep(0.05)  # Small delay between chunks
                            
                            logger.info(f"🎤 Sent {len(interruption_audio)} bytes of interruption audio")
                    
                    elif data.get("type") == "interruption_detected":
                        interruption_detected = True
                        interruption_latency = data.get("interruption_latency_ms", 0)
                        chunks_interrupted = data.get("chunks_interrupted", 0)
                        
                        logger.info(f"🎯 ✅ INTERRUPTION DETECTED!")
                        logger.info(f"   - Latency: {interruption_latency:.2f}ms")
                        logger.info(f"   - Chunks interrupted: {chunks_interrupted}")
                        
                        test_result["details"]["interruption"] = {
                            "detected": True,
                            "latency_ms": interruption_latency,
                            "chunks_interrupted": chunks_interrupted,
                            "confidence": data.get("confidence"),
                            "energy": data.get("energy")
                        }
                    
                    elif data.get("type") == "response_interrupted":
                        chunks_sent = data.get("chunks_sent", 0)
                        total_chunks = data.get("total_chunks", 0)
                        
                        logger.info(f"🎯 ✂️ RESPONSE INTERRUPTED after {chunks_sent}/{total_chunks} chunks")
                        
                        test_result["details"]["response_interrupted"] = {
                            "chunks_sent": chunks_sent,
                            "total_chunks": total_chunks,
                            "percentage_completed": (chunks_sent / total_chunks * 100) if total_chunks > 0 else 0
                        }
                        break
                    
                    elif data.get("type") == "response_complete":
                        logger.info("🎵 Response completed normally (no interruption)")
                        test_result["details"]["response_completed"] = True
                        break
                    
                    elif data.get("type") == "speech_detected":
                        state = data.get("conversation_state", "unknown")
                        confidence = data.get("confidence", 0)
                        logger.info(f"🗣️ Speech detected during {state} (confidence: {confidence:.2f})")
                        
                    else:
                        logger.info(f"📝 Received: {data.get('type')}")
                        
                except asyncio.TimeoutError:
                    logger.warning("⏰ Timeout waiting for response - ending test")
                    break
            
            # Validate test results
            test_result["details"]["audio_chunks_received"] = audio_chunks_received
            test_result["details"]["interruption_sent"] = interruption_time is not None
            
            # Test passes if interruption was detected and response was interrupted
            test_result["passed"] = (
                interruption_detected and
                test_result["details"].get("response_interrupted") is not None and
                audio_chunks_received >= 2  # Got some chunks before interruption
            )
            
            if not test_result["passed"]:
                if not interruption_detected:
                    test_result["errors"].append("Interruption was not detected")
                if test_result["details"].get("response_interrupted") is None:
                    test_result["errors"].append("Response was not interrupted")
                if audio_chunks_received < 2:
                    test_result["errors"].append(f"Only received {audio_chunks_received} audio chunks")
            
        except Exception as e:
            test_result["errors"].append(f"Interruption test error: {e}")
            
        return test_result
    
    async def test_interruption_performance(self, websocket) -> Dict[str, Any]:
        """Test interruption performance and latency"""
        logger.info("\n🎯 Testing Interruption Performance...")
        
        test_result = {
            "test_name": "interruption_performance",
            "passed": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Get performance summary
            logger.info("📊 Getting performance summary...")
            await websocket.send(json.dumps({"type": "get_performance_summary"}))
            
            summary_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            summary_data = json.loads(summary_response)
            
            if summary_data.get("type") == "performance_summary":
                interruption_perf = summary_data.get("interruption_performance", {})
                
                test_result["details"]["performance"] = {
                    "total_interruptions": interruption_perf.get("total_interruptions", 0),
                    "avg_latency_ms": interruption_perf.get("avg_latency_ms", 0),
                    "max_latency_ms": interruption_perf.get("max_latency_ms", 0),
                    "min_latency_ms": interruption_perf.get("min_latency_ms", 0),
                    "target_met": interruption_perf.get("target_met", False),
                    "enabled": interruption_perf.get("enabled", False),
                    "threshold": interruption_perf.get("threshold", 0),
                    "cooldown": interruption_perf.get("cooldown", 0)
                }
                
                logger.info(f"📊 Performance Summary:")
                logger.info(f"   - Total interruptions: {interruption_perf.get('total_interruptions', 0)}")
                logger.info(f"   - Avg latency: {interruption_perf.get('avg_latency_ms', 0):.2f}ms")
                logger.info(f"   - Max latency: {interruption_perf.get('max_latency_ms', 0):.2f}ms")
                logger.info(f"   - Target met (<50ms): {interruption_perf.get('target_met', False)}")
                
                # Test passes if we have at least one interruption and performance is good
                has_interruptions = interruption_perf.get("total_interruptions", 0) > 0
                good_performance = interruption_perf.get("avg_latency_ms", 999) < 50.0  # Target <50ms
                
                test_result["passed"] = has_interruptions and good_performance
                
                if not test_result["passed"]:
                    if not has_interruptions:
                        test_result["errors"].append("No interruptions recorded")
                    if not good_performance:
                        test_result["errors"].append(f"Average latency {interruption_perf.get('avg_latency_ms', 0):.2f}ms exceeds 50ms target")
            else:
                test_result["errors"].append("Performance summary not received")
        
        except Exception as e:
            test_result["errors"].append(f"Performance test error: {e}")
            
        return test_result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all interruption system tests"""
        logger.info("🚀 Starting Interruption System Test Suite...")
        
        results = {
            "test_suite": "interruption_system",
            "timestamp": time.time(),
            "session_id": None,
            "tests": [],
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "success_rate": 0.0
            }
        }
        
        try:
            websocket = await self.connect_and_initialize()
            results["session_id"] = self.session_id
            
            # Test 1: Configuration controls
            config_result = await self.test_interruption_configuration(websocket)
            results["tests"].append(config_result)
            
            # Wait between tests
            await asyncio.sleep(2.0)
            
            # Test 2: Actual interruption during response
            interruption_result = await self.test_interruption_during_response(websocket)
            results["tests"].append(interruption_result)
            
            # Wait between tests
            await asyncio.sleep(2.0)
            
            # Test 3: Performance measurement
            performance_result = await self.test_interruption_performance(websocket)
            results["tests"].append(performance_result)
            
            # Close connection
            await websocket.close()
            
        except Exception as e:
            logger.error(f"❌ Test suite error: {e}")
            results["error"] = str(e)
        
        # Calculate summary
        results["summary"]["total_tests"] = len(results["tests"])
        results["summary"]["passed_tests"] = sum(1 for test in results["tests"] if test["passed"])
        results["summary"]["failed_tests"] = results["summary"]["total_tests"] - results["summary"]["passed_tests"]
        results["summary"]["success_rate"] = (results["summary"]["passed_tests"] / results["summary"]["total_tests"] * 100) if results["summary"]["total_tests"] > 0 else 0
        
        return results
    
    def print_results(self, results: Dict[str, Any]):
        """Print formatted test results"""
        print("\n" + "="*80)
        print("🎯 INTERRUPTION SYSTEM TEST RESULTS")
        print("="*80)
        print(f"Session ID: {results.get('session_id', 'Unknown')}")
        print(f"Timestamp: {time.ctime(results.get('timestamp', 0))}")
        print()
        
        # Summary
        summary = results.get("summary", {})
        print(f"📊 SUMMARY:")
        print(f"   Total Tests: {summary.get('total_tests', 0)}")
        print(f"   Passed: {summary.get('passed_tests', 0)}")
        print(f"   Failed: {summary.get('failed_tests', 0)}")
        print(f"   Success Rate: {summary.get('success_rate', 0):.1f}%")
        print()
        
        # Individual test results
        for i, test in enumerate(results.get("tests", []), 1):
            status = "✅ PASS" if test["passed"] else "❌ FAIL"
            print(f"{i}. {test['test_name'].upper().replace('_', ' ')}: {status}")
            
            if test.get("details"):
                for key, value in test["details"].items():
                    if isinstance(value, dict):
                        print(f"   {key}: {value}")
                    else:
                        print(f"   {key}: {value}")
            
            if test.get("errors"):
                for error in test["errors"]:
                    print(f"   ❌ Error: {error}")
            print()
        
        # Overall status
        if summary.get("success_rate", 0) == 100:
            print("🎉 ALL TESTS PASSED - Interruption system working perfectly!")
        elif summary.get("success_rate", 0) >= 80:
            print("⚠️ MOSTLY WORKING - Some issues detected")
        else:
            print("❌ SIGNIFICANT ISSUES - Interruption system needs attention")
        
        print("="*80)

async def main():
    """Main test execution"""
    test = InterruptionSystemTest()
    
    try:
        results = await test.run_all_tests()
        test.print_results(results)
        
        # Return appropriate exit code
        success_rate = results.get("summary", {}).get("success_rate", 0)
        return 0 if success_rate == 100 else 1
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Test execution error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 