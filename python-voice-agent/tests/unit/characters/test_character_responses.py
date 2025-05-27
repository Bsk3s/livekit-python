import pytest
from unittest.mock import AsyncMock, MagicMock
from app.characters.base_character import BaseSpiritualAgent
from app.services.llm.base import BaseLLMService

class MockLLMService(BaseLLMService):
    """Mock LLM service for testing"""
    def _validate_config(self) -> None:
        pass
    
    async def initialize(self) -> None:
        self._initialized = True
    
    async def shutdown(self) -> None:
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return getattr(self, '_initialized', False)
    
    async def generate_response(self, prompt: str, context=None, temperature=0.7, max_tokens=None) -> str:
        return "Mock response"
    
    async def generate_stream(self, prompt: str, context=None, temperature=0.7, max_tokens=None):
        yield "Mock"
        yield "streaming"
        yield "response"

class TestCharacter(BaseSpiritualAgent):
    """Test character implementation"""
    def get_instructions(self) -> str:
        return "You are a test character"
    
    def get_voice_config(self) -> dict:
        return {"voice_id": "test_voice"}
    
    def get_tools(self) -> list:
        return []

@pytest.fixture
def mock_llm():
    return MockLLMService()

@pytest.fixture
def test_character(mock_llm):
    return TestCharacter(mock_llm)

@pytest.mark.asyncio
async def test_character_initialization(test_character):
    """Test character initialization"""
    assert not test_character.llm_service.is_initialized
    await test_character.initialize()
    assert test_character.llm_service.is_initialized

@pytest.mark.asyncio
async def test_character_response_generation(test_character):
    """Test basic response generation"""
    await test_character.initialize()
    
    response = await test_character.generate_response("Hello")
    assert response == "Mock response"
    
    # Check conversation history
    assert len(test_character._conversation_history) == 2
    assert test_character._conversation_history[0]["role"] == "user"
    assert test_character._conversation_history[0]["content"] == "Hello"
    assert test_character._conversation_history[1]["role"] == "assistant"
    assert test_character._conversation_history[1]["content"] == "Mock response"

@pytest.mark.asyncio
async def test_character_streaming_response(test_character):
    """Test streaming response generation"""
    await test_character.initialize()
    
    chunks = []
    async for chunk in test_character.generate_streaming_response("Hello"):
        chunks.append(chunk)
    
    assert chunks == ["Mock", "streaming", "response"]
    
    # Check conversation history
    assert len(test_character._conversation_history) == 2
    assert test_character._conversation_history[0]["role"] == "user"
    assert test_character._conversation_history[0]["content"] == "Hello"
    assert test_character._conversation_history[1]["role"] == "assistant"
    assert test_character._conversation_history[1]["content"] == "Mockstreamingresponse"

@pytest.mark.asyncio
async def test_conversation_history_management(test_character):
    """Test conversation history management"""
    await test_character.initialize()
    
    # Generate more than 20 exchanges
    for i in range(15):
        await test_character.generate_response(f"Message {i}")
    
    # Check that history is maintained but limited
    assert len(test_character._conversation_history) == 20  # 10 exchanges (20 messages)
    assert test_character._conversation_history[0]["content"] == "Message 5"  # First 5 exchanges removed
    assert test_character._conversation_history[-1]["content"] == "Mock response"  # Latest response 