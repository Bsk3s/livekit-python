import requests
import json
import jwt
import time

LIVEKIT_API_KEY = "APIjsXZYsEhhs8h"
LIVEKIT_API_SECRET = "h7DjYDxADoyimyJzb7SsK3I5BRAkHY0rU2hNRnpzWpM"


def generate_jwt(api_key, api_secret):
    now = int(time.time())
    payload = {
        "iss": api_key,
        "nbf": now,
        "exp": now + 60 * 5,  # 5 minutes expiry
        "admin": True
    }
    token = jwt.encode(payload, api_secret, algorithm="HS256")
    return token

def test_room_connection():
    # LiveKit server URL
    url = "https://hb-j73yzwmu.livekit.cloud"
    
    # Generate JWT for REST API
    jwt_token = generate_jwt(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    # Test room name
    room_name = "test-room"
    
    # First, try to get room info
    print(f"Checking room {room_name}...")
    try:
        response = requests.get(f"{url}/twirp/livekit.Room/ListRooms", headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            try:
                rooms = response.json()
                print("Available rooms:", json.dumps(rooms, indent=2))
            except Exception as json_err:
                print(f"Failed to parse JSON response: {json_err}")
    except requests.exceptions.RequestException as e:
        print(f"Error checking rooms: {e}")
        return
    
    # Try to create the room if it doesn't exist
    print(f"\nCreating room {room_name}...")
    try:
        create_data = {
            "name": room_name,
            "empty_timeout": 300,
            "max_participants": 10
        }
        response = requests.post(
            f"{url}/twirp/livekit.Room/CreateRoom",
            headers=headers,
            json=create_data
        )
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("Room created successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Error creating room: {e}")
        return
    
    # Get room info again to verify
    print(f"\nVerifying room {room_name}...")
    try:
        response = requests.get(f"{url}/twirp/livekit.Room/ListRooms", headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            try:
                rooms = response.json()
                print("Updated room list:", json.dumps(rooms, indent=2))
            except Exception as json_err:
                print(f"Failed to parse JSON response: {json_err}")
    except requests.exceptions.RequestException as e:
        print(f"Error verifying room: {e}")
        return

if __name__ == "__main__":
    test_room_connection() 