#!/usr/bin/env python3

import asyncio
import websockets
import json
import base64
import time
import struct
import logging
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_audio_samples():
    """Create test audio samples with different characteristics"""
    
    # Sample rate and duration
    sample_rate = 16000
    duration_seconds = 1.0
    samples_count = int(sample_rate * duration_seconds)
    
    samples = {}
    
    # 1. Pure silence (should NOT trigger speech detection)
    samples["silence"] = b'\x00\x00' * samples_count
    
    # 2. Low-level noise (should NOT trigger speech detection)
    np.random.seed(42)  # For reproducible results
    noise = (np.random.normal(0, 100, samples_count) * 100).astype(np.int16)
    samples["noise"] = noise.tobytes()
    
    # 3. Medium-level white noise (might trigger speech detection)
    medium_noise = (np.random.normal(0, 500, samples_count)).astype(np.int16)
    samples["medium_noise"] = medium_noise.tobytes()
    
    # 4. High-level audio (should trigger speech detection)
    # Simulate speech-like audio with varying amplitude
    t = np.linspace(0, duration_seconds, samples_count)
    speech_like = (np.sin(2 * np.pi * 300 * t) * 2000 + 
                   np.sin(2 * np.pi * 600 * t) * 1500 + 
                   np.sin(2 * np.pi * 900 * t) * 1000).astype(np.int16)
    samples["speech_like"] = speech_like.tobytes()
    
    return samples

def calculate_audio_energy(audio_data: bytes) -> float:
    """Calculate RMS energy of audio data (same as backend)"""
    try:
        if len(audio_data) < 2:
            return 0.0
        
        import struct
        import math
        
        # Convert bytes to 16-bit signed integers
        sample_count = len(audio_data) // 2
        samples = struct.unpack(f'<{sample_count}h', audio_data[:sample_count * 2])
        
        # Calculate RMS (Root Mean Square) energy
        sum_squares = sum(sample * sample for sample in samples)
        rms = math.sqrt(sum_squares / sample_count) if sample_count > 0 else 0.0
        
        return rms
        
    except Exception as e:
        logger.warning(f"⚠️ Error calculating audio energy: {e}")
        return 0.0

