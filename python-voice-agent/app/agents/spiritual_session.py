from livekit.agents import (
    Agent, AgentSession, JobContext, WorkerOptions, cli, room_io
)
from livekit.plugins import deepgram, openai, silero, noise_cancellation

# Try to import turn detector, but make it optional
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    TURN_DETECTOR_AVAILABLE = True
except ImportError as e:
    TURN_DETECTOR_AVAILABLE = False
    print(f"⚠️ Turn detector plugin not available: {e}")
    print("🔄 Agent will use standard VAD-based turn detection")

import logging
import time
import asyncio
from dotenv import load_dotenv

from characters.character_factory import CharacterFactory
from services.deepgram_service import create_deepgram_stt
from services.llm_service import create_gpt4o_mini
from services.livekit_deepgram_tts import LiveKitDeepgramTTS

load_dotenv()
logger = logging.getLogger(__name__)

# ... existing code ... 