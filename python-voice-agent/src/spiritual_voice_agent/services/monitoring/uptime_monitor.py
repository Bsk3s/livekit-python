"""
Uptime Monitor

Provides continuous uptime monitoring with external endpoint checks,
service availability tracking, and uptime statistics for SLA reporting.
"""

import asyncio
import aiohttp
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .external_monitoring import get_external_monitoring
from .alerting import get_alerting_service, AlertLevel
from ...config.environment import get_config

logger = logging.getLogger(__name__)


class UptimeStatus(Enum):
    """Uptime status values"""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class UptimeCheck:
    """Configuration for an uptime check"""
    name: str
    url: str
    method: str = "GET"
    timeout_seconds: int = 10
    interval_seconds: int = 60
    expected_status: int = 200
    expected_text: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True


@dataclass
class UptimeResult:
    """Result of an uptime check"""
    check_name: str
    status: UptimeStatus
    response_time_ms: float
    status_code: Optional[int]
    error_message: Optional[str]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_name': self.check_name,
            'status': self.status.value,
            'response_time_ms': self.response_time_ms,
            'status_code': self.status_code,
            'error_message': self.error_message,
            'timestamp': self.timestamp
        }


class UptimeMonitor:
    """
    Uptime monitoring service
    
    Continuously monitors critical endpoints and services to ensure
    availability. Provides uptime statistics, SLA reporting, and
    integrates with alerting for incident response.
    """
    
    def __init__(self):
        self.config = get_config()
        self.checks: List[UptimeCheck] = []
        self.results: List[UptimeResult] = []
        self.max_results = 10000  # Keep last 10k results
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
        # Setup default checks
        self._setup_default_checks()
        
        logger.info(f"⏰ Uptime monitor initialized with {len(self.checks)} checks")
    
    def _setup_default_checks(self):
        """Setup default uptime checks for voice agent services"""
        
        # Main API health check
        self.add_check(UptimeCheck(
            name="api_health",
            url="http://localhost:10000/health",
            interval_seconds=30,
            timeout_seconds=5
        ))
        
        # Kokoro TTS service
        self.add_check(UptimeCheck(
            name="kokoro_tts",
            url="http://localhost:8001/health",
            interval_seconds=60,
            timeout_seconds=10
        ))
        
        # API endpoints
        self.add_check(UptimeCheck(
            name="metrics_endpoint",
            url="http://localhost:10000/api/metrics/summary",
            interval_seconds=120,
            timeout_seconds=15
        ))
        
        # Voice configuration endpoint
        self.add_check(UptimeCheck(
            name="voice_config",
            url="http://localhost:10000/api/voice/characters",
            interval_seconds=180,
            timeout_seconds=10
        ))
        
        # Add external checks if configured
        external_url = getattr(self.config, 'external_health_check_url', None)
        if external_url:
            self.add_check(UptimeCheck(
                name="external_health",
                url=external_url,
                interval_seconds=60,
                timeout_seconds=30
            ))
    
    def add_check(self, check: UptimeCheck):
        """Add new uptime check"""
        self.checks.append(check)
        logger.info(f"📋 Added uptime check: {check.name} -> {check.url}")
    
    def remove_check(self, check_name: str):
        """Remove uptime check by name"""
        self.checks = [check for check in self.checks if check.name != check_name]
        
        # Stop monitoring task if running
        if check_name in self._monitoring_tasks:
            self._monitoring_tasks[check_name].cancel()
            del self._monitoring_tasks[check_name]
        
        logger.info(f"🗑️ Removed uptime check: {check_name}")
    
    async def start_monitoring(self):
        """Start uptime monitoring for all checks"""
        if self._running:
            return
        
        self._running = True
        
        # Initialize HTTP session
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Start monitoring tasks for each check
        for check in self.checks:
            if check.enabled:
                task = asyncio.create_task(self._monitor_check(check))
                self._monitoring_tasks[check.name] = task
        
        logger.info(f"🚀 Started monitoring {len(self._monitoring_tasks)} uptime checks")
    
    async def stop_monitoring(self):
        """Stop uptime monitoring"""
        self._running = False
        
        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)
        
        self._monitoring_tasks.clear()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
            self.session = None
        
        logger.info("🛑 Uptime monitoring stopped")
    
    async def _monitor_check(self, check: UptimeCheck):
        """Monitor a single uptime check"""
        logger.info(f"🔍 Starting uptime monitoring for {check.name}")
        
        while self._running:
            try:
                result = await self._perform_check(check)
                self._store_result(result)
                
                # Check for status changes and alert if needed
                await self._handle_status_change(check, result)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error monitoring {check.name}: {e}")
                
                # Create error result
                error_result = UptimeResult(
                    check_name=check.name,
                    status=UptimeStatus.UNKNOWN,
                    response_time_ms=0,
                    status_code=None,
                    error_message=str(e),
                    timestamp=datetime.now().isoformat()
                )
                self._store_result(error_result)
            
            # Wait for next check
            try:
                await asyncio.sleep(check.interval_seconds)
            except asyncio.CancelledError:
                break
        
        logger.info(f"🏁 Stopped monitoring {check.name}")
    
    async def _perform_check(self, check: UptimeCheck) -> UptimeResult:
        """Perform a single uptime check"""
        start_time = time.time()
        
        try:
            headers = check.headers or {}
            timeout = aiohttp.ClientTimeout(total=check.timeout_seconds)
            
            async with self.session.request(
                method=check.method,
                url=check.url,
                headers=headers,
                timeout=timeout
            ) as response:
                response_time_ms = (time.time() - start_time) * 1000
                
                # Check status code
                if response.status != check.expected_status:
                    return UptimeResult(
                        check_name=check.name,
                        status=UptimeStatus.DOWN,
                        response_time_ms=response_time_ms,
                        status_code=response.status,
                        error_message=f"Expected status {check.expected_status}, got {response.status}",
                        timestamp=datetime.now().isoformat()
                    )
                
                # Check response text if specified
                if check.expected_text:
                    text = await response.text()
                    if check.expected_text not in text:
                        return UptimeResult(
                            check_name=check.name,
                            status=UptimeStatus.DEGRADED,
                            response_time_ms=response_time_ms,
                            status_code=response.status,
                            error_message=f"Expected text '{check.expected_text}' not found in response",
                            timestamp=datetime.now().isoformat()
                        )
                
                # Determine status based on response time
                status = UptimeStatus.UP
                if response_time_ms > 5000:  # 5 seconds
                    status = UptimeStatus.DEGRADED
                
                return UptimeResult(
                    check_name=check.name,
                    status=status,
                    response_time_ms=response_time_ms,
                    status_code=response.status,
                    error_message=None,
                    timestamp=datetime.now().isoformat()
                )
                
        except asyncio.TimeoutError:
            response_time_ms = (time.time() - start_time) * 1000
            return UptimeResult(
                check_name=check.name,
                status=UptimeStatus.DOWN,
                response_time_ms=response_time_ms,
                status_code=None,
                error_message=f"Timeout after {check.timeout_seconds}s",
                timestamp=datetime.now().isoformat()
            )
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return UptimeResult(
                check_name=check.name,
                status=UptimeStatus.DOWN,
                response_time_ms=response_time_ms,
                status_code=None,
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def _store_result(self, result: UptimeResult):
        """Store uptime check result"""
        self.results.append(result)
        
        # Trim results if too many
        if len(self.results) > self.max_results:
            self.results = self.results[-self.max_results:]
        
        # Log significant events
        if result.status == UptimeStatus.DOWN:
            logger.warning(f"🔴 {result.check_name} is DOWN: {result.error_message}")
        elif result.status == UptimeStatus.DEGRADED:
            logger.warning(f"🟡 {result.check_name} is DEGRADED: {result.response_time_ms:.0f}ms")
    
    async def _handle_status_change(self, check: UptimeCheck, result: UptimeResult):
        """Handle status changes and trigger alerts"""
        # Get previous results for this check
        previous_results = [r for r in self.results[-10:] if r.check_name == check.name]
        
        if len(previous_results) < 2:
            return  # Need at least 2 results to detect change
        
        previous_status = previous_results[-2].status
        current_status = result.status
        
        # Detect status changes
        if previous_status != current_status:
            logger.info(f"🔄 {check.name} status changed: {previous_status.value} -> {current_status.value}")
            
            # Send external monitoring event
            external_monitoring = get_external_monitoring()
            await external_monitoring.send_event({
                'timestamp': result.timestamp,
                'event_type': 'uptime_status_change',
                'source': 'uptime_monitor',
                'level': 'warning' if current_status != UptimeStatus.UP else 'info',
                'message': f"{check.name} status changed from {previous_status.value} to {current_status.value}",
                'data': result.to_dict(),
                'tags': {
                    'check_name': check.name,
                    'previous_status': previous_status.value,
                    'current_status': current_status.value
                }
            })
            
            # Trigger alert for degraded/down status
            if current_status in [UptimeStatus.DOWN, UptimeStatus.DEGRADED]:
                alerting = get_alerting_service()
                await alerting._trigger_alert(
                    rule_name=f"uptime_{check.name}",
                    level=AlertLevel.CRITICAL if current_status == UptimeStatus.DOWN else AlertLevel.WARNING,
                    message=f"{check.name} is {current_status.value}: {result.error_message or 'No error message'}",
                    details=result.to_dict()
                )
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current status of all checks"""
        status = {}
        
        for check in self.checks:
            if not check.enabled:
                continue
            
            # Get latest result for this check
            check_results = [r for r in self.results if r.check_name == check.name]
            
            if check_results:
                latest = check_results[-1]
                status[check.name] = {
                    'status': latest.status.value,
                    'response_time_ms': latest.response_time_ms,
                    'last_check': latest.timestamp,
                    'error_message': latest.error_message
                }
            else:
                status[check.name] = {
                    'status': UptimeStatus.UNKNOWN.value,
                    'response_time_ms': 0,
                    'last_check': None,
                    'error_message': 'No checks performed yet'
                }
        
        return status
    
    def get_uptime_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get uptime statistics for specified period"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        stats = {}
        
        for check in self.checks:
            if not check.enabled:
                continue
            
            # Get results for this check in the time period
            check_results = [
                r for r in self.results
                if r.check_name == check.name and 
                   datetime.fromisoformat(r.timestamp) > cutoff
            ]
            
            if not check_results:
                stats[check.name] = {
                    'uptime_percentage': 0,
                    'total_checks': 0,
                    'successful_checks': 0,
                    'avg_response_time_ms': 0,
                    'incidents': 0
                }
                continue
            
            total_checks = len(check_results)
            successful_checks = len([r for r in check_results if r.status == UptimeStatus.UP])
            uptime_percentage = (successful_checks / total_checks) * 100 if total_checks > 0 else 0
            
            # Calculate average response time for successful checks
            successful_times = [r.response_time_ms for r in check_results if r.status == UptimeStatus.UP]
            avg_response_time = sum(successful_times) / len(successful_times) if successful_times else 0
            
            # Count incidents (consecutive down periods)
            incidents = 0
            in_incident = False
            for result in check_results:
                if result.status == UptimeStatus.DOWN:
                    if not in_incident:
                        incidents += 1
                        in_incident = True
                else:
                    in_incident = False
            
            stats[check.name] = {
                'uptime_percentage': round(uptime_percentage, 2),
                'total_checks': total_checks,
                'successful_checks': successful_checks,
                'avg_response_time_ms': round(avg_response_time, 2),
                'incidents': incidents
            }
        
        return stats
    
    def get_overall_uptime(self, hours: int = 24) -> Dict[str, Any]:
        """Get overall system uptime statistics"""
        stats = self.get_uptime_stats(hours)
        
        if not stats:
            return {
                'overall_uptime_percentage': 0,
                'total_checks': 0,
                'total_incidents': 0,
                'avg_response_time_ms': 0
            }
        
        # Calculate weighted average uptime
        total_checks = sum(s['total_checks'] for s in stats.values())
        total_successful = sum(s['successful_checks'] for s in stats.values())
        overall_uptime = (total_successful / total_checks) * 100 if total_checks > 0 else 0
        
        total_incidents = sum(s['incidents'] for s in stats.values())
        
        # Calculate average response time across all checks
        all_response_times = []
        for check_name in stats:
            check_results = [
                r for r in self.results
                if r.check_name == check_name and r.status == UptimeStatus.UP
            ]
            all_response_times.extend([r.response_time_ms for r in check_results])
        
        avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
        
        return {
            'overall_uptime_percentage': round(overall_uptime, 2),
            'total_checks': total_checks,
            'total_incidents': total_incidents,
            'avg_response_time_ms': round(avg_response_time, 2),
            'period_hours': hours
        }


# Global uptime monitor
_uptime_monitor: Optional[UptimeMonitor] = None

def get_uptime_monitor() -> UptimeMonitor:
    """Get global uptime monitor"""
    global _uptime_monitor
    if _uptime_monitor is None:
        _uptime_monitor = UptimeMonitor()
    return _uptime_monitor