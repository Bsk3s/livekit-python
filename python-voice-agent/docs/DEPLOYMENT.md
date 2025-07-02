# Deployment Guide

## Overview
This guide covers deploying the Spiritual Guidance Voice Agent to production environments.

## Prerequisites

### Required Services
1. **LiveKit Cloud Account**
   - Sign up at [livekit.io](https://livekit.io)
   - Create a project and note your credentials

2. **OpenAI API Account**
   - Get API key from [platform.openai.com](https://platform.openai.com)
   - Ensure sufficient credits for TTS and LLM usage

3. **Deepgram API Account**
   - Sign up at [deepgram.com](https://deepgram.com)
   - Get API key for speech-to-text

## Render Deployment (Recommended)

### 1. Prepare Repository
```bash
git add .
git commit -m "Clean up and prepare for deployment"
git push origin main
```

### 2. Create Render Service
1. Go to [render.com](https://render.com)
2. Connect your GitHub repository
3. Create a new **Web Service**
4. Use these settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python start_unified_service.py`
   - **Environment:** Docker

### 3. Environment Variables
Set these in Render dashboard:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=sk-your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
ENVIRONMENT=production
PORT=8000
```

### 4. Deploy
- Render will automatically deploy on git push
- Monitor logs for any startup issues
- Test health endpoint: `https://your-app.onrender.com/health`

## Alternative Deployments

### Railway
```yaml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python start_unified_service.py"
```

### Heroku
```yaml
# Procfile
web: python start_unified_service.py
```

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "start_unified_service.py"]
```

## Production Considerations

### 1. Environment Variables
- Never commit API keys to git
- Use secure environment variable management
- Regularly rotate API keys

### 2. Monitoring
- Set up health check monitoring
- Monitor API usage and costs
- Set up log aggregation

### 3. Scaling
- Monitor concurrent user limits
- Consider LoadBalancer for multiple instances
- Monitor LiveKit room limits

### 4. Security
- Implement rate limiting
- Add request validation
- Monitor for abuse

### 5. Backup
- Regular database backups (if using)
- Configuration backups
- Document recovery procedures

## Troubleshooting

### Common Deployment Issues

1. **Service Won't Start**
   - Check all environment variables are set
   - Verify API key formats (no extra whitespace)
   - Check logs for specific error messages

2. **Agent Not Connecting**
   - Verify LIVEKIT_URL format (must start with `wss://`)
   - Check LiveKit credentials
   - Ensure WebRTC ports are open

3. **Audio Issues**
   - Test STT/TTS services independently
   - Check API quotas and limits
   - Verify audio format compatibility

### Performance Optimization

1. **Reduce Latency**
   - Use closest data centers
   - Optimize TTS settings
   - Implement audio streaming

2. **Cost Optimization**
   - Monitor API usage
   - Implement usage limits
   - Cache common responses

3. **Reliability**
   - Implement health checks
   - Add retry logic
   - Monitor error rates

## Maintenance

### Regular Tasks
- Monitor API usage and costs
- Update dependencies
- Review logs for errors
- Test all functionality

### Updates
```bash
# Safe deployment process
git checkout main
git pull origin main
pip install -r requirements.txt
python -m pytest tests/
# Deploy to staging first
# Then deploy to production
``` 