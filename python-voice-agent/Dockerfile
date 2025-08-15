FROM python:3.11-slim

# Install system dependencies for voice AI
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the entire project first
COPY . .

# Install dependencies using Railway build command (no requirements file needed)
RUN pip install --no-cache-dir \
    fastapi==0.115.7 \
    uvicorn[standard]==0.33.0 \
    livekit-agents==1.2.2 \
    livekit-api==0.18.8 \
    openai==1.61.0 \
    deepgram-sdk==3.8.5 \
    python-dotenv==1.0.1 \
    supabase==2.17.0

# Create necessary directories
RUN mkdir -p spiritual_voice_agent/config logs

# Make scripts executable
RUN chmod +x start-complete-system.sh start-simple.sh start-production.sh start-railway.sh stop.sh

# Expose Railway's dynamic port (Railway sets PORT env var)
EXPOSE $PORT

# Health check (Railway uses PORT, not fixed 10000)
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Use direct Python execution to avoid shell issues
CMD ["python", "startup.py"]