async def test_websocket_audio_pipeline():
    """Test the complete WebSocket audio processing pipeline with improved voice detection"""
    
    # WebSocket URL
    ws_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🧪 Starting Enhanced WebSocket Audio Pipeline Test")
    logger.info(f"🔗 Connecting to: {ws_url}")
    
    # Create test audio samples
    test_samples = create_test_audio_samples()
    
    # Results tracking
    results = {
        "speech_detected": [],
        "transcriptions": [],
        "responses": [],
        "errors": []
    }
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("✅ WebSocket connected successfully")
            
            # 1. Wait for connection confirmation
            logger.info("📡 Waiting for connection confirmation...")
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Received: {msg}")
            
            if msg.get("type") != "connected":
                logger.error("❌ Unexpected connection response")
                return False
            
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
            
            if msg.get("type") != "initialized":
                logger.error("❌ Session initialization failed")
                return False
            
            # 3. Test each audio sample type
            for sample_name, audio_data in test_samples.items():
                logger.info(f"\n🎤 Testing {sample_name} audio...")
                
                # Calculate expected energy
                energy = calculate_audio_energy(audio_data)
                energy_threshold = 500
                should_trigger = energy > energy_threshold
                
                logger.info(f"📊 Audio energy: {energy:.1f} (threshold: {energy_threshold})")
                logger.info(f"🎯 Expected to trigger speech detection: {should_trigger}")
                
                # Send audio in chunks to simulate real streaming
                chunk_size = 3200  # ~200ms chunks at 16kHz
                chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
                
                logger.info(f"📤 Sending {len(chunks)} chunks of {sample_name} audio...")
                
                # Track responses for this sample
                sample_events = []
                
                for i, chunk in enumerate(chunks):
                    chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                    audio_message = {
                        "type": "audio",
                        "audio": chunk_b64
                    }
                    await websocket.send(json.dumps(audio_message))
                    
                    # Wait for immediate responses
                    start_time = time.time()
                    while time.time() - start_time < 1.0:  # 1 second timeout per chunk
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                            msg = json.loads(response)
                            msg_type = msg.get("type")
                            
                            sample_events.append(msg_type)
                            
                            if msg_type == "speech_detected":
                                energy_reported = msg.get("energy", 0)
                                confidence = msg.get("confidence", 0)
                                logger.info(f"🗣️ Speech detected: energy={energy_reported:.1f}, confidence={confidence:.2f}")
                                results["speech_detected"].append({
                                    "sample": sample_name,
                                    "energy": energy_reported,
                                    "confidence": confidence
                                })
                                
                            elif msg_type == "transcription_complete":
                                text = msg.get("text", "")
                                buffer_size = msg.get("buffer_size", 0)
                                logger.info(f"📝 Transcription: '{text}' (buffer: {buffer_size} bytes)")
                                results["transcriptions"].append({
                                    "sample": sample_name,
                                    "text": text,
                                    "buffer_size": buffer_size
                                })
                                
                            elif msg_type == "audio_chunk":
                                chunk_id = msg.get("chunk_id")
                                text = msg.get("text", "")
                                logger.info(f"🎵 AI Response chunk {chunk_id}: '{text[:30]}...'")
                                results["responses"].append({
                                    "sample": sample_name,
                                    "chunk_id": chunk_id,
                                    "text": text
                                })
                                
                            elif msg_type == "error":
                                error_msg = msg.get("message", "")
                                logger.error(f"❌ Error: {error_msg}")
                                results["errors"].append({
                                    "sample": sample_name,
                                    "error": error_msg
                                })
                                
                        except asyncio.TimeoutError:
                            break
                        except Exception as e:
                            logger.warning(f"⚠️ Error receiving message: {e}")
                            break
                
                # Validate results for this sample
                speech_detected = any(event == "speech_detected" for event in sample_events)
                transcription_completed = any(event == "transcription_complete" for event in sample_events)
                
                logger.info(f"📊 {sample_name} Results:")
                logger.info(f"   - Speech detected: {speech_detected} (expected: {should_trigger})")
                logger.info(f"   - Transcription completed: {transcription_completed}")
                logger.info(f"   - Events: {set(sample_events)}")
                
                # Wait a bit between samples
                await asyncio.sleep(0.5)
            
            # 4. Final summary
            logger.info(f"\n{'='*60}")
            logger.info("🎯 PIPELINE TEST SUMMARY")
            logger.info(f"{'='*60}")
            
            # Speech detection accuracy
            correct_detections = 0
            total_samples = len(test_samples)
            
            for sample_name, audio_data in test_samples.items():
                energy = calculate_audio_energy(audio_data)
                should_trigger = energy > 500
                
                detected = any(r["sample"] == sample_name for r in results["speech_detected"])
                is_correct = detected == should_trigger
                
                logger.info(f"📊 {sample_name}:")
                logger.info(f"   - Energy: {energy:.1f}")
                logger.info(f"   - Should trigger: {should_trigger}")
                logger.info(f"   - Actually triggered: {detected}")
                logger.info(f"   - Correct: {'✅' if is_correct else '❌'}")
                
                if is_correct:
                    correct_detections += 1
            
            accuracy = (correct_detections / total_samples) * 100
            logger.info(f"\n🎯 Speech Detection Accuracy: {accuracy:.1f}% ({correct_detections}/{total_samples})")
            
            # Transcription results
            transcription_count = len(results["transcriptions"])
            non_empty_transcriptions = len([t for t in results["transcriptions"] if t["text"].strip()])
            
            logger.info(f"📝 Transcriptions: {transcription_count} total, {non_empty_transcriptions} non-empty")
            
            # AI responses
            response_count = len(results["responses"])
            logger.info(f"🤖 AI Response chunks: {response_count}")
            
            # Errors
            error_count = len(results["errors"])
            logger.info(f"❌ Errors: {error_count}")
            
            # Overall assessment
            if accuracy >= 75 and error_count == 0:
                logger.info("\n🎉 PIPELINE TEST: PASSED")
                return True
            else:
                logger.info(f"\n❌ PIPELINE TEST: FAILED (accuracy: {accuracy}%, errors: {error_count})")
                return False
            
    except (ConnectionRefusedError, OSError):
        logger.error("❌ Connection refused - is the server running on port 8000?")
        logger.info("💡 To start the server, run: python start_unified_service.py")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🧪 Enhanced Audio Pipeline Test Script")
    print("=" * 60)
    print("This script tests the improved audio processing pipeline:")
    print("1. Proper voice activity detection")
    print("2. Smart buffering and processing")
    print("3. Accurate speech detection vs noise")
    print("4. Speech transcription accuracy")
    print("5. AI response generation")
    print("6. Audio synthesis and streaming")
    print("=" * 60)
    
    success = await test_websocket_audio_pipeline()
    
    if success:
        print("\n🎉 All tests passed! The audio pipeline is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main()) 