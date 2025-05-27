from livekit.plugins import deepgram
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def create_deepgram_stt():
    """Create an optimized Deepgram STT instance for real-time spiritual guidance"""
    logger.info("🎧 Creating optimized Deepgram STT instance")
    
    # Verify API key
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is required")
    
    # Create STT with optimized settings for conversation
    stt = deepgram.STT(
        model="nova-2",  # Latest model for best accuracy
        language="en",   # English language
        interim_results=True,  # Get partial results for responsiveness
        smart_format=True,     # Auto-format numbers, dates, etc.
        punctuate=True,        # Add punctuation
        diarize=False,         # Single speaker (user)
        multichannel=False,    # Mono audio
        alternatives=1,        # Single best result
        profanity_filter=False, # Allow natural speech
        redact=False,          # No redaction needed
        ner=False,             # No named entity recognition needed
        search=None,           # No search terms
        replace=None,          # No word replacement
        keywords=None,         # No keyword boosting
        utterance_end_ms=1000, # 1 second pause to end utterance
        vad_turnoff=250,       # 250ms to detect end of speech
    )
    
    logger.info("✅ Deepgram STT configured for real-time spiritual conversations")
    return stt 