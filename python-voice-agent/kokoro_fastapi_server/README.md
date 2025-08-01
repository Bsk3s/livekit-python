# Kokoro FastAPI TTS Server

## 🎯 Solution Overview

This FastAPI server solves the LiveKit TTS integration issues by running Kokoro TTS as a separate HTTP service. The spiritual voice agent calls this server via HTTP instead of trying to use Kokoro directly with LiveKit's streaming TTS interface.

## 🏗️ Architecture

```
Frontend → LiveKit → spiritual_voice_agent → HTTP calls → Kokoro FastAPI Server
                                                      ↓
                                                  Free TTS Audio
```

### Benefits:
- ✅ **Bypasses LiveKit TTS issues** - No more ChunkedStream errors
- ✅ **Cost-free TTS** - Kokoro runs locally without API costs  
- ✅ **Character voices** - Adina (af_heart) and Raffa (am_adam)
- ✅ **Easy deployment** - Can deploy to Railway, Heroku, etc.
- ✅ **Future XTTS ready** - Same interface works for XTTS upgrade

## 🚀 Quick Start

### 1. Start Kokoro FastAPI Server
```bash
cd kokoro_fastapi_server
./start.sh
```

### 2. Test the Server
```bash
# From project root
python test_kokoro_fastapi.py
```

### 3. Start Spiritual Agent
```bash
# From project root  
source venv/bin/activate
python -m spiritual_voice_agent.main &
python -m spiritual_voice_agent.agents.spiritual_worker dev
```

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

### List Voices  
```bash
GET /voices
```

### Synthesize Speech
```bash
POST /synthesize
Content-Type: multipart/form-data

text: "Hello, welcome to spiritual guidance"
voice: "adina" | "raffa" | "default"
speed: 1.1 (optional)
language: "en" (optional)
```

## 🎭 Character Voices

- **adina**: af_heart (compassionate female voice)
- **raffa**: am_adam (wise male voice)  
- **default**: af_heart (fallback)

## 🔧 Configuration

### Environment Variables
- `KOKORO_SERVER_URL`: FastAPI server URL (default: http://localhost:5000)
- `KOKORO_VOICE`: Default voice (default: adina)
- `KOKORO_SPEED`: Speech speed (default: 1.1)

### Deployment
This server can be deployed to:
- **Railway** (~$5-20/month)
- **Heroku** 
- **DigitalOcean App Platform**
- **Any container service**

## 🧪 Testing

### Test FastAPI Server Only
```bash
python test_kokoro_fastapi.py
```

### Test Full Pipeline
1. Start FastAPI server
2. Start spiritual agent
3. Connect frontend
4. Test voice conversation

## 🚀 Future: XTTS Upgrade

To upgrade to XTTS later:
1. Replace Kokoro model with XTTS in `app/main.py`
2. Deploy to GPU instance  
3. Same HTTP interface - no agent changes needed!

## 📝 Files

- `app/main.py` - FastAPI server with Kokoro TTS
- `requirements.txt` - Python dependencies  
- `start.sh` - Server startup script
- `README.md` - This documentation 