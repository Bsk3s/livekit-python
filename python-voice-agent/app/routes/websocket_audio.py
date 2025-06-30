from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import asyncio
import json
import logging
import base64
import numpy as np
from typing import Dict, Optional, List
import uuid
import time
import struct
import re
from datetime import datetime

# Import existing services
from ..services.stt.implementations.direct_deepgram import DirectDeepgramSTTService
from ..services.llm_service import create_gpt4o_mini
from ..services.openai_tts_service import OpenAITTSService
from ..characters.character_factory import CharacterFactory

router = APIRouter()
logger = logging.getLogger(__name__)

def create_wav_header(sample_rate: int = 24000, num_channels: int = 1, bit_depth: int = 16, data_length: int = 0) -> bytes:
    """Create WAV file header for proper audio format"""
    # Calculate derived values
    byte_rate = sample_rate * num_channels * bit_depth // 8
    block_align = num_channels * bit_depth // 8
    
    # WAV header structure
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                    # ChunkID
        36 + data_length,           # ChunkSize
        b'WAVE',                    # Format
        b'fmt ',                    # Subchunk1ID
        16,                         # Subchunk1Size (PCM)
        1,                          # AudioFormat (PCM)
        num_channels,               # NumChannels
        sample_rate,                # SampleRate
        byte_rate,                  # ByteRate
        block_align,                # BlockAlign
        bit_depth,                  # BitsPerSample
        b'data',                    # Subchunk2ID
        data_length                 # Subchunk2Size
    )
    return header

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, num_channels: int = 1, bit_depth: int = 16) -> bytes:
    """Convert raw PCM data to WAV format with proper headers"""
    if not pcm_data:
        return b''
    
    # Create WAV header
    header = create_wav_header(sample_rate, num_channels, bit_depth, len(pcm_data))
    
    # Combine header + data
    wav_data = header + pcm_data
    return wav_data

def chunk_ai_response(full_response: str, max_chunk_length: int = 100) -> List[str]:
    """
    Split AI response into natural chunks for streaming audio
    
    Args:
        full_response: Complete AI response text
        max_chunk_length: Target maximum characters per chunk
        
    Returns:
        List of text chunks optimized for TTS streaming
    """
    if not full_response or not full_response.strip():
        return []
    
    # Clean the response
    text = full_response.strip()
    
    # Split by sentences first (prioritize natural breaks)
    sentence_endings = r'[.!?]+\s+'
    sentences = re.split(sentence_endings, text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Add sentence ending back (except for last sentence)
        if not sentence.endswith(('.', '!', '?')):
            sentence += '.'
        
        # Check if adding this sentence exceeds chunk length
        if len(current_chunk + ' ' + sentence) <= max_chunk_length or not current_chunk:
            # Add to current chunk
            if current_chunk:
                current_chunk += ' ' + sentence
            else:
                current_chunk = sentence
        else:
            # Start new chunk
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    # If no chunks created, split by words as fallback
    if not chunks and text:
        words = text.split()
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + ' ' + word) <= max_chunk_length or not current_chunk:
                if current_chunk:
                    current_chunk += ' ' + word
                else:
                    current_chunk = word
            else:
                chunks.append(current_chunk)
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
    
    logger.info(f"📝 Chunked response into {len(chunks)} pieces: {[len(chunk) for chunk in chunks]} chars each")
    return chunks

