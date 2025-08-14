class AdinaVoiceConfig:
    CONFIG = {
        "provider": "kokoro_tts",
        "voice_name": "af_heart",  # Compassionate female voice for Adina
        "character_id": "adina",
        "style_prompt": "Speak with warmth, compassion, and gentle wisdom. Use a nurturing tone that feels like a caring spiritual mentor.",
        "streaming": True,
        "sample_rate": 24000,  # Kokoro native sample rate
        "cost_per_request": 0.0,  # Local TTS = zero cost
    }
