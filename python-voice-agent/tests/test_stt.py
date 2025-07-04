import os
import asyncio
import sounddevice as sd
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
# from spiritual_voice_agent.services.deepgram_service import create_deepgram_stt  # Service refactored
from spiritual_voice_agent.services.stt.implementations.deepgram import DeepgramSTTService

def create_deepgram_stt():
    """Legacy compatibility function"""
    return DeepgramSTTService()

async def test_stt_config():
    """Test Deepgram STT configuration and real-time transcription."""
    print("\n=== Deepgram STT Configuration Test ===")
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Debug information
    print("\nDebug Information:")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Environment variables:")
    for key, value in os.environ.items():
        if 'DEEPGRAM' in key or 'LIVEKIT' in key:
            print(f"{key}: {'*' * len(value) if value else 'Not set'}")
    
    try:
        # Test configuration
        stt = create_deepgram_stt()
        print("\n✅ STT configuration successful")
        
        # Print STT information
        print("\nSTT Information:")
        print(f"Label: {stt.label}")
        print(f"Capabilities:")
        print(f"  - Streaming: {stt.capabilities.streaming}")
        print(f"  - Interim Results: {stt.capabilities.interim_results}")
        
        # List available audio devices with more details
        print("\nAvailable audio input devices:")
        devices = sd.query_devices()
        input_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # Only show input devices
                input_devices.append((i, device))
                print(f"\nDevice {i}:")
                print(f"  Name: {device['name']}")
                print(f"  Input Channels: {device['max_input_channels']}")
                print(f"  Default Sample Rate: {device['default_samplerate']}")
                print(f"  Host API: {device['hostapi']}")
        
        if not input_devices:
            print("\n❌ No audio input devices found!")
            print("Please check your microphone connection and permissions.")
            return
            
        # Get user's choice of audio device
        device_id = int(input("\nEnter the number of your microphone device: "))
        
        print("\nStarting real-time transcription...")
        print("Speak into your microphone. Press Ctrl+C to stop.")
        
        # Audio parameters
        sample_rate = 16000
        channels = 1
        
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            # Process audio data
            audio_data = np.frombuffer(indata, dtype=np.float32)
            asyncio.create_task(process_audio(audio_data))
        
        async def process_audio(audio_data):
            try:
                result = await stt.recognize(audio_data)
                if result and result.text:
                    print(f"\nTranscription: {result.text}")
            except Exception as e:
                print(f"Error: {e}")
        
        # Start audio stream
        with sd.InputStream(device=device_id,
                          callback=audio_callback,
                          channels=channels,
                          samplerate=sample_rate,
                          dtype=np.float32):
            try:
                while True:
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                print("\nStopping test...")
                await stt.aclose()
                    
    except Exception as e:
        print(f"\n❌ STT configuration failed: {e}")
        return

def test_stt_with_wav():
    """Test Deepgram STT with a prerecorded WAV file."""
    print("\n=== Deepgram STT WAV File Test ===")
    load_dotenv()
    stt = create_deepgram_stt()
    # Load audio file (mono, 16kHz)
    wav_path = "test_audio.wav"
    if not os.path.exists(wav_path):
        print(f"❌ WAV file '{wav_path}' not found. Please add a test WAV file.")
        return
    audio_data, sample_rate = sf.read(wav_path, dtype='float32')
    if len(audio_data.shape) > 1:
        audio_data = audio_data[:, 0]  # Use first channel if stereo
    async def run():
        result = await stt.recognize(audio_data)
        print("Transcription:", result.text if result else "No result")
    asyncio.run(run())

if __name__ == "__main__":
    # test_stt_config()  # Commented out for now
    test_stt_with_wav() 