"""
Event-driven conversation processor for LLM training data collection

Handles conversation events asynchronously to ensure zero impact on voice performance.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re

from .models import ConversationTurn, SpiritualContext, TechnicalMetadata

logger = logging.getLogger(__name__)


class ConversationEventProcessor:
    """
    Processes conversation events and enriches them with spiritual context
    for LLM training and dashboard analytics
    """
    
    def __init__(self):
        self.spiritual_keywords = {
            "prayer": ["pray", "prayer", "praying", "prayers", "lord", "god", "heavenly father"],
            "forgiveness": ["forgive", "forgiveness", "mercy", "pardon", "grace", "sin", "guilt"],
            "doubt": ["doubt", "question", "uncertain", "confused", "struggling", "faith crisis"],
            "faith": ["faith", "believe", "trust", "hope", "strength", "guidance"],
            "scripture": ["bible", "verse", "scripture", "word", "psalm", "proverb", "matthew", "john"],
            "worship": ["worship", "praise", "thanksgiving", "grateful", "blessing", "church"],
            "love": ["love", "compassion", "kindness", "care", "heart", "relationship"],
            "peace": ["peace", "calm", "rest", "anxiety", "worry", "stress", "comfort"],
            "purpose": ["purpose", "calling", "mission", "direction", "path", "journey"],
            "suffering": ["pain", "hurt", "suffering", "trial", "difficulty", "struggle"]
        }
        
        self.emotional_patterns = {
            "struggling": ["struggling", "hard", "difficult", "can't", "lost", "overwhelmed"],
            "hopeful": ["hope", "better", "grateful", "blessed", "thankful", "positive"],
            "questioning": ["why", "how", "what if", "don't understand", "confused"],
            "peaceful": ["peace", "calm", "rest", "comfort", "joy", "content"],
            "seeking": ["help", "guidance", "show me", "teach me", "need", "want to grow"]
        }
        
        self.conversation_stages = {
            "opening": ["hello", "hi", "good morning", "good evening", "thank you for"],
            "deep_discussion": ["tell me more", "explain", "help me understand", "what about"],
            "prayer_request": ["pray for", "please pray", "would you pray", "prayer request"],
            "resolution": ["thank you", "that helps", "i understand", "feel better", "makes sense"],
            "closing": ["goodbye", "thank you", "bless you", "amen", "good night"]
        }
    
    async def process_conversation_turn(
        self, 
        session_id: str,
        user_id: str,
        turn_number: int,
        user_input: str,
        agent_response: str,
        technical_metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationTurn:
        """
        Process a conversation turn and enrich with spiritual context
        
        This runs asynchronously to avoid impacting voice performance
        """
        logger.debug(f"Processing conversation turn {turn_number} for session {session_id[:8]}...")
        
        # Extract spiritual context
        spiritual_context = await self._extract_spiritual_context(user_input, agent_response)
        
        # Process technical metadata
        tech_metadata = self._process_technical_metadata(technical_metadata or {})
        
        # Create conversation turn
        turn = ConversationTurn(
            session_id=session_id,
            user_id=user_id,
            turn_number=turn_number,
            timestamp=datetime.utcnow(),
            user_input=user_input,
            agent_response=agent_response,
            spiritual_context=spiritual_context,
            technical_metadata=tech_metadata
        )
        
        logger.info(f"✅ Processed turn {turn_number}: topic={spiritual_context.topic}, tone={spiritual_context.emotional_tone}")
        
        return turn
    
    async def _extract_spiritual_context(self, user_input: str, agent_response: str) -> SpiritualContext:
        """Extract spiritual context from conversation content"""
        
        # Combine input and response for analysis
        combined_text = f"{user_input} {agent_response}".lower()
        
        # Detect spiritual topic
        topic = await self._detect_spiritual_topic(combined_text)
        
        # Detect emotional tone
        emotional_tone = await self._detect_emotional_tone(user_input.lower())
        
        # Detect conversation stage
        conversation_stage = await self._detect_conversation_stage(user_input.lower(), agent_response.lower())
        
        # Extract bible references (simple pattern matching)
        bible_references = await self._extract_bible_references(agent_response)
        
        # Extract spiritual themes
        themes = await self._extract_themes(combined_text)
        
        return SpiritualContext(
            topic=topic,
            emotional_tone=emotional_tone,
            conversation_stage=conversation_stage,
            bible_references=bible_references,
            themes=themes
        )
    
    async def _detect_spiritual_topic(self, text: str) -> Optional[str]:
        """Detect the primary spiritual topic being discussed"""
        topic_scores = {}
        
        for topic, keywords in self.spiritual_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                topic_scores[topic] = score
        
        if topic_scores:
            return max(topic_scores, key=topic_scores.get)
        
        return None
    
    async def _detect_emotional_tone(self, user_input: str) -> Optional[str]:
        """Detect the emotional tone of the user's input"""
        emotion_scores = {}
        
        for emotion, keywords in self.emotional_patterns.items():
            score = sum(1 for keyword in keywords if keyword in user_input)
            if score > 0:
                emotion_scores[emotion] = score
        
        if emotion_scores:
            return max(emotion_scores, key=emotion_scores.get)
        
        return None
    
    async def _detect_conversation_stage(self, user_input: str, agent_response: str) -> Optional[str]:
        """Detect what stage of conversation this is"""
        combined_text = f"{user_input} {agent_response}"
        
        for stage, keywords in self.conversation_stages.items():
            if any(keyword in combined_text for keyword in keywords):
                return stage
        
        # Default to deep_discussion if no specific stage detected
        return "deep_discussion"
    
    async def _extract_bible_references(self, text: str) -> list:
        """Extract bible references from text"""
        # Simple pattern for common bible books
        bible_pattern = r'(Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation|Psalms|Proverbs|Genesis|Exodus|Leviticus|Numbers|Deuteronomy)\s+\d+[:\d-]*'
        
        matches = re.findall(bible_pattern, text, re.IGNORECASE)
        return list(set(matches))
    
    async def _extract_themes(self, text: str) -> list:
        """Extract general spiritual themes from the conversation"""
        themes = []
        
        # Look for multiple topic matches to identify themes
        for topic, keywords in self.spiritual_keywords.items():
            if any(keyword in text for keyword in keywords):
                themes.append(topic)
        
        return themes
    
    def _process_technical_metadata(self, metadata: Dict[str, Any]) -> TechnicalMetadata:
        """Process technical metadata for quality tracking"""
        return TechnicalMetadata(
            openai_tokens_used=metadata.get("openai_tokens"),
            deepgram_duration_ms=metadata.get("deepgram_duration_ms"),
            response_latency_ms=metadata.get("response_latency_ms"),
            voice_quality_score=metadata.get("voice_quality_score"),
            audio_interruptions=metadata.get("audio_interruptions", 0),
            background_noise_level=metadata.get("background_noise_level")
        )