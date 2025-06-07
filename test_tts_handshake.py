#!/usr/bin/env python3
"""
Test TTS WebSocket handshake with Deepgram
"""
import asyncio
import json
import base64
import os
import sys
import websockets

async def test_tts_handshake():
    """Test WebSocket connection to Deepgram TTS endpoint"""
    
    # Get API key
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        print("❌ DEEPGRAM_API_KEY environment variable not set")
        return False
    
    print(f"🔑 Using API key: {api_key[:8]}...")
    
    # WebSocket URL and headers - CORRECTED URL
    url = "wss://api.deepgram.com/v1/speak?model=aura-2-luna-en&encoding=linear16&sample_rate=24000"
    headers = {
        "Authorization": f"Token {api_key.strip()}"
    }
    
    print(f"🌐 Connecting to: {url}")
    print(f"📋 Headers: {headers}")
    
    try:
        # Use websockets 15.0 API with additional_headers
        async with websockets.connect(url, additional_headers=headers) as websocket:
            print("✅ WebSocket connection established!")
            
            # Send a test message
            test_message = {
                "type": "Speak",
                "text": "Hello, this is a test message from the TTS handshake test."
            }
            
            print(f"📤 Sending test message: {test_message}")
            await websocket.send(json.dumps(test_message))
            
            # Send flush to trigger synthesis
            flush_message = {"type": "Flush"}
            print(f"📤 Sending flush message: {flush_message}")
            await websocket.send(json.dumps(flush_message))
            
            # Listen for responses with timeout
            audio_chunks_received = 0
            try:
                async with asyncio.timeout(10):  # 10 second timeout
                    while True:
                        try:
                            response = await websocket.recv()
                            
                            # Handle binary audio data
                            if isinstance(response, bytes):
                                audio_chunks_received += 1
                                print(f"🎵 Received audio chunk #{audio_chunks_received} ({len(response)} bytes)")
                                
                                if audio_chunks_received >= 5:  # Stop after 5 chunks
                                    break
                            else:
                                # Handle JSON messages
                                try:
                                    data = json.loads(response)
                                    print(f"📥 Received JSON: {data}")
                                except json.JSONDecodeError:
                                    print(f"📥 Received text: {response}")
                                    
                        except websockets.exceptions.ConnectionClosed:
                            print("🔌 WebSocket connection closed by server")
                            break
                            
            except asyncio.TimeoutError:
                print("⏰ Timeout waiting for audio response")
            
            # Send close message
            close_message = {"type": "Close"}
            print(f"📤 Sending close message: {close_message}")
            await websocket.send(json.dumps(close_message))
            
            print(f"✅ Test completed! Received {audio_chunks_received} audio chunks")
            return audio_chunks_received > 0
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket error: {e}")
        if hasattr(e, 'headers'):
            print(f"📋 Error headers: {dict(e.headers)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Testing Deepgram TTS WebSocket handshake...")
    print("=" * 50)
    
    success = await test_tts_handshake()
    
    print("=" * 50)
    if success:
        print("🎉 TTS WebSocket handshake test PASSED!")
    else:
        print("💥 TTS WebSocket handshake test FAILED!")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 