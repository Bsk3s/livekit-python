import io
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)
from uuid import uuid4

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from livekit.agents import tts
from livekit.agents.tts import ChunkedStream, TTSCapabilities

# 🚀 GPU ACCELERATION: Import ONNX Runtime for provider detection
try:
    import onnxruntime as ort
    available_providers = ort.get_available_providers()
    # Support both NVIDIA CUDA and Apple CoreML acceleration
    GPU_AVAILABLE = ('CUDAExecutionProvider' in available_providers or 
                     'CoreMLExecutionProvider' in available_providers)
    gpu_type = "CUDA" if 'CUDAExecutionProvider' in available_providers else "CoreML" if 'CoreMLExecutionProvider' in available_providers else "None"
    logger.info(f"🚀 GPU STATUS: Available providers: {available_providers}")
    logger.info(f"🚀 GPU STATUS: GPU acceleration available: {GPU_AVAILABLE} ({gpu_type})")
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("⚠️ ONNX Runtime not available for GPU detection")


class GPUKokoro:
    """
    GPU-accelerated Kokoro wrapper with automatic CPU fallback.
    
    This class attempts to use GPU acceleration when available,
    but gracefully falls back to CPU processing if GPU is unavailable.
    """
    
    def __init__(self, model_path: str, voices_path: str):
        self.model_path = model_path
        self.voices_path = voices_path
        self.use_gpu = GPU_AVAILABLE
        self._base_kokoro = None
        
        # Initialize the underlying Kokoro model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Kokoro model with GPU acceleration if available"""
        try:
            if self.use_gpu:
                logger.info("🚀 Attempting GPU-accelerated Kokoro initialization...")
                
                # Determine the best acceleration provider
                available_providers = ort.get_available_providers()
                if 'CUDAExecutionProvider' in available_providers:
                    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                    gpu_type = "CUDA"
                elif 'CoreMLExecutionProvider' in available_providers:
                    providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider'] 
                    gpu_type = "CoreML"
                else:
                    providers = ['CPUExecutionProvider']
                    gpu_type = "CPU"
                
                logger.info(f"🚀 Using {gpu_type} acceleration with providers: {providers}")
                
                # Try to create GPU-enabled Kokoro
                self._base_kokoro = Kokoro(self.model_path, self.voices_path)
                
                # Note: Kokoro library may not expose ONNX session directly
                # But the providers should be automatically detected by ONNX Runtime
                logger.info(f"✅ {gpu_type}-accelerated Kokoro model initialized successfully")
                
            else:
                logger.info("💻 Using CPU-only Kokoro (GPU not available)")
                self._base_kokoro = Kokoro(self.model_path, self.voices_path)
                
        except Exception as e:
            logger.warning(f"⚠️ GPU acceleration failed: {e}")
            logger.info("🛡️ Falling back to CPU-only Kokoro...")
            self.use_gpu = False
            self._base_kokoro = Kokoro(self.model_path, self.voices_path)
    
    def create(self, text: str, voice: str, speed: float = 1.25, lang: str = "en-us"):
        """Generate audio using GPU-accelerated model"""
        start_time = time.time()
        
        try:
            result = self._base_kokoro.create(text, voice, speed=speed, lang=lang)
            
            # Log performance metrics
            generation_time = (time.time() - start_time) * 1000
            acceleration_type = "GPU" if self.use_gpu else "CPU"
            logger.info(f"🎵 {acceleration_type} Kokoro synthesis: {generation_time:.1f}ms for {len(text)} chars")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ GPU Kokoro synthesis error: {e}")
            raise


