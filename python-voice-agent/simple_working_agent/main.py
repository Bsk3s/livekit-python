#!/usr/bin/env python3
"""
CUSTOM TTS AGENT - Using tts_node() Override
Bypasses LiveKit TTS framework completely for direct audio control
"""
import asyncio
import logging
import os
import subprocess
import tempfile
import numpy as np
import wave
import io
from typing import AsyncIterable, AsyncGenerator
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    ModelSettings,
)
from livekit.plugins import deepgram, openai, silero
from livekit import rtc

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class CustomTTSAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant. Keep responses concise and natural. "
                "You can help with questions and have conversations."
            )
        )
        
    async def tts_node(
        self, 
        text: AsyncIterable[str], 
        model_settings: ModelSettings
    ) -> AsyncGenerator[rtc.AudioFrame, None]:
        """
        Custom TTS node using Kokoro TTS with sentence buffering for smooth audio
        """
        logger.info("🎵 Custom TTS node activated - using Kokoro TTS with buffering")
        
        text_buffer = ""
        
        async for text_chunk in text:
            if not text_chunk.strip():
                continue
                
            # Add to buffer
            text_buffer += text_chunk
            logger.info(f"📝 Buffered: '{text_buffer[:50]}...' (len: {len(text_buffer)})")
            
            # Check if we have a complete sentence or enough text
            should_synthesize = (
                text_buffer.endswith(('.', '!', '?', '\n')) or  # Complete sentence
                len(text_buffer) > 100 or  # Long enough chunk
                text_chunk.endswith('\n')  # Paragraph break
            )
            
            if should_synthesize and text_buffer.strip():
                logger.info(f"🎤 Synthesizing buffered text: '{text_buffer[:50]}...'")
                
                try:
                    # Generate audio with Kokoro TTS
                    audio_frames = await self._synthesize_with_kokoro(text_buffer.strip())
                    
                    # Yield each audio frame
                    for frame in audio_frames:
                        yield frame
                        
                    logger.info(f"✅ Generated {len(audio_frames)} audio frames for buffered text")
                    
                    # Clear buffer after successful synthesis
                    text_buffer = ""
                    
                except Exception as e:
                    logger.error(f"❌ Custom TTS synthesis failed: {e}")
                    # Yield silence as fallback but keep trying
                    yield self._create_silence_frame()
                    text_buffer = ""  # Clear buffer to avoid getting stuck
        
        # Synthesize any remaining text in buffer at the end
        if text_buffer.strip():
            logger.info(f"🎤 Synthesizing final buffer: '{text_buffer[:50]}...'")
            try:
                audio_frames = await self._synthesize_with_kokoro(text_buffer.strip())
                for frame in audio_frames:
                    yield frame
                logger.info(f"✅ Generated {len(audio_frames)} audio frames for final buffer")
            except Exception as e:
                logger.error(f"❌ Final buffer synthesis failed: {e}")
                yield self._create_silence_frame()
    
    async def _synthesize_with_kokoro(self, text: str) -> list[rtc.AudioFrame]:
        """Synthesize speech using Kokoro TTS via local FastAPI server"""
        logger.info(f"🎤 Kokoro TTS: '{text[:40]}{'...' if len(text) > 40 else ''}'")
        
        try:
            import httpx
            
            # Call local Kokoro TTS API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8001/synthesize",
                    data={
                        "text": text,
                        "character": "adina"  # Use Adina character for af_heart voice
                    }
                )
                
                if response.status_code == 200:
                    audio_bytes = response.content
                    logger.info(f"✅ Kokoro API success: {len(audio_bytes)} bytes")
                    
                    # Convert bytes to numpy array
                    audio_array = self._wav_bytes_to_array(audio_bytes)
                    if audio_array is not None:
                        logger.info(f"🔊 Audio array: {len(audio_array)} samples")
                        return self._audio_to_frames(audio_array, sample_rate=24000)  # Kokoro outputs 24kHz
                    else:
                        logger.warning("⚠️ Failed to convert audio bytes, using fallback")
                        return await self._generate_fallback_beep()
                else:
                    logger.warning(f"⚠️ Kokoro API error: {response.status_code} - {response.text}")
                    return await self._generate_fallback_beep()
                
        except Exception as e:
            logger.warning(f"⚠️ Kokoro API error: {e}, using fallback beep")
            return await self._generate_fallback_beep()
    
    async def _generate_fallback_beep(self) -> list[rtc.AudioFrame]:
        """Generate quiet fallback beep if Kokoro fails"""
        duration = 0.2
        sample_rate = 16000
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples, False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.1  # Quiet beep
        audio_int16 = (audio * 32767).astype(np.int16)
        return self._audio_to_frames(audio_int16, sample_rate=sample_rate)
    
    async def _synthesize_with_subprocess(self, text: str) -> list[rtc.AudioFrame]:
        """Fallback: Use Piper TTS via subprocess"""
        logger.info("🔧 Using Piper subprocess fallback...")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        try:
            # Try different model names for subprocess
            for model_name in ["en_US-lessac-medium", "en_US-lessac-low", "lessac", "en_US-ljspeech-medium"]:
                logger.info(f"🔍 Trying subprocess with model: {model_name}")
                
                # Run Piper TTS command via subprocess
                process = await asyncio.create_subprocess_exec(
                    "piper", 
                    "--model", model_name,
                    "--output_file", temp_wav_path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate(input=text.encode())
                
                if process.returncode == 0:
                    logger.info(f"✅ Subprocess succeeded with model: {model_name}")
                    break
                else:
                    logger.debug(f"❌ Subprocess failed with {model_name}: {stderr.decode()}")
                    continue
            else:
                logger.error("❌ All subprocess models failed")
                return [self._create_silence_frame()]
            
            # Read generated WAV file
            import wave
            with wave.open(temp_wav_path, 'rb') as wav_file:
                audio_data = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                return self._audio_to_frames(audio_array, sample_rate=sample_rate)
                
        except Exception as e:
            logger.error(f"❌ Subprocess synthesis failed: {e}")
            return [self._create_silence_frame()]
        finally:
            # Clean up temp file
            if os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
    
    async def _generate_test_audio(self, text: str) -> np.ndarray:
        """Generate audio using Piper TTS"""
        try:
            # Try to use Piper TTS
            import subprocess
            import tempfile
            import os
            
            # Create temp file for WAV output
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            try:
                # Run Piper TTS command with full model path
                model_path = os.path.expanduser("~/.local/share/piper-tts/voices/en_US-lessac-medium.onnx")
                result = subprocess.run([
                    "piper", 
                    "--model", model_path,
                    "--output_file", temp_path
                ], input=text, text=True, capture_output=True, timeout=5)
                
                if result.returncode == 0 and os.path.exists(temp_path):
                    # Read WAV file and convert to numpy array
                    import wave
                    with wave.open(temp_path, 'rb') as wav_file:
                        sample_rate = wav_file.getframerate()
                        audio_data = wav_file.readframes(wav_file.getnframes())
                        audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        
                        # Resample to 16kHz if needed (LiveKit prefers 16kHz)
                        if sample_rate != 16000:
                            # Simple resampling by taking every nth sample
                            resample_factor = sample_rate // 16000
                            if resample_factor > 1:
                                audio_array = audio_array[::resample_factor]
                        
                        return audio_array
                        
            except Exception as e:
                logger.debug(f"Piper failed: {e}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.debug(f"Piper import/setup failed: {e}")
        
        # Fallback to sine wave if Piper fails
        logger.info("🔧 Falling back to sine wave")
        duration = len(text) * 0.1  # 0.1 seconds per character
        sample_rate = 16000
        samples = int(duration * sample_rate)
        
        # Generate sine wave
        t = np.linspace(0, duration, samples, False)
        frequency = 440  # A4 note
        audio = np.sin(2 * np.pi * frequency * t) * 0.3  # Low volume
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16
    
    def _wav_bytes_to_array(self, wav_bytes: bytes) -> np.ndarray:
        """Convert WAV bytes to numpy array"""
        try:
            # Create a BytesIO object from the WAV bytes
            audio_io = io.BytesIO(wav_bytes)
            
            # Read the WAV file
            with wave.open(audio_io, 'rb') as wav_file:
                # Get audio parameters
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                
                logger.info(f"📊 WAV format: {frames} frames, {sample_rate}Hz, {channels} channels")
                
                # Read audio data
                audio_data = wav_file.readframes(frames)
                
                # Convert to numpy array (16-bit PCM)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Convert to mono if stereo
                if channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
                    logger.info("🔊 Converted stereo to mono")
                
                return audio_array
                
        except Exception as e:
            logger.error(f"❌ WAV conversion failed: {e}")
            return None
    
    def _audio_to_frames(self, audio_data: np.ndarray, sample_rate: int, frame_size_ms: int = 20) -> list[rtc.AudioFrame]:
        """Convert audio data to LiveKit AudioFrame chunks"""
        frame_samples = int(sample_rate * frame_size_ms / 1000)  # 20ms frames
        frames = []
        
        for i in range(0, len(audio_data), frame_samples):
            chunk = audio_data[i:i + frame_samples]
            
            # Pad if needed
            if len(chunk) < frame_samples:
                chunk = np.pad(chunk, (0, frame_samples - len(chunk)))
            
            # Create AudioFrame
            frame = rtc.AudioFrame(
                data=chunk.tobytes(),
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(chunk),
            )
            frames.append(frame)
        
        return frames
    
    def _create_silence_frame(self, duration_ms: int = 20) -> rtc.AudioFrame:
        """Create a silence audio frame"""
        sample_rate = 16000
        samples = int(sample_rate * duration_ms / 1000)
        silence = np.zeros(samples, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=silence.tobytes(),
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=samples,
        )

async def entrypoint(ctx: JobContext):
    """Main entrypoint for the voice agent"""
    logger.info(f"🔗 Connecting to room: {ctx.room.name}")
    await ctx.connect()
    
    logger.info("🚀 Creating agent session with CUSTOM TTS...")
    # NOTE: NO TTS in AgentSession - using tts_node() override instead!
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        # tts=openai.TTS(voice="echo"),  # REMOVED - using custom tts_node()
    )
    logger.info("✅ Agent session created (NO TTS - using custom override)")
    
    logger.info("🎯 Starting agent session with CustomTTSAgent...")
    await session.start(
        agent=CustomTTSAgent(),  # Using our custom agent
        room=ctx.room,
    )
    logger.info("✅ Agent session started!")
    
    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )
    logger.info("🎵 Initial greeting generated!")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="spiritual-agent",  # Match dispatch API expectation
        ),
    ) 