from livekit.agents import Agent
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
from ..services.llm.base import BaseLLMService

class BaseSpiritualAgent(Agent, ABC):
    def __init__(self, llm_service: BaseLLMService):
        super().__init__(
            instructions=self.get_instructions(),
            tools=self.get_tools()
        )
        self.llm_service = llm_service
        self._conversation_history: List[Dict[str, str]] = []
        
    @abstractmethod
    def get_instructions(self) -> str:
        """Each character defines their own personality"""
        pass
        
    @abstractmethod
    def get_voice_config(self) -> dict:
        """Each character has distinct voice settings"""
        pass
        
    @abstractmethod
    def get_tools(self) -> list:
        """Character-specific spiritual tools/functions"""
        pass
    
    async def initialize(self) -> None:
        """Initialize the character and its services"""
        await self.llm_service.initialize()
        
    async def shutdown(self) -> None:
        """Clean up resources"""
        await self.llm_service.shutdown()
        
    def get_base_spiritual_instructions(self) -> str:
        return """
        You are a wise spiritual guide providing comfort, biblical wisdom, 
        and prayer support. Keep responses warm but concise for voice conversation.
        Remember context from recent exchanges to provide continuity.
        Focus on scripture, prayer, and spiritual growth.
        """
    
    async def generate_response(
        self,
        user_input: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response using the LLM service with character context"""
        # Prepare the full prompt with character instructions
        full_prompt = f"{self.get_instructions()}\n\nUser: {user_input}"
        
        # Generate response using LLM
        response = await self.llm_service.generate_response(
            prompt=full_prompt,
            context=self._conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Update conversation history
        self._conversation_history.append({"role": "user", "content": user_input})
        self._conversation_history.append({"role": "assistant", "content": response})
        
        # Keep conversation history manageable (last 10 exchanges)
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]
            
        return response
    
    async def generate_streaming_response(
        self,
        user_input: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using the LLM service"""
        full_prompt = f"{self.get_instructions()}\n\nUser: {user_input}"
        
        # Update conversation history with user input
        self._conversation_history.append({"role": "user", "content": user_input})
        
        # Stream response
        response_chunks = []
        async for chunk in self.llm_service.generate_stream(
            prompt=full_prompt,
            context=self._conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            response_chunks.append(chunk)
            yield chunk
            
        # Update conversation history with complete response
        complete_response = "".join(response_chunks)
        self._conversation_history.append({"role": "assistant", "content": complete_response})
        
        # Keep conversation history manageable
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:] 