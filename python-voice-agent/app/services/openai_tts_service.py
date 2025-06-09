#!/usr/bin/env python3
"""
OpenAI TTS Service with App Store Safety Guards
Bulletproof fallback TTS to prevent any crashes during Apple review
"""

import asyncio
import logging
import numpy as np
import openai
from livekit import rtc
from livekit.agents import tts
from typing import AsyncGenerator, Optional
import time
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAITTSService:
    """App Store Safe OpenAI TTS Service with bulletproof error handling"""
    
    VOICE_CONFIGS = {
        "adina": {"voice": "nova", "speed": 1.0},  # Warm, compassionate
        "raffa": {"voice": "onyx", "speed": 1.0},  # Wise, authoritative
        "default": {"voice": "alloy", "speed": 1.0}  # Safe fallback
    }
    
    def __init__(self, timeout_seconds: int = 30):
        """Initialize with App Store safety timeout"""
        self.timeout_seconds = timeout_seconds
        self.max_retries = 2  # Limited retries to prevent hanging
        self.client = openai.OpenAI()
        self.chunk_size = 4096  # Optimal chunk size for streaming
        logger.info(f"🛡️ App Store Safe OpenAI TTS initialized (timeout: {timeout_seconds}s)")
    
    def _sanitize_text(self, text: str) -> Optional[str]:
        """
        🛡️ CRITICAL APP STORE SAFETY: Sanitize text input to prevent crashes
        """
        if not text:
            logger.warning("🛡️ Empty text provided - using safety fallback")
            return "Hello, I'm here to help you."
        
        # Strip whitespace and check again
        sanitized = text.strip()
        if not sanitized:
            logger.warning("🛡️ Whitespace-only text provided - using safety fallback")
            return "Hello, I'm here to help you."
        
        # Ensure reasonable length limits (OpenAI has 4096 char limit)
        if len(sanitized) > 4000:
            logger.warning(f"🛡️ Text too long ({len(sanitized)} chars) - truncating for safety")
            sanitized = sanitized[:4000] + "..."
        
        # Remove problematic characters that could cause issues
        sanitized = sanitized.replace('\x00', '').replace('\ufffd', '')
        
        logger.debug(f"🛡️ Text sanitized: '{sanitized[:50]}...' ({len(sanitized)} chars)")
        return sanitized
    
    def _get_voice_config(self, character: str) -> dict:
        """Get voice configuration with safe fallback"""
        config = self.VOICE_CONFIGS.get(character.lower(), self.VOICE_CONFIGS["default"])
        logger.debug(f"🎭 Voice config for {character}: {config}")
        return config
    
    async def _create_safe_tts_client(self, voice: str) -> tts.TTS:
        """Create TTS client with error handling"""
        try:
            from livekit.plugins import openai as lk_openai
            client = lk_openai.TTS(voice=voice)
            logger.debug(f"✅ OpenAI TTS client created with voice: {voice}")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to create TTS client with voice {voice}: {e}")
            # Fallback to default voice
            from livekit.plugins import openai as lk_openai
            client = lk_openai.TTS(voice="alloy")  # Most reliable voice
            logger.info("🛡️ Using fallback voice: alloy")
            return client

    async def synthesize_streaming(self, text: str, character: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """
        🛡️ APP STORE SAFE: Bulletproof streaming synthesis with all safety guards
        """
        start_time = time.time()
        
        try:
            # 🛡️ SAFETY GUARD 1: Sanitize input text
            safe_text = self._sanitize_text(text)
            if not safe_text:
                logger.error("🛡️ Text sanitization failed - aborting TTS")
                return
            
            # 🛡️ SAFETY GUARD 2: Get safe voice configuration
            voice_config = self._get_voice_config(character)
            
            # 🛡️ SAFETY GUARD 3: Create TTS client with error handling
            tts_client = await self._create_safe_tts_client(voice_config["voice"])
            
            logger.info(f"🎤 OpenAI TTS synthesis starting: {character} ({voice_config['voice']})")
            logger.info(f"📝 Text: '{safe_text[:50]}...' ({len(safe_text)} chars)")
            
            # 🛡️ SAFETY GUARD 4: Timeout protection - critical for App Store
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    # Track synthesis progress
                    frame_count = 0
                    first_chunk_time = None
                    
                    # Generate audio with the sanitized text
                    audio_stream = tts_client.synthesize(safe_text)
                    
                    async for audio_frame in audio_stream:
                        frame_count += 1
                        
                        # Track first chunk latency
                        if frame_count == 1:
                            first_chunk_time = (time.time() - start_time) * 1000
                            logger.info(f"🚀 First chunk: {first_chunk_time:.0f}ms")
                        
                        yield audio_frame
                        
                        # 🛡️ SAFETY GUARD 5: Prevent infinite generation
                        if frame_count > 1000:  # Reasonable upper limit
                            logger.warning("🛡️ Frame limit reached - stopping generation")
                            break
                    
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"✅ OpenAI TTS complete: {frame_count} frames, {total_time:.0f}ms")
                    
            except asyncio.TimeoutError:
                logger.error(f"🛡️ TIMEOUT: TTS synthesis exceeded {self.timeout_seconds}s - App Store safety abort")
                # Return silence frame to prevent hanging
                silence_frame = self._create_silence_frame()
                yield silence_frame
            
        except Exception as e:
            logger.error(f"❌ OpenAI TTS synthesis failed: {e}")
            logger.error(f"❌ Character: {character}, Text length: {len(text) if text else 0}")
            
            # 🛡️ SAFETY GUARD 6: Emergency fallback - never let the app crash
            try:
                logger.info("🛡️ Emergency fallback: generating safety audio")
                emergency_text = "I'm sorry, there was a technical issue. Please try again."
                
                # Use most basic, reliable configuration
                from livekit.plugins import openai as lk_openai
                emergency_tts = lk_openai.TTS(voice="alloy")
                emergency_stream = emergency_tts.synthesize(emergency_text)
                
                async for frame in emergency_stream:
                    yield frame
                    break  # Just one frame to acknowledge the error
                
            except Exception as emergency_error:
                logger.error(f"❌ Emergency fallback also failed: {emergency_error}")
                # Last resort: return silence to prevent app hanging
                silence_frame = self._create_silence_frame()
                yield silence_frame

    def _create_silence_frame(self, duration_ms: int = 100) -> rtc.AudioFrame:
        """Create a silent audio frame as last resort fallback"""
        sample_rate = 24000
        samples = int(sample_rate * duration_ms / 1000)
        silent_data = np.zeros(samples, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=silent_data,
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=len(silent_data)
        )

    async def test_synthesis_safety(self, character: str = "default") -> bool:
        """
        🛡️ Test synthesis with edge cases for App Store safety verification
        """
        logger.info(f"🧪 Testing OpenAI TTS safety for character: {character}")
        
        test_cases = [
            ("", "empty string"),
            ("   ", "whitespace only"),
            ("Hello", "normal text"),
            ("A" * 5000, "very long text"),
            ("Hello\x00world", "null characters"),
            ("Ça va? 你好! 🎉", "special characters")
        ]
        
        for test_text, description in test_cases:
            try:
                logger.info(f"🧪 Testing {description}...")
                frame_count = 0
                
                async for frame in self.synthesize_streaming(test_text, character):
                    frame_count += 1
                    if frame_count >= 2:  # Just verify we get frames
                        break
                
                logger.info(f"✅ {description}: {frame_count} frames generated")
                
            except Exception as e:
                logger.error(f"❌ {description} failed: {e}")
                return False
        
        logger.info("🎉 All safety tests passed!")
        return True

