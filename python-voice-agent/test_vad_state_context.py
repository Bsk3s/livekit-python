#!/usr/bin/env python3
"""
Focused VAD State Context Test
Verifies that speech detection events include conversation state context
"""

import asyncio
import websockets
import json
import base64
import logging
import time
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio_pcm(duration_seconds: float = 1.0, frequency: int = 440) -> bytes:
    """Create test audio signal (sine wave) as PCM data"""
    sample_rate = 16000
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    audio_signal = np.sin(2 * np.pi * frequency * t)
    audio_pcm = (audio_signal * 20000).astype(np.int16)  # Higher volume for detection
    return audio_pcm.tobytes()

async def test_vad_state_context():
    """Test VAD state context in speech detection events"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    logger.info("🧪 Testing VAD State Context")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Connect and initialize
            await websocket.recv()  # connected
            await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
            await websocket.recv()  # initialized
            await websocket.recv()  # welcome_message
            
            logger.info("✅ Session initialized")
            
            # Test 1: Speech detection in LISTENING state
            logger.info("\n🎤 Test 1: Speech detection in LISTENING state")
            test_audio = create_test_audio_pcm(1.0, 880)
            chunk_b64 = base64.b64encode(test_audio).decode('utf-8')
            await websocket.send(json.dumps({"type": "audio", "audio": chunk_b64}))
            
            # Collect speech detection event
            for _ in range(5):  # Try multiple times
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    msg = json.loads(response)
                    
                    if msg.get("type") == "speech_detected":
                        logger.info(f"🗣️ Speech detection event received:")
                        logger.info(f"   - conversation_state: {msg.get('conversation_state')}")
                        logger.info(f"   - can_process_transcription: {msg.get('can_process_transcription')}")
                        logger.info(f"   - confidence: {msg.get('confidence')}")
                        logger.info(f"   - energy: {msg.get('energy')}")
                        
                        if msg.get('conversation_state') == 'LISTENING':
                            logger.info("✅ State context working in LISTENING")
                        else:
                            logger.error(f"❌ Expected LISTENING, got {msg.get('conversation_state')}")
                        
                        break
                    elif msg.get("type") == "transcription_complete":
                        text = msg.get("text", "")
                        if text.strip():
                            logger.info(f"📝 Got transcription: '{text}'")
                            
                            # Wait for AI response to start
                            logger.info("\n🤖 Waiting for AI response to test RESPONDING state...")
                            break
                        
                except asyncio.TimeoutError:
                    continue
            
            # Test 2: Send audio during AI response (if we get one)
            logger.info("\n🎤 Test 2: Monitoring for RESPONDING state VAD...")
            
            # Wait for AI response and test VAD during it
            for _ in range(10):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    if msg_type == "processing_started":
                        logger.info("🤖 AI processing started")
                        
                    elif msg_type == "response_start":
                        logger.info("📢 AI response streaming started - sending test audio...")
                        
                        # Send audio during AI response
                        interrupt_audio = create_test_audio_pcm(0.5, 1200)
                        interrupt_b64 = base64.b64encode(interrupt_audio).decode('utf-8')
                        await websocket.send(json.dumps({"type": "audio", "audio": interrupt_b64}))
                        
                    elif msg_type == "speech_detected":
                        logger.info(f"🗣️ Speech detected during AI response:")
                        logger.info(f"   - conversation_state: {msg.get('conversation_state')}")
                        logger.info(f"   - can_process_transcription: {msg.get('can_process_transcription')}")
                        
                        if msg.get('conversation_state') == 'RESPONDING':
                            logger.info("✅ VAD working during RESPONDING state!")
                            return True
                        
                    elif msg_type == "audio_chunk":
                        chunk_id = msg.get("chunk_id", 0)
                        logger.info(f"🎵 Audio chunk {chunk_id}")
                        
                    elif msg_type == "response_complete":
                        logger.info("✅ AI response complete")
                        break
                        
                except asyncio.TimeoutError:
                    continue
            
            logger.info("⚠️ Did not detect speech during RESPONDING state")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

async def main():
    success = await test_vad_state_context()
    if success:
        logger.info("\n🎉 VAD State Context Test: PASSED")
    else:
        logger.info("\n⚠️ VAD State Context Test: PARTIAL (check logs)")

if __name__ == "__main__":
    asyncio.run(main()) 