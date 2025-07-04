#!/usr/bin/env python3
"""
🎯 Synthetic Audio Validation Test

Test to verify our synthetic audio can trigger VAD during LISTENING state,
then test if the issue is specific to RESPONDING state.
"""

import asyncio
import json
import math
import struct
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def generate_synthetic_audio(amplitude: int = 25000, duration_seconds: float = 2.0) -> bytes:
    """Generate synthetic audio with specified amplitude"""
    sample_rate = 16000
    frequency = 1000  # 1kHz tone
    
    num_samples = int(sample_rate * duration_seconds)
    audio_data = bytearray()
    
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(amplitude * math.sin(2 * math.pi * frequency * t))
        audio_data.extend(struct.pack('<h', sample))
    
    return bytes(audio_data)

async def test_listening_state_vad():
    """Test if VAD works during LISTENING state with synthetic audio"""
    websocket_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🔗 Connecting to voice agent...")
    websocket = await websockets.connect(websocket_url)
    
    try:
        # Connection and initialization
        response = await websocket.recv()
        connection_data = json.loads(response)
        session_id = connection_data.get("session_id")
        logger.info(f"✅ Connected: {session_id}")
        
        await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
        
        # Wait for init responses
        for i in range(3):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(response)
                logger.info(f"Init: {data.get('type')}")
            except asyncio.TimeoutError:
                break
        
        # Test 1: Send synthetic audio during LISTENING state
        logger.info("\n🧪 TEST 1: Synthetic audio during LISTENING state")
        
        speech_events = []
        
        # Send high-energy synthetic audio
        logger.info("🎤 Sending synthetic audio in LISTENING state...")
        test_audio = await generate_synthetic_audio(amplitude=25000, duration_seconds=2.0)
        
        # Send in chunks to simulate real audio streaming
        chunk_size = 3200  # 200ms chunks
        for j in range(0, len(test_audio), chunk_size):
            chunk = test_audio[j:j + chunk_size]
            await websocket.send(chunk)
            await asyncio.sleep(0.05)  # 50ms delay
        
        logger.info(f"📡 Sent {len(test_audio)} bytes of synthetic audio")
        
        # Listen for speech detection events
        for i in range(10):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                data = json.loads(response)
                message_type = data.get("type")
                
                if message_type == "speech_detected":
                    state = data.get("conversation_state", "unknown")
                    confidence = data.get("confidence", 0)
                    energy = data.get("energy", 0)
                    
                    speech_events.append({
                        "state": state,
                        "confidence": confidence,
                        "energy": energy
                    })
                    
                    logger.info(f"🎯 ✅ SPEECH DETECTED! State: {state}, Confidence: {confidence:.2f}, Energy: {energy:.1f}")
                
                elif message_type == "transcription_complete":
                    text = data.get("text", "")
                    logger.info(f"📝 Transcription: '{text}'")
                    break
                
                else:
                    logger.debug(f"📝 {message_type}")
                    
            except asyncio.TimeoutError:
                logger.info("⏰ No more messages in LISTENING test")
                break
        
        listening_test_passed = len(speech_events) > 0
        logger.info(f"\n📊 LISTENING STATE TEST: {'✅ PASSED' if listening_test_passed else '❌ FAILED'}")
        logger.info(f"   Speech events detected: {len(speech_events)}")
        
        if not listening_test_passed:
            logger.info("❌ Synthetic audio doesn't work at all - this explains the RESPONDING issue")
            return False
            
        # Test 2: Try during RESPONDING state
        logger.info("\n🧪 TEST 2: Synthetic audio during RESPONDING state")
        
        # Request AI response
        await websocket.send(json.dumps({
            "type": "text_message",
            "text": "Tell me about meditation in 3 sentences."
        }))
        
        responding_speech_events = []
        audio_chunks_received = 0
        
        for i in range(15):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=8.0)
                data = json.loads(response)
                message_type = data.get("type")
                
                if message_type == "processing_started":
                    logger.info("🧠 AI thinking...")
                
                elif message_type == "response_start":
                    logger.info("🎵 AI response started")
                
                elif message_type == "audio_chunk":
                    audio_chunks_received += 1
                    chunk_id = data.get("chunk_id", 0)
                    logger.info(f"🎵 Chunk {chunk_id}")
                    
                    # Send synthetic audio after first chunk
                    if audio_chunks_received == 1:
                        logger.info("🎤 Sending synthetic audio during RESPONDING state...")
                        
                        test_audio = await generate_synthetic_audio(amplitude=30000, duration_seconds=2.0)
                        
                        # Send quickly to catch RESPONDING state
                        chunk_size = 6400  # Larger chunks
                        for j in range(0, len(test_audio), chunk_size):
                            chunk = test_audio[j:j + chunk_size]
                            await websocket.send(chunk)
                            await asyncio.sleep(0.02)  # Very short delay
                        
                        logger.info(f"📡 Sent {len(test_audio)} bytes during RESPONDING")
                
                elif message_type == "speech_detected":
                    state = data.get("conversation_state", "unknown")
                    confidence = data.get("confidence", 0)
                    energy = data.get("energy", 0)
                    
                    responding_speech_events.append({
                        "state": state,
                        "confidence": confidence,
                        "energy": energy
                    })
                    
                    logger.info(f"🎯 ✅ SPEECH DURING RESPONDING! State: {state}, Confidence: {confidence:.2f}, Energy: {energy:.1f}")
                
                elif message_type == "interruption_detected":
                    logger.info(f"🚨 ✅ INTERRUPTION DETECTED!")
                    break
                
                elif message_type == "response_complete":
                    logger.info("🎵 AI response completed")
                    break
                
                elif message_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    logger.warning(f"⚠️ Error: {error_msg}")
                
                else:
                    logger.debug(f"📝 {message_type}")
                    
            except asyncio.TimeoutError:
                logger.warning("⏰ Timeout in RESPONDING test")
                break
        
        responding_speech_during_responding = any(event["state"] == "RESPONDING" for event in responding_speech_events)
        
        logger.info(f"\n📊 RESPONDING STATE TEST: {'✅ PASSED' if responding_speech_during_responding else '❌ FAILED'}")
        logger.info(f"   Speech events during RESPONDING: {len([e for e in responding_speech_events if e['state'] == 'RESPONDING'])}")
        logger.info(f"   Total speech events: {len(responding_speech_events)}")
        
        # Overall results
        logger.info("\n🎯 OVERALL RESULTS:")
        logger.info(f"   ✅ Synthetic audio works in LISTENING: {listening_test_passed}")
        logger.info(f"   {'✅' if responding_speech_during_responding else '❌'} Synthetic audio works in RESPONDING: {responding_speech_during_responding}")
        
        if listening_test_passed and not responding_speech_during_responding:
            logger.info("   🔍 CONCLUSION: Audio processing is blocked during RESPONDING state")
            logger.info("   💡 This is a code issue, not a real-device requirement")
        elif not listening_test_passed:
            logger.info("   🔍 CONCLUSION: Synthetic audio format/energy issues")
            logger.info("   💡 May need real device audio or different audio format")
        else:
            logger.info("   🎉 CONCLUSION: Interruption system works with synthetic audio!")
        
        return responding_speech_during_responding
    
    finally:
        await websocket.close()

async def main():
    """Main test execution"""
    try:
        success = await test_listening_state_vad()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 