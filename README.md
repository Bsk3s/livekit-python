# Clean LiveKit Voice Agent

A minimal LiveKit voice agent setup for TTS model development and testing.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

Required environment variables:
- `LIVEKIT_URL` - Your LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret
- `OPENAI_API_KEY` - OpenAI API key (for LLM and TTS)
- `DEEPGRAM_API_KEY` - Deepgram API key (for STT)

### 3. Run the Agent
```bash
python agent.py
```

## Project Structure

```
/
├── agent.py              # Main LiveKit agent
├── app/
│   ├── services/
│   │   ├── tts_service.py    # TTS service interface
│   │   ├── llm_service.py    # LLM service
│   │   └── deepgram_service.py # STT service
│   └── main.py           # API server (optional)
├── requirements.txt      # Dependencies
└── .env.example         # Environment template
```

## TTS Model Development

### Adding Custom TTS Models

1. Extend the `TTSService` class in `app/services/tts_service.py`
2. Implement your custom TTS logic in the `generate_speech` method
3. Update the agent to use your custom TTS service

Example:
```python
class MyCustomTTSService(TTSService):
    def __init__(self, model_path: str):
        self.model_path = model_path
        # Initialize your model here
    
    async def generate_speech(self, text: str, voice_config: dict = None):
        # Your custom TTS logic here
        pass
```

### Testing TTS Models

1. Create a test script to validate your TTS model
2. Test audio quality and latency
3. Integrate with the LiveKit agent for end-to-end testing

## Features

- **Clean Architecture**: Minimal, focused codebase
- **Easy Model Swapping**: Simple TTS service interface
- **LiveKit Integration**: Ready-to-use voice agent
- **Development Friendly**: Easy to extend and modify

## Troubleshooting

- **Connection Issues**: Check LiveKit URL and credentials
- **TTS Problems**: Verify OpenAI API key and voice configuration
- **STT Issues**: Ensure Deepgram API key is valid

## Next Steps

1. Implement your custom TTS model
2. Test with the LiveKit agent
3. Optimize for production use 