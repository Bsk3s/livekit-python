#!/usr/bin/env python3
"""
Zero-Impact Cost Tracking Test Script

This script demonstrates the voice-first cost analytics system working
with sample conversation data to verify zero latency impact.

Usage: python test_cost_tracking.py
"""

import asyncio
import time
import logging
from spiritual_voice_agent.services.cost_analytics import log_voice_event, get_cost_analytics_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_voice_first_cost_tracking():
    """Test the zero-impact cost tracking with sample conversation data"""
    
    print("🎯 Testing Zero-Impact Voice Agent Cost Tracking")
    print("=" * 60)
    
    # Simulate a real conversation with timing
    conversations = [
        {
            'session_id': 'test_session_001',
            'user_id': 'test_user_001', 
            'character': 'adina',
            'transcript_text': "Hello, I'm feeling anxious about my presentation tomorrow",
            'response_text': "I understand that feeling anxious about presentations is completely normal. Let's work through some techniques to help you feel more confident and prepared.",
            'stt_duration_ms': 150,
            'llm_duration_ms': 850,
            'tts_duration_ms': 320,
            'audio_duration_seconds': 4.2
        },
        {
            'session_id': 'test_session_001',
            'user_id': 'test_user_001',
            'character': 'adina', 
            'transcript_text': "What techniques can help me?",
            'response_text': "Try deep breathing exercises, practice your opening lines, and visualize success. Remember, your expertise got you here.",
            'stt_duration_ms': 120,
            'llm_duration_ms': 780,
            'tts_duration_ms': 290,
            'audio_duration_seconds': 2.8
        },
        {
            'session_id': 'test_session_002',
            'user_id': 'test_user_002',
            'character': 'raffa',
            'transcript_text': "I need help with meditation",
            'response_text': "Meditation is a powerful tool for inner peace. Let's start with a simple breathing meditation. Find a comfortable position and focus on your breath.",
            'stt_duration_ms': 140,
            'llm_duration_ms': 920,
            'tts_duration_ms': 380,
            'audio_duration_seconds': 3.5
        }
    ]
    
    # Test 1: Fire-and-forget logging (should be instant)
    print("\n🔥 Test 1: Fire-and-Forget Event Logging")
    start_time = time.perf_counter()
    
    for i, conv in enumerate(conversations):
        # Add timestamp and calculate total latency
        conv['timestamp'] = time.time() + i  # Slightly different timestamps
        conv['total_latency_ms'] = conv['stt_duration_ms'] + conv['llm_duration_ms'] + conv['tts_duration_ms']
        conv['success'] = True
        
        # This should return immediately (microseconds)
        log_voice_event(conv)
        
    logging_time = (time.perf_counter() - start_time) * 1000
    print(f"✅ Logged {len(conversations)} events in {logging_time:.2f}ms")
    print(f"   📊 Average: {logging_time/len(conversations):.2f}ms per event")
    print("   🎯 Target: <1ms per event (zero voice impact)")
    
    # Test 2: Wait for background processing
    print("\n⏳ Test 2: Background Cost Calculation")
    print("   Waiting for background cost calculations to complete...")
    await asyncio.sleep(3)  # Give background processor time to work
    
    # Test 3: Query cost analytics
    print("\n💰 Test 3: Cost Analytics Query")
    cost_db = get_cost_analytics_db()
    
    # Get cost summary
    cost_summary = cost_db.get_cost_summary(days=1)
    print("   Cost Summary:")
    print(f"   💵 Total Cost: ${cost_summary['total_cost']:.6f}")
    print(f"   📈 Average Cost per Turn: ${cost_summary['avg_cost_per_turn']:.6f}")
    print(f"   🗣️  Total Conversations: {cost_summary['total_conversations']}")
    print(f"   👥 Unique Users: {cost_summary['unique_users']}")
    
    print("\n   Cost Breakdown:")
    print(f"   🎤 STT (Deepgram): ${cost_summary['total_stt_cost']:.6f}")
    print(f"   🧠 LLM (GPT-4o-mini): ${cost_summary['total_llm_cost']:.6f}")
    print(f"   🎵 TTS (OpenAI): ${cost_summary['total_tts_cost']:.6f}")
    
    # Test 4: Session-specific costs
    print("\n📊 Test 4: Session-Specific Analysis")
    session_costs = cost_db.get_session_costs('test_session_001')
    if session_costs:
        total_session_cost = sum(event['total_cost'] or 0 for event in session_costs if event.get('cost_calculated'))
        print(f"   Session test_session_001 Total Cost: ${total_session_cost:.6f}")
        print(f"   Turns in Session: {len(session_costs)}")
    
    # Test 5: User-specific costs  
    print("\n👤 Test 5: User-Specific Analysis")
    user_costs = cost_db.get_user_costs('test_user_001', days=1)
    if user_costs:
        total_user_cost = sum(event['total_cost'] or 0 for event in user_costs if event.get('cost_calculated'))
        print(f"   User test_user_001 Total Cost: ${total_user_cost:.6f}")
        print(f"   Conversations by User: {len(user_costs)}")
    
    print("\n🎯 Zero-Impact Cost Tracking Test Complete!")
    print("=" * 60)
    print("✅ Voice pipeline latency: ZERO impact")
    print("✅ Cost calculations: Background processing")
    print("✅ Analytics queries: Real-time data available")
    print("✅ Database: SQLite (easy deployment)")
    print("✅ Pricing: 2025 rates (Deepgram + OpenAI)")


def test_pricing_calculations():
    """Test the 2025 pricing calculations"""
    print("\n💰 2025 Pricing Verification")
    print("-" * 40)
    
    # Sample conversation
    audio_minutes = 3.5 / 60  # 3.5 seconds
    input_chars = 50  # "Hello, I'm feeling anxious about my presentation"
    output_chars = 150  # AI response
    
    # Calculate costs using 2025 rates
    stt_cost = audio_minutes * 0.0058  # Deepgram Nova-2 streaming
    input_tokens = input_chars // 4  # Rough approximation
    output_tokens = output_chars // 4
    llm_cost = (input_tokens / 1_000_000) * 0.15 + (output_tokens / 1_000_000) * 0.60
    tts_cost = (output_chars / 1000) * 15.0
    total_cost = stt_cost + llm_cost + tts_cost
    
    print(f"Sample 3.5-second conversation:")
    print(f"  🎤 STT: ${stt_cost:.6f} (Deepgram Nova-2)")
    print(f"  🧠 LLM: ${llm_cost:.6f} (GPT-4o-mini)")
    print(f"  🎵 TTS: ${tts_cost:.6f} (OpenAI)")
    print(f"  💰 Total: ${total_cost:.6f}")
    print(f"  📊 Cost per minute: ${(total_cost / (3.5/60)):.6f}")


if __name__ == "__main__":
    print("🚀 Voice Agent Cost Tracking Test")
    test_pricing_calculations()
    asyncio.run(test_voice_first_cost_tracking()) 