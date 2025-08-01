import io
import logging
import wave

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


def convert_to_ios_format(audio_data, sample_rate):
    # 🎯 DIRECT 22050 Hz CONVERSION: Convert any sample rate to 22050 Hz for iOS compatibility
    if sample_rate != 22050:
        logger.info(f"🔄 Converting {sample_rate}Hz WAV to iOS-compatible 22050Hz")
        try:
            # Read the original WAV
            with io.BytesIO(audio_data) as wav_io:
                with wave.open(wav_io, "rb") as wav_in:
                    # Get original parameters
                    frames = wav_in.readframes(wav_in.getnframes())
                    original_sample_rate = wav_in.getframerate()
                    channels = wav_in.getnchannels()
                    sample_width = wav_in.getsampwidth()

                    # Convert to numpy array (int16)
                    audio_array = np.frombuffer(frames, dtype=np.int16)
                    
                    # 🔧 FIX: Convert to float32 for proper resampling (normalize to [-1.0, +1.0])
                    audio_float = audio_array.astype(np.float32) / 32768.0
                    
                    # Resample to 22050 Hz (iOS compatible)
                    target_sample_rate = 22050
                    resampled_audio = signal.resample(
                        audio_float,
                        int(len(audio_float) * target_sample_rate / original_sample_rate),
                    )
                    
                    # 🔧 FIX: Convert back to int16 with proper scaling and clipping prevention
                    resampled_audio = np.clip(resampled_audio, -1.0, 1.0)  # Prevent clipping
                    resampled_audio = (resampled_audio * 32767).astype(np.int16)

                    # Create new WAV with iOS-compatible format
                    with io.BytesIO() as new_wav_io:
                        with wave.open(new_wav_io, "wb") as wav_out:
                            wav_out.setnchannels(channels)
                            wav_out.setsampwidth(sample_width)
                            wav_out.setframerate(target_sample_rate)
                            wav_out.writeframes(resampled_audio.tobytes())

                        logger.info(
                            f"✅ Successfully converted to iOS-compatible 22050Hz WAV: {len(audio_data)} bytes"
                        )
                        return new_wav_io.getvalue()

        except Exception as conversion_error:
            logger.error(f"❌ WAV conversion failed: {conversion_error}")
            return audio_data
    else:
        logger.info(f"✅ WAV already at 22050Hz - iOS compatible")
        return audio_data
