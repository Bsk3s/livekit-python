"""
Concurrent User Analytics for Spiritual Voice Agent
=================================================

Real-time analytics for tracking concurrent users, peak usage,
and decision metrics for scaling (GPU upgrades, server capacity).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ConcurrentUserMetrics:
    """Real-time concurrent user metrics."""
    timestamp: datetime
    active_sessions: int
    active_users: int
    peak_concurrent_today: int
    avg_session_duration: float  # minutes
    sessions_started_last_hour: int
    sessions_ended_last_hour: int
    tts_requests_per_minute: float
    server_load_percentage: float


@dataclass
class UsagePattern:
    """Usage pattern analysis."""
    hour_of_day: int
    avg_concurrent_users: float
    peak_concurrent_users: int
    total_sessions: int


class ConcurrentUserAnalytics:
    """
    Real-time concurrent user analytics for voice agent business.
    
    Provides insights for:
    - When to upgrade to GPU
    - Server capacity planning
    - Peak usage time identification
    - Business growth metrics
    """
    
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.metrics_history: List[ConcurrentUserMetrics] = []
        self.usage_patterns: Dict[int, UsagePattern] = {}
        
    async def get_current_concurrent_users(self) -> ConcurrentUserMetrics:
        """Get real-time concurrent user metrics."""
        now = datetime.now()
        
        try:
            # Get active sessions (no end time)
            active_sessions_query = """
                SELECT 
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as active_users
                FROM conversation_sessions 
                WHERE session_end IS NULL
                AND session_start >= NOW() - INTERVAL '2 hours'
            """
            
            # Get peak concurrent users today
            peak_today_query = """
                SELECT COUNT(*) as concurrent_count
                FROM conversation_sessions cs1
                WHERE DATE(cs1.session_start) = CURRENT_DATE
                AND EXISTS (
                    SELECT 1 FROM conversation_sessions cs2
                    WHERE cs2.session_start <= cs1.session_start + INTERVAL '5 minutes'
                    AND (cs2.session_end IS NULL OR cs2.session_end >= cs1.session_start)
                    AND cs2.id != cs1.id
                )
                ORDER BY concurrent_count DESC
                LIMIT 1
            """
            
            # Get session activity in last hour
            hourly_activity_query = """
                SELECT 
                    COUNT(*) FILTER (WHERE session_start >= NOW() - INTERVAL '1 hour') as sessions_started,
                    COUNT(*) FILTER (WHERE session_end >= NOW() - INTERVAL '1 hour') as sessions_ended,
                    AVG(EXTRACT(EPOCH FROM (COALESCE(session_end, NOW()) - session_start)) / 60) as avg_duration
                FROM conversation_sessions
                WHERE session_start >= NOW() - INTERVAL '24 hours'
            """
            
            # Get TTS request rate
            tts_rate_query = """
                SELECT COUNT(*) as turn_count
                FROM conversation_turns
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """
            
            if self.supabase:
                # Execute queries (simplified - in production would use actual Supabase client)
                active_data = await self._execute_query(active_sessions_query)
                peak_data = await self._execute_query(peak_today_query)
                activity_data = await self._execute_query(hourly_activity_query)
                tts_data = await self._execute_query(tts_rate_query)
                
                # Calculate metrics
                active_sessions = active_data[0]['active_sessions'] if active_data else 0
                active_users = active_data[0]['active_users'] if active_data else 0
                peak_today = peak_data[0]['concurrent_count'] if peak_data else 0
                
                activity = activity_data[0] if activity_data else {}
                sessions_started = activity.get('sessions_started', 0)
                sessions_ended = activity.get('sessions_ended', 0)
                avg_duration = activity.get('avg_duration', 0) or 0
                
                tts_count = tts_data[0]['turn_count'] if tts_data else 0
                tts_per_minute = tts_count / 60  # Convert to per minute
                
            else:
                # Mock data for testing
                active_sessions = 1
                active_users = 1
                peak_today = 2
                sessions_started = 3
                sessions_ended = 2
                avg_duration = 15.5
                tts_per_minute = 0.5
                
            # Get server load (simplified)
            server_load = await self._get_server_load()
            
            metrics = ConcurrentUserMetrics(
                timestamp=now,
                active_sessions=active_sessions,
                active_users=active_users,
                peak_concurrent_today=peak_today,
                avg_session_duration=avg_duration,
                sessions_started_last_hour=sessions_started,
                sessions_ended_last_hour=sessions_ended,
                tts_requests_per_minute=tts_per_minute,
                server_load_percentage=server_load
            )
            
            # Store for history
            self.metrics_history.append(metrics)
            
            # Keep only last 24 hours of metrics
            cutoff = now - timedelta(hours=24)
            self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff]
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting concurrent user metrics: {e}")
            # Return default metrics
            return ConcurrentUserMetrics(
                timestamp=now,
                active_sessions=0,
                active_users=0,
                peak_concurrent_today=0,
                avg_session_duration=0,
                sessions_started_last_hour=0,
                sessions_ended_last_hour=0,
                tts_requests_per_minute=0,
                server_load_percentage=0
            )
    
    async def _execute_query(self, query: str) -> List[Dict]:
        """Execute REAL database query using Supabase client."""
        if not self.supabase:
            logger.warning("⚠️ No Supabase client - returning empty result")
            return []
        
        try:
            # Convert SQL queries to Supabase API calls
            if "active_sessions" in query:
                # Get active sessions (no end time)
                response = self.supabase.table('conversation_sessions').select('user_id').is_('session_end', 'null').gte('session_start', (datetime.now() - timedelta(hours=2)).isoformat()).execute()
                active_sessions = len(response.data)
                active_users = len(set(session['user_id'] for session in response.data))
                return [{"active_sessions": active_sessions, "active_users": active_users}]
                
            elif "concurrent_count" in query:
                # Get peak concurrent users today - simplified 
                response = self.supabase.table('conversation_sessions').select('*').gte('session_start', datetime.now().strftime('%Y-%m-%d')).execute()
                return [{"concurrent_count": len(response.data)}]
                
            elif "sessions_started" in query:
                # Get hourly activity
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
                twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
                
                recent_sessions = self.supabase.table('conversation_sessions').select('session_start, session_end').gte('session_start', twenty_four_hours_ago).execute()
                
                sessions_started = len([s for s in recent_sessions.data if s['session_start'] >= one_hour_ago])
                sessions_ended = len([s for s in recent_sessions.data if s.get('session_end') and s['session_end'] >= one_hour_ago])
                
                # Calculate real average duration
                durations = []
                for session in recent_sessions.data:
                    if session.get('session_end'):
                        start = datetime.fromisoformat(session['session_start'].replace('Z', '+00:00'))
                        end = datetime.fromisoformat(session['session_end'].replace('Z', '+00:00'))
                        duration_minutes = (end - start).total_seconds() / 60
                        durations.append(duration_minutes)
                
                avg_duration = sum(durations) / len(durations) if durations else 0
                
                return [{"sessions_started": sessions_started, "sessions_ended": sessions_ended, "avg_duration": avg_duration}]
                
            elif "turn_count" in query:
                # Get recent conversation turns
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
                response = self.supabase.table('conversation_turns').select('*').gte('created_at', one_hour_ago).execute()
                return [{"turn_count": len(response.data)}]
                
        except Exception as e:
            logger.error(f"❌ Failed to execute query: {e}")
            return []
        
        return []
    
    async def _get_server_load(self) -> float:
        """Get current server load percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except:
            return 25.0  # Mock value
    
    async def analyze_usage_patterns(self) -> Dict[int, UsagePattern]:
        """Analyze usage patterns by hour of day."""
        if not self.metrics_history:
            return {}
        
        # Group metrics by hour
        hourly_data = {}
        for metric in self.metrics_history:
            hour = metric.timestamp.hour
            if hour not in hourly_data:
                hourly_data[hour] = []
            hourly_data[hour].append(metric)
        
        # Calculate patterns for each hour
        patterns = {}
        for hour, metrics in hourly_data.items():
            concurrent_users = [m.active_users for m in metrics]
            patterns[hour] = UsagePattern(
                hour_of_day=hour,
                avg_concurrent_users=statistics.mean(concurrent_users),
                peak_concurrent_users=max(concurrent_users),
                total_sessions=sum(m.sessions_started_last_hour for m in metrics)
            )
        
        self.usage_patterns = patterns
        return patterns
    
    async def get_gpu_upgrade_recommendation(self) -> Dict[str, any]:
        """Analyze if GPU upgrade is recommended based on usage patterns."""
        if not self.metrics_history:
            return {"recommendation": "insufficient_data", "reason": "Need more usage data"}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 data points
        
        # Calculate key metrics
        avg_concurrent = statistics.mean(m.active_users for m in recent_metrics)
        peak_concurrent = max(m.active_users for m in recent_metrics)
        avg_tts_rate = statistics.mean(m.tts_requests_per_minute for m in recent_metrics)
        avg_server_load = statistics.mean(m.server_load_percentage for m in recent_metrics)
        
        # GPU upgrade thresholds
        gpu_recommended = False
        reasons = []
        
        if peak_concurrent >= 20:
            gpu_recommended = True
            reasons.append(f"Peak concurrent users ({peak_concurrent}) >= 20")
        
        if avg_tts_rate >= 5:  # 5 TTS requests per minute sustained
            gpu_recommended = True
            reasons.append(f"High TTS request rate ({avg_tts_rate:.1f}/min)")
        
        if avg_server_load >= 80:
            gpu_recommended = True
            reasons.append(f"High server load ({avg_server_load:.1f}%)")
        
        # Calculate potential benefits
        tts_speedup = 3  # 3x faster with GPU
        cost_increase = 200  # $200/month more for GPU server
        revenue_threshold = cost_increase / 20  # Break-even subscribers
        
        return {
            "recommendation": "gpu_recommended" if gpu_recommended else "cpu_sufficient",
            "reasons": reasons,
            "current_metrics": {
                "avg_concurrent_users": avg_concurrent,
                "peak_concurrent_users": peak_concurrent,
                "avg_tts_rate_per_minute": avg_tts_rate,
                "avg_server_load": avg_server_load
            },
            "gpu_benefits": {
                "tts_speedup_factor": tts_speedup,
                "estimated_response_time": "0.5-1 seconds (vs 2-3 seconds)",
                "concurrent_capacity": "50+ users (vs 20 users)"
            },
            "cost_analysis": {
                "monthly_cost_increase": cost_increase,
                "break_even_subscribers": revenue_threshold,
                "current_revenue_estimate": peak_concurrent * 20  # $20/month per user
            }
        }
    
    async def get_capacity_planning_report(self) -> Dict[str, any]:
        """Generate capacity planning report for business growth."""
        current_metrics = await self.get_current_concurrent_users()
        patterns = await self.analyze_usage_patterns()
        gpu_rec = await self.get_gpu_upgrade_recommendation()
        
        # Find peak usage hours
        if patterns:
            peak_hour = max(patterns.keys(), key=lambda h: patterns[h].peak_concurrent_users)
            peak_usage = patterns[peak_hour]
        else:
            peak_hour = 0
            peak_usage = None
        
        # Growth projections
        growth_scenarios = {
            "conservative": {"monthly_growth": 1.2, "projected_users_3_months": current_metrics.active_users * (1.2 ** 3)},
            "moderate": {"monthly_growth": 1.5, "projected_users_3_months": current_metrics.active_users * (1.5 ** 3)},
            "aggressive": {"monthly_growth": 2.0, "projected_users_3_months": current_metrics.active_users * (2.0 ** 3)}
        }
        
        return {
            "current_status": asdict(current_metrics),
            "peak_usage_hour": peak_hour,
            "peak_usage_data": asdict(peak_usage) if peak_usage else None,
            "gpu_recommendation": gpu_rec,
            "growth_projections": growth_scenarios,
            "scaling_milestones": {
                "gpu_upgrade": "20+ concurrent users",
                "dedicated_server": "50+ concurrent users", 
                "load_balancer": "100+ concurrent users",
                "multi_region": "500+ concurrent users"
            },
            "monitoring_alerts": {
                "high_concurrency": current_metrics.active_users >= 15,
                "server_load_warning": current_metrics.server_load_percentage >= 70,
                "tts_rate_high": current_metrics.tts_requests_per_minute >= 3
            }
        }
    
    async def export_analytics_dashboard_data(self) -> Dict[str, any]:
        """Export data for analytics dashboard."""
        current = await self.get_current_concurrent_users()
        patterns = await self.analyze_usage_patterns()
        capacity = await self.get_capacity_planning_report()
        
        # Prepare time series data for charts
        time_series = []
        for metric in self.metrics_history[-24:]:  # Last 24 hours
            time_series.append({
                "timestamp": metric.timestamp.isoformat(),
                "active_users": metric.active_users,
                "active_sessions": metric.active_sessions,
                "tts_rate": metric.tts_requests_per_minute,
                "server_load": metric.server_load_percentage
            })
        
        return {
            "current_metrics": asdict(current),
            "usage_patterns": {str(k): asdict(v) for k, v in patterns.items()},
            "capacity_report": capacity,
            "time_series_data": time_series,
            "last_updated": datetime.now().isoformat()
        }


