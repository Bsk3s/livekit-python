"""
Conversation Tracker - Zero-impact data collection for LLM training

Collects comprehensive conversation data asynchronously without affecting voice performance.
Stores structured data ready for LLM training and dashboard analytics.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import httpx

from .models import ConversationSession, ConversationTurn
from .event_processor import ConversationEventProcessor
from .voice_usage_tracker import get_voice_usage_tracker

logger = logging.getLogger(__name__)


class ConversationTracker:
    """
    Event-driven conversation tracker for LLM training data collection
    
    Features:
    - Zero voice performance impact (async processing)
    - Comprehensive data collection for LLM training
    - Dashboard-ready analytics
    - Spiritual context enrichment
    - Clean data architecture
    """
    
    def __init__(self):
        self.event_processor = ConversationEventProcessor()
        self.voice_usage_tracker = get_voice_usage_tracker()
        self.active_sessions: Dict[str, ConversationSession] = {}
        self.event_queue = asyncio.Queue()
        self.processing_task = None
        
        logger.info("🎓 Conversation Tracker initialized for LLM training data collection")
        logger.info("⏱️ Voice usage tracking integrated for billing analytics")
    
    async def start_session(self, user_id: str, session_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new conversation session
        
        Args:
            user_id: Real Supabase user UUID
            session_metadata: Optional metadata about the session
            
        Returns:
            session_id: Unique session identifier
        """
        session_id = str(uuid.uuid4())
        
        session = ConversationSession(
            id=session_id,
            user_id=user_id,
            session_start=datetime.utcnow(),
            session_metadata=session_metadata or {}
        )
        
        self.active_sessions[session_id] = session
        
        # Start voice usage tracking
        await self.voice_usage_tracker.start_session_tracking(session_id, user_id)
        
        # Queue session start event for async processing
        await self.event_queue.put({
            "type": "session_start",
            "session_id": session_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "metadata": session_metadata
        })
        
        # 🔌 REAL-TIME: Send HTTP request to API server for WebSocket broadcast
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:10000/api/ws/broadcast",
                    json={
                        "type": "conversation_start",
                        "session_id": session_id,
                        "user_id": user_id,
                        "metadata": {
                            "character": session_metadata.get("character", "unknown"),
                            "session_type": session_metadata.get("session_type", "voice_chat"),
                            "room_name": session_metadata.get("room_name", "unknown")
                        }
                    },
                    timeout=1.0  # Fast timeout to avoid blocking voice
                )
            logger.debug(f"📡 HTTP→WebSocket: Broadcasted session start {session_id[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ HTTP→WebSocket broadcast failed (session start): {e}")
        
        logger.info(f"🎯 Started conversation session {session_id[:8]}... for user {user_id[:8]}...")
        logger.info(f"⏱️ Voice usage tracking started for billing analytics")
        
        return session_id
    
    async def track_conversation_turn(
        self,
        session_id: str,
        user_id: str,
        user_input: str,
        agent_response: str,
        technical_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track a conversation turn (NON-BLOCKING for voice performance)
        
        Args:
            session_id: Session identifier
            user_id: Real Supabase user UUID  
            user_input: What the user said
            agent_response: How Adina responded
            technical_metadata: Performance metrics, token usage, etc.
        """
        # Get session or create if missing
        session = self.active_sessions.get(session_id)
        if not session:
            logger.warning(f"Session {session_id[:8]}... not found, creating new session")
            await self.start_session(user_id)
            session = self.active_sessions[session_id]
        
        turn_number = session.total_turns + 1
        
        # Queue event for async processing (ZERO voice impact)
        await self.event_queue.put({
            "type": "conversation_turn",
            "session_id": session_id,
            "user_id": user_id,
            "turn_number": turn_number,
            "user_input": user_input,
            "agent_response": agent_response,
            "technical_metadata": technical_metadata or {},
            "timestamp": datetime.utcnow()
        })
        
        # Update session turn count immediately (in memory)
        session.total_turns = turn_number
        
        # 🔌 REAL-TIME: Send HTTP request to API server for WebSocket broadcast
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:10000/api/ws/broadcast",
                    json={
                        "type": "conversation_turn",
                        "session_id": session_id,
                        "user_id": user_id,
                        "turn_data": {
                            "turn_number": turn_number,
                            "user_input": user_input[:100] + "..." if len(user_input) > 100 else user_input,
                            "agent_response": agent_response[:100] + "..." if len(agent_response) > 100 else agent_response,
                            "input_length": len(user_input),
                            "response_length": len(agent_response),
                            "character": session.session_metadata.get("character", "unknown"),
                            "technical_metadata": technical_metadata or {}
                        }
                    },
                    timeout=1.0  # Fast timeout to avoid blocking voice
                )
            logger.debug(f"📡 HTTP→WebSocket: Broadcasted turn {turn_number} for session {session_id[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ HTTP→WebSocket broadcast failed (conversation turn): {e}")
        
        logger.debug(f"🎤 Queued conversation turn {turn_number} for session {session_id[:8]}...")
    
    async def end_session(self, session_id: str):
        """End a conversation session"""
        session = self.active_sessions.get(session_id)
        if session:
            session.end_session()
            
            # End voice usage tracking and get duration
            duration_seconds = await self.voice_usage_tracker.end_session_tracking(session_id)
            
            # Update session with actual duration
            if duration_seconds:
                session.total_duration_seconds = duration_seconds
            
            # Queue session end event
            await self.event_queue.put({
                "type": "session_end",
                "session_id": session_id,
                "user_id": session.user_id,
                "timestamp": datetime.utcnow(),
                "session_summary": session.get_session_summary(),
                "voice_duration_seconds": duration_seconds
            })
            
            # 🔌 REAL-TIME: Broadcast session end to dashboard immediately
            try:
                await broadcast_conversation_end(
                    session_id=session_id,
                    user_id=session.user_id,
                    summary={
                        "total_turns": session.total_turns,
                        "duration_seconds": duration_seconds,
                        "character": session.session_metadata.get("character", "unknown"),
                        "session_summary": session.get_session_summary()
                    }
                )
                logger.debug(f"📡 WebSocket: Broadcasted session end {session_id[:8]}...")
            except Exception as e:
                logger.warning(f"⚠️ WebSocket broadcast failed (session end): {e}")
            
            # Remove from active sessions
            del self.active_sessions[session_id]
            
            logger.info(f"🏁 Ended conversation session {session_id[:8]}... ({session.total_turns} turns, {duration_seconds}s)")
            logger.info(f"⏱️ Voice usage updated in user_profiles for billing")
    
    async def start_processing(self):
        """Start the async event processing loop"""
        if self.processing_task and not self.processing_task.done():
            logger.warning("Event processing already running")
            return
        
        self.processing_task = asyncio.create_task(self._process_events())
        logger.info("🚀 Started async conversation event processing")
    
    async def stop_processing(self):
        """Stop the async event processing loop"""
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("⏹️ Stopped conversation event processing")
    
    async def _process_events(self):
        """
        Process conversation events asynchronously
        
        This runs in the background and doesn't impact voice performance
        """
        logger.info("🎓 Starting LLM training data collection event loop...")
        
        while True:
            try:
                # Get event from queue (non-blocking for voice)
                event = await self.event_queue.get()
                
                # Process different event types
                if event["type"] == "conversation_turn":
                    await self._process_conversation_turn_event(event)
                elif event["type"] == "session_start":
                    await self._process_session_start_event(event)
                elif event["type"] == "session_end":
                    await self._process_session_end_event(event)
                
                # Mark event as processed
                self.event_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("Event processing cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error processing conversation event: {e}", exc_info=True)
                # Continue processing other events
                continue
    
    async def _process_conversation_turn_event(self, event: Dict[str, Any]):
        """Process a single conversation turn event"""
        try:
            # Enrich conversation with spiritual context (async)
            turn = await self.event_processor.process_conversation_turn(
                session_id=event["session_id"],
                user_id=event["user_id"],
                turn_number=event["turn_number"],
                user_input=event["user_input"],
                agent_response=event["agent_response"],
                technical_metadata=event["technical_metadata"]
            )
            
            # Store in Supabase (would be implemented here)
            await self._store_conversation_turn(turn)
            
            # Add to session for analytics
            session = self.active_sessions.get(event["session_id"])
            if session:
                session.add_turn(turn)
            
            logger.debug(f"✅ Processed and stored conversation turn {event['turn_number']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to process conversation turn: {e}", exc_info=True)
    
    async def _process_session_start_event(self, event: Dict[str, Any]):
        """Process session start event"""
        try:
            # Store session start in Supabase
            await self._store_session_start(event)
            logger.debug(f"✅ Stored session start for {event['session_id'][:8]}...")
        except Exception as e:
            logger.error(f"❌ Failed to process session start: {e}", exc_info=True)
    
    async def _process_session_end_event(self, event: Dict[str, Any]):
        """Process session end event"""
        try:
            # Store session end and summary in Supabase
            await self._store_session_end(event)
            logger.info(f"✅ Stored session end for {event['session_id'][:8]}...")
        except Exception as e:
            logger.error(f"❌ Failed to process session end: {e}", exc_info=True)
    
    async def _store_conversation_turn(self, turn: ConversationTurn):
        """Store conversation turn in Supabase - REAL IMPLEMENTATION"""
        from .supabase_integration import get_supabase_conversation_service
        
        supabase_service = get_supabase_conversation_service()
        success = await supabase_service.store_conversation_turn(turn)
        
        if success:
            logger.debug(f"✅ STORED turn in Supabase: session={turn.session_id[:8]}..., turn={turn.turn_number}")
        else:
            logger.error(f"❌ Failed to store turn in Supabase: session={turn.session_id[:8]}..., turn={turn.turn_number}")
    
    async def _store_session_start(self, event: Dict[str, Any]):
        """Store session start in Supabase - REAL IMPLEMENTATION"""
        from .supabase_integration import get_supabase_conversation_service
        
        # Create session object for storage
        session = ConversationSession(
            id=event["session_id"],
            user_id=event["user_id"],
            session_start=event["timestamp"],
            session_metadata=event.get("metadata", {})
        )
        
        supabase_service = get_supabase_conversation_service()
        success = await supabase_service.store_conversation_session(session)
        
        if success:
            logger.debug(f"✅ STORED session start in Supabase: {event['session_id'][:8]}...")
        else:
            logger.error(f"❌ Failed to store session start in Supabase: {event['session_id'][:8]}...")
    
    async def _store_session_end(self, event: Dict[str, Any]):
        """Store session end in Supabase - REAL IMPLEMENTATION"""
        from .supabase_integration import get_supabase_conversation_service
        
        # Update the session with end data
        supabase_service = get_supabase_conversation_service()
        
        try:
            # Update session end time and duration
            session_update = {
                "session_end": event["timestamp"].isoformat(),
                "total_duration_seconds": event.get("voice_duration_seconds"),
                "session_metadata": event.get("session_summary", {})
            }
            
            # Use direct Supabase update
            if supabase_service.supabase_client:
                result = supabase_service.supabase_client.table("conversation_sessions").update(
                    session_update
                ).eq("session_id", event["session_id"]).execute()
                
                if result.data:
                    logger.info(f"✅ UPDATED session end in Supabase: {event['session_id'][:8]}... ({event.get('voice_duration_seconds')}s)")
                else:
                    logger.error(f"❌ Failed to update session end in Supabase: {event['session_id'][:8]}...")
            else:
                logger.error("❌ Supabase client not available for session end update")
                
        except Exception as e:
            logger.error(f"❌ Failed to store session end: {e}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics for dashboard"""
        usage_stats = self.voice_usage_tracker.get_all_usage_stats()
        
        return {
            "active_sessions": len(self.active_sessions),
            "queue_size": self.event_queue.qsize(),
            "processing_status": "running" if self.processing_task and not self.processing_task.done() else "stopped",
            "voice_usage": usage_stats
        }


# Global instance
_conversation_tracker = None

def get_conversation_tracker() -> ConversationTracker:
    """Get the global conversation tracker instance"""
    global _conversation_tracker
    if _conversation_tracker is None:
        _conversation_tracker = ConversationTracker()
    return _conversation_tracker