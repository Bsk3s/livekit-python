#!/usr/bin/env python3
"""
VAD Debug Test
Debug VAD processing step by step to identify issues
"""

import asyncio
import websockets
import json
import base64
import logging
import numpy as np
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_very_loud_audio_pcm(duration_seconds: float = 2.0) -> bytes:
    """Create very loud test audio to ensure threshold is exceeded"""
    sample_rate = 16000
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    
    # Create composite signal: sine wave + noise for more realistic speech pattern
    primary_freq = 800  # Primary frequency
    audio_signal = np.sin(2 * np.pi * primary_freq * t)
    audio_signal += 0.3 * np.sin(2 * np.pi * (primary_freq * 2) * t)  # Harmonic
    audio_signal += 0.1 * np.random.normal(0, 1, len(t))  # Background noise
    
    # Very high amplitude - should definitely exceed threshold of 800
    audio_pcm = (audio_signal * 32000).astype(np.int16)  # Near max volume
    
    logger.info(f"Generated audio: {len(audio_pcm)} samples, max amplitude: {np.max(np.abs(audio_pcm))}")
    return audio_pcm.tobytes()

def calculate_rms_energy(audio_bytes: bytes) -> float:
    """Calculate RMS energy manually to verify our calculation"""
    # Convert bytes to int16 array
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
    
    # Calculate RMS
    rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))
    
    logger.info(f"Manual RMS calculation: {rms:.1f}")
    return rms

async def test_vad_debug():
    """Debug VAD processing step by step"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    logger.info("🔍 VAD Debug Test - Step by Step Analysis")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Initialize session
            logger.info("🔗 Initializing session...")
            await websocket.recv()  # connected
            await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
            await websocket.recv()  # initialized
            await websocket.recv()  # welcome_message
            
            logger.info("✅ Session ready")
            
            # Test 1: Very loud audio in small chunks
            logger.info("\n🎤 Test 1: Very loud audio in multiple chunks")
            test_audio = create_very_loud_audio_pcm(3.0)  # 3 seconds
            manual_rms = calculate_rms_energy(test_audio)
            
            # Send in small chunks to simulate real streaming
            chunk_size = 3200  # ~200ms chunks
            chunks = [test_audio[i:i+chunk_size] for i in range(0, len(test_audio), chunk_size)]
            
            logger.info(f"Sending {len(chunks)} chunks of {chunk_size} bytes each")
            logger.info(f"Expected RMS: {manual_rms:.1f}, Threshold: 800")
            
            chunk_responses = []
            
            for i, chunk in enumerate(chunks):
                chunk_rms = calculate_rms_energy(chunk)
                logger.info(f"📦 Sending chunk {i+1}/{len(chunks)} (RMS: {chunk_rms:.1f})")
                
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                await websocket.send(json.dumps({"type": "audio", "audio": chunk_b64}))
                
                # Collect immediate responses
                start_time = time.time()
                while time.time() - start_time < 1.0:  # 1 second timeout per chunk
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.3)
                        msg = json.loads(response)
                        msg_type = msg.get("type")
                        
                        if msg_type == "speech_detected":
                            logger.info(f"🗣️ 🎉 SPEECH DETECTED on chunk {i+1}!")
                            logger.info(f"   State: {msg.get('conversation_state')}")
                            logger.info(f"   Energy: {msg.get('energy')}")
                            logger.info(f"   Confidence: {msg.get('confidence')}")
                            chunk_responses.append(f"speech_detected_chunk_{i+1}")
                            
                        elif msg_type == "transcription_partial":
                            logger.info(f"📝 Transcription started for chunk {i+1}")
                            chunk_responses.append(f"transcription_partial_chunk_{i+1}")
                            
                        elif msg_type == "transcription_complete":
                            text = msg.get("text", "")
                            logger.info(f"📝 Transcription complete: '{text}'")
                            chunk_responses.append(f"transcription_complete_chunk_{i+1}")
                            
                    except asyncio.TimeoutError:
                        break
                
                # Small delay between chunks
                await asyncio.sleep(0.1)
            
            # Test 2: Check if any logs show VAD processing
            logger.info("\n📊 Debug Summary:")
            logger.info(f"Chunks sent: {len(chunks)}")
            logger.info(f"Responses received: {len(chunk_responses)}")
            logger.info(f"Response types: {chunk_responses}")
            
            if not chunk_responses:
                logger.error("❌ NO RESPONSES RECEIVED")
                logger.error("Possible issues:")
                logger.error("1. VAD energy threshold too high")
                logger.error("2. Audio format/encoding issue") 
                logger.error("3. VAD processing not happening")
                logger.error("4. WebSocket message handling issue")
                
                # Test 3: Send raw energy values via different message type
                logger.info("\n🔧 Test 3: Testing if WebSocket is receiving messages at all...")
                test_msg = {"type": "debug", "message": "testing connectivity"}
                await websocket.send(json.dumps(test_msg))
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.info(f"📨 Received: {response}")
                except asyncio.TimeoutError:
                    logger.error("❌ No response to debug message")
                    
            else:
                logger.info("✅ VAD processing is working!")
                
            return len(chunk_responses) > 0
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_vad_debug()
    
    if success:
        logger.info("\n✅ VAD is responding to audio")
    else:
        logger.info("\n❌ VAD debugging needed - check server logs")

if __name__ == "__main__":
    asyncio.run(main()) 