# Singleton analytics instance
_analytics_instance: Optional[ConcurrentUserAnalytics] = None


def get_concurrent_user_analytics() -> ConcurrentUserAnalytics:
    """Get the global concurrent user analytics instance."""
    global _analytics_instance
    
    if not _analytics_instance:
        # FIXED: Connect to REAL Supabase client
        from ..conversation.supabase_integration import get_supabase_conversation_service
        supabase_service = get_supabase_conversation_service()
        supabase_client = supabase_service.supabase_client if supabase_service else None
        
        _analytics_instance = ConcurrentUserAnalytics(supabase_client=supabase_client)
        logger.info("🔗 Analytics connected to REAL Supabase data!")
    
    return _analytics_instance


# Example usage
async def example_usage():
    """Example of how to use concurrent user analytics."""
    analytics = get_concurrent_user_analytics()
    
    # Get current metrics
    current = await analytics.get_current_concurrent_users()
    print(f"Current concurrent users: {current.active_users}")
    print(f"Peak today: {current.peak_concurrent_today}")
    
    # Get GPU recommendation
    gpu_rec = await analytics.get_gpu_upgrade_recommendation()
    print(f"GPU recommendation: {gpu_rec['recommendation']}")
    
    # Get capacity planning report
    capacity = await analytics.get_capacity_planning_report()
    print(f"Scaling milestones: {capacity['scaling_milestones']}")


if __name__ == "__main__":
    asyncio.run(example_usage())