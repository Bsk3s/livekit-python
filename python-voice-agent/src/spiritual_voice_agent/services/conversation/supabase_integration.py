"""
Supabase Integration for Conversation Data and Voice Usage Tracking

REAL IMPLEMENTATION - Handles storing conversation data and updating user voice usage in Supabase.
"""
import logging
from typing import Dict, Any, Optional
import os
from supabase import create_client, Client

from .models import ConversationTurn, ConversationSession

logger = logging.getLogger(__name__)


class SupabaseConversationService:
    """
    REAL Supabase operations for conversation tracking and voice usage
    """
    
    def __init__(self):
        # Initialize Supabase client - REQUIRES environment variables
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")
        
        try:
            self.supabase_client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("🔗 REAL Supabase client connected successfully!")
            logger.info(f"📡 Connected to: {self.supabase_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            self.supabase_client = None
    
    async def store_conversation_session(self, session: ConversationSession):
        """Store conversation session in Supabase - REAL IMPLEMENTATION"""
        if not self.supabase_client:
            logger.error("❌ Supabase client not available")
            return False
            
        try:
            session_data = {
                "session_id": session.id,  # Map session.id to session_id column
                "user_id": session.user_id,
                "session_start": session.session_start.isoformat(),
                "session_end": session.session_end.isoformat() if session.session_end else None,
                "total_turns": session.total_turns,
                "total_duration_seconds": session.total_duration_seconds,
                "character_name": session.character_name,
                "session_metadata": session.session_metadata
            }
            
            # REAL Supabase insert
            result = self.supabase_client.table("conversation_sessions").insert(session_data).execute()
            
            if result.data:
                # Store the auto-generated ID for use in conversation_turns
                db_session_id = result.data[0]["id"]
                self._session_id_mapping = getattr(self, '_session_id_mapping', {})
                self._session_id_mapping[session.id] = db_session_id
                
                logger.info(f"✅ STORED conversation session: {session.id[:8]}... (DB ID: {str(db_session_id)[:8]}...)")
                return True
            else:
                logger.error(f"❌ No data returned from conversation session insert")
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to store conversation session: {e}")
            return False
    
    async def store_conversation_turn(self, turn: ConversationTurn):
        """Store conversation turn in Supabase - REAL IMPLEMENTATION"""
        if not self.supabase_client:
            logger.error("❌ Supabase client not available")
            return False
            
        try:
            turn_data = turn.to_supabase_format()
            
            # Map the session_id to the database ID
            session_id_mapping = getattr(self, '_session_id_mapping', {})
            if turn.session_id in session_id_mapping:
                turn_data["session_id"] = session_id_mapping[turn.session_id]
            else:
                logger.warning(f"⚠️ No session mapping found for {turn.session_id[:8]}...")
                # Try to find the session in database
                session_result = self.supabase_client.table("conversation_sessions").select("id").eq("session_id", turn.session_id).execute()
                if session_result.data and len(session_result.data) > 0:
                    turn_data["session_id"] = session_result.data[0]["id"]
                else:
                    logger.error(f"❌ Cannot find session {turn.session_id[:8]}... in database")
                    return False
            
            # REAL Supabase insert
            result = self.supabase_client.table("conversation_turns").insert(turn_data).execute()
            
            if result.data:
                logger.info(f"✅ STORED conversation turn: session={turn.session_id[:8]}..., turn={turn.turn_number}")
                return True
            else:
                logger.error(f"❌ No data returned from conversation turn insert")
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to store conversation turn: {e}")
            return False
    
    async def update_user_speech_time(self, user_id: str, additional_seconds: int):
        """
        Update user's cumulative speech_time in user_profiles table - REAL IMPLEMENTATION
        
        This is the key function for billing analytics!
        """
        if not self.supabase_client:
            logger.error("❌ Supabase client not available")
            return False
            
        try:
            # REAL Supabase update with SQL function
            result = self.supabase_client.rpc(
                'update_user_speech_time', 
                {
                    'user_uuid': user_id,
                    'additional_seconds': additional_seconds
                }
            ).execute()
            
            if result.data is not None:
                logger.info(f"✅ UPDATED speech_time for user {user_id[:8]}... (+{additional_seconds}s)")
                return True
            else:
                # Fallback to direct update if RPC doesn't exist
                logger.warning("⚠️ RPC function not found, using direct update")
                
                # Get current speech_time
                current_result = self.supabase_client.table("user_profiles").select("speech_time").eq("id", user_id).execute()
                
                if current_result.data:
                    current_time = current_result.data[0].get("speech_time", 0) or 0
                    new_time = current_time + additional_seconds
                    
                    # Update with new total
                    update_result = self.supabase_client.table("user_profiles").update({
                        "speech_time": new_time
                    }).eq("id", user_id).execute()
                    
                    if update_result.data:
                        logger.info(f"✅ UPDATED speech_time for user {user_id[:8]}... (+{additional_seconds}s) via direct update")
                        return True
                
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to update speech_time for user {user_id[:8]}...: {e}")
            return False
    
    async def get_user_total_speech_time(self, user_id: str) -> Optional[int]:
        """Get user's total speech time from user_profiles - REAL IMPLEMENTATION"""
        if not self.supabase_client:
            logger.error("❌ Supabase client not available")
            return None
            
        try:
            # REAL Supabase query
            result = self.supabase_client.table("user_profiles").select("speech_time").eq("id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                speech_time = result.data[0].get("speech_time", 0) or 0
                logger.debug(f"📊 Retrieved speech_time for user {user_id[:8]}...: {speech_time}s")
                return speech_time
            else:
                logger.warning(f"⚠️ No user_profile found for user {user_id[:8]}...")
                return 0
            
        except Exception as e:
            logger.error(f"❌ Failed to get speech_time for user {user_id[:8]}...: {e}")
            return None
    
    async def get_conversation_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get conversation analytics for dashboard"""
        try:
            # TODO: Implement analytics queries
            logger.debug(f"📊 [TODO] Get conversation analytics for user {user_id[:8]}...")
            
            return {
                "total_sessions": 0,
                "total_turns": 0,
                "total_speech_time": 0,
                "avg_session_duration": 0,
                "spiritual_topics": [],
                "recent_sessions": []
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get analytics for user {user_id[:8]}...: {e}")
            return {}


# Global instance
_supabase_service = None

def get_supabase_conversation_service() -> SupabaseConversationService:
    """Get the global Supabase conversation service instance"""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseConversationService()
    return _supabase_service