class AudioSession:
    """Manages individual audio streaming sessions"""
    
    def __init__(self, session_id: str, character: str = "adina"):
        self.session_id = session_id
        self.character = character
        self.created_at = datetime.now()
        self.conversation_history = []
        
        # Initialize services
        self.stt_service = None
        self.llm_service = None
        self.tts_service = None
        self._audio_buffer = bytearray()
        self._processing_audio = False
        
    async def initialize(self):
        """Initialize all services for this session"""
        try:
            # STT Service - Direct Deepgram (no LiveKit context needed)
            self.stt_service = DirectDeepgramSTTService({
                "model": "nova-2",
                "language": "en-US",
                "punctuate": True,
                "interim_results": False
            })
            await self.stt_service.initialize()
            
            # LLM Service - Fixed OpenAI adapter
            self.llm_service = create_gpt4o_mini()
            
            # TTS Service - OpenAI with character voice
            character_config = CharacterFactory.get_character_config(self.character)
            self.tts_service = OpenAITTSService()
            
            logger.info(f"✅ Audio session {self.session_id} initialized with character {self.character}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize session {self.session_id}: {e}")
            raise
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[str]:
        """Process incoming audio chunk and return transcription if available"""
        try:
            # Add to buffer
            self._audio_buffer.extend(audio_data)
            
            # Process when buffer has enough data (e.g., 1 second worth)
            if len(self._audio_buffer) >= 32000:  # ~1 second at 16kHz 16-bit
                # Get raw audio bytes from buffer
                audio_bytes = bytes(self._audio_buffer)
                
                # Clear buffer
                self._audio_buffer.clear()
                
                # Convert raw PCM to WAV format for Deepgram
                wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000, num_channels=1, bit_depth=16)
                
                # Transcribe using Direct Deepgram service
                transcription = await self.stt_service.transcribe_audio_bytes(wav_audio)
                
                if transcription and transcription.strip():
                    logger.info(f"👤 User ({self.character}): '{transcription}'")
                    return transcription.strip()
                    
        except Exception as e:
            logger.error(f"❌ Audio processing error in session {self.session_id}: {e}")
            
        return None
    
    async def generate_response(self, user_input: str) -> str:
        """Generate AI response using character personality"""
        try:
            # Get character personality
            character = CharacterFactory.create_character(self.character)
            
            # Create conversation context
            messages = [
                {"role": "system", "content": character.personality}
            ]
            
            # Add recent conversation history
            for msg in self.conversation_history[-10:]:  # Last 5 exchanges
                messages.append(msg)
            
            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            # Generate response using LLM
            from livekit.agents import llm
            chat_ctx = llm.ChatContext(messages=messages)
            
            response_stream = await self.llm_service.chat(chat_ctx=chat_ctx)
            
            # Collect full response
            response_text = ""
            async for chunk in response_stream:
                if hasattr(chunk, 'content') and chunk.content:
                    response_text += chunk.content
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            logger.info(f"🤖 {self.character.title()}: '{response_text[:100]}...'")
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Response generation error: {e}")
            return f"I apologize, I'm having a technical difficulty. Could you please try again?"
    
    async def synthesize_speech_chunk(self, text: str) -> bytes:
        """Convert text chunk to speech in WAV format"""
        try:
            # Use TTS service to generate audio
            audio_frames = []
            async for frame in self.tts_service.synthesize_streaming(text, self.character):
                if hasattr(frame, 'data'):
                    audio_frames.append(frame.data.tobytes())
            
            # Combine all audio frames
            if audio_frames:
                combined_pcm = b''.join(audio_frames)
                # Convert PCM to WAV format
                wav_data = pcm_to_wav(combined_pcm)
                logger.debug(f"🎵 Generated {len(wav_data)} bytes WAV for: '{text[:30]}...'")
                return wav_data
            else:
                logger.warning(f"⚠️ No audio frames generated for text: {text[:50]}...")
                return b''
                
        except Exception as e:
            logger.error(f"❌ Speech synthesis error: {e}")
            return b''
    
    async def process_and_stream_response(self, websocket: WebSocket, user_input: str):
        """Generate AI response and stream audio chunks in real-time"""
        try:
            # Generate AI response
            response_text = await self.generate_response(user_input)
            
            # Split response into chunks
            chunks = chunk_ai_response(response_text, max_chunk_length=120)
            
            if not chunks:
                logger.warning("⚠️ No chunks generated from AI response")
                return
            
            logger.info(f"🎯 Streaming {len(chunks)} audio chunks for response")
            
            # Send initial transcription
            await websocket.send_json({
                "type": "transcription",
                "text": user_input,
                "timestamp": datetime.now().isoformat()
            })
            
            # Send response start notification
            await websocket.send_json({
                "type": "response_start",
                "character": self.character,
                "total_chunks": len(chunks),
                "full_text": response_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Process and stream each chunk
            for i, chunk_text in enumerate(chunks):
                chunk_start_time = time.time()
                
                # Generate TTS for this chunk
                wav_audio = await self.synthesize_speech_chunk(chunk_text)
                
                if wav_audio:
                    chunk_duration = (time.time() - chunk_start_time) * 1000
                    
                    # Send audio chunk immediately
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "chunk_id": i + 1,
                        "total_chunks": len(chunks),
                        "is_final": i == len(chunks) - 1,
                        "text": chunk_text,
                        "audio": base64.b64encode(wav_audio).decode('utf-8'),
                        "character": self.character,
                        "generation_time_ms": round(chunk_duration),
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    logger.info(f"🎵 Sent chunk {i+1}/{len(chunks)} ({len(chunk_text)} chars, {chunk_duration:.0f}ms)")
                else:
                    logger.error(f"❌ Failed to generate audio for chunk {i+1}: '{chunk_text[:30]}...'")
            
            # Send completion notification
            await websocket.send_json({
                "type": "response_complete",
                "character": self.character,
                "chunks_sent": len(chunks),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Error in streaming response: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Failed to stream response",
                "timestamp": datetime.now().isoformat()
            })
    
    async def cleanup(self):
        """Clean up session resources"""
        try:
            if self.stt_service:
                await self.stt_service.shutdown()
            logger.info(f"🧹 Session {self.session_id} cleaned up")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error for session {self.session_id}: {e}")

# Global session manager
active_sessions: Dict[str, AudioSession] = {}

@router.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    session_id = str(uuid.uuid4())
    session = None
    
    try:
        await websocket.accept()
        logger.info(f"🔗 WebSocket connected: session {session_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                # Receive message from client
                data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                
                if data.get("type") == "websocket.disconnect":
                    break
                
                # Handle different message types
                if "text" in data:
                    message = json.loads(data["text"])
                    session = await handle_json_message(websocket, session, message, session_id)
                    
                elif "bytes" in data:
                    # Handle binary audio data
                    if session and session.stt_service:
                        audio_data = data["bytes"]
                        transcription = await session.process_audio_chunk(audio_data)
                        
                        if transcription:
                            # Process and stream response in chunks
                            await session.process_and_stream_response(websocket, transcription)
                            
            except asyncio.TimeoutError:
                # Send keepalive ping
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "ping"})
                    
            except WebSocketDisconnect:
                break
                
            except Exception as e:
                logger.error(f"❌ Error processing message in session {session_id}: {e}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Processing error occurred",
                        "timestamp": datetime.now().isoformat()
                    })
    
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
        
    finally:
        # Cleanup
        if session:
            await session.cleanup()
            if session_id in active_sessions:
                del active_sessions[session_id]
        
        logger.info(f"🔌 WebSocket disconnected: session {session_id}")

