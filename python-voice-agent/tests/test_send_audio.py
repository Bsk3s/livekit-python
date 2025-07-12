#!/usr/bin/env python3
"""
🎤 Send Audio Test

Sends actual audio data to trigger validation logging.
"""

import asyncio
import json
import math
import struct
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_send_audio():
    """Send audio data to trigger validation logging"""
    websocket_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🔗 Connecting to send audio...")
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
        
        # Generate test audio (sine wave)
        sample_rate = 16000
        frequency = 1000  # 1kHz tone
        amplitude = 5000   # Moderate amplitude
        duration = 2.0     # 2 seconds
        
        samples = []
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            sample = int(amplitude * math.sin(2 * math.pi * frequency * t))
            samples.append(sample)
        
        audio_data = struct.pack(f'<{len(samples)}h', *samples)
        logger.info(f"🎵 Generated {len(audio_data)} bytes of test audio")
        
        # Send audio in chunks
        chunk_size = 1600  # 0.1 second chunks
        total_chunks = len(audio_data) // chunk_size
        
        logger.info(f"📤 Sending {total_chunks} audio chunks...")
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            await websocket.send(chunk)
            logger.info(f"   Sent chunk {i//chunk_size + 1}/{total_chunks} ({len(chunk)} bytes)")
            await asyncio.sleep(0.1)  # Small delay between chunks
        
        logger.info("✅ Audio sending complete")
        
        # Wait for any responses
        logger.info("⏳ Waiting for responses...")
        events_received = []
        
        for i in range(20):  # 10 seconds
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
                    
            except asyncio.TimeoutError:
                continue
        
        # Summary
        logger.info("📊 AUDIO SENDING SUMMARY:")
        logger.info(f"   Events received: {len(events_received)}")
        
        speech_events = [e for e in events_received if e.get("type") == "speech_detected"]
        transcription_events = [e for e in events_received if e.get("type") == "transcription_complete"]
        
        logger.info(f"   Speech detected: {len(speech_events)}")
        logger.info(f"   Transcriptions: {len(transcription_events)}")
        
        if speech_events:
            logger.info("✅ SUCCESS: Speech detection working!")
        else:
            logger.info("❌ ISSUE: No speech detected from test audio")
            logger.info("   Check backend logs for validation messages")
            
        logger.info("🔍 Check the backend server logs for:")
        logger.info("   - '🔍 VALIDATION: First 20 bytes hex:'")
        logger.info("   - '🔍 VALIDATION: Is WAV header:'")
        logger.info("   - '🔍 VALIDATION: Energy analysis:'")
    
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await websocket.close()
        logger.info("🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(test_send_audio()) 