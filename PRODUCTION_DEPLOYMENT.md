# 🌟 Spiritual Guidance Voice Agent - Production Deployment Guide

## Overview
This guide covers deploying the Heavenly Hub Voice Agent to production using Render for hosting both the FastAPI token service and LiveKit agent worker.

## Architecture
```
User Device (Expo App) 
    ↓ (requests token)
FastAPI Token Service (Render Web Service)
    ↓ (generates JWT)
User joins LiveKit room
    ↓ (triggers agent)
LiveKit Agent Worker (Render Worker Service)
    ↓ (spawns character)
Adina/Raffa Character Instance
```

## 🚀 Deployment Steps

### 1. LiveKit Cloud Setup
1. Sign up at [LiveKit Cloud](https://cloud.livekit.io)
2. Create a new project
3. Note your:
   - `LIVEKIT_URL` (e.g., `wss://your-project.livekit.cloud`)
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_API_SECRET`

### 2. Render Deployment

#### Option A: Deploy via GitHub (Recommended)
1. Push this repository to GitHub
2. Connect Render to your GitHub account
3. Create new services using `render.yaml`:
   - Go to Render Dashboard
   - Click "New" → "Blueprint"
   - Connect your repository
   - Render will automatically create both services

#### Option B: Manual Service Creation
1. **Token API Service**:
   - Type: Web Service
   - Build Command: `cd python-voice-agent && pip install -r requirements.txt`
   - Start Command: `cd python-voice-agent && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

2. **Agent Worker Service**:
   - Type: Background Worker
   - Build Command: `cd python-voice-agent && pip install -r requirements.txt`
   - Start Command: `cd python-voice-agent && python app/agents/spiritual_worker.py`

### 3. Environment Variables
Set these in Render for **both services**:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# AI Service Keys
DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key

# Environment
ENVIRONMENT=production
RENDER=true
```

### 4. Service URLs
After deployment, you'll get:
- **Token API**: `https://spiritual-token-api.onrender.com`
- **Agent Worker**: Runs in background (no public URL)

## 🧪 Testing Production Deployment

### 1. Test Token Generation
```bash
curl -X POST "https://spiritual-token-api.onrender.com/api/spiritual-token" \
  -H "Content-Type: application/json" \
  -d '{
    "character": "adina",
    "user_id": "test_user_123",
    "user_name": "Test User",
    "session_duration_minutes": 30
  }'
```

Expected response:
```json
{
  "token": "eyJ...",
  "room_name": "spiritual-adina-1234567890_abcd1234",
  "character": "adina",
  "expires_at": "2024-01-01T12:30:00Z",
  "session_id": "1234567890_abcd1234"
}
```

### 2. Test Health Check
```bash
curl https://spiritual-token-api.onrender.com/health
```

### 3. Test with Expo Client
Update your Expo app's API endpoint:
```javascript
const API_BASE_URL = 'https://spiritual-token-api.onrender.com';
```

## 📱 Mobile App Integration

### Update Expo Client
1. Update `expo-client/App.js`:
```javascript
const API_BASE_URL = 'https://spiritual-token-api.onrender.com';

// Use new token endpoint
const response = await fetch(`${API_BASE_URL}/api/spiritual-token`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    character: selectedCharacter,
    user_id: 'mobile_user_' + Date.now(),
    user_name: 'Mobile User',
    session_duration_minutes: 30
  })
});
```

## 🔧 Production Optimizations

### Performance Settings
- **Agent Worker**: Start with 1 instance, scale based on usage
- **Token API**: Auto-scaling enabled
- **Memory**: 512MB minimum for agent worker
- **CPU**: Standard plan recommended for production

### Monitoring
- Check Render logs for both services
- Monitor LiveKit Cloud dashboard for room activity
- Set up alerts for service health

### Security
- Restrict CORS origins to your domain
- Implement rate limiting for token endpoint
- Use environment-specific API keys
- Enable HTTPS only

## 🎭 Character Routing

The system automatically routes users to the correct character:
- Room names: `spiritual-{character}-{session_id}`
- Adina: Compassionate female guide (aura-2-luna-en voice)
- Raffa: Wise male mentor (aura-2-orion-en voice)

## 📊 Performance Metrics

### Target Performance
- **Token Generation**: <200ms
- **Agent Spawn**: <2 seconds
- **First Audio Chunk**: <300ms (achieved: ~226ms average)
- **Full Pipeline**: <500ms

### Scaling Guidelines
- 1 worker instance handles ~10 concurrent sessions
- Scale horizontally for more users
- Monitor CPU/memory usage in Render dashboard

## 🚨 Troubleshooting

### Common Issues
1. **Agent not spawning**: Check environment variables in worker service
2. **Token generation fails**: Verify LiveKit credentials
3. **Audio quality issues**: Check Deepgram API key and quota
4. **Connection timeouts**: Verify LiveKit URL format

### Debug Commands
```bash
# Check service logs
render logs --service spiritual-token-api
render logs --service spiritual-agent-worker

# Test locally
cd python-voice-agent
python -m pytest tests/
```

## 🎉 Success Checklist

- [ ] LiveKit Cloud project created
- [ ] Render services deployed successfully
- [ ] Environment variables configured
- [ ] Health check returns 200 OK
- [ ] Token generation works
- [ ] Agent worker starts without errors
- [ ] Expo app connects successfully
- [ ] Voice conversation works end-to-end
- [ ] Both characters (Adina/Raffa) accessible

## 📞 Support

For issues:
1. Check Render service logs
2. Verify environment variables
3. Test API endpoints manually
4. Check LiveKit Cloud dashboard
5. Review agent worker logs for character spawning

---

**🌟 Your Spiritual Guidance Voice Agent is now ready for production! 🌟** 