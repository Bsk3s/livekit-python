"""
Dashboard API Routes for Voice AI Dashboard
=========================================

Provides data endpoints specifically formatted for the Next.js voice AI dashboard.
Matches the exact data structure expected by each dashboard component.
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

from ..services.analytics.performance_metrics import get_performance_tracker
from ..services.auth import verify_api_key
from ..services.analytics.cost_metrics import get_cost_tracker
from ..services.analytics.system_health import get_health_monitor

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/performance")
async def get_performance_dashboard_data(_: bool = Depends(verify_api_key)):
    """Get performance data formatted for PerformanceDashboard component."""
    try:
        tracker = get_performance_tracker()
        
        # Get current performance metrics
        current_metrics = await tracker.get_current_performance()
        
        # Get latency history for charts
        latency_history = await tracker.get_latency_history(30)
        
        # Format for dashboard component
        return {
            "status": "success",
            "data": {
                "currentLatency": round(current_metrics.current_latency),
                "breakdown": {
                    "stt": round(current_metrics.breakdown["stt"]),
                    "llm": round(current_metrics.breakdown["llm"]),
                    "tts": round(current_metrics.breakdown["tts"]),
                    "network": round(current_metrics.breakdown["network"])
                },
                "status": current_metrics.status,
                "latencyHistory": [
                    {
                        "timestamp": item.timestamp,
                        "total": round(item.total),
                        "stt": round(item.stt),
                        "llm": round(item.llm),
                        "tts": round(item.tts),
                        "network": round(item.network)
                    }
                    for item in latency_history
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance data: {str(e)}")


@router.get("/cost-analytics")
async def get_cost_analytics_data(_: bool = Depends(verify_api_key)):
    """Get cost data formatted for CostAnalytics component."""
    try:
        tracker = get_cost_tracker()
        
        # Get current cost metrics
        current_metrics = await tracker.get_current_cost_metrics()
        
        # Get cost optimization insights
        insights = await tracker.get_cost_optimization_insights()
        
        # Calculate trends (simplified for now)
        daily_trend = "+12%"  # Would calculate from historical data
        monthly_trend = "+8%"
        per_conv_trend = "-5%"
        kokoro_trend = "72%"  # Savings percentage
        
        return {
            "status": "success",
            "data": {
                "dailyCost": round(current_metrics.daily_cost, 2),
                "monthlyProjection": round(current_metrics.monthly_projection, 0),
                "costPerConversation": round(current_metrics.cost_per_conversation, 3),
                "kokoroSavings": round(current_metrics.kokoro_monthly_savings, 0),  # Monthly savings
                "trends": {
                    "daily": daily_trend,
                    "monthly": monthly_trend,
                    "perConversation": per_conv_trend,
                    "kokoro": kokoro_trend
                },
                "optimization": insights
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cost analytics: {str(e)}")


@router.get("/system-health")
async def get_system_health_data():
    """Get system health data formatted for SystemHealth component."""
    try:
        monitor = get_health_monitor()
        
        # Get full system status
        system_status = await monitor.get_full_system_status()
        
        # Format services for dashboard
        services = []
        for service in system_status.services:
            services.append({
                "service": service.service,
                "status": service.status,  # "healthy", "warning", "critical"
                "uptime": service.uptime,  # Percentage
                "responseTime": int(service.response_time),  # milliseconds
                "port": service.port
            })
        
        # System metrics
        metrics = system_status.system_metrics
        
        return {
            "status": "success",
            "data": {
                "overallStatus": system_status.overall_status,
                "services": services,
                "systemMetrics": {
                    "cpuUsage": metrics.get("cpu_percent", 0),
                    "memoryUsage": metrics.get("memory_percent", 0),
                    "diskUsage": metrics.get("disk_percent", 0),
                    "networkSent": metrics.get("network_sent_mb", 0),
                    "networkReceived": metrics.get("network_recv_mb", 0)
                },
                "lastUpdated": system_status.last_updated
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system health: {str(e)}")


@router.get("/historical")
async def get_historical_analytics_data():
    """Get historical data formatted for HistoricalAnalytics component."""
    try:
        performance_tracker = get_performance_tracker()
        cost_tracker = get_cost_tracker()
        
        # Get performance history
        latency_history = await performance_tracker.get_latency_history(100)
        
        # Get cost breakdown history
        cost_history = await cost_tracker.get_cost_breakdown_history(30)
        
        # Performance statistics
        performance_stats = await performance_tracker.get_performance_stats()
        
        return {
            "status": "success",
            "data": {
                "performance": {
                    "history": [
                        {
                            "timestamp": item.timestamp,
                            "totalLatency": round(item.total),
                            "sttLatency": round(item.stt),
                            "llmLatency": round(item.llm),
                            "ttsLatency": round(item.tts)
                        }
                        for item in latency_history
                    ],
                    "statistics": {
                        "avgLatency": round(performance_stats["avg_latency"], 1),
                        "minLatency": round(performance_stats["min_latency"], 1),
                        "maxLatency": round(performance_stats["max_latency"], 1),
                        "p95Latency": round(performance_stats["p95_latency"], 1),
                        "totalConversations": performance_stats["total_conversations"]
                    }
                },
                "cost": {
                    "history": [
                        {
                            "date": item.date,
                            "totalCost": round(item.total_cost, 2),
                            "deepgramCost": round(item.deepgram_cost, 2),
                            "openaiCost": round(item.openai_cost, 2),
                            "kokoroSavings": round(item.kokoro_savings, 2),
                            "conversations": item.conversations
                        }
                        for item in cost_history
                    ]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting historical data: {str(e)}")


@router.get("/voice-control")
async def get_voice_control_data():
    """Get voice control data formatted for VoiceControlCenter component."""
    try:
        # This would integrate with your voice configuration system
        # For now, return sample data matching the expected format
        
        return {
            "status": "success",
            "data": {
                "currentVoice": "adina",
                "availableVoices": [
                    {
                        "id": "adina",
                        "name": "Adina",
                        "description": "Warm, spiritual guidance voice",
                        "active": True
                    },
                    {
                        "id": "raffa",
                        "name": "Raffa",
                        "description": "Strong, confident voice",
                        "active": False
                    }
                ],
                "voiceSettings": {
                    "speed": 1.0,
                    "pitch": 1.0,
                    "volume": 0.8,
                    "stability": 0.7
                },
                "ttsProvider": "kokoro",
                "ttsStatus": "healthy",
                "responseTime": 250
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting voice control data: {str(e)}")


@router.get("/overview")
async def get_dashboard_overview():
    """Get overview data for dashboard home/overview page."""
    try:
        # Get data from all services
        performance_tracker = get_performance_tracker()
        cost_tracker = get_cost_tracker()
        health_monitor = get_health_monitor()
        
        # Get current metrics
        current_performance = await performance_tracker.get_current_performance()
        current_costs = await cost_tracker.get_current_cost_metrics()
        system_health = await health_monitor.get_full_system_status()
        
        # Calculate key metrics
        healthy_services = len([s for s in system_health.services if s.status == "healthy"])
        total_services = len(system_health.services)
        
        return {
            "status": "success",
            "data": {
                "summary": {
                    "currentLatency": round(current_performance.current_latency),
                    "systemStatus": system_health.overall_status,
                    "dailyCost": round(current_costs.daily_cost, 2),
                    "healthyServices": f"{healthy_services}/{total_services}",
                    "kokoroSavings": round(current_costs.kokoro_monthly_savings, 0)
                },
                "alerts": [
                    {
                        "type": "info",
                        "message": f"System running smoothly - {current_performance.status} performance",
                        "timestamp": datetime.now().isoformat()
                    }
                ] if current_performance.status == "good" else [
                    {
                        "type": "warning" if current_performance.status == "warning" else "error",
                        "message": f"Performance {current_performance.status} - monitoring latency",
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "quickStats": {
                    "avgResponseTime": round(current_performance.current_latency),
                    "uptime": round(sum(s.uptime for s in system_health.services) / len(system_health.services), 1),
                    "costEfficiency": "Optimized with free TTS",
                    "activeUsers": 1  # Would get from concurrent user analytics
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting overview data: {str(e)}")


@router.get("/real-time-metrics")
async def get_real_time_metrics():
    """Get real-time metrics for live dashboard updates."""
    try:
        performance_tracker = get_performance_tracker()
        health_monitor = get_health_monitor()
        
        # Get current performance
        current_performance = await performance_tracker.get_current_performance()
        
        # Get system metrics
        system_metrics = await health_monitor.get_system_metrics()
        
        return {
            "status": "success",
            "data": {
                "timestamp": datetime.now().isoformat(),
                "latency": {
                    "total": round(current_performance.current_latency),
                    "stt": round(current_performance.breakdown["stt"]),
                    "llm": round(current_performance.breakdown["llm"]),
                    "tts": round(current_performance.breakdown["tts"]),
                    "status": current_performance.status
                },
                "system": {
                    "cpu": system_metrics.get("cpu_percent", 0),
                    "memory": system_metrics.get("memory_percent", 0),
                    "disk": system_metrics.get("disk_percent", 0)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting real-time metrics: {str(e)}")


@router.get("/export")
async def export_dashboard_data(_: bool = Depends(verify_api_key)):
    """Export all dashboard data for external analysis."""
    try:
        # Get all dashboard data
        performance_data = await get_performance_dashboard_data()
        cost_data = await get_cost_analytics_data()
        health_data = await get_system_health_data()
        historical_data = await get_historical_analytics_data()
        overview_data = await get_dashboard_overview()
        
        return {
            "status": "success",
            "export_timestamp": datetime.now().isoformat(),
            "data": {
                "performance": performance_data["data"],
                "cost": cost_data["data"],
                "health": health_data["data"],
                "historical": historical_data["data"],
                "overview": overview_data["data"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting dashboard data: {str(e)}")