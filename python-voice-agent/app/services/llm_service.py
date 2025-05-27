from livekit.plugins import openai

def create_gpt4o_mini():
    return openai.LLM(
        model="gpt-4o-mini",
        temperature=0.7
    ) 