import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class PipelineMetrics:
    """Pipeline stage timing breakdown"""
    total_latency_ms: float
    stt_latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    tts_first_chunk_ms: Optional[float] = None
    tts_total_ms: Optional[float] = None
    audio_processing_ms: Optional[float] = None

@dataclass
class QualityMetrics:
    """Quality and success indicators"""
    success: bool
    audio_chunks: int = 0
    total_audio_bytes: int = 0
    transcription_confidence: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class ContextMetrics:
    """Conversation context"""
    user_input_length: int = 0
    ai_response_length: int = 0
    session_duration_s: float = 0
    conversation_turn: int = 0

@dataclass
class MetricsEvent:
    """Complete metrics event"""
    timestamp: str
    session_id: str
    character: str
    tts_model: str
    pipeline_metrics: PipelineMetrics
    quality_metrics: QualityMetrics
    context_metrics: ContextMetrics
    source: str  # 'websocket' or 'livekit_agent'

class MetricsService:
    """Centralized metrics collection and storage"""
    
    def __init__(self, log_dir: str = "logs/metrics"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = 7
        
        # Current day's log file
        self._current_log_file = None
        self._current_date = None
        self._ensure_log_file()
        
        # In-memory cache for dashboard (last 1000 events)
        self._recent_events: List[MetricsEvent] = []
        self._max_cache_size = 1000
        
        logger.info(f"📊 MetricsService initialized - logging to {self.log_dir}")

    def _ensure_log_file(self) -> Path:
        """Ensure we have the correct log file for today"""
        today = datetime.now().date()
        
        if self._current_date != today:
            self._current_date = today
            self._current_log_file = self.log_dir / f"metrics_{today.isoformat()}.jsonl"
            logger.info(f"📊 Metrics logging to: {self._current_log_file}")
            
        return self._current_log_file

    async def log_event(self, 
                       session_id: str,
                       character: str,
                       tts_model: str,
                       pipeline_metrics: PipelineMetrics,
                       quality_metrics: QualityMetrics,
                       context_metrics: ContextMetrics,
                       source: str = "websocket") -> None:
        """Log a metrics event asynchronously"""
        
        try:
            event = MetricsEvent(
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                character=character,
                tts_model=tts_model,
                pipeline_metrics=pipeline_metrics,
                quality_metrics=quality_metrics,
                context_metrics=context_metrics,
                source=source
            )
            
            # Add to in-memory cache for dashboard
            self._recent_events.append(event)
            if len(self._recent_events) > self._max_cache_size:
                self._recent_events.pop(0)
            
            # Write to JSON log file (async to avoid blocking)
            await self._write_event_async(event)
            
        except Exception as e:
            logger.error(f"📊 Failed to log metrics event: {e}")

    async def _write_event_async(self, event: MetricsEvent) -> None:
        """Write event to JSON log file asynchronously"""
        def write_to_file():
            log_file = self._ensure_log_file()
            with open(log_file, 'a') as f:
                json.dump(asdict(event), f, separators=(',', ':'))
                f.write('\n')
        
        # Run file I/O in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, write_to_file)

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events for dashboard"""
        recent = self._recent_events[-limit:] if len(self._recent_events) > limit else self._recent_events
        return [asdict(event) for event in reversed(recent)]  # Most recent first

    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance summary for dashboard"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter recent events
        recent_events = []
        for event in self._recent_events:
            event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00').replace('+00:00', ''))
            if event_time >= cutoff_time:
                recent_events.append(event)
        
        if not recent_events:
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "stage_breakdown": {},
                "character_performance": {}
            }

        # Calculate metrics
        total_requests = len(recent_events)
        successful_requests = [e for e in recent_events if e.quality_metrics.success]
        success_rate = len(successful_requests) / total_requests if total_requests > 0 else 0

        if successful_requests:
            # Average latencies
            avg_latency = sum(e.pipeline_metrics.total_latency_ms for e in successful_requests) / len(successful_requests)
            
            # Stage breakdown
            stt_times = [e.pipeline_metrics.stt_latency_ms for e in successful_requests if e.pipeline_metrics.stt_latency_ms]
            llm_times = [e.pipeline_metrics.llm_latency_ms for e in successful_requests if e.pipeline_metrics.llm_latency_ms]
            tts_times = [e.pipeline_metrics.tts_first_chunk_ms for e in successful_requests if e.pipeline_metrics.tts_first_chunk_ms]
            
            stage_breakdown = {
                "stt_avg_ms": sum(stt_times) / len(stt_times) if stt_times else 0,
                "llm_avg_ms": sum(llm_times) / len(llm_times) if llm_times else 0,
                "tts_avg_ms": sum(tts_times) / len(tts_times) if tts_times else 0
            }
            
            # Character performance
            character_perf = {}
            for char in ["adina", "raffa"]:
                char_events = [e for e in successful_requests if e.character == char]
                if char_events:
                    char_avg = sum(e.pipeline_metrics.total_latency_ms for e in char_events) / len(char_events)
                    character_perf[char] = {
                        "avg_latency_ms": char_avg,
                        "requests": len(char_events)
                    }
        else:
            avg_latency = 0
            stage_breakdown = {}
            character_perf = {}

        return {
            "total_requests": total_requests,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "stage_breakdown": stage_breakdown,
            "character_performance": character_perf,
            "time_period_hours": hours
        }

    async def cleanup_old_logs(self) -> None:
        """Remove log files older than retention_days"""
        try:
            cutoff_date = datetime.now().date() - timedelta(days=self.retention_days)
            
            for log_file in self.log_dir.glob("metrics_*.jsonl"):
                try:
                    # Extract date from filename
                    date_str = log_file.stem.replace("metrics_", "")
                    file_date = datetime.fromisoformat(date_str).date()
                    
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info(f"📊 Cleaned up old metrics file: {log_file}")
                        
                except Exception as e:
                    logger.warning(f"📊 Could not parse date from metrics file {log_file}: {e}")
                    
        except Exception as e:
            logger.error(f"📊 Error during metrics cleanup: {e}")

# Global metrics service instance
_metrics_service: Optional[MetricsService] = None

def get_metrics_service() -> MetricsService:
    """Get or create the global metrics service instance"""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000

def timing_context(name: str) -> TimingContext:
    """Create a timing context for measuring operation duration"""
    return TimingContext(name) 