import pytest
from typing import List, Dict, Optional, AsyncGenerator
from app.services.llm.base import BaseLLMService

class MockLLMService(BaseLLMService):
    """Mock implementation of BaseLLMService for testing"""
    
    def _validate_config(self) -> None:
        pass
    
    async def initialize(self) -> None:
        self._initialized = True
    
    async def shutdown(self) -> None:
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return getattr(self, '_initialized', False)
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        return "Mock response"
    
    async def generate_stream(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        yield "Mock"
        yield "stream"
        yield "response"

@pytest.fixture
def mock_llm():
    return MockLLMService()

@pytest.mark.asyncio
async def test_base_llm_interface(mock_llm):
    """Test that the mock implementation follows the base interface contract"""
    # Test initialization
    assert not mock_llm.is_initialized
    await mock_llm.initialize()
    assert mock_llm.is_initialized
    
    # Test response generation
    response = await mock_llm.generate_response("test prompt")
    assert response == "Mock response"
    
    # Test response generation with context
    context = [{"role": "user", "content": "previous"}]
    response = await mock_llm.generate_response("test prompt", context=context)
    assert response == "Mock response"
    
    # Test streaming
    chunks = []
    async for chunk in mock_llm.generate_stream("test prompt"):
        chunks.append(chunk)
    assert chunks == ["Mock", "stream", "response"]
    
    # Test shutdown
    await mock_llm.shutdown()
    assert not mock_llm.is_initialized

@pytest.mark.asyncio
async def test_base_llm_parameters(mock_llm):
    """Test that the interface handles parameters correctly"""
    # Test temperature bounds
    response = await mock_llm.generate_response(
        "test prompt",
        temperature=0.5,
        max_tokens=100
    )
    assert response == "Mock response"
    
    # Test with None max_tokens
    response = await mock_llm.generate_response(
        "test prompt",
        temperature=0.7,
        max_tokens=None
    )
    assert response == "Mock response" 