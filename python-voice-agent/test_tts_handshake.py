#!/usr/bin/env python3
"""
Test TTS WebSocket Handshake
Quick test to verify Deepgram TTS WebSocket connection works
"""

import asyncio
import json
import logging
import os
import websockets
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tts_handshake():
    """Test TTS WebSocket handshake and basic functionality"""
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("❌ DEEPGRAM_API_KEY not found")
        return False
    
    logger.info(f"🔑 Using API key: {api_key[:8]}...")
    
    websocket_url = "wss://api.deepgram.com/v1/tts-stream"
    headers = {
        "Authorization": f"Token {api_key.strip()}"
    }
    
    try:
        logger.info(f"🔗 Connecting to {websocket_url}")
        
        async with websockets.connect(websocket_url, extra_headers=headers) as websocket:
            logger.info(f"✅ WebSocket connected successfully!")
            logger.info(f"🌐 WebSocket state: {websocket.state}")
            
            # Send config message
            config_message = {
                "type": "config",
                "model": "aura-2-luna-en",
                "encoding": "linear16",
                "sample_rate": 24000,
                "container": "none"
            }
            
            await websocket.send(json.dumps(config_message))
            logger.info("📤 Sent config message")
            
            # Send a simple test text
            text_message = {
                "type": "text",
                "text": "Hello, this is a test."
            }
            
            await websocket.send(json.dumps(text_message))
            logger.info("📤 Sent test text")
            
            # Send flush to trigger synthesis
            flush_message = {"type": "flush"}
            await websocket.send(json.dumps(flush_message))
            logger.info("📤 Sent flush message")
            
            # Listen for responses (with timeout)
            audio_chunks = 0
            try:
                async with asyncio.timeout(10):  # 10 second timeout
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type", "unknown")
                            
                            if msg_type == "audio":
                                audio_chunks += 1
                                audio_data = data.get("audio", "")
                                logger.info(f"🎵 Received audio chunk #{audio_chunks} ({len(audio_data)} chars base64)")
                                
                                if audio_chunks >= 3:  # Stop after a few chunks
                                    logger.info("✅ Successfully received audio chunks!")
                                    break
                            
                            elif msg_type == "metadata":
                                logger.info(f"📊 Metadata: {data}")
                            
                            elif msg_type == "error":
                                logger.error(f"❌ Server error: {data.get('message', 'Unknown')}")
                                return False
                            
                            else:
                                logger.info(f"📨 Message type: {msg_type}")
                        
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ Invalid JSON: {message}")
                            continue
            
            except asyncio.TimeoutError:
                logger.warning("⏰ Timeout waiting for audio response")
                if audio_chunks == 0:
                    logger.error("❌ No audio chunks received - TTS may not be working")
                    return False
            
            if audio_chunks > 0:
                logger.info(f"✅ TTS WebSocket test successful! Received {audio_chunks} audio chunks")
                return True
            else:
                logger.error("❌ No audio chunks received")
                return False
    
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ WebSocket handshake failed with status {e.status_code}")
        if e.status_code == 401:
            logger.error("❌ Authentication failed - check your DEEPGRAM_API_KEY")
        elif e.status_code == 429:
            logger.error("❌ Rate limited - too many requests")
        elif e.status_code == 403:
            logger.error("❌ Access forbidden - check API key permissions")
        return False
    
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🧪 Testing TTS WebSocket Handshake...")
    success = asyncio.run(test_tts_handshake())
    
    if success:
        print("🎉 TTS WebSocket test PASSED!")
    else:
        print("💥 TTS WebSocket test FAILED!")
        print("🔍 Check your DEEPGRAM_API_KEY and network connection") 