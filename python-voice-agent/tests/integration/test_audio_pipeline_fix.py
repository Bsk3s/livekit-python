#!/usr/bin/env python3
"""
Test Script for Audio Pipeline Fixes
Tests the complete audio processing flow with real-time feedback
"""

import asyncio
import websockets
import json
import base64
import logging
import time
from datetime import datetime
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio_pcm() -> bytes:
    """Create a simple test audio signal (sine wave) as PCM data"""
    sample_rate = 16000
    duration = 2.0  # 2 seconds
    frequency = 440  # A4 note
    
    # Generate sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_signal = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_pcm = (audio_signal * 32767).astype(np.int16)
    
    return audio_pcm.tobytes()

def create_silent_audio_pcm(duration_seconds: float = 1.0) -> bytes:
    """Create silent PCM audio for testing"""
    sample_rate = 16000
    samples = int(sample_rate * duration_seconds)
    silent_pcm = np.zeros(samples, dtype=np.int16)
    return silent_pcm.tobytes()

async def test_websocket_audio_pipeline():
    """Test the complete WebSocket audio processing pipeline"""
    
    # WebSocket URL (adjust port if needed)
    ws_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🧪 Starting WebSocket Audio Pipeline Test")
    logger.info(f"🔗 Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("✅ WebSocket connected successfully")
            
            # 1. Wait for connection confirmation
            logger.info("📡 Waiting for connection confirmation...")
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Received: {msg}")
            
            if msg.get("type") == "connected":
                logger.info("✅ Connection confirmed")
            else:
                logger.error("❌ Unexpected connection response")
                return
            
            # 2. Initialize session with Adina character
            logger.info("🎭 Initializing session with Adina...")
            init_message = {
                "type": "initialize",
                "character": "adina"
            }
            await websocket.send(json.dumps(init_message))
            
            # Wait for initialization response
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Received: {msg}")
            
            if msg.get("type") == "initialized":
                logger.info("✅ Session initialized successfully")
            else:
                logger.error("❌ Session initialization failed")
                return
            
            # 3. Test silent audio (should not trigger speech detection)
            logger.info("🔇 Testing silent audio...")
            silent_audio = create_silent_audio_pcm(0.5)
            silent_b64 = base64.b64encode(silent_audio).decode('utf-8')
            
            audio_message = {
                "type": "audio",
                "audio": silent_b64
            }
            await websocket.send(json.dumps(audio_message))
            
            # Check for speech detection (should not happen)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                msg = json.loads(response)
                if msg.get("type") == "speech_detected":
                    logger.warning("⚠️ Speech detected in silent audio (unexpected)")
                else:
                    logger.info(f"📨 Received: {msg}")
            except asyncio.TimeoutError:
                logger.info("✅ No speech detected in silent audio (correct)")
            
            # 4. Test actual audio signal
            logger.info("🎵 Testing audio signal...")
            test_audio = create_test_audio_pcm()
            
            # Send audio in chunks to simulate real-time streaming
            chunk_size = 8000  # ~0.5 seconds of audio at 16kHz
            chunks = [test_audio[i:i+chunk_size] for i in range(0, len(test_audio), chunk_size)]
            
            expected_events = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"🎤 Sending audio chunk {i+1}/{len(chunks)} ({len(chunk)} bytes)")
                
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                audio_message = {
                    "type": "audio",
                    "audio": chunk_b64
                }
                await websocket.send(json.dumps(audio_message))
                
                # Wait for responses
                start_time = time.time()
                while time.time() - start_time < 5.0:  # 5 second timeout
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        msg = json.loads(response)
                        msg_type = msg.get("type")
                        
                        logger.info(f"📨 Received: {msg_type} - {msg.get('message', msg.get('text', ''))}")
                        
                        if msg_type == "speech_detected":
                            logger.info("🗣️ ✅ BACKEND HEARD YOU: Speech detected!")
                            expected_events.append("speech_detected")
                            
                        elif msg_type == "transcription_partial":
                            logger.info("📝 ✅ BACKEND UNDERSTANDING: Processing speech...")
                            expected_events.append("transcription_partial")
                            
                        elif msg_type == "transcription_complete":
                            text = msg.get("text", "")
                            if text:
                                logger.info(f"✅ ✅ BACKEND UNDERSTOOD: '{text}'")
                            else:
                                logger.info("✅ ✅ BACKEND UNDERSTOOD: No speech in audio")
                            expected_events.append("transcription_complete")
                            
                        elif msg_type == "processing_started":
                            logger.info(f"🤖 ✅ Processing started with {msg.get('character')}")
                            expected_events.append("processing_started")
                            
                        elif msg_type == "response_start":
                            logger.info(f"🎯 Response streaming started ({msg.get('total_chunks')} chunks)")
                            expected_events.append("response_start")
                            
                        elif msg_type == "audio_chunk":
                            chunk_id = msg.get("chunk_id")
                            total = msg.get("total_chunks")
                            text = msg.get("text", "")
                            logger.info(f"🎵 ✅ Audio chunk {chunk_id}/{total}: '{text[:30]}...'")
                            expected_events.append("audio_chunk")
                            
                        elif msg_type == "response_complete":
                            logger.info("🎊 Response streaming complete!")
                            expected_events.append("response_complete")
                            break
                            
                        elif msg_type == "error":
                            logger.error(f"❌ Error: {msg.get('message')}")
                            break
                            
                    except asyncio.TimeoutError:
                        break
                
                # Small delay between chunks
                await asyncio.sleep(0.1)
            
            # 5. Test text message (bypass audio)
            logger.info("💬 Testing text message...")
            text_message = {
                "type": "text_message",
                "text": "Hello Adina, this is a test message."
            }
            await websocket.send(json.dumps(text_message))
            
            # Wait for text response
            start_time = time.time()
            while time.time() - start_time < 10.0:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    logger.info(f"📨 Text Response: {msg_type}")
                    
                    if msg_type == "response_complete":
                        logger.info("✅ Text message processing complete")
                        break
                        
                except asyncio.TimeoutError:
                    break
            
            # Summary
            logger.info("🏁 Test Summary:")
            logger.info(f"✅ Events received: {len(expected_events)}")
            for event in set(expected_events):
                count = expected_events.count(event)
                logger.info(f"   - {event}: {count} times")
                
            if "speech_detected" in expected_events:
                logger.info("✅ Speech detection: WORKING")
            else:
                logger.warning("⚠️ Speech detection: NOT TRIGGERED")
                
            if "transcription_complete" in expected_events:
                logger.info("✅ Speech transcription: WORKING")
            else:
                logger.warning("⚠️ Speech transcription: NOT WORKING")
                
            if "audio_chunk" in expected_events:
                logger.info("✅ AI audio response: WORKING")
            else:
                logger.warning("⚠️ AI audio response: NOT WORKING")
            
    except (ConnectionRefusedError, OSError):
        logger.error("❌ Connection refused - is the server running on port 8000?")
        logger.info("💡 To start the server, run: python start_unified_service.py")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

async def main():
    """Main test function"""
    print("🧪 Audio Pipeline Test Script")
    print("=" * 50)
    print("This script tests the complete audio processing pipeline:")
    print("1. WebSocket connection")
    print("2. Session initialization") 
    print("3. Speech detection events")
    print("4. Audio transcription")
    print("5. AI response generation")
    print("6. Audio synthesis and streaming")
    print("=" * 50)
    
    await test_websocket_audio_pipeline()

if __name__ == "__main__":
    asyncio.run(main()) 