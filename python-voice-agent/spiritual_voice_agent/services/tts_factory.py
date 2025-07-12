#!/usr/bin/env python3
"""
TTS Factory - Easy Model Swapping for Testing
Change one line to switch between different TTS models
"""

import logging
import os
from typing import Any, Dict, Optional

from livekit.agents import tts

logger = logging.getLogger(__name__)

# 🔧 EASY CONFIGURATION: Change this to switch TTS models
TTS_MODEL = os.getenv("TTS_MODEL", "wav")  # openai, custom, gemini, elevenlabs, wav


class TTSFactory:
    """Factory for creating different TTS services - easy model swapping"""

    @staticmethod
    def create_tts(character: str = "default", model_override: Optional[str] = None) -> tts.TTS:
        """
        Create TTS service based on configuration

        Args:
            character: Character name (adina, raffa)
            model_override: Override the default model for testing

        Returns:
            TTS service instance
        """
        model = model_override or TTS_MODEL

        logger.info(f"🎙️ Creating TTS service: {model} for character: {character}")

        try:
            if model == "openai":
                return TTSFactory._create_openai_tts(character)
            elif model == "custom":
                return TTSFactory._create_custom_tts(character)
            elif model == "gemini":
                return TTSFactory._create_gemini_tts(character)
            elif model == "elevenlabs":
                return TTSFactory._create_elevenlabs_tts(character)
            elif model == "wav":
                return TTSFactory._create_wav_tts(character)
            elif model == "kokoro":
                return TTSFactory._create_kokoro_tts(character)
            else:
                logger.warning(f"⚠️ Unknown TTS model: {model}, falling back to MP3")
                return TTSFactory._create_wav_tts(character)

        except Exception as e:
            logger.error(f"❌ Failed to create {model} TTS: {e}")
            logger.info("🛡️ Falling back to OpenAI TTS")
            return TTSFactory._create_openai_tts(character)

    @staticmethod
    def _create_openai_tts(character: str) -> tts.TTS:
        """Create OpenAI TTS service"""
        from livekit.plugins import openai

        # Character-specific voices
        voice_map = {
            "adina": "nova",  # Warm, feminine
            "raffa": "onyx",  # Deep, masculine
            "default": "alloy",  # Neutral
        }

        voice = voice_map.get(character.lower(), "alloy")

        logger.info(f"✅ Creating OpenAI TTS (voice: {voice})")
        return openai.TTS(voice=voice, model="tts-1-hd")

    @staticmethod
    def _create_custom_tts(character: str) -> tts.TTS:
        """Create your custom TTS service"""
        from .custom_tts_service import create_custom_tts

        logger.info(f"✅ Creating Custom TTS for {character}")
        return create_custom_tts(character)

    @staticmethod
    def _create_gemini_tts(character: str) -> tts.TTS:
        """Create Gemini TTS service (if you have it configured)"""
        try:
            # Gemini TTS via LiveKit plugin (if available)
            from livekit.plugins import google

            logger.info(f"✅ Creating Gemini TTS for {character}")
            return google.TTS(language="en-US")
        except ImportError:
            logger.warning("⚠️ Gemini TTS not available, falling back to OpenAI")
            return TTSFactory._create_openai_tts(character)

    @staticmethod
    def _create_elevenlabs_tts(character: str) -> tts.TTS:
        """Create ElevenLabs TTS service (if you have it configured)"""
        try:
            from livekit.plugins import elevenlabs

            # You would configure ElevenLabs voices here
            voice_map = {
                "adina": "your-elevenlabs-voice-id-1",
                "raffa": "your-elevenlabs-voice-id-2",
                "default": "default-voice-id",
            }

            voice_id = voice_map.get(character.lower(), voice_map["default"])

            logger.info(f"✅ Creating ElevenLabs TTS (voice: {voice_id})")
            return elevenlabs.TTS(voice_id=voice_id)

        except ImportError:
            logger.warning("⚠️ ElevenLabs TTS not available, falling back to OpenAI")
            return TTSFactory._create_openai_tts(character)

    @staticmethod
    def _create_wav_tts(character: str) -> tts.TTS:
        """Create WAV TTS service"""
        from .custom_tts_service import create_wav_tts

        logger.info(f"✅ Creating WAV TTS for {character}")
        return create_wav_tts(character)

    @staticmethod
    def _create_kokoro_tts(character: str) -> tts.TTS:
        """Create kokoro TTS service"""
        from .custom_tts_service import create_kokoro_tts

        logger.info(f"✅ Creating WAV TTS with Kokoro")
        return create_kokoro_tts(character)


# 🎯 TESTING UTILITIES


def list_available_models() -> Dict[str, str]:
    """List all available TTS models"""
    return {
        "openai": "OpenAI TTS-1 HD (reliable, fast)",
        "custom": "Your Custom TTS Model",
        "gemini": "Google Gemini TTS (if configured)",
        "elevenlabs": "ElevenLabs TTS (if configured)",
    }


def test_tts_model(
    model: str, character: str = "adina", test_text: str = "Hello, this is a test."
) -> bool:
    """
    Quick test function for TTS models
    """
    logger.info(f"🧪 Testing TTS model: {model} with character: {character}")

    try:
        tts_service = TTSFactory.create_tts(character, model_override=model)
        logger.info(f"✅ {model} TTS created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ {model} TTS test failed: {e}")
        return False


# 🔧 ENVIRONMENT-BASED CONFIGURATION


def get_tts_config() -> Dict[str, Any]:
    """Get current TTS configuration"""
    return {
        "current_model": TTS_MODEL,
        "available_models": list_available_models(),
        "model_source": "environment" if "TTS_MODEL" in os.environ else "default",
    }
