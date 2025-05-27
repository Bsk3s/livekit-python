from livekit.agents import Agent, function_tool, RunContext
from typing import Dict, Any

class VoiceAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Voice Assistant",
            description="A voice-enabled AI assistant that can help with various tasks",
            instructions="""You are a helpful voice assistant. 
            Be concise and natural in your responses.
            Use a friendly and professional tone."""
        )

    @function_tool
    async def get_weather(self, context: RunContext, location: str) -> Dict[str, Any]:
        """Get weather information for a location."""
        # Implement weather lookup logic here
        return {"weather": "sunny", "temperature": 70}

    async def on_message(self, context: RunContext, message: str) -> str:
        """Handle incoming messages and generate responses."""
        # Process the message and generate a response
        response = await self.llm.chat(
            messages=[{"role": "user", "content": message}],
            stream=False
        )
        return response.content 