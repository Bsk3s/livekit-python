"""
Voice Usage Tracker - Updates user_profiles.speech_time for billing analytics

Tracks cumulative voice minutes per user in Supabase user_profiles table.
Integrates with conversation tracking for automatic usage updates.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .supabase_integration import get_supabase_conversation_service

logger = logging.getLogger(__name__)


class VoiceUsageTracker:
    """
    Tracks voice usage and updates user_profiles.speech_time in Supabase
    
    Features:
    - Automatic speech time tracking per user
    - Cumulative billing analytics  
    - Integration with conversation sessions
    - Dashboard-ready usage data
    """
    
    def __init__(self):
        self.session_usage_cache: Dict[str, Dict[str, Any]] = {}
        self.supabase_service = get_supabase_conversation_service()
        logger.info("⏱️ Voice Usage Tracker initialized for billing analytics")
    
    async def start_session_tracking(self, session_id: str, user_id: str):
        """Start tracking voice usage for a session"""
        self.session_usage_cache[session_id] = {
            "user_id": user_id,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration_seconds": 0
        }
        
        logger.debug(f"⏱️ Started voice usage tracking for session {session_id[:8]}...")
    
    async def end_session_tracking(self, session_id: str) -> Optional[int]:
        """
        End session tracking and calculate duration
        
        Returns:
            Duration in seconds, or None if session not found
        """
        if session_id not in self.session_usage_cache:
            logger.warning(f"Session {session_id[:8]}... not found in usage cache")
            return None
        
        session_data = self.session_usage_cache[session_id]
        session_data["end_time"] = datetime.utcnow()
        
        if session_data["start_time"]:
            duration = session_data["end_time"] - session_data["start_time"]
            session_data["duration_seconds"] = int(duration.total_seconds())
        
        duration_seconds = session_data["duration_seconds"]
        user_id = session_data["user_id"]
        
        # Update user's total speech time in Supabase
        await self._update_user_speech_time(user_id, duration_seconds)
        
        # Clean up cache
        del self.session_usage_cache[session_id]
        
        logger.info(f"⏱️ Session {session_id[:8]}... ended: {duration_seconds}s for user {user_id[:8]}...")
        
        return duration_seconds
    
    async def _update_user_speech_time(self, user_id: str, additional_seconds: int):
        """
        Update user's cumulative speech_time in user_profiles table
        
        Args:
            user_id: Real Supabase user UUID
            additional_seconds: Seconds to add to their total
        """
        try:
            # Update via Supabase service
            success = await self.supabase_service.update_user_speech_time(user_id, additional_seconds)
            
            if success:
                logger.info(f"✅ Updated speech_time for user {user_id[:8]}... (+{additional_seconds}s)")
            else:
                logger.error(f"❌ Failed to update speech_time for user {user_id[:8]}...")
            
        except Exception as e:
            logger.error(f"❌ Failed to update speech_time for user {user_id[:8]}...: {e}")
    
    async def get_user_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get voice usage statistics for a user (for dashboard)
        
        Returns:
            Usage statistics including total time, session count, etc.
        """
        # Get total speech time from Supabase
        total_speech_time = await self.supabase_service.get_user_total_speech_time(user_id)
        
        return {
            "user_id": user_id,
            "total_speech_time_seconds": total_speech_time or 0,
            "active_sessions": len([s for s in self.session_usage_cache.values() if s["user_id"] == user_id]),
            "last_session": None  # Would come from conversation_sessions
        }
    
    def get_all_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all users (for dashboard)"""
        active_sessions = len(self.session_usage_cache)
        active_users = len(set(s["user_id"] for s in self.session_usage_cache.values()))
        
        return {
            "active_sessions": active_sessions,
            "active_users": active_users,
            "total_cache_size": len(self.session_usage_cache)
        }


# Global instance
_voice_usage_tracker = None

def get_voice_usage_tracker() -> VoiceUsageTracker:
    """Get the global voice usage tracker instance"""
    global _voice_usage_tracker
    if _voice_usage_tracker is None:
        _voice_usage_tracker = VoiceUsageTracker()
    return _voice_usage_tracker