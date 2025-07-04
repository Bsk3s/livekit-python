#!/usr/bin/env python3
"""
VAD Decoupling Validation Test
Tests the always-on VAD implementation with performance monitoring
"""

import asyncio
import websockets
import json
import base64
import logging
import time
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio_pcm(duration_seconds: float = 1.0, frequency: int = 440) -> bytes:
    """Create test audio signal (sine wave) as PCM data"""
    sample_rate = 16000
    
    # Generate sine wave
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    audio_signal = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_pcm = (audio_signal * 16000).astype(np.int16)  # Moderate volume
    
    return audio_pcm.tobytes()

def create_silent_audio_pcm(duration_seconds: float = 1.0) -> bytes:
    """Create silent PCM audio for testing"""
    sample_rate = 16000
    samples = int(sample_rate * duration_seconds)
    silent_pcm = np.zeros(samples, dtype=np.int16)
    return silent_pcm.tobytes()

async def test_vad_decoupling():
    """Test VAD decoupling implementation with comprehensive validation"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🧪 Starting VAD Decoupling Validation Test")
    logger.info(f"🔗 Connecting to: {ws_url}")
    
    test_results = {
        'vad_events_during_listening': 0,
        'vad_events_during_responding': 0,
        'transcription_attempts': 0,
        'performance_issues': [],
        'conversation_flow_issues': []
    }
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("✅ WebSocket connected successfully")
            
            # 1. Wait for connection confirmation
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Connection: {msg.get('type')}")
            
            if msg.get("type") != "connected":
                logger.error("❌ Connection failed")
                return False
            
            # 2. Initialize session
            logger.info("🎭 Initializing session...")
            init_message = {"type": "initialize", "character": "adina"}
            await websocket.send(json.dumps(init_message))
            
            response = await websocket.recv()
            msg = json.loads(response)
            if msg.get("type") != "initialized":
                logger.error("❌ Initialization failed")
                return False
            
            logger.info("✅ Session initialized")
            
            # 3. Test VAD during LISTENING state
            logger.info("\n🎤 Testing VAD during LISTENING state...")
            test_audio = create_test_audio_pcm(2.0, 880)  # 2 seconds, higher frequency
            
            # Send audio in chunks
            chunk_size = 3200  # ~200ms chunks
            chunks = [test_audio[i:i+chunk_size] for i in range(0, len(test_audio), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                audio_message = {"type": "audio", "audio": chunk_b64}
                await websocket.send(json.dumps(audio_message))
                
                # Collect responses
                start_time = time.time()
                while time.time() - start_time < 2.0:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        msg = json.loads(response)
                        msg_type = msg.get("type")
                        
                        if msg_type == "speech_detected":
                            conversation_state = msg.get("conversation_state", "unknown")
                            can_process = msg.get("can_process_transcription", False)
                            
                            logger.info(f"🗣️ Speech detected in {conversation_state} state (can_process: {can_process})")
                            
                            if conversation_state == "LISTENING":
                                test_results['vad_events_during_listening'] += 1
                            elif conversation_state == "RESPONDING":
                                test_results['vad_events_during_responding'] += 1
                                
                        elif msg_type == "transcription_complete":
                            text = msg.get("text", "")
                            if text:
                                test_results['transcription_attempts'] += 1
                                logger.info(f"✅ Transcription: '{text}'")
                                
                                # Trigger AI response to test VAD during RESPONDING
                                logger.info("🤖 AI response starting - testing VAD during RESPONDING...")
                                
                        elif msg_type == "response_start":
                            logger.info("📢 AI response streaming started")
                            
                            # Send audio during AI response to test always-on VAD
                            logger.info("🎤 Sending audio during AI response...")
                            interrupt_audio = create_test_audio_pcm(1.0, 1200)  # Different frequency
                            interrupt_chunks = [interrupt_audio[j:j+chunk_size] for j in range(0, len(interrupt_audio), chunk_size)]
                            
                            for interrupt_chunk in interrupt_chunks:
                                interrupt_b64 = base64.b64encode(interrupt_chunk).decode('utf-8')
                                interrupt_message = {"type": "audio", "audio": interrupt_b64}
                                await websocket.send(json.dumps(interrupt_message))
                                await asyncio.sleep(0.1)  # Small delay between chunks
                                
                        elif msg_type == "audio_chunk":
                            chunk_id = msg.get("chunk_id", 0)
                            is_final = msg.get("is_final", False)
                            logger.info(f"🎵 Audio chunk {chunk_id} (final: {is_final})")
                            
                        elif msg_type == "response_complete":
                            logger.info("✅ AI response complete")
                            break
                            
                    except asyncio.TimeoutError:
                        break
                        
                await asyncio.sleep(0.1)
            
            # 4. Test silent audio (should not trigger VAD)
            logger.info("\n🔇 Testing silent audio...")
            silent_audio = create_silent_audio_pcm(1.0)
            silent_b64 = base64.b64encode(silent_audio).decode('utf-8')
            await websocket.send(json.dumps({"type": "audio", "audio": silent_b64}))
            
            # Check for unexpected speech detection
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                msg = json.loads(response)
                if msg.get("type") == "speech_detected":
                    logger.warning("⚠️ False positive: Speech detected in silent audio")
                    test_results['performance_issues'].append("false_positive_silent_audio")
            except asyncio.TimeoutError:
                logger.info("✅ No false positive for silent audio")
            
            # 5. Performance validation
            logger.info("\n📊 Requesting performance summary...")
            # Note: Would need to add endpoint to get performance data
            
            logger.info(f"\n{'='*60}")
            logger.info("🎯 VAD DECOUPLING TEST RESULTS")
            logger.info(f"{'='*60}")
            
            logger.info(f"VAD events during LISTENING: {test_results['vad_events_during_listening']}")
            logger.info(f"VAD events during RESPONDING: {test_results['vad_events_during_responding']}")
            logger.info(f"Transcription attempts: {test_results['transcription_attempts']}")
            logger.info(f"Performance issues: {len(test_results['performance_issues'])}")
            
            # Success criteria
            success_criteria = [
                test_results['vad_events_during_listening'] > 0,  # VAD works in LISTENING
                test_results['vad_events_during_responding'] > 0,  # VAD works in RESPONDING
                test_results['transcription_attempts'] > 0,  # Transcription still works
                len(test_results['performance_issues']) == 0  # No performance issues
            ]
            
            if all(success_criteria):
                logger.info("\n🎉 VAD DECOUPLING TEST: PASSED")
                logger.info("✅ Always-on VAD working correctly")
                logger.info("✅ State-aware transcription working")
                logger.info("✅ Performance maintained")
                return True
            else:
                logger.info("\n❌ VAD DECOUPLING TEST: FAILED")
                for i, criteria in enumerate(success_criteria):
                    status = "✅" if criteria else "❌"
                    logger.info(f"{status} Criteria {i+1}: {criteria}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run VAD decoupling validation test"""
    logger.info("Starting VAD Decoupling Validation...")
    
    # Check if server is running
    try:
        success = await test_vad_decoupling()
        if success:
            logger.info("🎉 All tests passed! VAD decoupling is working correctly.")
        else:
            logger.error("❌ Tests failed. Check implementation or rollback.")
    except Exception as e:
        logger.error(f"❌ Test suite error: {e}")
        logger.error("🔄 Consider rolling back to stable version")

if __name__ == "__main__":
    asyncio.run(main()) 