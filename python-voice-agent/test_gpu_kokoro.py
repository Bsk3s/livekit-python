#!/usr/bin/env python3
"""
Test GPU Acceleration for Kokoro TTS
Measures performance difference between GPU and CPU modes
"""

import asyncio
import logging
import time

import torch

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_gpu_acceleration():
    """Test GPU vs CPU performance for Kokoro TTS"""

    # Test text samples
    test_phrases = [
        "Hello, dear one. How are you feeling today?Hello, dear one. How are you feeling today?Hello, dear one. How are you feeling today?Hello, dear one. How are you feeling today?Hello, dear one. How are you feeling today?Hello, dear one. How are you feeling today?",
        "I'm here to provide spiritual guidance and support.",
        "Take a moment to breathe deeply and find your center.",
    ]

    try:
        # Import our GPU-enabled Kokoro
        from spiritual_voice_agent.services.tts.implementations.kokoro.kokoro import KokoroTTS

        kokoro = KokoroTTS()

        acceleration_type = {"GPU" if torch.cuda.is_available() else "CPU"}
        logger.info(f"🚀 Testing with: {acceleration_type} acceleration")

        # Run performance tests
        total_time = 0
        total_chars = 0
        import sounddevice as sd

        for i, phrase in enumerate(test_phrases):
            start_time = time.time()

            # Generate audio
            audio = kokoro.asynthesize(phrase)
            full_audio = b""
            async for chunk in audio:
                full_audio += chunk

            generation_time = (time.time() - start_time) * 1000
            total_time += generation_time
            total_chars += len(phrase)

            logger.info(f"🎵 Test {i+1}: {generation_time:.1f}ms for {len(phrase)} chars")
            logger.info(f"    Text: '{phrase[:50]}...'")
            # logger.info(f"    Audio: {len(samples)} samples at 24000Hz")

        # Summary
        avg_time = total_time / len(test_phrases)
        chars_per_ms = total_chars / total_time

        logger.info(f"\n🎯 {acceleration_type} PERFORMANCE SUMMARY:")
        logger.info(f"    Average time per phrase: {avg_time:.1f}ms")
        logger.info(f"    Processing speed: {chars_per_ms:.2f} chars/ms")
        logger.info(f"    Total characters: {total_chars}")
        logger.info(f"    Total time: {total_time:.1f}ms")

        if acceleration_type == "GPU":
            logger.info("✅ GPU acceleration is ACTIVE!")
            if avg_time < 500:
                logger.info("🚀 EXCELLENT: Sub-500ms TTS performance achieved!")
            elif avg_time < 800:
                logger.info("🎯 GOOD: Sub-800ms TTS performance achieved!")
            else:
                logger.info("⚠️ GPU acceleration may not be optimal")
        else:
            logger.info("💻 Using CPU-only processing")
            logger.info("ℹ️ For GPU acceleration, ensure CUDA and onnxruntime-gpu are installed")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    logger.info("🚀 GPU Kokoro Performance Test")
    logger.info("=" * 50)
    asyncio.run(test_gpu_acceleration())
