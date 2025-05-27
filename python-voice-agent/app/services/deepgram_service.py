from livekit.plugins import deepgram
import os

def create_deepgram_stt():
    # Verify API key is set
    if not os.getenv("DEEPGRAM_API_KEY"):
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")
    return deepgram.STT(
        model="nova-3",          # Latest model with 53.4% WER reduction
        language="multi",        # Multilingual auto-detection
        interim_results=True,    # Real-time partial transcripts
        punctuate=True,          # Smart punctuation
        smart_format=True,       # Auto-format numbers, dates, etc.
        no_delay=True,          # Minimize latency for real-time
        endpointing_ms=25,      # Quick speech boundary detection
        filler_words=True,      # Keep natural speech patterns
        sample_rate=16000,      # Standard audio quality
        profanity_filter=False, # Keep natural spiritual language
        numerals=False,         # Spell out numbers for clarity
    ) 