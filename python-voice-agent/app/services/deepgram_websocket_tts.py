#!/usr/bin/env python3
"""
Real-Time Deepgram WebSocket TTS Implementation
Uses wss://api.deepgram.com/v1/tts-stream for true sub-200ms streaming
Bypasses the broken SDK to access Deepgram's real streaming API
"""

import asyncio
import json
import logging
import base64
import time
import uuid
from typing import AsyncGenerator, Optional, Dict, Any
import websockets
import numpy as np
from livekit import rtc
from livekit.agents import tts
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class DeepgramWebSocketTTS(tts.TTS):
    """Real-time Deepgram TTS using WebSocket streaming API"""
    
    VOICE_CONFIGS = {
        "adina": {
            "model": "aura-2-luna-en",  # Gentle, soothing female
            "description": "Compassionate spiritual guide"
        },
        "raffa": {
            "model": "aura-2-orion-en",  # Warm, approachable male  
            "description": "Wise spiritual mentor"
        }
    }
    
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True,
            ),
            sample_rate=24000,
            num_channels=1,
        )
        
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        self.websocket_url = "wss://api.deepgram.com/v1/tts-stream"
        self._current_character = "adina"  # Default character
        self._active_streams = set()  # Track active streams for interruption
        self._connection_count = 0  # Track connections to prevent spam
        self._last_connection_time = 0  # Rate limiting
        self._retry_count = 0  # Exponential backoff
        self._active_connections = set()  # Track active WebSocket connections
        
        logger.info("🚀 Real-time Deepgram WebSocket TTS initialized")
    
    def set_character(self, character: str):
        """Set the character voice for TTS"""
        if character not in self.VOICE_CONFIGS:
            raise ValueError(f"Invalid character: {character}. Must be one of: {list(self.VOICE_CONFIGS.keys())}")
        
        self._current_character = character
        config = self.VOICE_CONFIGS[character]
        logger.info(f"Set TTS character to {character} ({config['description']}) - Model: {config['model']}")
    
    def synthesize(self, text: str) -> "WebSocketStream":
        """Synthesize text to audio stream (LiveKit TTS interface)"""
        return WebSocketStream(self, text, self._current_character)
    
    def stream(self):
        """Create a streaming context manager for LiveKit compatibility"""
        return StreamingContext(self)
    
    async def interrupt_all_streams(self):
        """Interrupt all active TTS streams"""
        logger.info(f"🛑 Interrupting {len(self._active_streams)} active WebSocket streams")
        self._active_streams.clear()
        
        # Close all active WebSocket connections
        for connection in list(self._active_connections):
            try:
                await connection.close()
                logger.debug("🔌 Closed WebSocket connection during interruption")
            except Exception as e:
                logger.warning(f"⚠️ Error closing WebSocket during interruption: {e}")
        self._active_connections.clear()
    
    async def _check_rate_limit(self):
        """Implement rate limiting to prevent 429 errors"""
        current_time = time.time()
        time_since_last = current_time - self._last_connection_time
        
        # Minimum 1 second between connections to prevent spam
        if time_since_last < 1.0:
            wait_time = 1.0 - time_since_last
            logger.info(f"⏳ Rate limiting: waiting {wait_time:.1f}s before next connection")
            await asyncio.sleep(wait_time)
        
        self._last_connection_time = time.time()
        self._connection_count += 1
    
    async def _exponential_backoff(self):
        """Implement exponential backoff for retries"""
        if self._retry_count > 0:
            backoff_time = min(2 ** self._retry_count, 30)  # Max 30 seconds
            logger.info(f"🔄 Retry #{self._retry_count}: backing off for {backoff_time}s")
            await asyncio.sleep(backoff_time)
        self._retry_count += 1
    
    async def _synthesize_streaming(self, text: str, character: str, stream_id: str) -> AsyncGenerator[rtc.AudioFrame, None]:
        """Real-time WebSocket streaming synthesis targeting sub-200ms first chunk"""
        if not text.strip():
            logger.warning("Empty text provided for TTS")
            return
        
        config = self.VOICE_CONFIGS[character]
        start_time = time.time()
        first_chunk_yielded = False
        chunk_count = 0
        total_audio_duration = 0.0
        websocket = None
        max_retries = 3
        
        logger.info(f"🎤 Starting REAL-TIME WebSocket TTS for {character}: '{text[:50]}...'")
        
        # WebSocket headers for authentication
        headers = {
            "Authorization": f"Token {self.api_key}"
        }
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting to prevent 429 errors
                await self._check_rate_limit()
                
                # Apply exponential backoff if this is a retry
                if attempt > 0:
                    await self._exponential_backoff()
                
                # Connect to Deepgram WebSocket TTS streaming endpoint
                websocket = await websockets.connect(self.websocket_url, extra_headers=headers)
                self._active_connections.add(websocket)
                logger.info(f"✅ WebSocket connection established (attempt {attempt + 1})")
                
                # Reset retry count on successful connection
                self._retry_count = 0
                
                # Send configuration message
                config_message = {
                    "type": "config",
                    "model": config["model"],
                    "encoding": "linear16",
                    "sample_rate": 24000,
                    "container": "none"
                }
                
                await websocket.send(json.dumps(config_message))
                logger.info(f"📤 Sent config: {config['model']}")
                
                # Split text into smaller chunks for faster streaming
                text_chunks = self._split_text_for_streaming(text)
                logger.info(f"📝 Split text into {len(text_chunks)} chunks for optimal streaming")
                
                # Send text chunks and listen for audio simultaneously
                async def send_text():
                    """Send text chunks to WebSocket"""
                    try:
                        for i, chunk in enumerate(text_chunks):
                            if stream_id not in self._active_streams:
                                logger.info(f"🛑 Stream {stream_id} interrupted during text sending")
                                break
                            
                            # Send text chunk
                            text_message = {
                                "type": "text",
                                "text": chunk
                            }
                            await websocket.send(json.dumps(text_message))
                            logger.debug(f"📤 Sent text chunk {i+1}/{len(text_chunks)}: '{chunk[:30]}...'")
                            
                            # Small delay between chunks to allow processing
                            await asyncio.sleep(0.01)
                        
                        # Send flush to trigger synthesis
                        flush_message = {"type": "flush"}
                        await websocket.send(json.dumps(flush_message))
                        logger.info("📤 Sent flush - synthesis starting")
                        
                    except Exception as e:
                        logger.error(f"Error sending text: {e}")
                
                # Start sending text in background
                send_task = asyncio.create_task(send_text())
                
                # Listen for audio responses
                try:
                    async for message in websocket:
                        # Check for interruption
                        if stream_id not in self._active_streams:
                            logger.info(f"🛑 Stream {stream_id} interrupted, stopping WebSocket")
                            break
                        
                        try:
                            data = json.loads(message)
                            
                            if data.get("type") == "audio":
                                chunk_count += 1
                                
                                # Log first chunk latency (targeting sub-200ms)
                                if not first_chunk_yielded:
                                    first_chunk_latency = (time.time() - start_time) * 1000
                                    logger.info(f"🚀 REAL-TIME FIRST CHUNK for {character}: {first_chunk_latency:.0f}ms")
                                    first_chunk_yielded = True
                                
                                # Decode base64 audio
                                audio_base64 = data.get("audio", "")
                                if audio_base64:
                                    audio_bytes = base64.b64decode(audio_base64)
                                    
                                    # Convert to AudioFrame and yield immediately
                                    audio_frame = self._create_audio_frame(audio_bytes)
                                    total_audio_duration += audio_frame.duration
                                    yield audio_frame
                                    
                                    # Log progress every 20 chunks
                                    if chunk_count % 20 == 0:
                                        logger.debug(f"🎵 Streamed {chunk_count} chunks, {total_audio_duration:.1f}s audio")
                            
                            elif data.get("type") == "metadata":
                                logger.debug(f"📊 Metadata: {data}")
                            
                            elif data.get("type") == "error":
                                error_msg = data.get("message", "Unknown error")
                                logger.error(f"❌ WebSocket error: {error_msg}")
                                raise Exception(f"Deepgram WebSocket error: {error_msg}")
                        
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ Invalid JSON received: {message}")
                            continue
                
                except websockets.exceptions.ConnectionClosed:
                    logger.info("🔌 WebSocket connection closed")
                
                # Wait for send task to complete
                try:
                    await asyncio.wait_for(send_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("⏰ Send task timed out")
                    send_task.cancel()
                
                # Success - break out of retry loop
                break
                
            except websockets.exceptions.InvalidStatusCode as e:
                if e.status_code == 429:
                    logger.warning(f"⚠️ Rate limited (429) on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        # Exponential backoff for rate limiting
                        backoff_time = min(2 ** (attempt + 1), 30)
                        logger.info(f"⏳ Backing off for {backoff_time}s due to rate limiting")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        logger.error("❌ Max retries exceeded due to rate limiting")
                        raise Exception("Deepgram API rate limit exceeded - consider upgrading your plan")
                else:
                    logger.error(f"❌ WebSocket connection failed with status {e.status_code}: {e}")
                    raise
            
            except Exception as e:
                logger.error(f"❌ WebSocket synthesis error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in {2 ** attempt}s...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("❌ Max retries exceeded for WebSocket synthesis")
                    raise
            
            finally:
                # Always clean up the WebSocket connection
                if websocket:
                    try:
                        self._active_connections.discard(websocket)
                        await websocket.close()
                        logger.debug("🔌 WebSocket connection closed and cleaned up")
                    except Exception as e:
                        logger.warning(f"⚠️ Error closing WebSocket: {e}")
        
        # Log final statistics
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ WebSocket TTS completed: {chunk_count} chunks, {total_audio_duration:.1f}s audio, {total_time:.0f}ms total")
    
    def _split_text_for_streaming(self, text: str, max_chunk_size: int = 100) -> list:
        """Split text into optimal chunks for streaming"""
        # Split by sentences first
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # If adding this sentence would exceed max size, start new chunk
            if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # Ensure we have at least one chunk
        if not chunks:
            chunks = [text]
        
        return chunks
    
    def _create_audio_frame(self, audio_bytes: bytes) -> rtc.AudioFrame:
        """Convert audio bytes to LiveKit AudioFrame"""
        # Convert bytes to 16-bit signed integers
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        
        return rtc.AudioFrame(
            data=audio_data,
            sample_rate=24000,  # Deepgram standard rate
            num_channels=1,     # Mono audio
            samples_per_channel=len(audio_data)
        )
    
    async def aclose(self):
        """Clean up all WebSocket connections and reset state"""
        logger.info("🧹 Cleaning up Deepgram WebSocket TTS service")
        
        # Interrupt all active streams
        await self.interrupt_all_streams()
        
        # Close any remaining connections
        for connection in list(self._active_connections):
            try:
                await connection.close()
                logger.debug("🔌 Closed remaining WebSocket connection")
            except Exception as e:
                logger.warning(f"⚠️ Error closing remaining WebSocket: {e}")
        
        # Reset all state
        self._active_connections.clear()
        self._active_streams.clear()
        self._connection_count = 0
        self._retry_count = 0
        self._last_connection_time = 0
        
        logger.info("✅ Deepgram WebSocket TTS service cleaned up")


class StreamingContext:
    """Async context manager for LiveKit streaming interface"""
    
    def __init__(self, tts_instance: DeepgramWebSocketTTS):
        self._tts = tts_instance
        self._current_stream = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        # This should never be called directly - synthesize() creates the actual stream
        raise StopAsyncIteration
    
    def synthesize(self, text: str) -> "WebSocketStream":
        """Synthesize text using the TTS instance"""
        stream = self._tts.synthesize(text)
        self._current_stream = stream
        return stream


class WebSocketStream:
    """Real-time WebSocket TTS stream with interruption support"""
    
    def __init__(self, tts_instance: DeepgramWebSocketTTS, text: str, character: str):
        self._tts = tts_instance
        self._text = text
        self._character = character
        self._stream = None
        self._stream_id = f"ws_tts_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        self._interrupted = False
        
        # Add to active streams for interruption tracking
        self._tts._active_streams.add(self._stream_id)
        logger.debug(f"🆔 Created WebSocket stream: {self._stream_id}")
    
    def interrupt(self):
        """Interrupt this specific stream"""
        self._interrupted = True
        self._tts._active_streams.discard(self._stream_id)
        logger.info(f"🛑 WebSocket stream {self._stream_id} marked for interruption")
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> tts.SynthesizedAudio:
        if self._interrupted:
            raise StopAsyncIteration
        
        if self._stream is None:
            self._stream = self._tts._synthesize_streaming(self._text, self._character, self._stream_id)
        
        try:
            audio_frame = await self._stream.__anext__()
            return tts.SynthesizedAudio(
                frame=audio_frame,
                request_id=self._stream_id,
            )
        except StopAsyncIteration:
            # Clean up when stream ends
            self._tts._active_streams.discard(self._stream_id)
            logger.debug(f"🏁 WebSocket stream {self._stream_id} completed")
            raise StopAsyncIteration
    
    async def aclose(self):
        """Close the stream and clean up"""
        self.interrupt()
        if self._stream:
            try:
                await self._stream.aclose()
            except:
                pass
        logger.debug(f"🧹 WebSocket stream {self._stream_id} closed") 