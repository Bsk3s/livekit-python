"""
WebSocket Dashboard Routes - Real-time data streaming
===================================================

WebSocket endpoints for streaming live conversation data and analytics
to dashboard clients with zero latency.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any

from ..services.websocket import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketBroadcastRequest(BaseModel):
    type: str
    session_id: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None
    turn_data: Optional[Dict[str, Any]] = None


@router.post("/ws/broadcast")
async def broadcast_to_websockets(request: WebSocketBroadcastRequest):
    """
    HTTP endpoint for triggering WebSocket broadcasts from LiveKit agent process
    """
    try:
        websocket_manager = get_websocket_manager()
        
        if request.type == "conversation_start":
            await websocket_manager.broadcast_json({
                "type": "conversation_start", 
                "session_id": request.session_id,
                "user_id": request.user_id,
                "metadata": request.metadata or {}
            })
            
        elif request.type == "conversation_turn":
            await websocket_manager.broadcast_json({
                "type": "conversation_turn",
                "session_id": request.session_id, 
                "user_id": request.user_id,
                "turn_data": request.turn_data or {}
            })
            
        elif request.type == "conversation_end":
            await websocket_manager.broadcast_json({
                "type": "conversation_end",
                "session_id": request.session_id,
                "user_id": request.user_id,
                "metadata": request.metadata or {}
            })
            
        logger.info(f"📡 HTTP→WebSocket: Broadcasted {request.type} for session {request.session_id[:8]}...")
        return {"status": "success", "message": f"Broadcasted {request.type}"}
        
    except Exception as e:
        logger.error(f"❌ HTTP→WebSocket broadcast failed: {e}")
        return {"status": "error", "message": str(e)}


@router.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(
    websocket: WebSocket, 
    client_id: Optional[str] = Query(None),
    dashboard_type: Optional[str] = Query("main")
):
    """
    WebSocket endpoint for real-time dashboard updates.
    
    Streams:
    - Live conversation events (start, turn, end)
    - Real-time analytics updates
    - System health status
    - Cost and usage metrics
    
    Usage:
    ws://localhost:10000/api/ws/dashboard?client_id=dashboard_1&dashboard_type=main
    """
    
    manager = get_websocket_manager()
    
    # Client metadata
    client_info = {
        "client_id": client_id or "unknown",
        "dashboard_type": dashboard_type,
        "user_agent": websocket.headers.get("user-agent", "unknown")
    }
    
    try:
        # Accept connection
        await manager.connect(websocket, client_info)
        
        logger.info(f"🔌 Dashboard WebSocket connected: {client_info}")
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong, commands, etc.)
                message = await websocket.receive_text()
                
                # Handle client commands
                if message == "ping":
                    await websocket.send_text("pong")
                elif message == "get_stats":
                    stats = manager.get_connection_stats()
                    await websocket.send_text(f"stats:{stats}")
                else:
                    logger.debug(f"📨 Received message from dashboard: {message}")
                    
            except WebSocketDisconnect:
                logger.info(f"🔌 Dashboard client disconnected: {client_info}")
                break
                
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
                break
    
    finally:
        # Clean up connection
        await manager.disconnect(websocket)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_websocket_manager()
    stats = manager.get_connection_stats()
    
    return {
        "status": "success",
        "data": {
            "websocket_stats": stats,
            "description": "Real-time WebSocket connection statistics"
        }
    }