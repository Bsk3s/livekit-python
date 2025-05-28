# Render Deployment Instructions

## 🎯 Goal: Deploy Both Services Together

You need **TWO services** running simultaneously:
1. ✅ **Token API** (already running at https://heavenly-new.onrender.com)
2. ❌ **Agent Worker** (needs to be deployed)

## 🚀 Deploy the Agent Worker

### Method 1: Manual Dashboard (Recommended)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Background Worker"**
3. Connect repository: `Bsk3s/livekit-python`
4. Branch: `main`

**Settings:**
- **Name**: `spiritual-agent-worker`
- **Environment**: `Python`
- **Build Command**: 
  ```bash
  pip install --upgrade pip && pip install -r python-voice-agent/requirements.txt
  ```
- **Start Command**:
  ```bash
  cd python-voice-agent && python app/agents/spiritual_worker.py
  ```

**Environment Variables** (copy from your web service):
```
LIVEKIT_URL=wss://your-livekit-url
LIVEKIT_API_KEY=your-api-key  
LIVEKIT_API_SECRET=your-api-secret
DEEPGRAM_API_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
ENVIRONMENT=production
RENDER=true
```

### Method 2: Blueprint Deployment

1. In Render dashboard, click **"New +"** → **"Blueprint"**
2. Connect repository: `Bsk3s/livekit-python`
3. Select blueprint file: `render-fixed.yaml`
4. Set all environment variables
5. Deploy

## ✅ Verification

Once both services are running:

1. **Token API**: https://heavenly-new.onrender.com/health
2. **Worker Logs**: Check for "🌟 Starting Spiritual Guidance Agent Worker"

## 🎭 Test End-to-End

1. Generate token: `POST https://heavenly-new.onrender.com/api/spiritual-token`
2. Use token to connect to LiveKit room
3. Agent should spawn and greet you as Adina or Raffa

## 🔧 Troubleshooting

- **Build fails**: Check build command paths match repository structure
- **Worker crashes**: Verify all environment variables are set
- **No agent spawns**: Check LiveKit URL and API credentials
- **TTS errors**: Verify Deepgram API key and permissions 