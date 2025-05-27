import asyncio
import logging
from typing import Optional, Callable
from livekit import rtc

logger = logging.getLogger(__name__)

class InterruptionHandler:
    """Handles interruptions during TTS playback for natural conversation flow"""
    
    def __init__(self):
        self._current_tts_task: Optional[asyncio.Task] = None
        self._is_speaking = False
        self._interruption_callback: Optional[Callable] = None
        self._speech_detected = False
        
        logger.info("Interruption handler initialized")
    
    def set_interruption_callback(self, callback: Callable):
        """Set callback to be called when interruption is detected"""
        self._interruption_callback = callback
    
    def start_speaking(self, tts_task: asyncio.Task):
        """Mark that TTS is currently playing"""
        self._current_tts_task = tts_task
        self._is_speaking = True
        self._speech_detected = False
        logger.info("🎤 Started speaking - monitoring for interruptions")
    
    def stop_speaking(self):
        """Mark that TTS has finished"""
        self._is_speaking = False
        self._current_tts_task = None
        logger.info("🔇 Stopped speaking")
    
    async def handle_speech_detected(self, audio_frame: rtc.AudioFrame):
        """Handle when user speech is detected during TTS playback"""
        if not self._is_speaking:
            return  # Not currently speaking, no interruption needed
        
        # Simple voice activity detection (in real implementation, use VAD)
        audio_level = self._calculate_audio_level(audio_frame)
        
        if audio_level > 0.1:  # Threshold for speech detection
            if not self._speech_detected:
                self._speech_detected = True
                logger.info("🛑 User speech detected during TTS - handling interruption")
                await self._handle_interruption()
    
    async def _handle_interruption(self):
        """Handle the actual interruption"""
        if self._current_tts_task and not self._current_tts_task.done():
            # Cancel current TTS
            self._current_tts_task.cancel()
            logger.info("❌ Cancelled current TTS due to interruption")
            
            # Call interruption callback if set
            if self._interruption_callback:
                try:
                    await self._interruption_callback()
                except Exception as e:
                    logger.error(f"Error in interruption callback: {e}")
        
        self.stop_speaking()
    
    def _calculate_audio_level(self, audio_frame: rtc.AudioFrame) -> float:
        """Calculate audio level for simple voice activity detection"""
        try:
            # Simple RMS calculation
            import numpy as np
            audio_data = np.frombuffer(audio_frame.data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            return rms / 32768.0  # Normalize to 0-1 range
        except Exception as e:
            logger.warning(f"Error calculating audio level: {e}")
            return 0.0
    
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self._is_speaking
    
    async def cleanup(self):
        """Clean up resources"""
        if self._current_tts_task and not self._current_tts_task.done():
            self._current_tts_task.cancel()
        
        self._is_speaking = False
        self._current_tts_task = None
        logger.info("🧹 Interruption handler cleaned up")

# Example usage in agent session
class InterruptibleTTSManager:
    """Manager that combines TTS with interruption handling"""
    
    def __init__(self, tts_service, interruption_handler: InterruptionHandler):
        self.tts_service = tts_service
        self.interruption_handler = interruption_handler
        
        # Set up interruption callback
        self.interruption_handler.set_interruption_callback(self._on_interruption)
    
    async def speak(self, text: str, character: str):
        """Speak text with interruption handling"""
        logger.info(f"🗣️ Starting to speak: '{text[:50]}...'")
        
        try:
            # Create TTS task
            tts_task = asyncio.create_task(
                self._stream_tts(text, character)
            )
            
            # Register with interruption handler
            self.interruption_handler.start_speaking(tts_task)
            
            # Wait for completion or interruption
            await tts_task
            
        except asyncio.CancelledError:
            logger.info("🛑 TTS was interrupted")
        except Exception as e:
            logger.error(f"Error during TTS: {e}")
        finally:
            self.interruption_handler.stop_speaking()
    
    async def _stream_tts(self, text: str, character: str):
        """Stream TTS audio"""
        async for audio_chunk in self.tts_service._synthesize_streaming(text, character):
            # In real implementation, this would send to LiveKit room
            await asyncio.sleep(0.01)  # Simulate streaming delay
    
    async def _on_interruption(self):
        """Called when interruption is detected"""
        logger.info("🔄 Handling interruption - ready for user input")
        # In real implementation, this would:
        # 1. Stop current audio playback
        # 2. Clear audio buffers
        # 3. Signal agent to listen for new input 