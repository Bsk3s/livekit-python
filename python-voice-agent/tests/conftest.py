import os
import pytest
from typing import Dict, Any

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    # Store original environment
    original_env = dict(os.environ)
    
    # Set test environment variables
    os.environ["OPENAI_API_KEY"] = "test_key"
    os.environ["DEEPGRAM_API_KEY"] = "test_key"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Common test configuration"""
    return {
        "model": "gpt-4",
        "timeout": 30.0,
        "temperature": 0.7,
        "max_tokens": 100
    } 