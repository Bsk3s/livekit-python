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
    """
    🚀 ZERO-LATENCY METRICS SYSTEM
    
    Production-grade metrics with fire-and-forget async queue pattern.
    Voice pipeline drops metrics and continues - zero latency impact.
    Background worker processes queue independently.
    """
    
    def __init__(self, log_dir: str = "logs/metrics"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = 7
        
        # 🚀 ZERO-LATENCY: Fire-and-forget async queue
        self._metrics_queue = asyncio.Queue(maxsize=10000)  # Large buffer for burst traffic
        self._processing_task = None
        self._running = False
        
        # In-memory cache for instant dashboard reads (thread-safe)
        self._recent_events: List[Dict[str, Any]] = []
        self._max_cache_size = 1000
        self._cache_lock = asyncio.Lock()
        
        # Performance counters (atomic operations)
        self._stats = {
            "events_queued": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "queue_full_count": 0
        }
        
        logger.info(f"📊 Zero-Latency MetricsService initialized - logging to {self.log_dir}")
        
        # Start background processing immediately
        self._start_background_processor()

    def _start_background_processor(self):
        """Start the background metrics processing task"""
        if self._processing_task and not self._processing_task.done():
            return
            
        self._running = True
        self._processing_task = asyncio.create_task(self._process_metrics_queue())
        logger.info("📊 Background metrics processor started")

    async def _process_metrics_queue(self):
        """Background task that processes metrics queue with zero voice impact"""
        current_date = None
        current_log_file = None
        
        while self._running:
            try:
                # Get batch of events (non-blocking with timeout)
                events_batch = []
                
                try:
                    # Get first event (wait up to 1 second)
                    event = await asyncio.wait_for(self._metrics_queue.get(), timeout=1.0)
                    events_batch.append(event)
                    
                    # Collect additional events if available (non-blocking)
                    while len(events_batch) < 50:  # Process in batches up to 50
                        try:
                            event = self._metrics_queue.get_nowait()
                            events_batch.append(event)
                        except asyncio.QueueEmpty:
                            break
                            
                except asyncio.TimeoutError:
                    # No events to process, continue loop
                    continue
                
                # Process batch of events
                if events_batch:
                    await self._process_events_batch(events_batch)
                    
            except Exception as e:
                logger.error(f"📊 Background metrics processor error: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    async def _process_events_batch(self, events: List[Dict[str, Any]]):
        """Process a batch of metrics events (runs in background)"""
        try:
            # Ensure log file for today
            today = datetime.now().date()
            log_file = self.log_dir / f"metrics_{today.isoformat()}.jsonl"
            
            # Write batch to file (async I/O)
            def write_batch():
                with open(log_file, 'a') as f:
                    for event in events:
                        json.dump(event, f, separators=(',', ':'))
                        f.write('\n')
            
            # Run file I/O in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, write_batch)
            
            # Update in-memory cache (thread-safe)
            async with self._cache_lock:
                self._recent_events.extend(events)
                
                # Trim cache if too large
                if len(self._recent_events) > self._max_cache_size:
                    trim_count = len(self._recent_events) - self._max_cache_size
                    self._recent_events = self._recent_events[trim_count:]
            
            # Update stats
            self._stats["events_processed"] += len(events)
            
            # Mark queue tasks as done
            for _ in events:
                self._metrics_queue.task_done()
            
        except Exception as e:
            logger.error(f"📊 Error processing metrics batch: {e}")

    def log_event(self, event_data: Dict[str, Any]) -> None:
        """
        🚀 ZERO-LATENCY: Drop metrics event in queue and return immediately.
        
        This is called from the voice pipeline and MUST NOT block.
        If queue is full, drop the event to preserve voice quality.
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in event_data:
                event_data['timestamp'] = datetime.now().isoformat()
            
            # Try to add to queue (non-blocking)
            try:
                self._metrics_queue.put_nowait(event_data)
                self._stats["events_queued"] += 1
            except asyncio.QueueFull:
                # Queue full - drop event to preserve voice latency
                self._stats["events_dropped"] += 1
                self._stats["queue_full_count"] += 1
                # Don't log error - would add latency
                pass
                
        except Exception:
            # Silent failure to preserve voice latency
            # Any error here should not impact voice processing
            pass

    async def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events for dashboard (thread-safe)"""
        async with self._cache_lock:
            recent = self._recent_events[-limit:] if len(self._recent_events) > limit else self._recent_events
            return list(reversed(recent))  # Most recent first

    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance summary for dashboard (non-blocking)"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Filter recent events (no async - read from cache snapshot)
            recent_events = []
            cache_snapshot = self._recent_events.copy()  # Atomic copy
            
            for event in cache_snapshot:
                try:
                    event_time = datetime.fromisoformat(event.get('timestamp', ''))
                    if event_time >= cutoff_time:
                        recent_events.append(event)
                except (ValueError, TypeError):
                    continue
            
            if not recent_events:
                return {
                    "total_requests": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "stage_breakdown": {
                        "stt_avg_ms": 0,
                        "llm_avg_ms": 0,
                        "tts_avg_ms": 0
                    },
                    "character_performance": {
                        "adina": {"avg_latency_ms": 0, "requests": 0},
                        "raffa": {"avg_latency_ms": 0, "requests": 0}
                    },
                    "system_stats": self._stats.copy()
                }

            # Calculate metrics from cache data
            total_requests = len(recent_events)
            successful_requests = []
            
            for event in recent_events:
                quality_metrics = event.get('quality_metrics', {})
                if isinstance(quality_metrics, dict) and quality_metrics.get('success', False):
                    successful_requests.append(event)
            
            success_rate = len(successful_requests) / total_requests if total_requests > 0 else 0

            if successful_requests:
                # Calculate average latencies
                latencies = []
                stt_times = []
                llm_times = []
                tts_times = []
                
                for event in successful_requests:
                    pipeline = event.get('pipeline_metrics', {})
                    if isinstance(pipeline, dict):
                        total_latency = pipeline.get('total_latency_ms', 0)
                        if total_latency > 0:
                            latencies.append(total_latency)
                        
                        stt_latency = pipeline.get('stt_latency_ms')
                        if stt_latency and stt_latency > 0:
                            stt_times.append(stt_latency)
                            
                        llm_latency = pipeline.get('llm_latency_ms')
                        if llm_latency and llm_latency > 0:
                            llm_times.append(llm_latency)
                            
                        tts_latency = pipeline.get('tts_first_chunk_ms')
                        if tts_latency and tts_latency > 0:
                            tts_times.append(tts_latency)
                
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                
                stage_breakdown = {
                    "stt_avg_ms": sum(stt_times) / len(stt_times) if stt_times else 0,
                    "llm_avg_ms": sum(llm_times) / len(llm_times) if llm_times else 0,
                    "tts_avg_ms": sum(tts_times) / len(tts_times) if tts_times else 0
                }
                
                # Character performance
                character_perf = {}
                for char in ["adina", "raffa"]:
                    char_events = [e for e in successful_requests if e.get('character') == char]
                    if char_events:
                        char_latencies = []
                        for e in char_events:
                            pipeline = e.get('pipeline_metrics', {})
                            if isinstance(pipeline, dict):
                                lat = pipeline.get('total_latency_ms', 0)
                                if lat > 0:
                                    char_latencies.append(lat)
                        
                        char_avg = sum(char_latencies) / len(char_latencies) if char_latencies else 0
                        character_perf[char] = {
                            "avg_latency_ms": char_avg,
                            "requests": len(char_events)
                        }
                    else:
                        character_perf[char] = {"avg_latency_ms": 0, "requests": 0}
            else:
                avg_latency = 0
                stage_breakdown = {"stt_avg_ms": 0, "llm_avg_ms": 0, "tts_avg_ms": 0}
                character_perf = {
                    "adina": {"avg_latency_ms": 0, "requests": 0},
                    "raffa": {"avg_latency_ms": 0, "requests": 0}
                }

            # 🚀 PHASE 2C: Calculate streaming-specific metrics
            streaming_metrics = self._calculate_streaming_metrics(successful_requests)
            
            return {
                "total_requests": total_requests,
                "success_rate": success_rate,
                "avg_latency_ms": avg_latency,
                "stage_breakdown": stage_breakdown,
                "character_performance": character_perf,
                "streaming_metrics": streaming_metrics,
                "system_stats": self._stats.copy()
            }
            
        except Exception as e:
            logger.error(f"📊 Error generating performance summary: {e}")
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "stage_breakdown": {"stt_avg_ms": 0, "llm_avg_ms": 0, "tts_avg_ms": 0},
                "character_performance": {"adina": {"avg_latency_ms": 0, "requests": 0}, "raffa": {"avg_latency_ms": 0, "requests": 0}},
                "streaming_metrics": {"first_token_avg_ms": 0, "streaming_usage_pct": 0, "parallel_tts_chunks_avg": 0, "early_trigger_success_pct": 0},
                "system_stats": self._stats.copy()
            }
    
    def _calculate_streaming_metrics(self, successful_requests: list) -> dict:
        """
        🚀 PHASE 2C: Calculate streaming-specific performance metrics
        """
        try:
            if not successful_requests:
                return {
                    "first_token_avg_ms": 0,
                    "streaming_usage_pct": 0.0,
                    "parallel_tts_chunks_avg": 0.0,
                    "early_trigger_success_pct": 0.0
                }
            
            # Extract streaming metrics from events
            first_token_latencies = []
            streaming_mode_count = 0
            parallel_tts_chunks = []
            early_trigger_count = 0
            
            for event in successful_requests:
                pipeline_metrics = event.get('pipeline_metrics', {})
                if isinstance(pipeline_metrics, dict):
                    # First token latency (Phase 2C streaming)
                    first_token_ms = pipeline_metrics.get('llm_first_token_ms', 0)
                    if first_token_ms > 0:
                        first_token_latencies.append(first_token_ms)
                        streaming_mode_count += 1
                    
                    # TTS first chunk latency (indicates streaming)
                    tts_first_chunk = pipeline_metrics.get('tts_first_chunk_ms', 0)
                    if tts_first_chunk > 0:
                        parallel_tts_chunks.append(1)  # At least one chunk processed
                
                # Count early trigger events (Progressive streaming)
                context_metrics = event.get('context_metrics', {})
                if isinstance(context_metrics, dict):
                    early_trigger = context_metrics.get('early_trigger_used', False)
                    if early_trigger:
                        early_trigger_count += 1
            
            # Calculate averages
            first_token_avg = sum(first_token_latencies) / len(first_token_latencies) if first_token_latencies else 0
            streaming_usage_pct = (streaming_mode_count / len(successful_requests)) * 100 if successful_requests else 0
            parallel_tts_avg = sum(parallel_tts_chunks) / len(parallel_tts_chunks) if parallel_tts_chunks else 0
            early_trigger_success_pct = (early_trigger_count / len(successful_requests)) * 100 if successful_requests else 0
            
            return {
                "first_token_avg_ms": round(first_token_avg, 1),
                "streaming_usage_pct": round(streaming_usage_pct, 1),
                "parallel_tts_chunks_avg": round(parallel_tts_avg, 1),
                "early_trigger_success_pct": round(early_trigger_success_pct, 1)
            }
            
        except Exception as e:
            logger.warning(f"Error calculating streaming metrics: {e}")
            return {
                "first_token_avg_ms": 0,
                "streaming_usage_pct": 0.0,
                "parallel_tts_chunks_avg": 0.0,
                "early_trigger_success_pct": 0.0
            }

    async def cleanup(self):
        """Clean shutdown of background processor"""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("📊 Metrics service shutdown complete")

# Global singleton instance
_metrics_service: Optional[MetricsService] = None

def get_metrics_service() -> MetricsService:
    """Get or create the global metrics service instance"""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service

async def cleanup_metrics():
    """Clean shutdown of metrics service"""
    global _metrics_service
    if _metrics_service:
        await _metrics_service.cleanup()
        _metrics_service = None 