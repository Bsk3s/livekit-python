"""
SQLite Database Adapter

Provides SQLite backend for development and simple deployments.
Maintains compatibility with existing SQLite implementation.
"""

import sqlite3
import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .base import DatabaseAdapter, DatabaseConfig, DatabaseError, ConnectionError, QueryError

logger = logging.getLogger(__name__)


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite database adapter with async interface
    
    Wraps synchronous SQLite operations in async interface for consistency
    with PostgreSQL adapter. Uses thread pool for non-blocking operations.
    """
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self.db_path = config.sqlite_path
        self._executor = None
        
    async def initialize(self) -> None:
        """Initialize SQLite database and thread pool"""
        try:
            # Create thread pool for SQLite operations
            self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlite")
            
            # Ensure database directory exists
            await self._run_in_executor(self._ensure_db_directory)
            
            # Create tables
            await self.create_tables()
            
            self._initialized = True
            logger.info(f"✅ SQLite adapter initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"❌ SQLite initialization failed: {e}")
            raise ConnectionError(f"Failed to initialize SQLite: {e}")
    
    async def close(self) -> None:
        """Close SQLite connections and thread pool"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        self._initialized = False
        logger.info("✅ SQLite adapter closed")
    
    async def create_tables(self) -> None:
        """Create database tables and indexes"""
        def _create_tables():
            with sqlite3.connect(self.db_path) as conn:
                # Create cost_events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cost_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        character TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        
                        -- Performance metrics
                        stt_duration_ms INTEGER,
                        llm_duration_ms INTEGER,
                        tts_duration_ms INTEGER, 
                        total_latency_ms INTEGER,
                        
                        -- Usage data
                        transcript_text TEXT,
                        response_text TEXT,
                        audio_duration_seconds REAL,
                        
                        -- Cost calculations (computed in background)
                        stt_cost REAL,
                        llm_cost REAL,
                        tts_cost REAL,
                        total_cost REAL,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        
                        -- Status
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        cost_calculated BOOLEAN DEFAULT FALSE,
                        
                        -- Metadata
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON cost_events(session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON cost_events(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cost_events(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_character ON cost_events(character)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_calculated ON cost_events(cost_calculated)")
                
                conn.commit()
        
        await self._run_in_executor(_create_tables)
    
    async def insert_cost_event(self, event_data: Dict[str, Any]) -> int:
        """Insert a cost event and return the ID"""
        def _insert():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO cost_events (
                        session_id, user_id, character, timestamp,
                        stt_duration_ms, llm_duration_ms, tts_duration_ms, total_latency_ms,
                        transcript_text, response_text, audio_duration_seconds,
                        success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_data['session_id'], event_data['user_id'], 
                    event_data['character'], event_data['timestamp'],
                    event_data.get('stt_duration_ms'), event_data.get('llm_duration_ms'),
                    event_data.get('tts_duration_ms'), event_data.get('total_latency_ms'),
                    event_data.get('transcript_text'), event_data.get('response_text'),
                    event_data.get('audio_duration_seconds'), event_data['success'],
                    event_data.get('error_message')
                ))
                return cursor.lastrowid
        
        try:
            return await self._run_in_executor(_insert)
        except Exception as e:
            logger.error(f"❌ Failed to insert cost event: {e}")
            raise QueryError(f"Failed to insert cost event: {e}")
    
    async def update_cost_calculation(self, event_id: int, costs: Dict[str, Any]) -> None:
        """Update cost calculations for an event"""
        def _update():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE cost_events SET
                        stt_cost = ?, llm_cost = ?, tts_cost = ?, total_cost = ?,
                        input_tokens = ?, output_tokens = ?,
                        cost_calculated = TRUE
                    WHERE id = ?
                """, (
                    costs.get('stt_cost'), costs.get('llm_cost'),
                    costs.get('tts_cost'), costs.get('total_cost'),
                    costs.get('input_tokens'), costs.get('output_tokens'),
                    event_id
                ))
        
        try:
            await self._run_in_executor(_update)
        except Exception as e:
            logger.error(f"❌ Failed to update cost calculation: {e}")
            raise QueryError(f"Failed to update cost calculation: {e}")
    
    async def get_session_costs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all cost events for a session"""
        def _get_session():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM cost_events 
                    WHERE session_id = ? 
                    ORDER BY timestamp
                """, (session_id,))
                return [dict(row) for row in cursor.fetchall()]
        
        try:
            return await self._run_in_executor(_get_session)
        except Exception as e:
            logger.error(f"❌ Failed to get session costs: {e}")
            raise QueryError(f"Failed to get session costs: {e}")
    
    async def get_user_costs(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get cost events for a user within specified days"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        def _get_user():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM cost_events 
                    WHERE user_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                """, (user_id, cutoff_time))
                return [dict(row) for row in cursor.fetchall()]
        
        try:
            return await self._run_in_executor(_get_user)
        except Exception as e:
            logger.error(f"❌ Failed to get user costs: {e}")
            raise QueryError(f"Failed to get user costs: {e}")
    
    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get cost summary for dashboard"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        def _get_summary():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        SUM(total_cost) as total_cost,
                        SUM(stt_cost) as total_stt_cost,
                        SUM(llm_cost) as total_llm_cost,
                        SUM(tts_cost) as total_tts_cost,
                        AVG(total_cost) as avg_cost_per_turn,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM cost_events 
                    WHERE timestamp > ? AND cost_calculated = TRUE
                """, (cutoff_time,))
                
                row = cursor.fetchone()
                return {
                    "total_conversations": row[0] or 0,
                    "total_cost": round(row[1] or 0, 4),
                    "total_stt_cost": round(row[2] or 0, 4), 
                    "total_llm_cost": round(row[3] or 0, 4),
                    "total_tts_cost": round(row[4] or 0, 4),
                    "avg_cost_per_turn": round(row[5] or 0, 4),
                    "unique_sessions": row[6] or 0,
                    "unique_users": row[7] or 0
                }
        
        try:
            return await self._run_in_executor(_get_summary)
        except Exception as e:
            logger.error(f"❌ Failed to get cost summary: {e}")
            raise QueryError(f"Failed to get cost summary: {e}")
    
    async def get_user_cost_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get cost summary for specific user"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        def _get_user_summary():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        SUM(total_cost) as total_cost,
                        AVG(total_cost) as avg_cost_per_turn,
                        COUNT(DISTINCT session_id) as unique_sessions
                    FROM cost_events 
                    WHERE user_id = ? AND timestamp > ? AND cost_calculated = TRUE
                """, (user_id, cutoff_time))
                
                row = cursor.fetchone()
                return {
                    "user_id": user_id,
                    "total_conversations": row[0] or 0,
                    "total_cost": round(row[1] or 0, 4),
                    "avg_cost_per_turn": round(row[2] or 0, 4),
                    "unique_sessions": row[3] or 0
                }
        
        try:
            return await self._run_in_executor(_get_user_summary)
        except Exception as e:
            logger.error(f"❌ Failed to get user cost summary: {e}")
            raise QueryError(f"Failed to get user cost summary: {e}")
    
    async def health_check(self) -> bool:
        """Check if database is healthy and responsive"""
        def _health_check():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT 1")
                    return cursor.fetchone() is not None
            except Exception:
                return False
        
        try:
            return await self._run_in_executor(_health_check)
        except Exception:
            return False
    
    def _ensure_db_directory(self):
        """Create the database directory if it doesn't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def _run_in_executor(self, func, *args):
        """Run a function in the thread pool executor"""
        if not self._executor:
            raise RuntimeError("SQLite adapter not initialized")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)