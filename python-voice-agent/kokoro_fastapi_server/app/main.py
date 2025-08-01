import os
import uuid
import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Import Kokoro TTS
from kokoro import KPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kokoro TTS FastAPI Server", version="1.0.0")

# Add CORS middleware for frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Kokoro model (singleton)
kokoro_model = None
VOICE_MAP = {
    "adina": "af_heart",
    "raffa": "am_adam",
    "default": "af_heart"
}

def get_kokoro_model():
    """Get or initialize Kokoro model singleton"""
    global kokoro_model
    if kokoro_model is None:
        logger.info("🎵 Initializing Kokoro TTS model...")
        kokoro_model = KPipeline(lang_code="a")  # 'a' = American English (correct initialization)
        logger.info("✅ Kokoro TTS model initialized successfully")
    return kokoro_model

@app.on_event("startup")
async def startup_event():
    """Initialize Kokoro model on startup"""
    get_kokoro_model()
    logger.info("🚀 Kokoro FastAPI server started")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "kokoro-tts-server",
        "voices": list(VOICE_MAP.keys())
    }

@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    voice: str = Form("adina"),
    speed: float = Form(1.1),
    language: str = Form("en")  # For compatibility with XTTS API
):
    """
    Synthesize speech using Kokoro TTS
    
    Args:
        text: Text to synthesize
        voice: Voice name (adina, raffa, default)
        speed: Speech speed (default: 1.1)
        language: Language code (ignored for Kokoro)
    
    Returns:
        WAV audio file
    """
    try:
        logger.info(f"🎤 Synthesizing: '{text[:50]}...' with voice '{voice}'")
        
        # Get Kokoro model
        model = get_kokoro_model()
        
        # Map voice name to Kokoro voice
        kokoro_voice = VOICE_MAP.get(voice.lower(), VOICE_MAP["default"])
        
        # Generate audio with Kokoro
        # Use the correct KPipeline calling pattern
        audio_gen = model(text, voice=kokoro_voice, speed=speed)
        
        # Collect all audio chunks from generator
        audio_chunks = []
        for gs, ps, audio in audio_gen:
            # audio is already a numpy array
            audio_chunks.append(audio)
        
        # Concatenate all chunks
        if audio_chunks:
            samples = np.concatenate(audio_chunks, axis=0)
            sample_rate = 24000  # Kokoro default sample rate
        else:
            raise Exception("No audio generated")
        
        # Convert to 16-bit PCM if needed
        if samples.dtype != np.int16:
            samples = (samples * 32767).astype(np.int16)
        
        # Create temporary output file
        output_path = f"/tmp/kokoro_{uuid.uuid4()}_output.wav"
        
        # Save as WAV file
        sf.write(output_path, samples, sample_rate)
        
        logger.info(f"✅ Generated {len(samples)} samples at {sample_rate}Hz → {output_path}")
        
        # Return audio file
        return FileResponse(
            output_path, 
            media_type="audio/wav",
            filename=f"kokoro_audio_{uuid.uuid4().hex[:8]}.wav"
        )
        
    except Exception as e:
        logger.error(f"❌ Kokoro synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")

@app.get("/voices")
async def list_voices():
    """List available voices"""
    return {
        "voices": [
            {"name": "adina", "kokoro_voice": "af_heart", "description": "Compassionate spiritual guide"},
            {"name": "raffa", "kokoro_voice": "am_adam", "description": "Wise spiritual mentor"},
            {"name": "default", "kokoro_voice": "af_heart", "description": "Default voice"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 