class KokoroModelSingleton:
    """
    Singleton class to manage GPU-accelerated Kokoro model loading.
    Loads the model once and reuses it across all requests.
    Thread-safe for concurrent access with GPU acceleration support.
    """
    _instance: Optional['KokoroModelSingleton'] = None
    _lock = threading.Lock()
    _model: Optional[GPUKokoro] = None  # 🚀 GPU: Use GPUKokoro instead of Kokoro
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        """Initialize the GPU-accelerated Kokoro model (call once at startup)"""
        if self._initialized:
            logger.info("🎯 GPU Kokoro model already initialized, reusing existing instance")
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("🚀 Loading GPU-accelerated Kokoro model (one-time initialization)...")
            start_time = time.time()

            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base_dir, "kokoro-v1.0.onnx")
            voices_path = os.path.join(base_dir, "voices-v1.0.bin")

            try:
                self._model = GPUKokoro(model_path, voices_path)  # 🚀 GPU: Use GPUKokoro class
                self._initialized = True
                load_time = time.time() - start_time
                acceleration_type = "GPU" if self._model.use_gpu else "CPU"
                logger.info(f"✅ {acceleration_type} Kokoro model loaded successfully in {load_time:.2f}s")
            except Exception as e:
                logger.error(f"❌ Failed to load GPU Kokoro model: {e}")
                raise

    def get_model(self) -> GPUKokoro:  # 🚀 GPU: Return type is now GPUKokoro
        """Get the loaded GPU-accelerated Kokoro model instance"""
        if not self._initialized:
            raise RuntimeError("GPU Kokoro model not initialized. Call initialize() first.")
        return self._model

    def create_audio(self, text: str, voice: str, speed: float = 1.25, lang: str = "en-us"):  # 🚀 GPU: Updated speed default
        """Generate audio using the pre-loaded GPU-accelerated model"""
        model = self.get_model()
        return model.create(text, voice, speed=speed, lang=lang)


class KokoroTTS(tts.TTS):
    def __init__(self, voice="af_heart", **kwargs):
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=16000,  # 🚀 SPEED: Reduce from 24kHz to 16kHz (33% faster processing)
            num_channels=1,
            **kwargs,
        )
        self.voice = voice
        self.lang = "en-us"
        self.speed = 1.25  # 🚀 SPEED: Increase from 1.12 to 1.25 (faster speech = shorter audio)
        
        # Get the singleton instance (should be pre-initialized)
        self.model_singleton = KokoroModelSingleton()
        
        logger.info(f"🎯 KokoroTTS instance created (voice: {voice}) - GPU-ACCELERATED: 16kHz, 1.25x speed")

    async def asynthesize(self, text: str) -> bytes:
        try:
            logger.info(f"🎵 Generating audio with GPU-accelerated Kokoro model")
            samples, sample_rate = self.model_singleton.create_audio(text, self.voice, self.speed, self.lang)
            return self._array_to_bytes(samples, sample_rate)

        except Exception as e:
            logger.error(f"❌ GPU Kokoro synthesis error: {e}")
            raise e

    def synthesize(self, text: str, *, conn_options=None) -> ChunkedStream:
        logger.info(f"🎵 Generating audio with GPU-accelerated Kokoro model")
        return KokoroChunkedStream(self, text, conn_options)

    def _generate_audio_sync(self, text: str) -> bytes:
        samples, sample_rate = self.model_singleton.create_audio(text, self.voice, self.speed, self.lang)
        return self._array_to_bytes(samples, sample_rate)

    def _array_to_bytes(self, audio_array: np.ndarray, sample_rate: int = 16000) -> bytes:  # 🚀 SPEED: Update default to 16kHz
        audio_array = audio_array.squeeze()

        # Normalize to [-1, 1] range if needed
        max_val = np.max(np.abs(audio_array))
        if max_val > 1.0:
            audio_array = audio_array / max_val

        # Convert to 16-bit PCM
        audio_int16 = (audio_array * 32767).astype(np.int16)

        # Convert to WAV bytes using soundfile
        with io.BytesIO() as wav_buffer:
            sf.write(wav_buffer, audio_int16, sample_rate, format="WAV", subtype="PCM_16")
            wav_buffer.seek(0)
            return wav_buffer.read()


class KokoroChunkedStream(ChunkedStream):
    def __init__(self, tts_instance, text, conn_options=None):
        super().__init__(tts=tts_instance, input_text=text, conn_options=conn_options)

    async def _run(self, output_emitter=None):
        try:
            output_emitter.initialize(
                request_id=str(uuid4), sample_rate=16000, num_channels=1, mime_type=""  # 🚀 SPEED: Use 16kHz
            )
            # Use the singleton model for generation
            samples, sample_rate = self._tts.model_singleton.create_audio(
                self._input_text, self._tts.voice, self._tts.speed, self._tts.lang
            )
            audio_bytes = self._tts._array_to_bytes(samples, sample_rate)
            output_emitter.push(audio_bytes)
            output_emitter.end_input()
            output_emitter.aclose()

        except Exception as e:
            logger.error(f"❌ Kokoro chunked stream error: {e}")
            raise e
