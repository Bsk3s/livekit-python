"""
Cost Analytics Service - Zero-Impact Voice Agent Cost Tracking

This service handles cost calculation and analytics storage completely separate 
from the voice processing pipeline to ensure zero latency impact on conversations.

Key Features:
- SQLite database for cost analytics (easy deployment, no config needed)
- Async background processing (voice pipeline never waits)
- Accurate cost calculations using 2025 pricing
- Event-driven architecture for real-time insights

Author: Voice Agent Team
"""

import asyncio
import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


@dataclass
class CostEvent:
    """
    Represents a single cost event from the voice pipeline.
    
    This is the minimal data structure that gets logged from the voice pipeline
    with zero latency impact. All cost calculations happen later in background.
    """
    session_id: str
    user_id: str
    timestamp: float
    character: str
    
    # Performance metrics (from voice pipeline)
    stt_duration_ms: Optional[int] = None
    llm_duration_ms: Optional[int] = None  
    tts_duration_ms: Optional[int] = None
    total_latency_ms: Optional[int] = None
    
    # Usage metrics (for cost calculation)
    transcript_text: Optional[str] = None
    response_text: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    
    # Success tracking
    success: bool = True
    error_message: Optional[str] = None


@dataclass 
class CalculatedCosts:
    """
    Calculated costs for a conversation turn.
    
    These are computed in background after the voice processing is complete,
    ensuring zero impact on conversation latency.
    """
    # Individual service costs (USD)
    stt_cost: float = 0.0      # Deepgram Nova-2 STT
    llm_cost: float = 0.0      # OpenAI GPT-4o-mini  
    tts_cost: float = 0.0      # OpenAI TTS
    total_cost: float = 0.0    # Sum of all costs
    
    # Token usage (for LLM cost breakdown)
    input_tokens: int = 0
    output_tokens: int = 0
    
    # Pricing rates used (for audit trail)
    stt_rate_per_minute: float = 0.0058  # Deepgram streaming rate
    llm_input_rate_per_1m: float = 0.15  # GPT-4o-mini input
    llm_output_rate_per_1m: float = 0.60 # GPT-4o-mini output  
    tts_rate_per_1k_chars: float = 15.0  # OpenAI TTS standard


