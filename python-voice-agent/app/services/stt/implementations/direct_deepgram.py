import os
import io
import asyncio
import logging
from typing import Dict, Any, Optional
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from ..base import BaseSTTService

logger = logging.getLogger(__name__)

class DirectDeepgramSTTService(BaseSTTService):
    """Direct Deepgram implementation without LiveKit context dependencies."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._client = None
        self._initialized = False
        self._session_timeout = 30.0  # 30 second timeout for API calls
    
    def _validate_config(self) -> None:
        """Validate required configuration and environment variables"""
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")
        
        if not api_key.strip():
            raise ValueError("DEEPGRAM_API_KEY is empty or whitespace")
            
        logger.info(f"🔑 Deepgram API key validated: {api_key[:8]}...")
    
    async def initialize(self) -> None:
        """Initialize the Deepgram client"""
        if not self._initialized:
            try:
                self._validate_config()
                
                # Initialize Deepgram client with API key
                api_key = os.getenv("DEEPGRAM_API_KEY").strip()
                self._client = DeepgramClient(api_key)
                
                # Test connection with a minimal request
                await self._test_connection()
                
                self._initialized = True
                logger.info("✅ DirectDeepgramSTTService initialized successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize DirectDeepgramSTTService: {e}")
                raise
    
    async def _test_connection(self) -> None:
        """Test the Deepgram connection with a minimal audio sample"""
        try:
            # Create a minimal silent audio sample for testing
            # 1 second of silence at 16kHz, 16-bit mono
            silence_samples = 16000 * 1  # 1 second at 16kHz
            silence_bytes = b'\x00\x00' * silence_samples  # 16-bit silence
            
            # Create file source
            test_source = FileSource(
                buffer=silence_bytes,
                mimetype="audio/wav"
            )
            
            # Basic options for testing
            test_options = PrerecordedOptions(
                model="nova-2",
                language="en-US",
                punctuate=False,
                smart_format=False
            )
            
            # Test transcription (should return empty or minimal result)
            response = await self._client.listen.rest.v("1").transcribe_file(
                test_source, 
                test_options,
                timeout=5.0  # Short timeout for test
            )
            
            logger.info("🔗 Deepgram connection test successful")
            
        except Exception as e:
            logger.warning(f"⚠️ Connection test failed (may be normal): {e}")
            # Don't raise - connection test failure shouldn't block initialization
    
    async def shutdown(self) -> None:
        """Clean up resources"""
        if self._client:
            # Deepgram client doesn't require explicit cleanup
            self._client = None
        self._initialized = False
        logger.info("🧹 DirectDeepgramSTTService shut down")
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    async def transcribe_audio_bytes(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe raw audio bytes using Deepgram REST API
        
        Args:
            audio_data: Raw audio bytes (PCM format expected)
            
        Returns:
            Transcription text or None if no speech detected
        """
        if not self._initialized:
            await self.initialize()
        
        if not audio_data or len(audio_data) == 0:
            logger.debug("⚠️ Empty audio data provided")
            return None
        
        try:
            logger.debug(f"🎤 Processing {len(audio_data)} bytes of audio")
            
            # Create file source from audio bytes
            audio_source = FileSource(
                buffer=audio_data,
                mimetype="audio/wav"  # Assume WAV format with proper headers
            )
            
            # Configure transcription options based on service config
            options = PrerecordedOptions(
                model=self.config.get("model", "nova-2"),
                language=self.config.get("language", "en-US"),
                punctuate=self.config.get("punctuate", True),
                smart_format=self.config.get("smart_format", True),
                interim_results=False,  # We want final results only
                utterances=False,  # Don't need utterance splitting
                profanity_filter=self.config.get("profanity_filter", False),
                numerals=self.config.get("numerals", False),
                no_delay=True,  # Process immediately
            )
            
            # Make transcription request with timeout
            response = await asyncio.wait_for(
                self._client.listen.rest.v("1").transcribe_file(audio_source, options),
                timeout=self._session_timeout
            )
            
            # Extract transcript from response
            transcript = self._extract_transcript(response)
            
            if transcript:
                logger.info(f"👤 Transcribed: '{transcript}'")
                return transcript
            else:
                logger.debug("🔇 No speech detected in audio")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"⏰ Transcription timeout after {self._session_timeout}s")
            return None
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return None
    
    def _extract_transcript(self, response) -> Optional[str]:
        """
        Extract transcript text from Deepgram response
        
        Args:
            response: Deepgram API response object
            
        Returns:
            Transcript text or None
        """
        try:
            # Navigate Deepgram response structure
            if hasattr(response, 'results'):
                results = response.results
                
                if hasattr(results, 'channels') and len(results.channels) > 0:
                    channel = results.channels[0]
                    
                    if hasattr(channel, 'alternatives') and len(channel.alternatives) > 0:
                        alternative = channel.alternatives[0]
                        
                        if hasattr(alternative, 'transcript'):
                            transcript = alternative.transcript.strip()
                            
                            # Only return non-empty transcripts
                            if transcript and len(transcript) > 0:
                                return transcript
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting transcript: {e}")
            return None
    
    async def transcribe_stream(self, audio_stream) -> str:
        """
        Legacy method for compatibility - not used in WebSocket context
        """
        logger.warning("⚠️ transcribe_stream called but not implemented for direct usage")
        return ""
    
    async def transcribe_file(self, audio_file_path: str) -> str:
        """
        Transcribe an audio file
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Transcription text
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            return await self.transcribe_audio_bytes(audio_data) or ""
            
        except Exception as e:
            logger.error(f"❌ File transcription error: {e}")
            return ""

# Test function for validation
async def test_direct_deepgram():
    """Test the DirectDeepgramSTTService"""
    logger.info("🧪 Testing DirectDeepgramSTTService...")
    
    service = DirectDeepgramSTTService({
        "model": "nova-2",
        "language": "en-US",
        "punctuate": True,
    })
    
    try:
        await service.initialize()
        logger.info("✅ Service initialization successful")
        
        # Test with minimal audio data
        test_audio = b'\x00\x00' * 8000  # 0.5 seconds of silence
        result = await service.transcribe_audio_bytes(test_audio)
        
        if result is None:
            logger.info("✅ Correctly returned None for silence")
        else:
            logger.info(f"📝 Transcription result: '{result}'")
        
        await service.shutdown()
        logger.info("✅ Service shutdown successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_direct_deepgram()) 