"""
Real-Time WebSocket Manager for Voice Agent Dashboard
====================================================

Provides instant streaming of conversation data to dashboard clients.
Zero-latency updates for live analytics and conversation monitoring.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConversationEvent:
    """Real-time conversation event for dashboard."""
    event_type: str  # "session_start", "session_end", "turn_completed", "analytics_update"
    timestamp: str
    session_id: str
    user_id: str
    data: Dict


@dataclass
class AnalyticsEvent:
    """Real-time analytics update for dashboard."""
    event_type: str = "analytics_update"
    timestamp: str = ""
    active_users: int = 0
    active_sessions: int = 0
    total_turns_today: int = 0
    avg_latency_ms: int = 0
    cost_today: float = 0.0


class WebSocketManager:
    """
    Manages WebSocket connections for real-time dashboard updates.
    
    Features:
    - Multiple dashboard clients support
    - Automatic connection cleanup
    - Event broadcasting
    - Connection health monitoring
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Connection metadata
        self.connection_info: Dict[WebSocket, Dict] = {}
        
        # Event queue for reliable delivery
        self.event_queue = asyncio.Queue()
        self.broadcast_task = None
        
        logger.info("🔌 WebSocket Manager initialized for real-time dashboard")
    
    async def connect(self, websocket: WebSocket, client_info: Dict = None):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Store client metadata
        self.connection_info[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "client_info": client_info or {},
            "events_sent": 0
        }
        
        # Start broadcast task if first connection
        if len(self.active_connections) == 1 and not self.broadcast_task:
            self.broadcast_task = asyncio.create_task(self._broadcast_worker())
        
        logger.info(f"🔌 Dashboard client connected (total: {len(self.active_connections)})")
        
        # Send initial connection confirmation
        await self._send_to_client(websocket, {
            "event_type": "connection_established",
            "timestamp": datetime.now().isoformat(),
            "message": "Real-time dashboard connected",
            "active_connections": len(self.active_connections)
        })
    
    async def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if websocket in self.connection_info:
            connection_duration = datetime.now() - datetime.fromisoformat(
                self.connection_info[websocket]["connected_at"]
            )
            events_sent = self.connection_info[websocket]["events_sent"]
            del self.connection_info[websocket]
            
            logger.info(f"🔌 Dashboard client disconnected (duration: {connection_duration}, events: {events_sent})")
        
        # Stop broadcast task if no connections
        if len(self.active_connections) == 0 and self.broadcast_task:
            self.broadcast_task.cancel()
            self.broadcast_task = None
            
        logger.info(f"🔌 Active connections: {len(self.active_connections)}")
    
    async def broadcast_conversation_event(self, event: ConversationEvent):
        """Broadcast conversation event to all connected dashboards."""
        if not self.active_connections:
            logger.debug("📡 No dashboard connections - skipping broadcast")
            return
            
        await self.event_queue.put(event)
        logger.debug(f"📡 Queued conversation event: {event.event_type}")
    
    async def broadcast_analytics_update(self, analytics: AnalyticsEvent):
        """Broadcast analytics update to all connected dashboards."""
        if not self.active_connections:
            logger.debug("📊 No dashboard connections - skipping analytics")
            return
            
        await self.event_queue.put(analytics)
        logger.debug(f"📊 Queued analytics update")
    
    async def _broadcast_worker(self):
        """Background worker to broadcast events to all clients."""
        logger.info("📡 WebSocket broadcast worker started")
        
        try:
            while True:
                # Get next event from queue
                event = await self.event_queue.get()
                
                # Convert to dict for JSON serialization
                if hasattr(event, '__dict__'):
                    event_data = asdict(event)
                else:
                    event_data = event
                
                # Broadcast to all connected clients
                disconnected_clients = []
                
                for websocket in self.active_connections.copy():
                    try:
                        await self._send_to_client(websocket, event_data)
                        self.connection_info[websocket]["events_sent"] += 1
                        
                    except WebSocketDisconnect:
                        logger.info("🔌 Client disconnected during broadcast")
                        disconnected_clients.append(websocket)
                        
                    except Exception as e:
                        logger.error(f"❌ Error broadcasting to client: {e}")
                        disconnected_clients.append(websocket)
                
                # Clean up disconnected clients
                for websocket in disconnected_clients:
                    await self.disconnect(websocket)
                
                logger.debug(f"📡 Broadcasted {event_data.get('event_type', 'unknown')} to {len(self.active_connections)} clients")
                
        except asyncio.CancelledError:
            logger.info("📡 WebSocket broadcast worker stopped")
            
        except Exception as e:
            logger.error(f"❌ WebSocket broadcast worker error: {e}")
    
    async def _send_to_client(self, websocket: WebSocket, data: Dict):
        """Send data to a specific WebSocket client."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"❌ Failed to send to client: {e}")
            raise
    
    def get_connection_stats(self) -> Dict:
        """Get WebSocket connection statistics."""
        total_events_sent = sum(
            info["events_sent"] for info in self.connection_info.values()
        )
        
        return {
            "active_connections": len(self.active_connections),
            "total_events_sent": total_events_sent,
            "queue_size": self.event_queue.qsize(),
            "broadcast_worker_active": self.broadcast_task is not None and not self.broadcast_task.done()
        }


# Global WebSocket manager instance
_websocket_manager: WebSocketManager = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _websocket_manager
    
    if not _websocket_manager:
        _websocket_manager = WebSocketManager()
    
    return _websocket_manager


# Convenience functions for broadcasting
async def broadcast_conversation_start(session_id: str, user_id: str, metadata: Dict = None):
    """Broadcast conversation start event."""
    event = ConversationEvent(
        event_type="session_start",
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        user_id=user_id,
        data=metadata or {}
    )
    
    manager = get_websocket_manager()
    await manager.broadcast_conversation_event(event)


async def broadcast_conversation_turn(session_id: str, user_id: str, turn_data: Dict):
    """Broadcast conversation turn event."""
    event = ConversationEvent(
        event_type="turn_completed",
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        user_id=user_id,
        data=turn_data
    )
    
    manager = get_websocket_manager()
    await manager.broadcast_conversation_event(event)


async def broadcast_conversation_end(session_id: str, user_id: str, summary: Dict = None):
    """Broadcast conversation end event."""
    event = ConversationEvent(
        event_type="session_end",
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        user_id=user_id,
        data=summary or {}
    )
    
    manager = get_websocket_manager()
    await manager.broadcast_conversation_event(event)


async def broadcast_analytics_update(analytics_data: Dict):
    """Broadcast analytics update to dashboard."""
    analytics = AnalyticsEvent(
        timestamp=datetime.now().isoformat(),
        active_users=analytics_data.get("active_users", 0),
        active_sessions=analytics_data.get("active_sessions", 0),
        total_turns_today=analytics_data.get("total_turns_today", 0),
        avg_latency_ms=analytics_data.get("avg_latency_ms", 0),
        cost_today=analytics_data.get("cost_today", 0.0)
    )
    
    manager = get_websocket_manager()
    await manager.broadcast_analytics_update(analytics)