"""
Cost Analytics Service for Voice AI Dashboard
===========================================

Tracks API costs, per-conversation costs, Kokoro TTS savings,
and provides cost projections for business intelligence.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Daily cost breakdown by service."""
    date: str
    total_cost: float
    deepgram_cost: float  # STT costs
    openai_cost: float    # LLM costs  
    kokoro_savings: float # Savings from free TTS
    conversations: int
    cost_per_conversation: float


@dataclass
class CostMetrics:
    """Current cost metrics for dashboard."""
    daily_cost: float
    monthly_projection: float
    cost_per_conversation: float
    kokoro_savings: float
    kokoro_monthly_savings: float
    

class CostTracker:
    """
    Tracks API costs and provides cost analytics for dashboard.
    
    Features:
    - Real-time cost tracking
    - Per-conversation cost calculation
    - Kokoro TTS savings calculation
    - Monthly projections
    - Cost optimization insights
    """
    
    def __init__(self):
        self.cost_history: List[CostBreakdown] = []
        self.current_day_costs = {
            "deepgram": 0.0,
            "openai": 0.0,
            "conversations": 0
        }
        
        # Cost estimates (per unit)
        self.pricing = {
            "deepgram_per_minute": 0.0059,  # Deepgram pricing
            "openai_gpt4o_mini_per_1k": 0.00015,  # GPT-4o-mini input
            "openai_gpt4o_mini_output_per_1k": 0.0006,  # GPT-4o-mini output
            "openai_tts_per_1k_chars": 0.015,  # OpenAI TTS (what we're saving)
        }
        
    async def record_conversation_cost(self, 
                                     audio_duration_minutes: float,
                                     input_tokens: int,
                                     output_tokens: int,
                                     tts_characters: int) -> float:
        """Record costs for a single conversation."""
        
        # Calculate individual service costs
        deepgram_cost = audio_duration_minutes * self.pricing["deepgram_per_minute"]
        
        openai_input_cost = (input_tokens / 1000) * self.pricing["openai_gpt4o_mini_per_1k"]
        openai_output_cost = (output_tokens / 1000) * self.pricing["openai_gpt4o_mini_output_per_1k"]
        openai_cost = openai_input_cost + openai_output_cost
        
        # Calculate TTS savings (what we would have paid OpenAI)
        kokoro_savings = (tts_characters / 1000) * self.pricing["openai_tts_per_1k_chars"]
        
        total_cost = deepgram_cost + openai_cost
        
        # Update current day tracking
        self.current_day_costs["deepgram"] += deepgram_cost
        self.current_day_costs["openai"] += openai_cost
        self.current_day_costs["conversations"] += 1
        
        logger.info(f"💰 Conversation cost: ${total_cost:.4f} (Deepgram: ${deepgram_cost:.4f}, OpenAI: ${openai_cost:.4f}, Kokoro saved: ${kokoro_savings:.4f})")
        
        return total_cost
    
    async def get_current_cost_metrics(self) -> CostMetrics:
        """Get current cost metrics for dashboard."""
        
        # Calculate daily costs
        daily_deepgram = self.current_day_costs["deepgram"]
        daily_openai = self.current_day_costs["openai"]
        daily_total = daily_deepgram + daily_openai
        
        # Estimate daily Kokoro savings (based on typical TTS usage)
        conversations_today = self.current_day_costs["conversations"]
        estimated_chars_per_conversation = 200  # Average characters per response
        estimated_daily_kokoro_savings = (conversations_today * estimated_chars_per_conversation / 1000) * self.pricing["openai_tts_per_1k_chars"]
        
        # Calculate per-conversation cost
        cost_per_conversation = daily_total / conversations_today if conversations_today > 0 else 0
        
        # Monthly projections
        monthly_projection = daily_total * 30
        kokoro_monthly_savings = estimated_daily_kokoro_savings * 30
        
        return CostMetrics(
            daily_cost=daily_total,
            monthly_projection=monthly_projection,
            cost_per_conversation=cost_per_conversation,
            kokoro_savings=estimated_daily_kokoro_savings,
            kokoro_monthly_savings=kokoro_monthly_savings
        )
    
    async def get_cost_breakdown_history(self, days: int = 30) -> List[CostBreakdown]:
        """Get historical cost breakdown."""
        return self.cost_history[-days:]
    
    async def add_daily_breakdown(self) -> CostBreakdown:
        """Add current day to cost history and reset daily counters."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        total_cost = self.current_day_costs["deepgram"] + self.current_day_costs["openai"]
        conversations = self.current_day_costs["conversations"]
        
        # Estimate Kokoro savings for the day
        estimated_chars_per_conversation = 200
        kokoro_savings = (conversations * estimated_chars_per_conversation / 1000) * self.pricing["openai_tts_per_1k_chars"]
        
        breakdown = CostBreakdown(
            date=today,
            total_cost=total_cost,
            deepgram_cost=self.current_day_costs["deepgram"],
            openai_cost=self.current_day_costs["openai"],
            kokoro_savings=kokoro_savings,
            conversations=conversations,
            cost_per_conversation=total_cost / conversations if conversations > 0 else 0
        )
        
        self.cost_history.append(breakdown)
        
        # Keep only last 30 days
        if len(self.cost_history) > 30:
            self.cost_history = self.cost_history[-30:]
        
        # Reset daily counters
        self.current_day_costs = {
            "deepgram": 0.0,
            "openai": 0.0,
            "conversations": 0
        }
        
        return breakdown
    
    async def get_cost_optimization_insights(self) -> Dict:
        """Get cost optimization recommendations."""
        current_metrics = await self.get_current_cost_metrics()
        
        insights = {
            "kokoro_tts_savings": {
                "daily_savings": current_metrics.kokoro_savings,
                "monthly_savings": current_metrics.kokoro_monthly_savings,
                "annual_savings": current_metrics.kokoro_monthly_savings * 12,
                "percentage_saved": "100% TTS costs eliminated"
            },
            "cost_efficiency": {
                "cost_per_conversation": current_metrics.cost_per_conversation,
                "cost_breakdown": "60% LLM, 40% STT, 0% TTS",
                "optimization_potential": "Already optimized with free TTS"
            },
            "projections": {
                "monthly_cost": current_metrics.monthly_projection,
                "with_paid_tts": current_metrics.monthly_projection + current_metrics.kokoro_monthly_savings,
                "savings_percentage": round((current_metrics.kokoro_monthly_savings / (current_metrics.monthly_projection + current_metrics.kokoro_monthly_savings)) * 100, 1) if current_metrics.monthly_projection > 0 else 0
            }
        }
        
        return insights
    
    async def simulate_cost_with_scale(self, users: int, conversations_per_user_per_day: int = 3) -> Dict:
        """Simulate costs at different scales."""
        current_metrics = await self.get_current_cost_metrics()
        
        # Use current cost per conversation or estimate
        cost_per_conv = current_metrics.cost_per_conversation if current_metrics.cost_per_conversation > 0 else 0.05
        
        daily_conversations = users * conversations_per_user_per_day
        daily_cost = daily_conversations * cost_per_conv
        monthly_cost = daily_cost * 30
        
        # Calculate Kokoro savings at scale
        chars_per_conversation = 200
        daily_chars = daily_conversations * chars_per_conversation
        daily_tts_savings = (daily_chars / 1000) * self.pricing["openai_tts_per_1k_chars"]
        monthly_tts_savings = daily_tts_savings * 30
        
        return {
            "scale": f"{users} users",
            "daily_conversations": daily_conversations,
            "daily_cost": daily_cost,
            "monthly_cost": monthly_cost,
            "annual_cost": monthly_cost * 12,
            "kokoro_savings": {
                "daily": daily_tts_savings,
                "monthly": monthly_tts_savings,
                "annual": monthly_tts_savings * 12
            },
            "total_with_paid_tts": monthly_cost + monthly_tts_savings,
            "savings_percentage": round((monthly_tts_savings / (monthly_cost + monthly_tts_savings)) * 100, 1)
        }


# Singleton cost tracker
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _cost_tracker
    
    if not _cost_tracker:
        _cost_tracker = CostTracker()
    
    return _cost_tracker


# Convenience functions for easy integration
async def record_conversation_costs(audio_minutes: float, input_tokens: int, output_tokens: int, tts_chars: int) -> float:
    """Record costs for a conversation."""
    tracker = get_cost_tracker()
    return await tracker.record_conversation_cost(audio_minutes, input_tokens, output_tokens, tts_chars)


async def get_daily_cost_summary() -> CostMetrics:
    """Get current daily cost summary."""
    tracker = get_cost_tracker()
    return await tracker.get_current_cost_metrics()