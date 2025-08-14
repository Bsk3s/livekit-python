"""
Data models for conversation tracking and LLM training
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


@dataclass
class SpiritualContext:
    """Spiritual context for LLM training specialization"""
    topic: Optional[str] = None  # "prayer", "forgiveness", "doubt", "faith", etc.
    emotional_tone: Optional[str] = None  # "struggling", "hopeful", "questioning", "peaceful"
    conversation_stage: Optional[str] = None  # "opening", "deep_discussion", "resolution", "prayer"
    bible_references: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)


@dataclass
class TechnicalMetadata:
    """Technical metadata for quality and performance tracking"""
    openai_tokens_used: Optional[int] = None
    deepgram_duration_ms: Optional[int] = None
    response_latency_ms: Optional[int] = None
    voice_quality_score: Optional[float] = None
    audio_interruptions: int = 0
    background_noise_level: Optional[str] = None  # "low", "medium", "high"


@dataclass
class ConversationTurn:
    """Single conversation turn for LLM training"""
    session_id: str
    user_id: str
    turn_number: int
    timestamp: datetime
    user_input: str
    agent_response: str
    spiritual_context: SpiritualContext = field(default_factory=SpiritualContext)
    technical_metadata: TechnicalMetadata = field(default_factory=TechnicalMetadata)
    
    def to_llm_training_format(self) -> Dict[str, Any]:
        """Convert to format suitable for LLM training"""
        return {
            "messages": [
                {"role": "user", "content": self.user_input},
                {"role": "assistant", "content": self.agent_response}
            ],
            "metadata": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "timestamp": self.timestamp.isoformat(),
                "spiritual_context": {
                    "topic": self.spiritual_context.topic,
                    "emotional_tone": self.spiritual_context.emotional_tone,
                    "stage": self.spiritual_context.conversation_stage,
                    "themes": self.spiritual_context.themes
                },
                "quality": {
                    "response_latency_ms": self.technical_metadata.response_latency_ms,
                    "voice_quality_score": self.technical_metadata.voice_quality_score,
                    "audio_interruptions": self.technical_metadata.audio_interruptions
                }
            }
        }
    
    def to_supabase_format(self) -> Dict[str, Any]:
        """Convert to format for Supabase storage"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id, 
            "turn_number": self.turn_number,
            "timestamp": self.timestamp.isoformat(),
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "spiritual_context": {
                "topic": self.spiritual_context.topic,
                "emotional_tone": self.spiritual_context.emotional_tone,
                "conversation_stage": self.spiritual_context.conversation_stage,
                "bible_references": self.spiritual_context.bible_references,
                "themes": self.spiritual_context.themes
            },
            "technical_metadata": {
                "openai_tokens_used": self.technical_metadata.openai_tokens_used,
                "deepgram_duration_ms": self.technical_metadata.deepgram_duration_ms,
                "response_latency_ms": self.technical_metadata.response_latency_ms,
                "voice_quality_score": self.technical_metadata.voice_quality_score,
                "audio_interruptions": self.technical_metadata.audio_interruptions,
                "background_noise_level": self.technical_metadata.background_noise_level
            },
            "openai_tokens_used": self.technical_metadata.openai_tokens_used,
            "deepgram_duration_ms": self.technical_metadata.deepgram_duration_ms,
            "response_latency_ms": self.technical_metadata.response_latency_ms,
            "voice_quality_score": self.technical_metadata.voice_quality_score
        }


@dataclass
class ConversationSession:
    """Complete conversation session for analytics and LLM training"""
    id: str
    user_id: str
    session_start: datetime
    session_end: Optional[datetime] = None
    total_turns: int = 0
    total_duration_seconds: Optional[int] = None
    character_name: str = "adina"
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    turns: List[ConversationTurn] = field(default_factory=list)
    
    def add_turn(self, turn: ConversationTurn):
        """Add a conversation turn to this session"""
        self.turns.append(turn)
        self.total_turns = len(self.turns)
    
    def end_session(self):
        """Mark session as ended"""
        self.session_end = datetime.utcnow()
        if self.session_start:
            duration = self.session_end - self.session_start
            self.total_duration_seconds = int(duration.total_seconds())
    
    def to_llm_dataset(self) -> List[Dict[str, Any]]:
        """Convert entire session to LLM training dataset format"""
        return [turn.to_llm_training_format() for turn in self.turns]
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary for dashboard analytics"""
        if not self.turns:
            return {}
        
        # Extract spiritual themes
        all_topics = [turn.spiritual_context.topic for turn in self.turns if turn.spiritual_context.topic]
        all_emotions = [turn.spiritual_context.emotional_tone for turn in self.turns if turn.spiritual_context.emotional_tone]
        
        # Calculate average quality metrics
        quality_scores = [turn.technical_metadata.voice_quality_score for turn in self.turns if turn.technical_metadata.voice_quality_score]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
        
        total_tokens = sum(turn.technical_metadata.openai_tokens_used or 0 for turn in self.turns)
        
        return {
            "session_id": self.id,
            "user_id": self.user_id,
            "duration_seconds": self.total_duration_seconds,
            "total_turns": self.total_turns,
            "spiritual_topics": list(set(all_topics)),
            "emotional_journey": all_emotions,
            "average_voice_quality": avg_quality,
            "total_openai_tokens": total_tokens,
            "conversation_stages": [turn.spiritual_context.conversation_stage for turn in self.turns if turn.spiritual_context.conversation_stage]
        }