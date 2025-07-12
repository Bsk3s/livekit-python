#!/usr/bin/env python3
"""
🔍 Audio Format Validation Test

Tests the validation logging to diagnose audio format issues.
"""

import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_audio_validation():
    """Test audio validation logging with real microphone input"""
    websocket_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🔗 Connecting for audio validation test...")
    websocket = await websockets.connect(websocket_url)
    
    try:
        # Connection
        response = await websocket.recv()
        connection_data = json.loads(response)
        session_id = connection_data.get("session_id")
        logger.info(f"✅ Connected: {session_id}")
        
        # Initialize session
        await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
        await websocket.recv()  # init response
        await websocket.recv()  # welcome message
        logger.info("✅ Session initialized")
        
        # Instructions for manual testing
        logger.info("🎤 VALIDATION TEST INSTRUCTIONS:")
        logger.info("1. Speak into your microphone for 10-15 seconds")
        logger.info("2. Watch the backend logs for validation messages:")
        logger.info("   - '🔍 VALIDATION: First 20 bytes hex:'")
        logger.info("   - '🔍 VALIDATION: Is WAV header:'")
        logger.info("   - '🔍 VALIDATION: Energy analysis:'")
        logger.info("3. Check if energy values are above threshold (800)")
        logger.info("4. Look for speech detection events")
        
        # Wait for manual testing
        logger.info("⏳ Waiting 30 seconds for manual audio input...")
        await asyncio.sleep(30)
        
        # Check for any events received
        events_received = []
        timeout_count = 0
        
        while timeout_count < 20:  # 10 seconds
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                event = json.loads(message)
                events_received.append(event)
                
                event_type = event.get("type")
                if event_type == "speech_detected":
                    confidence = event.get("confidence", 0)
                    energy = event.get("energy", 0)
                    logger.info(f"🗣️ ✅ SPEECH DETECTED! Confidence: {confidence:.3f}, Energy: {energy:.1f}")
                    
                elif event_type == "transcription_complete":
                    text = event.get("text", "")
                    logger.info(f"📝 ✅ TRANSCRIPTION: '{text}'")
                    
                elif event_type == "audio_chunk":
                    chunk_id = event.get("chunk_id", 0)
                    base64_length = len(event.get("audio", ""))
                    logger.info(f"🎵 ✅ AUDIO CHUNK {chunk_id}: {base64_length} chars base64")
                    
            except asyncio.TimeoutError:
                timeout_count += 1
                continue
        
        # Summary
        logger.info("📊 VALIDATION TEST SUMMARY:")
        logger.info(f"   Events received: {len(events_received)}")
        
        speech_events = [e for e in events_received if e.get("type") == "speech_detected"]
        transcription_events = [e for e in events_received if e.get("type") == "transcription_complete"]
        audio_events = [e for e in events_received if e.get("type") == "audio_chunk"]
        
        logger.info(f"   Speech detected: {len(speech_events)}")
        logger.info(f"   Transcriptions: {len(transcription_events)}")
        logger.info(f"   Audio chunks: {len(audio_events)}")
        
        if speech_events:
            logger.info("✅ SUCCESS: Speech detection working!")
            for event in speech_events:
                energy = event.get("energy", 0)
                confidence = event.get("confidence", 0)
                logger.info(f"   Energy: {energy:.1f}, Confidence: {confidence:.3f}")
        else:
            logger.info("❌ ISSUE: No speech detected")
            logger.info("   Check backend logs for energy values and format validation")
            
        if audio_events:
            logger.info("✅ SUCCESS: Audio output working!")
            for event in audio_events:
                base64_length = len(event.get("audio", ""))
                logger.info(f"   Base64 length: {base64_length} chars")
        else:
            logger.info("❌ ISSUE: No audio output")
            
        logger.info("🔍 NEXT STEPS:")
        logger.info("1. Check backend logs for '🔍 VALIDATION:' messages")
        logger.info("2. Look for energy values and threshold comparisons")
        logger.info("3. Verify WAV header detection (should be False for PCM)")
        logger.info("4. Check base64 length (should be >210 chars for WAV)")
    
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await websocket.close()
        logger.info("🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(test_audio_validation()) 