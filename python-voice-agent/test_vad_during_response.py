#!/usr/bin/env python3
"""
Test VAD During AI Response
Uses text input to trigger AI response, then tests VAD during RESPONDING state
"""

import asyncio
import websockets
import json
import base64
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio_pcm(duration_seconds: float = 1.0, frequency: int = 440) -> bytes:
    """Create test audio signal (sine wave) as PCM data"""
    sample_rate = 16000
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    audio_signal = np.sin(2 * np.pi * frequency * t)
    audio_pcm = (audio_signal * 25000).astype(np.int16)  # Very high volume for detection
    return audio_pcm.tobytes()

async def test_vad_during_ai_response():
    """Test VAD functionality during AI response using text input"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    logger.info("🧪 Testing VAD During AI Response")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Connect and initialize
            await websocket.recv()  # connected
            await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
            await websocket.recv()  # initialized
            await websocket.recv()  # welcome_message
            
            logger.info("✅ Session initialized")
            
            # Send text message to trigger AI response
            logger.info("💬 Sending text message to trigger AI response...")
            text_message = {
                "type": "text", 
                "text": "Hello, how are you?"
            }
            await websocket.send(json.dumps(text_message))
            
            # Monitor for AI response and test VAD during it
            logger.info("🎧 Monitoring for AI response states...")
            
            speech_detected_during_responding = False
            
            for i in range(20):  # Give more time for full response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    logger.info(f"📨 Received: {msg_type}")
                    
                    if msg_type == "processing_started":
                        logger.info("🤖 AI processing started - conversation state should be PROCESSING")
                        
                        # Send audio during processing
                        logger.info("🎤 Sending audio during PROCESSING state...")
                        test_audio = create_test_audio_pcm(0.8, 1000)
                        audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                        await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "response_start":
                        logger.info("📢 AI response streaming started - conversation state should be RESPONDING")
                        
                        # Send audio during AI response
                        logger.info("🎤 Sending audio during RESPONDING state...")
                        test_audio = create_test_audio_pcm(1.0, 1200)
                        audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                        await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "speech_detected":
                        conversation_state = msg.get('conversation_state', 'unknown')
                        can_process = msg.get('can_process_transcription', False)
                        confidence = msg.get('confidence', 0)
                        energy = msg.get('energy', 0)
                        
                        logger.info(f"🗣️ SPEECH DETECTED!")
                        logger.info(f"   State: {conversation_state}")
                        logger.info(f"   Can process transcription: {can_process}")
                        logger.info(f"   Confidence: {confidence}")
                        logger.info(f"   Energy: {energy}")
                        
                        if conversation_state == "RESPONDING":
                            logger.info("🎉 SUCCESS: VAD working during RESPONDING state!")
                            speech_detected_during_responding = True
                        elif conversation_state == "PROCESSING":
                            logger.info("✅ VAD working during PROCESSING state")
                        elif conversation_state == "LISTENING":
                            logger.info("✅ VAD working during LISTENING state")
                        
                    elif msg_type == "audio_chunk":
                        chunk_id = msg.get("chunk_id", 0)
                        is_final = msg.get("is_final", False)
                        text = msg.get("text", "")[:30]
                        logger.info(f"🎵 Audio chunk {chunk_id} (final: {is_final}): '{text}...'")
                        
                        # Send more audio during response streaming
                        if chunk_id <= 2:  # Send during first few chunks
                            test_audio = create_test_audio_pcm(0.5, 1500 + chunk_id * 100)
                            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                            await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "response_complete":
                        logger.info("✅ AI response complete")
                        break
                        
                except asyncio.TimeoutError:
                    logger.info("⏰ Timeout waiting for response")
                    break
            
            # Summary
            if speech_detected_during_responding:
                logger.info("\n🎉 VAD DURING RESPONSE TEST: PASSED")
                logger.info("✅ Always-on VAD is working correctly!")
                logger.info("✅ Speech detected during RESPONDING state")
                return True
            else:
                logger.info("\n⚠️ VAD DURING RESPONSE TEST: PARTIAL")
                logger.info("❓ Check if speech detection events include state context")
                return False
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_vad_during_ai_response()
    if success:
        logger.info("\n🎉 VAD decoupling implementation is working correctly!")
    else:
        logger.info("\n🔍 Check server logs for VAD events and state context")

if __name__ == "__main__":
    asyncio.run(main()) 