async def handle_json_message(websocket: WebSocket, session: Optional[AudioSession], message: dict, session_id: str) -> Optional[AudioSession]:
    """Handle JSON messages from client"""
    message_type = message.get("type")
    
    try:
        if message_type == "initialize":
            # Initialize session with character
            character = message.get("character", "adina")
            
            if character not in ["adina", "raffa"]:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid character: {character}. Must be 'adina' or 'raffa'"
                })
                return session
            
            # Create and initialize session
            session = AudioSession(session_id, character)
            await session.initialize()
            active_sessions[session_id] = session
            
            await websocket.send_json({
                "type": "initialized",
                "character": character,
                "session_id": session_id,
                "message": f"Session initialized with {character.title()}",
                "timestamp": datetime.now().isoformat()
            })
            
        elif message_type == "switch_character":
            if session:
                new_character = message.get("character", "adina")
                if new_character in ["adina", "raffa"]:
                    session.character = new_character
                    await websocket.send_json({
                        "type": "character_switched",
                        "character": new_character,
                        "message": f"Switched to {new_character.title()}",
                        "timestamp": datetime.now().isoformat()
                    })
                    
        elif message_type == "text_message":
            # Handle text-only message (no audio) - stream chunks too
            if session:
                user_text = message.get("text", "")
                if user_text.strip():
                    await session.process_and_stream_response(websocket, user_text)
                    
        elif message_type == "ping":
            await websocket.send_json({"type": "pong"})
            
    except Exception as e:
        logger.error(f"❌ Error handling JSON message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to process message",
            "timestamp": datetime.now().isoformat()
        })
    
    return session 