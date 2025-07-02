# API Documentation

## Overview
The Spiritual Guidance Voice Agent API provides real-time voice interactions with AI-powered spiritual guides.

## Base URL
- Production: `https://your-app.onrender.com`
- Development: `http://localhost:8000`

## Authentication
LiveKit tokens are required for WebRTC connections. Use the token endpoint to generate authenticated tokens.

## Endpoints

### Health Check
```http
GET /health
HEAD /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-29T12:00:00Z",
  "service": "spiritual-guidance-api",
  "version": "1.0.0",
  "environment": "production",
  "components": {
    "websocket": "available",
    "llm": "gpt-4o-mini",
    "stt": "deepgram",
    "tts": "openai",
    "characters": ["adina", "raffa"]
  }
}
```

### Root Information
```http
GET /
HEAD /
```

**Response:**
```json
{
  "message": "Spiritual Guidance Voice Agent API",
  "version": "1.0.0",
  "status": "healthy",
  "characters": ["adina", "raffa"],
  "endpoints": {
    "health": "/health",
    "websocket": "/ws/audio",
    "token": "/api/spiritual-token",
    "legacy_token": "/api/createToken"
  },
  "docs": "/docs"
}
```

### Generate LiveKit Token
```http
POST /api/spiritual-token
```

**Request Body:**
```json
{
  "roomName": "room-adina-12345",
  "participantName": "user-12345",
  "character": "adina"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "url": "wss://your-livekit-url.livekit.cloud",
  "character": "adina",
  "room": "room-adina-12345"
}
```

### Legacy Token Endpoint
```http
POST /api/createToken
```
Same functionality as `/api/spiritual-token` for backward compatibility.

## Characters

### Adina - The Compassionate Guide
- **Room naming:** `room-adina-{uuid}`
- **Voice:** Nova (OpenAI)
- **Personality:** Empathetic, nurturing, gentle

### Raffa - The Wise Mentor
- **Room naming:** `room-raffa-{uuid}`
- **Voice:** Onyx (OpenAI)
- **Personality:** Wise, grounded, philosophical

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid character. Must be 'adina' or 'raffa'"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to generate token: [error message]"
}
```

## WebRTC Connection Flow

1. **Request Token:** POST to `/api/spiritual-token` with room and character info
2. **Connect to LiveKit:** Use returned token and URL to establish WebRTC connection
3. **Join Room:** Agent automatically joins when user connects
4. **Start Conversation:** Begin speaking - the agent will respond

## Rate Limiting
No rate limiting is currently implemented, but it's recommended for production use.

## CORS
Configured for:
- `http://localhost:3000` (React development)
- `http://localhost:19006` (Expo web)
- `https://*.onrender.com` (Deployment)
- `https://*.expo.dev` (Expo hosted apps) 