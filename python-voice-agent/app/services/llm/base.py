from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from ...services.base_service import BaseService

class BaseLLMService(BaseService):
    """Base class for Language Model services."""
    
    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response from the language model.
        
        Args:
            prompt: The input prompt
            context: Optional conversation history
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated response text
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the language model.
        
        Args:
            prompt: The input prompt
            context: Optional conversation history
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Generated response text chunks
        """
        pass
    
    @property
    def service_name(self) -> str:
        return "LLM" 