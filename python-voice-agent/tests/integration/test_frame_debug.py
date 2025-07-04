#!/usr/bin/env python3
"""
Debug TTS frame structure to fix audio chunk generation
"""

import asyncio
import sys

async def debug_frame_structure():
    """Debug the exact structure of TTS frames"""
    print("🔍 Debugging TTS Frame Structure")
    print("=" * 40)
    
    try:
        from spiritual_voice_agent.services.openai_tts_service import OpenAITTSService
        
        tts_service = OpenAITTSService()
        print("✅ OpenAI TTS service created")
        
        frame_count = 0
        total_audio_data = []
        
        async for synth_audio in tts_service.synthesize_streaming("Hello world", "adina"):
            frame_count += 1
            print(f"\n📊 Frame {frame_count}:")
            print(f"   Type: {type(synth_audio)}")
            print(f"   is_final: {synth_audio.is_final}")
            print(f"   request_id: {synth_audio.request_id}")
            
            # Check the actual audio frame
            audio_frame = synth_audio.frame
            print(f"   audio_frame type: {type(audio_frame)}")
            print(f"   audio_frame attributes: {dir(audio_frame)}")
            
            # Extract audio data from the frame
            if hasattr(audio_frame, 'data'):
                data = audio_frame.data
                print(f"   frame.data type: {type(data)}")
                
                if hasattr(data, 'tobytes'):
                    audio_bytes = data.tobytes()
                    print(f"   ✅ audio_bytes length: {len(audio_bytes)}")
                    total_audio_data.append(audio_bytes)
                else:
                    print(f"   frame.data value: {data}")
                    
            elif hasattr(audio_frame, 'tobytes'):
                audio_bytes = audio_frame.tobytes()
                print(f"   ✅ frame.tobytes() length: {len(audio_bytes)}")
                total_audio_data.append(audio_bytes)
            
            # Check other frame attributes
            for attr in ['samples', 'pcm', 'audio', 'sample_rate', 'num_channels']:
                if hasattr(audio_frame, attr):
                    value = getattr(audio_frame, attr)
                    print(f"   {attr}: {value}")
            
            if frame_count >= 3:  # Check first 3 frames
                break
        
        print(f"\n📊 Summary:")
        print(f"   Frames processed: {frame_count}")
        print(f"   Audio chunks collected: {len(total_audio_data)}")
        print(f"   Total audio bytes: {sum(len(chunk) for chunk in total_audio_data)}")
        
        if total_audio_data:
            print("✅ Audio data extraction: SUCCESS")
            # Test WAV conversion
            try:
                from spiritual_voice_agent.routes.websocket_audio import pcm_to_wav
                combined_pcm = b''.join(total_audio_data)
                wav_data = pcm_to_wav(combined_pcm, sample_rate=24000)  # OpenAI uses 24kHz
                print(f"✅ WAV conversion: {len(wav_data)} bytes")
            except Exception as e:
                print(f"❌ WAV conversion failed: {e}")
            return True
        else:
            print("❌ Audio data extraction: FAILED")
            return False
        
    except Exception as e:
        print(f"❌ Frame debugging failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(debug_frame_structure()) 