import os
import pytest
from app.characters.adina.agent import AdinaAgent
from app.services.llm.implementations.openai import OpenAILLMService

# Override the test environment with real API key
REAL_API_KEY = "your_openai_api_key_here"

@pytest.fixture(autouse=True)
def override_test_env():
    """Override test environment with real API key"""
    os.environ["OPENAI_API_KEY"] = REAL_API_KEY
    yield
    # The original test environment will be restored by the conftest fixture

@pytest.fixture
def adina_llm():
    """Create a real OpenAI LLM service for Adina"""
    return OpenAILLMService({
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 150
    })

@pytest.fixture
def adina(adina_llm):
    """Create an instance of Adina with the LLM service"""
    return AdinaAgent(llm_service=adina_llm)

@pytest.mark.asyncio
async def test_adina_initialization(adina):
    """Test Adina's initialization"""
    assert not adina.llm_service.is_initialized
    await adina.initialize()
    assert adina.llm_service.is_initialized

@pytest.mark.asyncio
async def test_adina_basic_response(adina):
    """Test Adina's basic response generation"""
    await adina.initialize()
    
    # Test a simple greeting
    response = await adina.generate_response("Hello, how are you today?")
    print("\nBasic Response:")
    print("User: Hello, how are you today?")
    print(f"Adina: {response}")
    assert response is not None
    assert len(response) > 0

@pytest.mark.asyncio
async def test_adina_conversation_flow(adina):
    """Test a conversation flow with Adina"""
    await adina.initialize()
    
    # First message
    response = await adina.generate_response("I'm feeling anxious today")
    print("\nConversation Flow:")
    print("User: I'm feeling anxious today")
    print(f"Adina: {response}")
    assert response is not None
    assert len(response) > 0
    
    # Follow-up message
    follow_up = await adina.generate_response("Can you pray for me?")
    print("User: Can you pray for me?")
    print(f"Adina: {follow_up}")
    assert follow_up is not None
    assert len(follow_up) > 0
    
    # Check conversation history
    assert len(adina._conversation_history) == 4  # 2 exchanges (2 user + 2 assistant messages)

@pytest.mark.asyncio
async def test_adina_streaming_response(adina):
    """Test Adina's streaming response"""
    await adina.initialize()
    
    print("\nStreaming Response:")
    print("User: Tell me about God's love")
    print("Adina: ", end="", flush=True)
    
    async for chunk in adina.generate_streaming_response("Tell me about God's love"):
        print(chunk, end="", flush=True)
    print()  # New line after response
    
    # Check conversation history
    assert len(adina._conversation_history) == 2  # 1 exchange (1 user + 1 assistant message) 