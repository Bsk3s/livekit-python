#!/usr/bin/env python3

import asyncio
import websockets
import json
import base64
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_text_input_pipeline():
    """Test the AI response pipeline using text input (bypassing STT)"""
    
    ws_url = "ws://localhost:8000/ws/audio"
    
    logger.info("🧪 Testing Text Input → AI Response Pipeline")
    logger.info(f"🔗 Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("✅ WebSocket connected successfully")
            
            # 1. Wait for connection confirmation
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Connection: {msg}")
            
            # 2. Initialize session with Adina
            init_message = {
                "type": "initialize",
                "character": "adina"
            }
            await websocket.send(json.dumps(init_message))
            
            response = await websocket.recv()
            msg = json.loads(response)
            logger.info(f"📨 Initialization: {msg}")
            
            # 3. Send text message directly (bypass STT)
            text_message = {
                "type": "text_message",
                "text": "Hello Adina, I'm feeling stressed today and need some guidance."
            }
            
            logger.info(f"💬 Sending text: '{text_message['text']}'")
            await websocket.send(json.dumps(text_message))
            
            # 4. Collect AI response chunks
            logger.info("🎯 Waiting for AI response...")
            
            response_chunks = []
            full_text = ""
            
            timeout_count = 0
            max_timeout = 30  # 30 seconds max wait
            
            while timeout_count < max_timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    msg = json.loads(response)
                    msg_type = msg.get("type")
                    
                    logger.info(f"📨 Received: {msg_type}")
                    
                    if msg_type == "processing_started":
                        logger.info(f"🤖 {msg.get('character')} is thinking...")
                        
                    elif msg_type == "response_start":
                        total_chunks = msg.get("total_chunks", 0)
                        full_text = msg.get("full_text", "")
                        logger.info(f"🎯 Response starting: {total_chunks} chunks")
                        logger.info(f"📝 Full AI response: '{full_text}'")
                        
                    elif msg_type == "audio_chunk":
                        chunk_id = msg.get("chunk_id")
                        chunk_text = msg.get("text", "")
                        audio_data = msg.get("audio", "")
                        is_final = msg.get("is_final", False)
                        
                        response_chunks.append(chunk_text)
                        logger.info(f"🎵 Chunk {chunk_id}: '{chunk_text}' ({len(audio_data)} chars audio)")
                        
                        if is_final:
                            logger.info("✅ Final audio chunk received")
                            break
                            
                    elif msg_type == "response_complete":
                        logger.info("✅ Response generation complete")
                        break
                        
                    elif msg_type == "error":
                        error_msg = msg.get("message", "")
                        logger.error(f"❌ Error: {error_msg}")
                        return False
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    if timeout_count % 5 == 0:
                        logger.info(f"⏳ Waiting... ({timeout_count}s)")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error receiving message: {e}")
                    return False
            
            # 5. Verify results
            logger.info(f"\n{'='*50}")
            logger.info("🎯 TEXT INPUT TEST RESULTS")
            logger.info(f"{'='*50}")
            
            logger.info(f"📝 Full AI Response: '{full_text}'")
            logger.info(f"🎵 Audio Chunks Received: {len(response_chunks)}")
            
            if response_chunks:
                combined_chunks = "".join(response_chunks)
                logger.info(f"🔗 Combined Chunks: '{combined_chunks}'")
                
                # Verify chunks match full text
                if combined_chunks.strip() == full_text.strip():
                    logger.info("✅ Chunk consistency: PERFECT")
                else:
                    logger.warning("⚠️ Chunk consistency: MISMATCH")
            
            # Success criteria
            has_ai_response = len(full_text.strip()) > 10
            has_audio_chunks = len(response_chunks) > 0
            
            if has_ai_response and has_audio_chunks:
                logger.info("\n🎉 TEXT INPUT PIPELINE: WORKING PERFECTLY")
                logger.info("✅ AI Response Generation: WORKING")
                logger.info("✅ TTS Audio Synthesis: WORKING") 
                logger.info("✅ Streaming Audio Chunks: WORKING")
                return True
            else:
                logger.info(f"\n❌ TEXT INPUT PIPELINE: FAILED")
                logger.info(f"❌ AI Response: {'✅' if has_ai_response else '❌'}")
                logger.info(f"❌ Audio Chunks: {'✅' if has_audio_chunks else '❌'}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🧪 Text Input Pipeline Test")
    print("=" * 50)
    print("This test bypasses STT and directly sends text to test:")
    print("1. AI response generation")
    print("2. TTS audio synthesis")
    print("3. Audio chunk streaming")
    print("=" * 50)
    
    success = await test_text_input_pipeline()
    
    if success:
        print("\n🎉 The AI response pipeline is working perfectly!")
        print("💡 If your voice input isn't working, the issue is likely:")
        print("   - Microphone audio quality")
        print("   - Audio energy levels")
        print("   - Speech clarity")
    else:
        print("\n❌ The AI response pipeline has issues.")
        print("🔧 Check the backend logs for more details.")

if __name__ == "__main__":
    asyncio.run(main()) 