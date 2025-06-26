from livekit.plugins import openai
import logging

logger = logging.getLogger(__name__)

class TTSService:
    """Clean TTS service interface for easy model swapping"""
    
    def __init__(self, voice="alloy"):
        self.voice = voice
        self.tts = openai.TTS(voice=voice)
        logger.info(f"TTS service initialized with voice: {voice}")
    
    async def generate_speech(self, text: str, voice_config: dict = None):
        """Generate speech from text"""
        try:
            # Use custom voice config if provided
            if voice_config and 'voice' in voice_config:
                self.tts = openai.TTS(voice=voice_config['voice'])
            
            # Generate speech using OpenAI TTS
            audio_data = await self.tts.generate_speech(text)
            logger.info(f"Generated speech for text: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            raise
    
    async def aclose(self):
        """Cleanup TTS resources"""
        try:
            if hasattr(self.tts, 'aclose'):
                await self.tts.aclose()
            logger.info("TTS service resources cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up TTS service: {e}")

# Example of how to extend for custom TTS models:
class CustomTTSService(TTSService):
    """Example custom TTS service implementation"""
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        # Initialize your custom TTS model here
        logger.info(f"Custom TTS service initialized with model: {model_path}")
    
    async def generate_speech(self, text: str, voice_config: dict = None):
        """Generate speech using custom TTS model"""
        try:
            # Implement your custom TTS logic here
            # This is where you'd integrate your own TTS model
            
            # For now, fallback to OpenAI
            return await super().generate_speech(text, voice_config)
            
        except Exception as e:
            logger.error(f"Error in custom TTS: {e}")
            raise 