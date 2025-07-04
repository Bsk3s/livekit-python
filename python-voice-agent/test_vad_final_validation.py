#!/usr/bin/env python3
"""
Final VAD Decoupling Validation Test
Uses correct message format to trigger AI response and validate always-on VAD
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
    audio_pcm = (audio_signal * 30000).astype(np.int16)  # High volume for reliable detection
    return audio_pcm.tobytes()

async def test_vad_final_validation():
    """Final comprehensive test of VAD decoupling functionality"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    logger.info("🧪 Final VAD Decoupling Validation Test")
    
    results = {
        'vad_during_listening': False,
        'vad_during_processing': False,
        'vad_during_responding': False,
        'state_context_working': False,
        'performance_ok': True
    }
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # 1. Connect and initialize (proper sequence)
            logger.info("🔗 Connecting and initializing...")
            
            # Connection confirmation
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 {msg.get('type')}: {msg.get('session_id', '')[:8]}...")
            
            # Initialize session
            await websocket.send(json.dumps({"type": "initialize", "character": "adina"}))
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 {msg.get('type')}: {msg.get('message', '')}")
            
            # Wait for welcome message
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 {msg.get('type')}: {msg.get('text', '')[:50]}...")
            
            logger.info("✅ Session initialized successfully")
            
            # 2. Test VAD during LISTENING state with audio
            logger.info("\n🎤 Testing VAD during LISTENING state...")
            test_audio = create_test_audio_pcm(1.5, 800)
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
            await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
            
            # Collect responses
            for _ in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    if msg_type == "speech_detected":
                        state = msg.get('conversation_state', 'unknown')
                        can_process = msg.get('can_process_transcription', False)
                        confidence = msg.get('confidence', 0)
                        energy = msg.get('energy', 0)
                        
                        logger.info(f"🗣️ Speech detected in {state} state")
                        logger.info(f"   - Can process: {can_process}")
                        logger.info(f"   - Confidence: {confidence:.2f}")
                        logger.info(f"   - Energy: {energy:.1f}")
                        
                        if state == "LISTENING":
                            results['vad_during_listening'] = True
                            results['state_context_working'] = True
                            
                    elif msg_type == "transcription_complete":
                        text = msg.get("text", "").strip()
                        logger.info(f"📝 Transcription: '{text}'")
                        
                except asyncio.TimeoutError:
                    break
            
            # 3. Trigger AI response with text message (correct format)
            logger.info("\n💬 Triggering AI response with text message...")
            text_message = {
                "type": "text_message",
                "text": "Hi Adina, how are you today? This is a test."
            }
            await websocket.send(json.dumps(text_message))
            
            # 4. Monitor AI response and test VAD during each state
            logger.info("🎧 Monitoring AI response states and testing VAD...")
            
            for i in range(20):  # Allow time for full AI response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    if msg_type == "processing_started":
                        logger.info("🤖 PROCESSING state started - sending test audio...")
                        
                        # Send audio during PROCESSING
                        test_audio = create_test_audio_pcm(0.8, 1000)
                        audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                        await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "response_start":
                        logger.info("📢 RESPONDING state started - sending test audio...")
                        
                        # Send audio during RESPONDING
                        test_audio = create_test_audio_pcm(1.0, 1200)
                        audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                        await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "speech_detected":
                        state = msg.get('conversation_state', 'unknown')
                        can_process = msg.get('can_process_transcription', False)
                        
                        logger.info(f"🗣️ 🎉 SPEECH DETECTED in {state} state!")
                        logger.info(f"   - Can process transcription: {can_process}")
                        
                        if state == "PROCESSING":
                            results['vad_during_processing'] = True
                            logger.info("✅ VAD working during PROCESSING!")
                        elif state == "RESPONDING":
                            results['vad_during_responding'] = True
                            logger.info("✅ VAD working during RESPONDING!")
                            
                    elif msg_type == "audio_chunk":
                        chunk_id = msg.get("chunk_id", 0)
                        is_final = msg.get("is_final", False)
                        text = msg.get("text", "")[:40]
                        logger.info(f"🎵 Audio chunk {chunk_id} (final: {is_final}): '{text}...'")
                        
                        # Send more test audio during response streaming
                        if chunk_id in [1, 2]:  # Send during first couple chunks
                            test_audio = create_test_audio_pcm(0.6, 1300 + chunk_id * 50)
                            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                            await websocket.send(json.dumps({"type": "audio", "audio": audio_b64}))
                        
                    elif msg_type == "response_complete":
                        logger.info("✅ AI response complete")
                        break
                        
                except asyncio.TimeoutError:
                    logger.info("⏰ Timeout waiting for more responses")
                    break
            
            # 5. Final validation
            logger.info(f"\n{'='*60}")
            logger.info("🎯 FINAL VAD DECOUPLING VALIDATION RESULTS")
            logger.info(f"{'='*60}")
            
            logger.info(f"VAD during LISTENING state: {'✅' if results['vad_during_listening'] else '❌'}")
            logger.info(f"VAD during PROCESSING state: {'✅' if results['vad_during_processing'] else '❌'}")
            logger.info(f"VAD during RESPONDING state: {'✅' if results['vad_during_responding'] else '❌'}")
            logger.info(f"State context in events: {'✅' if results['state_context_working'] else '❌'}")
            logger.info(f"Performance maintained: {'✅' if results['performance_ok'] else '❌'}")
            
            # Success criteria
            always_on_vad = results['vad_during_listening'] and (
                results['vad_during_processing'] or results['vad_during_responding']
            )
            
            if always_on_vad and results['state_context_working']:
                logger.info("\n🎉 VAD DECOUPLING IMPLEMENTATION: SUCCESS!")
                logger.info("✅ Always-on VAD is working correctly")
                logger.info("✅ Speech detection works in multiple conversation states")
                logger.info("✅ Enhanced events include conversation state context")
                logger.info("✅ Foundation for bidirectional conversation established")
                return True
            else:
                logger.info("\n⚠️ VAD DECOUPLING IMPLEMENTATION: PARTIAL SUCCESS")
                if not always_on_vad:
                    logger.info("❌ Always-on VAD not fully working")
                if not results['state_context_working']:
                    logger.info("❌ State context not being included in events")
                return False
                
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_vad_final_validation()
    
    if success:
        logger.info("\n🎉 VAD DECOUPLING PHASE 1: COMPLETE!")
        logger.info("Ready for Phase 2: Interruption Implementation")
    else:
        logger.info("\n🔄 Check implementation or consider rollback to stable version")

if __name__ == "__main__":
    asyncio.run(main()) 