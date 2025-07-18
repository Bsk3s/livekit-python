#!/usr/bin/env python3

"""
🐛 Debug test for Phase 2C LLM Streaming

Simple test to see what messages the server sends back.
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_test():
    """Simple debug test to see all server messages"""
    try:
        async with websockets.connect("ws://localhost:10000/ws/audio") as websocket:
            # Initialize session
            init_message = {
                "type": "initialize",
                "character": "adina",
                "user_id": "debug_test"
            }
            
            await websocket.send(json.dumps(init_message))
            logger.info("📤 Sent initialization message")
            
            # Read all initialization messages
            for i in range(3):  # Read a few messages
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    logger.info(f"📨 Message {i+1}: {data.get('type')} - {data}")
                except asyncio.TimeoutError:
                    logger.info(f"⏱️ Timeout waiting for message {i+1}")
                    break
            
            # Send text message
            text_message = {
                "type": "text_message",
                "text": "Hello, test streaming!"
            }
            
            await websocket.send(json.dumps(text_message))
            logger.info("📤 Sent text message")
            
            # Read all response messages
            timeout_time = asyncio.get_event_loop().time() + 10.0  # 10 second timeout
            message_count = 0
            
            while asyncio.get_event_loop().time() < timeout_time:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    message_count += 1
                    logger.info(f"📨 Response {message_count}: {data.get('type')} - {data}")
                    
                    # Look for specific streaming events
                    if data.get('type') in ['llm_streaming_started', 'llm_token', 'streaming_audio_chunk', 'llm_streaming_complete']:
                        logger.info(f"🚀 STREAMING EVENT: {data.get('type')}")
                        
                except asyncio.TimeoutError:
                    logger.info("⏱️ No more messages")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error: {e}")
                    break
            
            logger.info(f"✅ Debug complete - received {message_count} response messages")
                    
    except Exception as e:
        logger.error(f"❌ Debug test error: {e}")


if __name__ == "__main__":
    asyncio.run(debug_test()) 