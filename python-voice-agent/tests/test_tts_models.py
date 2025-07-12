#!/usr/bin/env python3
"""
TTS Model Testing Script
Easy way to test different TTS models for your voice agent
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_tts_model(model: str, character: str = "adina", text: str = None):
    """Test a specific TTS model"""

    if text is None:
        text = f"Hello, I'm {character.title()}, and I'm here to provide you with spiritual guidance and support."

    print(f"\n🧪 Testing TTS Model: {model}")
    print(f"🎭 Character: {character}")
    print(f"📝 Text: {text[:50]}...")

    try:
        # Set environment variable for this test
        os.environ["TTS_MODEL"] = model

        # Import after setting environment
        from app.services.tts_factory import TTSFactory

        # Create TTS service
        tts_service = TTSFactory.create_tts(character)
        print(f"✅ {model} TTS service created: {tts_service.__class__.__name__}")

        # Test synthesis
        frame_count = 0
        print("🎤 Starting synthesis...")

        audio_stream = tts_service.synthesize(text)

        async for audio_frame in audio_stream:
            frame_count += 1
            if frame_count == 1:
                print(f"🚀 First audio frame received!")
            if frame_count >= 5:  # Test first few frames
                break

        print(f"✅ Test completed: {frame_count} audio frames generated")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


async def test_all_models():
    """Test all available TTS models"""

    models = ["openai", "custom"]  # Add more as you implement them
    character = "adina"

    print("🎯 Testing All TTS Models")
    print("=" * 40)

    results = {}

    for model in models:
        success = await test_tts_model(model, character)
        results[model] = success

        if success:
            print(f"✅ {model}: PASSED")
        else:
            print(f"❌ {model}: FAILED")

        print("-" * 20)

    print("\n📊 Test Results Summary:")
    for model, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {model}: {status}")


async def interactive_test():
    """Interactive TTS testing"""

    print("\n🎮 Interactive TTS Testing")
    print("Available models: openai, custom")
    print("Available characters: adina, raffa")

    while True:
        print("\n" + "=" * 40)
        model = input("Enter TTS model (or 'quit'): ").strip().lower()

        if model == "quit":
            break

        character = input("Enter character (adina/raffa): ").strip().lower() or "adina"
        text = input("Enter text to synthesize (or press Enter for default): ").strip()

        await test_tts_model(model, character, text or None)


def main():
    """Main testing function"""
    print("🎙️ TTS Model Testing Tool")
    print("=" * 40)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "all":
            asyncio.run(test_all_models())
        elif command == "interactive":
            asyncio.run(interactive_test())
        elif command in ["openai", "custom"]:
            character = sys.argv[2] if len(sys.argv) > 2 else "adina"
            asyncio.run(test_tts_model(command, character))
        else:
            print(f"Unknown command: {command}")
    else:
        print("Usage:")
        print("  python test_tts_models.py all                    # Test all models")
        print("  python test_tts_models.py interactive            # Interactive testing")
        print("  python test_tts_models.py openai [character]     # Test specific model")
        print("  python test_tts_models.py custom [character]     # Test custom model")


if __name__ == "__main__":
    main()
