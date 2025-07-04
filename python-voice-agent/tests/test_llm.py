import os
from dotenv import load_dotenv
from spiritual_voice_agent.services.llm_service import create_gpt4o_mini
from spiritual_voice_agent.characters.raffa.personality import RaffaPersonality
from livekit.agents import llm
import asyncio

def test_llm():
    print("\n=== GPT-4o Mini LLM Test ===")
    load_dotenv()
    llm_model = create_gpt4o_mini()
    chat_ctx = llm.ChatContext()
    # Add system prompt (character instructions)
    chat_ctx.append(role="system", text=RaffaPersonality.INSTRUCTIONS)
    # Add user message
    chat_ctx.append(role="user", text="Say hello to the user.")
    print(f"System prompt: {RaffaPersonality.INSTRUCTIONS}")
    print(f"User prompt: Say hello to the user.")
    async def run():
        response_stream = await llm_model.chat(chat_ctx=chat_ctx)
        full_response = ""
        async for chunk in response_stream:
            if hasattr(chunk, "text") and chunk.text:
                full_response += chunk.text
            elif hasattr(chunk, "content") and chunk.content:
                full_response += chunk.content
        print("Response:", full_response)
    asyncio.run(run())

if __name__ == "__main__":
    test_llm() 