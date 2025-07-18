from spiritual_voice_agent.services.stt.implementations.streaming_deepgram import StreamingDeepgramSTTService


def create_deepgram_stt():
    """Create optimized streaming Deepgram STT for sub-100ms latency"""
    return StreamingDeepgramSTTService({
        "model": "nova-2",  # Optimized for speed
        "language": "en-US",  # Single language for speed
    })
