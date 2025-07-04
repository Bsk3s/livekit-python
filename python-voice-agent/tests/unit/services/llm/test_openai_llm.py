import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from spiritual_voice_agent.services.llm.implementations.openai import OpenAILLMService

@pytest.fixture
def mock_openai():
    with patch('openai.AsyncOpenAI') as mock:
        # Create a mock client
        mock_client = MagicMock()
        mock.return_value = mock_client
        
        # Mock the chat completions
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Test response"))
        ]
        
        # Create async mock for create method
        mock_create = AsyncMock(return_value=mock_completion)
        mock_client.chat.completions.create = mock_create
        
        yield mock_client

@pytest.fixture
def llm_service():
    # Set up test environment
    os.environ["OPENAI_API_KEY"] = "test_key"
    return OpenAILLMService({
        "model": "gpt-4",
        "timeout": 30.0
    })

@pytest.mark.asyncio
async def test_initialization(llm_service):
    """Test service initialization"""
    assert not llm_service.is_initialized
    await llm_service.initialize()
    assert llm_service.is_initialized

@pytest.mark.asyncio
async def test_initialization_without_api_key():
    """Test initialization fails without API key"""
    os.environ.pop("OPENAI_API_KEY", None)
    service = OpenAILLMService()
    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is not set"):
        await service.initialize()

@pytest.mark.asyncio
async def test_generate_response(llm_service, mock_openai):
    """Test generating a response"""
    await llm_service.initialize()
    
    response = await llm_service.generate_response(
        prompt="Test prompt",
        temperature=0.7,
        max_tokens=100
    )
    
    assert response == "Test response"
    mock_openai.chat.completions.create.assert_called_once()
    call_args = mock_openai.chat.completions.create.call_args[1]
    assert call_args["model"] == "gpt-4"
    assert call_args["temperature"] == 0.7
    assert call_args["max_tokens"] == 100
    assert call_args["stream"] is False

@pytest.mark.asyncio
async def test_generate_response_with_context(llm_service, mock_openai):
    """Test generating a response with conversation context"""
    await llm_service.initialize()
    
    context = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Previous message"}
    ]
    
    response = await llm_service.generate_response(
        prompt="Test prompt",
        context=context,
        temperature=0.7
    )
    
    assert response == "Test response"
    call_args = mock_openai.chat.completions.create.call_args[1]
    assert len(call_args["messages"]) == 3  # System + Previous + Current

@pytest.mark.asyncio
async def test_generate_stream(llm_service, mock_openai):
    """Test streaming response generation"""
    await llm_service.initialize()
    
    # Mock streaming response
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="chunk"))]
    
    # Create async iterator for streaming
    async def mock_stream():
        yield mock_chunk
    
    mock_openai.chat.completions.create.return_value = mock_stream()
    
    chunks = []
    async for chunk in llm_service.generate_stream("Test prompt"):
        chunks.append(chunk)
    
    assert chunks == ["chunk"]
    call_args = mock_openai.chat.completions.create.call_args[1]
    assert call_args["stream"] is True

@pytest.mark.asyncio
async def test_shutdown(llm_service):
    """Test service shutdown"""
    await llm_service.initialize()
    assert llm_service.is_initialized
    
    await llm_service.shutdown()
    assert not llm_service.is_initialized 