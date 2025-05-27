#!/usr/bin/env python3

import asyncio
import time
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def simple_openai_test():
    """Simple OpenAI TTS test"""
    print("🚀 Simple OpenAI TTS Test")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found")
        return
    
    client = AsyncOpenAI(api_key=api_key)
    
    test_text = "Hello, this is a test."
    
    try:
        print(f"📡 Testing: '{test_text}'")
        start_time = time.perf_counter()
        
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=test_text,
            response_format="mp3"
        )
        
        audio_content = response.content
        response_time = (time.perf_counter() - start_time) * 1000
        
        print(f"✅ Success!")
        print(f"   Response time: {response_time:.0f}ms")
        print(f"   Audio bytes: {len(audio_content)}")
        
        if response_time < 1500:
            print("🎯 Under 1.5s target!")
        else:
            print("❌ Over 1.5s target")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(simple_openai_test()) 