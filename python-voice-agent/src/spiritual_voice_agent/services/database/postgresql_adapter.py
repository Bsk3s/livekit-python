"""
PostgreSQL Database Adapter

Provides PostgreSQL backend for production scaling with connection pooling
and async operations optimized for high-throughput voice agent workloads.
"""

import asyncio
import asyncpg
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import DatabaseAdapter, DatabaseConfig, DatabaseError, ConnectionError, QueryError

logger = logging.getLogger(__name__)


class PostgreSQLAdapter(DatabaseAdapter):
    """
    PostgreSQL database adapter with connection pooling
    
    Provides high-performance async PostgreSQL operations with connection pooling
    for production voice agent workloads. Optimized for zero-latency event logging.
    """
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._pool = None
        
    async def initialize(self) -> None:
        """Initialize PostgreSQL connection pool"""
        try:
            # Parse connection details
            if self.config.url:
                connection_string = self.config.url
            else:
                connection_string = self.config.get_connection_string()
            
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                connection_string,
                min_size=2,
                max_size=self.config.pool_size,
                max_inactive_connection_lifetime=300,  # 5 minutes
                command_timeout=30,
                server_settings={
                    'application_name': 'spiritual_voice_agent',
                    'jit': 'off'  # Disable JIT for better small query performance
                }
            )
            
            # Create tables and indexes
            await self.create_tables()
            
            self._initialized = True
            logger.info(f"✅ PostgreSQL adapter initialized with {self.config.pool_size} connections")
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL initialization failed: {e}")
            raise ConnectionError(f"Failed to initialize PostgreSQL: {e}")
    
    async def close(self) -> None:
        """Close PostgreSQL connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._initialized = False
        logger.info("✅ PostgreSQL adapter closed")
    
    async def create_tables(self) -> None:
        """Create database tables and indexes"""
        async with self._pool.acquire() as conn:
            # Create cost_events table with PostgreSQL optimizations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_events (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    character TEXT NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    
                    -- Performance metrics
                    stt_duration_ms INTEGER,
                    llm_duration_ms INTEGER,
                    tts_duration_ms INTEGER,
                    total_latency_ms INTEGER,
                    
                    -- Usage data
                    transcript_text TEXT,
                    response_text TEXT,
                    audio_duration_seconds DOUBLE PRECISION,
                    
                    -- Cost calculations (computed in background)
                    stt_cost NUMERIC(10,6),
                    llm_cost NUMERIC(10,6),
                    tts_cost NUMERIC(10,6),
                    total_cost NUMERIC(10,6),
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    
                    -- Status
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    cost_calculated BOOLEAN DEFAULT FALSE,
                    
                    -- Metadata
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indexes for high-performance queries
            indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_session_id ON cost_events(session_id)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_user_id ON cost_events(user_id)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_timestamp ON cost_events(timestamp)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_character ON cost_events(character)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_cost_calculated ON cost_events(cost_calculated)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_user_timestamp ON cost_events(user_id, timestamp)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_events_summary ON cost_events(timestamp, cost_calculated) WHERE cost_calculated = TRUE"
            ]
            
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                except Exception as e:
                    # Index might already exist, that's OK
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")
    
    async def insert_cost_event(self, event_data: Dict[str, Any]) -> int:
        """Insert a cost event and return the ID"""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO cost_events (
                        session_id, user_id, character, timestamp,
                        stt_duration_ms, llm_duration_ms, tts_duration_ms, total_latency_ms,
                        transcript_text, response_text, audio_duration_seconds,
                        success, error_message
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    RETURNING id
                """, 
                    event_data['session_id'], event_data['user_id'],
                    event_data['character'], event_data['timestamp'],
                    event_data.get('stt_duration_ms'), event_data.get('llm_duration_ms'),
                    event_data.get('tts_duration_ms'), event_data.get('total_latency_ms'),
                    event_data.get('transcript_text'), event_data.get('response_text'),
                    event_data.get('audio_duration_seconds'), event_data['success'],
                    event_data.get('error_message')
                )
                return row['id']
                
        except Exception as e:
            logger.error(f"❌ Failed to insert cost event: {e}")
            raise QueryError(f"Failed to insert cost event: {e}")
    
    async def update_cost_calculation(self, event_id: int, costs: Dict[str, Any]) -> None:
        """Update cost calculations for an event"""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE cost_events SET
                        stt_cost = $1, llm_cost = $2, tts_cost = $3, total_cost = $4,
                        input_tokens = $5, output_tokens = $6,
                        cost_calculated = TRUE
                    WHERE id = $7
                """,
                    costs.get('stt_cost'), costs.get('llm_cost'),
                    costs.get('tts_cost'), costs.get('total_cost'),
                    costs.get('input_tokens'), costs.get('output_tokens'),
                    event_id
                )
                
        except Exception as e:
            logger.error(f"❌ Failed to update cost calculation: {e}")
            raise QueryError(f"Failed to update cost calculation: {e}")
    
    async def get_session_costs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all cost events for a session"""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM cost_events 
                    WHERE session_id = $1 
                    ORDER BY timestamp
                """, session_id)
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get session costs: {e}")
            raise QueryError(f"Failed to get session costs: {e}")
    
    async def get_user_costs(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get cost events for a user within specified days"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM cost_events 
                    WHERE user_id = $1 AND timestamp > $2
                    ORDER BY timestamp DESC
                """, user_id, cutoff_time)
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get user costs: {e}")
            raise QueryError(f"Failed to get user costs: {e}")
    
    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get cost summary for dashboard"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        COALESCE(SUM(total_cost), 0) as total_cost,
                        COALESCE(SUM(stt_cost), 0) as total_stt_cost,
                        COALESCE(SUM(llm_cost), 0) as total_llm_cost,
                        COALESCE(SUM(tts_cost), 0) as total_tts_cost,
                        COALESCE(AVG(total_cost), 0) as avg_cost_per_turn,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM cost_events 
                    WHERE timestamp > $1 AND cost_calculated = TRUE
                """, cutoff_time)
                
                return {
                    "total_conversations": int(row['total_conversations']),
                    "total_cost": round(float(row['total_cost']), 4),
                    "total_stt_cost": round(float(row['total_stt_cost']), 4),
                    "total_llm_cost": round(float(row['total_llm_cost']), 4),
                    "total_tts_cost": round(float(row['total_tts_cost']), 4),
                    "avg_cost_per_turn": round(float(row['avg_cost_per_turn']), 4),
                    "unique_sessions": int(row['unique_sessions']),
                    "unique_users": int(row['unique_users'])
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get cost summary: {e}")
            raise QueryError(f"Failed to get cost summary: {e}")
    
    async def get_user_cost_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get cost summary for specific user"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        COALESCE(SUM(total_cost), 0) as total_cost,
                        COALESCE(AVG(total_cost), 0) as avg_cost_per_turn,
                        COUNT(DISTINCT session_id) as unique_sessions
                    FROM cost_events 
                    WHERE user_id = $1 AND timestamp > $2 AND cost_calculated = TRUE
                """, user_id, cutoff_time)
                
                return {
                    "user_id": user_id,
                    "total_conversations": int(row['total_conversations']),
                    "total_cost": round(float(row['total_cost']), 4),
                    "avg_cost_per_turn": round(float(row['avg_cost_per_turn']), 4),
                    "unique_sessions": int(row['unique_sessions'])
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get user cost summary: {e}")
            raise QueryError(f"Failed to get user cost summary: {e}")
    
    async def health_check(self) -> bool:
        """Check if database is healthy and responsive"""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"❌ PostgreSQL health check failed: {e}")
            return False
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        if not self._pool:
            return {"status": "not_initialized"}
        
        return {
            "status": "active",
            "size": self._pool.get_size(),
            "idle_connections": self._pool.get_idle_size(),
            "max_size": self._pool.get_max_size(),
            "min_size": self._pool.get_min_size()
        }