#!/usr/bin/env python3
"""
TTS Factory - Kokoro Only (No Bloat)
"""

import logging
from livekit.agents import tts

logger = logging.getLogger(__name__)


class TTSFactory:
    """Factory for creating Kokoro TTS - simplified, no bloat"""

    @staticmethod
    def create_tts(character: str) -> tts.TTS:
        """Create TTS service - back to FREE Kokoro TTS"""
        logger.info(f"🎵 Creating Kokoro TTS for {character} (FREE)")
        return TTSFactory._create_kokoro_tts(character)

    @staticmethod
    def _create_kokoro_tts(character: str) -> tts.TTS:
        """Create Kokoro TTS service (free, local TTS)"""
        from .tts.implementations.kokoro.kokoro import create_kokoro_tts
        
        logger.info(f"✅ Creating Kokoro TTS for {character} (FREE)")
        return create_kokoro_tts(character)

    @staticmethod
    def get_tts_config() -> dict:
        """Get TTS configuration - Kokoro TTS (free, local)"""
        return {
            "type": "kokoro",
            "provider": "Kokoro (Local)",
            "voices": ["af_heart", "am_adam"],
            "sample_rate": 16000,
            "free": True,
            "local": True
        }
