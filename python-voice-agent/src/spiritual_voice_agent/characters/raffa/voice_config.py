class RaffaVoiceConfig:
    CONFIG = {
        "provider": "kokoro_tts",
        "voice_name": "am_adam",  # Wise male voice for Raffa
        "character_id": "raffa",
        "style_prompt": "Speak with gentle authority and paternal wisdom. Use a warm but strong tone that conveys spiritual guidance and strength.",
        "streaming": True,
        "sample_rate": 24000,  # Kokoro native sample rate
        "cost_per_request": 0.0,  # Local TTS = zero cost
    }
