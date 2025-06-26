from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import asyncio
import json
import logging
import base64
import numpy as np
from typing import Dict, Optional
import uuid
import time
from datetime import datetime

# Import existing services
from ..services.stt.implementations.deepgram import DeepgramSTTService
from ..services.llm_service import create_gpt4o_mini
from ..services.openai_tts_service import OpenAITTSService
from ..characters.character_factory import CharacterFactory

router = APIRouter()
logger = logging.getLogger(__name__)

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
            # STT Service - Deepgram
            self.stt_service = DeepgramSTTService({
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
                # Convert buffer to numpy array
                audio_array = np.frombuffer(self._audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Clear buffer
                self._audio_buffer.clear()
                
                # Use LiveKit Deepgram plugin directly for transcription
                from livekit.agents import stt
                
                # Create audio frame
                from livekit import rtc
                audio_frame = rtc.AudioFrame(
                    data=audio_array,
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=len(audio_array)
                )
                
                # Transcribe using the client
                if hasattr(self.stt_service, '_client'):
                    result = await self.stt_service._client.recognize(audio_frame)
                    
                    if result and hasattr(result, 'text') and result.text.strip():
                        transcription = result.text.strip()
                        logger.info(f"👤 User ({self.character}): '{transcription}'")
                        return transcription
                    
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
    
    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech using character voice"""
        try:
            # Use TTS service to generate audio
            audio_frames = []
            async for frame in self.tts_service.synthesize_streaming(text, self.character):
                if hasattr(frame, 'data'):
                    audio_frames.append(frame.data.tobytes())
            
            # Combine all audio frames
            if audio_frames:
                combined_audio = b''.join(audio_frames)
                return combined_audio
            else:
                logger.warning(f"⚠️ No audio frames generated for text: {text[:50]}...")
                return b''
                
        except Exception as e:
            logger.error(f"❌ Speech synthesis error: {e}")
            return b''
    
    async def cleanup(self):
        """Clean up session resources"""
        try:
            if self.stt_service:
                await self.stt_service.aclose()
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
                            # Generate AI response
                            response_text = await session.generate_response(transcription)
                            
                            # Convert to speech
                            audio_response = await session.synthesize_speech(response_text)
                            
                            # Send transcription and audio response
                            await websocket.send_json({
                                "type": "transcription",
                                "text": transcription,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            if audio_response:
                                await websocket.send_json({
                                    "type": "audio_response",
                                    "text": response_text,
                                    "audio": base64.b64encode(audio_response).decode('utf-8'),
                                    "character": session.character,
                                    "timestamp": datetime.now().isoformat()
                                })
                            
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
            # Handle text-only message (no audio)
            if session:
                user_text = message.get("text", "")
                if user_text.strip():
                    response_text = await session.generate_response(user_text)
                    await websocket.send_json({
                        "type": "text_response",
                        "text": response_text,
                        "character": session.character,
                        "timestamp": datetime.now().isoformat()
                    })
                    
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