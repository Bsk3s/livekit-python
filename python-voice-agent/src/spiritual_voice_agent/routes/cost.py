"""
Cost Analytics API - Clean endpoints for external dashboard consumption

Provides cost tracking and financial analytics for the voice agent system.
Since Kokoro TTS is free, most costs come from LLM usage only.
"""

from fastapi import APIRouter
from spiritual_voice_agent.services.cost_analytics import get_cost_analytics_db
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/cost/api/summary")
async def cost_api_summary(days: int = 7):
    """Get cost summary for specified number of days."""
    try:
        cost_db = get_cost_analytics_db()
        summary = cost_db.get_cost_summary(days=days)
        
        return {
            'period': f'{days} days',
            'total_cost': summary.get('total_cost', 0.0),
            'stt_cost': summary.get('stt_cost', 0.0),
            'llm_cost': summary.get('llm_cost', 0.0),  # Main cost component
            'tts_cost': 0.0,  # Kokoro is free!
            'total_requests': summary.get('total_requests', 0),
            'cost_per_request': summary.get('cost_per_request', 0.0),
            'daily_average': summary.get('total_cost', 0.0) / max(days, 1),
            'savings_info': {
                'tts_savings': calculate_tts_savings(summary.get('total_requests', 0)),
                'vs_openai_tts': 'Using free Kokoro TTS instead of paid OpenAI TTS'
            },
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Cost summary error: {e}")
        return {'error': str(e), 'generated_at': datetime.now().isoformat()}

@router.get("/cost/api/user/{user_id}")
async def cost_api_user(user_id: str, days: int = 30):
    """Get cost breakdown for specific user."""
    try:
        cost_db = get_cost_analytics_db()
        
        # Get user-specific cost data
        user_summary = cost_db.get_user_cost_summary(user_id, days=days)
        
        return {
            'user_id': user_id,
            'period': f'{days} days',
            'total_cost': user_summary.get('total_cost', 0.0),
            'session_count': user_summary.get('session_count', 0),
            'avg_cost_per_session': user_summary.get('avg_cost_per_session', 0.0),
            'characters_used': user_summary.get('characters_used', []),
            'cost_breakdown': {
                'stt_cost': user_summary.get('stt_cost', 0.0),
                'llm_cost': user_summary.get('llm_cost', 0.0),
                'tts_cost': 0.0  # Free with Kokoro
            },
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"User cost analysis error: {e}")
        return {'error': str(e), 'user_id': user_id}

@router.get("/cost/api/breakdown")
async def cost_breakdown_api(days: int = 7):
    """Get detailed cost breakdown by component and time."""
    try:
        cost_db = get_cost_analytics_db()
        
        # Get recent cost events for analysis
        import sqlite3
        recent_events = []
        
        try:
            with sqlite3.connect(cost_db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT session_id, user_id, character, timestamp, 
                           stt_cost, llm_cost, tts_cost, total_cost,
                           success
                    FROM cost_events 
                    WHERE cost_calculated = TRUE
                    AND datetime(timestamp) >= datetime('now', '-? days')
                    ORDER BY timestamp DESC 
                    LIMIT 100
                """, (days,))
                recent_events = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Could not fetch recent events: {e}")
        
        # Analyze the events
        component_totals = {'stt': 0.0, 'llm': 0.0, 'tts': 0.0}
        character_usage = {}
        daily_costs = {}
        
        for event in recent_events:
            # Component costs
            component_totals['stt'] += event.get('stt_cost', 0.0)
            component_totals['llm'] += event.get('llm_cost', 0.0)
            component_totals['tts'] += event.get('tts_cost', 0.0)
            
            # Character usage
            char = event.get('character', 'unknown')
            character_usage[char] = character_usage.get(char, 0) + 1
            
            # Daily aggregation
            date = event.get('timestamp', '')[:10]  # YYYY-MM-DD
            daily_costs[date] = daily_costs.get(date, 0.0) + event.get('total_cost', 0.0)
        
        return {
            'period': f'{days} days',
            'total_events': len(recent_events),
            'component_breakdown': component_totals,
            'character_usage': character_usage,
            'daily_costs': daily_costs,
            'cost_insights': {
                'primary_cost_driver': 'LLM processing (GPT-4o-mini)',
                'tts_savings': 'TTS is 100% free with Kokoro',
                'optimization_opportunity': 'Consider shorter LLM prompts for cost reduction'
            },
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Cost breakdown error: {e}")
        return {'error': str(e)}

@router.get("/cost/api/projections")
async def cost_projections_api(days: int = 30):
    """Get cost projections and trends."""
    try:
        cost_db = get_cost_analytics_db()
        
        # Get recent data for trending
        recent_summary = cost_db.get_cost_summary(days=7)
        monthly_summary = cost_db.get_cost_summary(days=30)
        
        # Calculate trends and projections
        weekly_cost = recent_summary.get('total_cost', 0.0)
        monthly_cost = monthly_summary.get('total_cost', 0.0)
        
        # Project based on recent trends
        daily_avg = weekly_cost / 7
        monthly_projection = daily_avg * 30
        yearly_projection = daily_avg * 365
        
        return {
            'current_trends': {
                'daily_average': round(daily_avg, 4),
                'weekly_actual': round(weekly_cost, 4),
                'monthly_actual': round(monthly_cost, 4)
            },
            'projections': {
                'monthly': round(monthly_projection, 2),
                'yearly': round(yearly_projection, 2)
            },
            'savings_analysis': {
                'tts_monthly_savings': calculate_tts_savings(recent_summary.get('total_requests', 0) * 4),
                'cost_efficiency': 'Extremely high due to free Kokoro TTS',
                'main_expense': 'LLM API calls only'
            },
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Cost projections error: {e}")
        return {'error': str(e)}

def calculate_tts_savings(total_requests: int) -> float:
    """Calculate estimated TTS cost savings vs OpenAI."""
    # OpenAI TTS pricing: ~$15 per 1M characters
    # Average response: ~100 characters per request
    # Kokoro: FREE!
    
    avg_chars_per_request = 100
    openai_cost_per_char = 15 / 1_000_000  # $15 per million chars
    
    total_chars = total_requests * avg_chars_per_request
    would_have_cost = total_chars * openai_cost_per_char
    
    return round(would_have_cost, 4)