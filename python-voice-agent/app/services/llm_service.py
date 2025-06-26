import os
from typing import AsyncGenerator
from livekit.agents import llm
from .llm.implementations.openai import OpenAILLMService

class LiveKitOpenAIAdapter(llm.LLM):
    """LiveKit adapter for our working OpenAI implementation"""
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7, timeout: float = 30.0):
        super().__init__()
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
    
    async def chat(
        self,
        chat_ctx: llm.ChatContext,
        conn_options: llm.LLMOptions = llm.LLMOptions(),
        fnc_ctx: llm.FunctionContext | None = None,
    ) -> llm.LLMStream:
        """Chat with the language model using LiveKit's interface"""
        await self._ensure_initialized()
        
        # Convert LiveKit ChatContext to OpenAI messages format
        messages = []
        for msg in chat_ctx.messages:
            if hasattr(msg, 'role') and hasattr(msg, 'text'):
                messages.append({
                    "role": msg.role,
                    "content": msg.text
                })
        
        # Use streaming for LiveKit compatibility
        stream = await self._openai_service._client.chat.completions.create(
            model=self._openai_service.config.get("model", "gpt-4o-mini"),
            messages=messages,
            temperature=self._openai_service.config.get("temperature", 0.7),
            stream=True
        )
        
        # Return LiveKit-compatible stream
        return OpenAILLMStream(stream)

class OpenAILLMStream(llm.LLMStream):
    """LiveKit-compatible stream wrapper for OpenAI streaming responses"""
    
    def __init__(self, openai_stream):
        super().__init__()
        self._openai_stream = openai_stream
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        try:
            chunk = await self._openai_stream.__anext__()
            if chunk.choices and chunk.choices[0].delta.content:
                # Return LiveKit ChatChunk
                return llm.ChatChunk(
                    choices=[
                        llm.Choice(
                            delta=llm.ChoiceDelta(
                                content=chunk.choices[0].delta.content,
                                role="assistant"
                            )
                        )
                    ]
                )
            else:
                # Continue to next chunk if this one is empty
                return await self.__anext__()
        except StopAsyncIteration:
            raise

def create_gpt4o_mini():
    """Create GPT-4o Mini LLM service using our working OpenAI implementation"""
    return LiveKitOpenAIAdapter(
        model="gpt-4o-mini",
        temperature=0.7,
        timeout=30.0
    )

def create_character_llm(character_personality):
    """Create LLM configured with character personality"""
    return create_gpt4o_mini() 