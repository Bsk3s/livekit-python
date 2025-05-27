import asyncio
import json
import jwt
import time
import websockets

LIVEKIT_WS_URL = "wss://hb-j73yzwmu.livekit.cloud"
LIVEKIT_API_KEY = "APIjsXZYsEhhs8h"
LIVEKIT_API_SECRET = "h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM"

def generate_token(room_name, participant_name):
    now = int(time.time())
    payload = {
        "iss": LIVEKIT_API_KEY,
        "sub": participant_name,
        "nbf": now,
        "exp": now + 60 * 5,  # 5 minutes expiry
        "room": room_name,
        "room_join": True,
        "can_publish": True,
        "can_subscribe": True
    }
    token = jwt.encode(payload, LIVEKIT_API_SECRET, algorithm="HS256")
    return token

async def connect_to_room(room_name, participant_name):
    # Generate token
    token = generate_token(room_name, participant_name)
    
    # Connect to LiveKit WebSocket with token as query parameter
    uri = f"{LIVEKIT_WS_URL}/rtc/{room_name}?access_token={token}"
    print(f"Connecting to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to LiveKit room!")
            # Listen for messages
            while True:
                try:
                    message = await websocket.recv()
                    print(f"Received message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
    except Exception as e:
        print(f"Error connecting to room: {e}")

async def main():
    room_name = "test-room"
    participant_name = "test-user"
    print(f"Connecting to room '{room_name}' as '{participant_name}'...")
    await connect_to_room(room_name, participant_name)

if __name__ == "__main__":
    asyncio.run(main()) 