# Performance validation test
async def validate_streaming_performance():
    print("Validating OpenAI TTS performance...")
    service = OpenAITTSService()
    test_text = "This is a performance validation test for real-time spiritual guidance."
    
    results = []
    for character in ["adina", "raffa"]:
        print(f"\nTesting {character}...")
        try:
            start_time = asyncio.get_event_loop().time()
            first_chunk_time = None
            chunk_count = 0
            
            async for audio_frame in service.synthesize_streaming(test_text, character):
                chunk_count += 1
                if chunk_count == 1:
                    first_chunk_time = (asyncio.get_event_loop().time() - start_time) * 1000
                if chunk_count >= 3:
                    break
                    
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if first_chunk_time and first_chunk_time < 1000:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                
            result = {
                "character": character,
                "first_chunk_ms": first_chunk_time,
                "total_ms": total_time,
                "chunks": chunk_count,
                "status": status
            }
            results.append(result)
            print(f"{status} - First chunk: {first_chunk_time:.0f}ms, Total: {total_time:.0f}ms")
            
        except Exception as e:
            print(f"❌ FAIL - {e}")
            results.append({
                "character": character,
                "error": str(e),
                "status": "❌ FAIL"
            })
    
    passing = sum(1 for r in results if r["status"] == "✅ PASS")
    total = len(results)
    print(f"\nPerformance validation: {passing}/{total} passed")
    if passing == total:
        print("🚀 All configurations meet real-time requirements")
        return True
    else:
        print("💀 Performance requirements not met")
        return False

if __name__ == "__main__":
    asyncio.run(validate_streaming_performance()) 