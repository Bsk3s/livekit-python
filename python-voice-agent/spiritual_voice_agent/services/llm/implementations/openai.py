import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import openai

from ..base import BaseLLMService


class OpenAILLMService(BaseLLMService):
    """OpenAI implementation of the LLM service."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._client = None
        self._initialized = False

    def _validate_config(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set or empty")

    async def initialize(self) -> None:
        if not self._initialized:
            self._client = openai.AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY", "").strip(),
                base_url=self.config.get("base_url"),
                timeout=self.config.get("timeout", 30.0),
            )
            self._initialized = True

    async def shutdown(self) -> None:
        if self._client:
            # Add any necessary cleanup
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def generate_response(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not self._initialized:
            await self.initialize()

        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self.config.get("model", "gpt-4"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        return response.choices[0].message.content

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        if not self._initialized:
            await self.initialize()

        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        stream = await self._client.chat.completions.create(
            model=self.config.get("model", "gpt-4"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
