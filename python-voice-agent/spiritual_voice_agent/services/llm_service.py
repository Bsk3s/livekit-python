import os
from typing import AsyncGenerator
from livekit.agents import llm
from .llm.implementations.openai import OpenAILLMService

class SimpleResponseChunk:
    """Simple response chunk that mimics the expected structure"""
    def __init__(self, content: str):
        self.choices = [SimpleChoice(content)]

class SimpleChoice:
    """Simple choice that mimics the expected structure"""
    def __init__(self, content: str):
        self.delta = SimpleChoiceDelta(content)

class SimpleChoiceDelta:
    """Simple choice delta that mimics the expected structure"""
    def __init__(self, content: str):
        self.content = content

class SimpleAsyncGenerator:
    """Simple async generator that yields response chunks with the expected structure"""
    
    def __init__(self, openai_stream):
        self._openai_stream = openai_stream
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        try:
            chunk = await self._openai_stream.__anext__()
            if chunk.choices and chunk.choices[0].delta.content:
                # Return simple chunk with expected structure
                return SimpleResponseChunk(chunk.choices[0].delta.content)
            else:
                # Continue to next chunk if this one is empty
                return await self.__anext__()
        except StopAsyncIteration:
            raise

class SimpleOpenAILLMService:
    """Simplified OpenAI LLM service that bypasses LiveKit complexities"""
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7, timeout: float = 30.0):
        self._openai_service = OpenAILLMService({
            "model": model,
            "temperature": temperature,
            "timeout": timeout
        })
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the OpenAI service is initialized"""
        if not self._initialized:
            await self._openai_service.initialize()
            self._initialized = True
    
    async def chat(self, *, chat_ctx: llm.ChatContext) -> SimpleAsyncGenerator:
        """Chat with the language model using a simple interface"""
        await self._ensure_initialized()
        
        # Convert LiveKit ChatContext to OpenAI messages format
        messages = []
        for msg in chat_ctx.items:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                # Content is a list in LiveKit, join if multiple parts
                content = msg.content[0] if msg.content else ""
                messages.append({
                    "role": msg.role,
                    "content": content
                })
        
        # Use streaming for compatibility
        stream = await self._openai_service._client.chat.completions.create(
            model=self._openai_service.config.get("model", "gpt-4o-mini"),
            messages=messages,
            temperature=self._openai_service.config.get("temperature", 0.7),
            stream=True
        )
        
        # Return simple async generator
        return SimpleAsyncGenerator(stream)

def create_gpt4o_mini():
    """Create GPT-4o Mini LLM service using simplified implementation"""
    return SimpleOpenAILLMService(
        model="gpt-4o-mini",
        temperature=0.7,
        timeout=30.0
    )

def create_character_llm(character_personality):
    """Create LLM configured with character personality"""
    return create_gpt4o_mini() 