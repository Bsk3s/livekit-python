"""
Performance Metrics Service for Voice AI Dashboard
================================================

Tracks latency breakdown, response times, and performance analytics
specifically designed for the voice AI dashboard components.
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class LatencyBreakdown:
    """Latency breakdown for voice pipeline."""
    timestamp: str
    total: float  # Total response time in ms
    stt: float    # Speech-to-text processing time
    llm: float    # LLM response generation time  
    tts: float    # Text-to-speech generation time
    network: float # Network delay


@dataclass
class PerformanceMetrics:
    """Current performance metrics."""
    current_latency: float
    breakdown: Dict[str, float]  # stt, llm, tts, network
    status: str  # "good", "warning", "critical"
    
    
class PerformanceTracker:
    """
    Tracks voice pipeline performance metrics for dashboard.
    
    Monitors:
    - End-to-end conversation latency
    - Component breakdown (STT, LLM, TTS, Network)
    - Performance status and alerts
    """
    
    def __init__(self):
        self.latency_history: List[LatencyBreakdown] = []
        self.current_metrics: Optional[PerformanceMetrics] = None
        
        # Performance thresholds (ms)
        self.thresholds = {
            "good": 500,      # < 500ms = good
            "warning": 1000,  # 500-1000ms = warning  
            "critical": 1000  # > 1000ms = critical
        }
        
    async def start_conversation_timing(self) -> str:
        """Start timing a new conversation. Returns conversation_id."""
        conversation_id = f"conv_{int(time.time() * 1000)}"
        # Store start time for this conversation
        setattr(self, f"_start_{conversation_id}", time.time())
        return conversation_id
        
    async def record_stt_latency(self, conversation_id: str, latency_ms: float):
        """Record STT processing latency."""
        setattr(self, f"_stt_{conversation_id}", latency_ms)
        
    async def record_llm_latency(self, conversation_id: str, latency_ms: float):
        """Record LLM response latency."""
        setattr(self, f"_llm_{conversation_id}", latency_ms)
        
    async def record_tts_latency(self, conversation_id: str, latency_ms: float):
        """Record TTS generation latency."""
        setattr(self, f"_tts_{conversation_id}", latency_ms)
        
    async def complete_conversation_timing(self, conversation_id: str) -> LatencyBreakdown:
        """Complete timing and calculate total latency breakdown."""
        try:
            start_time = getattr(self, f"_start_{conversation_id}", time.time())
            total_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Get component latencies (fallback to estimates if not recorded)
            stt_latency = getattr(self, f"_stt_{conversation_id}", total_time * 0.15)
            llm_latency = getattr(self, f"_llm_{conversation_id}", total_time * 0.60)
            tts_latency = getattr(self, f"_tts_{conversation_id}", total_time * 0.20)
            network_latency = total_time - (stt_latency + llm_latency + tts_latency)
            
            # Ensure network latency is positive
            if network_latency < 0:
                network_latency = total_time * 0.05
                # Adjust other components proportionally
                remaining = total_time - network_latency
                stt_latency = remaining * 0.15
                llm_latency = remaining * 0.60
                tts_latency = remaining * 0.25
            
            breakdown = LatencyBreakdown(
                timestamp=datetime.now().isoformat(),
                total=total_time,
                stt=stt_latency,
                llm=llm_latency,
                tts=tts_latency,
                network=network_latency
            )
            
            # Add to history
            self.latency_history.append(breakdown)
            
            # Keep only last 30 data points
            if len(self.latency_history) > 30:
                self.latency_history = self.latency_history[-30:]
                
            # Update current metrics
            await self._update_current_metrics(breakdown)
            
            # Cleanup temporary data
            self._cleanup_conversation_data(conversation_id)
            
            return breakdown
            
        except Exception as e:
            logger.error(f"❌ Error completing conversation timing: {e}")
            # Return default breakdown
            return LatencyBreakdown(
                timestamp=datetime.now().isoformat(),
                total=500.0,
                stt=75.0,
                llm=300.0,
                tts=100.0,
                network=25.0
            )
    
    def _cleanup_conversation_data(self, conversation_id: str):
        """Clean up temporary conversation timing data."""
        attrs_to_remove = [
            f"_start_{conversation_id}",
            f"_stt_{conversation_id}",
            f"_llm_{conversation_id}",
            f"_tts_{conversation_id}"
        ]
        
        for attr in attrs_to_remove:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
                
    async def _update_current_metrics(self, breakdown: LatencyBreakdown):
        """Update current performance metrics."""
        # Determine status based on total latency
        if breakdown.total < self.thresholds["good"]:
            status = "good"
        elif breakdown.total < self.thresholds["warning"]:
            status = "warning"
        else:
            status = "critical"
            
        self.current_metrics = PerformanceMetrics(
            current_latency=breakdown.total,
            breakdown={
                "stt": breakdown.stt,
                "llm": breakdown.llm,
                "tts": breakdown.tts,
                "network": breakdown.network
            },
            status=status
        )
    
    async def get_current_performance(self) -> PerformanceMetrics:
        """Get current performance metrics for dashboard."""
        if not self.current_metrics:
            # Generate sample data if no real data available
            await self._generate_sample_metrics()
            
        return self.current_metrics
    
    async def get_latency_history(self, limit: int = 30) -> List[LatencyBreakdown]:
        """Get recent latency history for dashboard charts."""
        return self.latency_history[-limit:]
    
    async def _generate_sample_metrics(self):
        """Generate sample metrics for dashboard testing."""
        # Simulate realistic latency breakdown
        total_latency = 450.0  # Good performance
        
        breakdown = LatencyBreakdown(
            timestamp=datetime.now().isoformat(),
            total=total_latency,
            stt=total_latency * 0.15,  # ~68ms
            llm=total_latency * 0.60,  # ~270ms  
            tts=total_latency * 0.20,  # ~90ms
            network=total_latency * 0.05  # ~22ms
        )
        
        self.latency_history.append(breakdown)
        await self._update_current_metrics(breakdown)
    
    async def get_performance_stats(self) -> Dict:
        """Get performance statistics for analytics."""
        if not self.latency_history:
            return {
                "avg_latency": 0,
                "min_latency": 0,
                "max_latency": 0,
                "p95_latency": 0,
                "total_conversations": 0
            }
        
        latencies = [b.total for b in self.latency_history]
        
        return {
            "avg_latency": statistics.mean(latencies),
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "p95_latency": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            "total_conversations": len(self.latency_history)
        }


# Singleton performance tracker
_performance_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    global _performance_tracker
    
    if not _performance_tracker:
        _performance_tracker = PerformanceTracker()
    
    return _performance_tracker


# Convenience functions for easy integration
async def start_timing() -> str:
    """Start timing a new conversation."""
    tracker = get_performance_tracker()
    return await tracker.start_conversation_timing()


async def record_stt_time(conversation_id: str, latency_ms: float):
    """Record STT processing time."""
    tracker = get_performance_tracker()
    await tracker.record_stt_latency(conversation_id, latency_ms)


async def record_llm_time(conversation_id: str, latency_ms: float):
    """Record LLM response time."""
    tracker = get_performance_tracker()
    await tracker.record_llm_latency(conversation_id, latency_ms)


async def record_tts_time(conversation_id: str, latency_ms: float):
    """Record TTS generation time."""
    tracker = get_performance_tracker()
    await tracker.record_tts_latency(conversation_id, latency_ms)


async def complete_timing(conversation_id: str) -> LatencyBreakdown:
    """Complete conversation timing and get breakdown."""
    tracker = get_performance_tracker()
    return await tracker.complete_conversation_timing(conversation_id)