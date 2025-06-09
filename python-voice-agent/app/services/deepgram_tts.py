#!/usr/bin/env python3
"""
Single source of truth for Deepgram TTS - imports from the working implementation
This ensures no import conflicts and LiveKit gets the correct class
"""

# Import the working implementation
from .livekit_deepgram_tts import LiveKitDeepgramTTS

# Re-export for compatibility
__all__ = ['LiveKitDeepgramTTS']

import logging
logger = logging.getLogger(__name__)
logger.info("🔗 Deepgram TTS: Importing from livekit_deepgram_tts.py (single source of truth)") 