class CostAnalyticsDB:
    """
    SQLite database handler for cost analytics.
    
    Simple, file-based database that requires zero configuration.
    Perfect for analytics workloads and easy to migrate to PostgreSQL later.
    """
    
    def __init__(self, db_path: str = "logs/cost_analytics.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Create the logs directory if it doesn't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database schema if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
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
            
            # Create indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON cost_events(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON cost_events(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cost_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_character ON cost_events(character)")
            
    def insert_cost_event(self, event: CostEvent) -> int:
        """
        Insert a cost event (fast, minimal data).
        
        This is called from the voice pipeline and must be extremely fast.
        Cost calculations happen later in background.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO cost_events (
                    session_id, user_id, character, timestamp,
                    stt_duration_ms, llm_duration_ms, tts_duration_ms, total_latency_ms,
                    transcript_text, response_text, audio_duration_seconds,
                    success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.session_id, event.user_id, event.character, event.timestamp,
                event.stt_duration_ms, event.llm_duration_ms, event.tts_duration_ms, event.total_latency_ms,
                event.transcript_text, event.response_text, event.audio_duration_seconds,
                event.success, event.error_message
            ))
            return cursor.lastrowid
    
    def update_cost_calculation(self, event_id: int, costs: CalculatedCosts):
        """
        Update cost calculations for an event (background operation).
        
        This happens after voice processing is complete, ensuring zero impact.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE cost_events SET
                    stt_cost = ?, llm_cost = ?, tts_cost = ?, total_cost = ?,
                    input_tokens = ?, output_tokens = ?,
                    cost_calculated = TRUE
                WHERE id = ?
            """, (
                costs.stt_cost, costs.llm_cost, costs.tts_cost, costs.total_cost,
                costs.input_tokens, costs.output_tokens, event_id
            ))
    
    def get_session_costs(self, session_id: str) -> List[Dict]:
        """Get all cost events for a session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM cost_events 
                WHERE session_id = ? 
                ORDER BY timestamp
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_costs(self, user_id: str, days: int = 30) -> List[Dict]:
        """Get cost events for a user within specified days"""
        cutoff_time = time.time() - (days * 24 * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM cost_events 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (user_id, cutoff_time))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_cost_summary(self, days: int = 7) -> Dict:
        """Get cost summary for dashboard"""
        cutoff_time = time.time() - (days * 24 * 3600)
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


class AsyncEventLogger:
    """
    Fire-and-forget event logger for voice pipeline.
    
    This is the critical component that ensures ZERO latency impact.
    Voice pipeline calls log_event_async() which returns immediately.
    All processing happens in background thread.
    """
    
    def __init__(self):
        self.event_queue = Queue()
        self.db = CostAnalyticsDB()
        self.background_thread = None
        self.shutdown_flag = threading.Event()
        self._start_background_processor()
    
    def _start_background_processor(self):
        """Start background thread for processing events"""
        self.background_thread = threading.Thread(
            target=self._process_events_background,
            daemon=True,
            name="CostEventProcessor"
        )
        self.background_thread.start()
        logger.info("🎯 AsyncEventLogger background processor started")
    
    def log_event_async(self, event_data: Dict) -> None:
        """
        Log event with ZERO latency impact.
        
        This method returns immediately (microseconds).
        All processing happens in background thread.
        """
        try:
            # Convert dict to CostEvent (validation happens here, not in voice pipeline)
            event = CostEvent(**event_data)
            
            # Put in queue without waiting - this is the key to zero latency
            self.event_queue.put_nowait(event)
            
            # Method returns immediately - voice pipeline continues
            
        except Exception as e:
            # Even errors don't impact voice pipeline
            logger.error(f"❌ Error queuing cost event (non-blocking): {e}")
    
    def _process_events_background(self):
        """
        Background thread that processes events from queue.
        
        This runs continuously, processing cost events and calculating
        costs without any impact on the voice pipeline.
        """
        logger.info("🔄 Cost event background processor started")
        
        while not self.shutdown_flag.is_set():
            try:
                # Get event from queue (with timeout)
                event = self.event_queue.get(timeout=1.0)
                
                # Store event in database (fast operation)
                event_id = self.db.insert_cost_event(event)
                
                # Calculate costs in background
                self._calculate_costs_background(event_id, event)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except Empty:
                # Timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"❌ Error processing cost event: {e}")
    
    def _calculate_costs_background(self, event_id: int, event: CostEvent):
        """
        Calculate costs for an event in background.
        
        This uses 2025 pricing rates and handles all the complex cost logic
        without impacting voice processing performance.
        """
        try:
            costs = CalculatedCosts()
            
            # 1. Calculate STT cost (Deepgram Nova-2 streaming)
            if event.audio_duration_seconds:
                audio_minutes = event.audio_duration_seconds / 60.0
                costs.stt_cost = audio_minutes * costs.stt_rate_per_minute
            
            # 2. Calculate LLM cost (GPT-4o-mini)
            if event.transcript_text and event.response_text:
                # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
                costs.input_tokens = len(event.transcript_text) // 4
                costs.output_tokens = len(event.response_text) // 4
                
                # Calculate LLM costs
                costs.llm_cost = (
                    (costs.input_tokens / 1_000_000) * costs.llm_input_rate_per_1m +
                    (costs.output_tokens / 1_000_000) * costs.llm_output_rate_per_1m
                )
            
            # 3. Calculate TTS cost (OpenAI TTS)
            if event.response_text:
                char_count = len(event.response_text)
                costs.tts_cost = (char_count / 1000) * costs.tts_rate_per_1k_chars
            
            # 4. Calculate total cost
            costs.total_cost = costs.stt_cost + costs.llm_cost + costs.tts_cost
            
            # 5. Update database with calculated costs
            self.db.update_cost_calculation(event_id, costs)
            
            logger.debug(f"💰 Calculated costs for event {event_id}: ${costs.total_cost:.4f}")
            
        except Exception as e:
            logger.error(f"❌ Error calculating costs for event {event_id}: {e}")
    
    def shutdown(self):
        """Graceful shutdown of background processor"""
        logger.info("🛑 Shutting down AsyncEventLogger...")
        self.shutdown_flag.set()
        if self.background_thread:
            self.background_thread.join(timeout=5.0)
        logger.info("✅ AsyncEventLogger shutdown complete")


# Global instance for easy access
cost_logger = AsyncEventLogger()


def get_cost_analytics_db() -> CostAnalyticsDB:
    """Get cost analytics database instance"""
    return cost_logger.db


def log_voice_event(event_data: Dict) -> None:
    """
    Convenience function for logging voice events with zero latency.
    
    Usage from voice pipeline:
        log_voice_event({
            'session_id': session_id,
            'user_id': user_id,
            'character': character,
            'timestamp': time.time(),
            'stt_duration_ms': stt_duration,
            'llm_duration_ms': llm_duration,
            'tts_duration_ms': tts_duration,
            'transcript_text': transcript,
            'response_text': response_text,
            'audio_duration_seconds': audio_duration
        })
    """
    cost_logger.log_event_async(event_data) 