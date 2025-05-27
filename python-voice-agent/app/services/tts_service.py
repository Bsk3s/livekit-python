from livekit.plugins import google

def create_gemini_tts(agent):
    voice_config = agent.get_voice_config()
    
    return google.TTS(
        model="gemini-2.5-flash-tts",
        voice=voice_config["voice"],
        language="en-US",
        speaking_rate=1.0,        # Natural speaking pace
        pitch=0.0,               # Natural pitch
        volume_gain_db=0.0,      # Natural volume
        effects_profile_id="large-home-entertainment-class-device",  # Optimized for voice
        audio_encoding="MP3",    # High quality audio
        sample_rate_hertz=24000  # High quality sample rate
    ) 