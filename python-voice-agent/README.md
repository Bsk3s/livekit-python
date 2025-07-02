# 🌟 Spiritual Guidance Voice Agent

A **production-ready** LiveKit voice agent providing spiritual guidance through AI-powered conversations with two distinct characters: **Adina** (compassionate) and **Raffa** (wise).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![LiveKit](https://img.shields.io/badge/LiveKit-Agents-purple.svg)](https://livekit.io)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Professional Python Package** - Properly structured, pip-installable, and production-ready.

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+** (recommended: 3.11 or 3.12)
- **LiveKit account** with API credentials ([Get started](https://livekit.io))
- **OpenAI API key** ([Get yours](https://platform.openai.com/api-keys))
- **Deepgram API key** ([Get yours](https://console.deepgram.com/))

### Installation

1. **Clone and install as a proper Python package:**
```bash
git clone <repository-url>
cd python-voice-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode (proper Python package)
pip install -e .
```

2. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```env
LIVEKIT_URL=wss://your-livekit-url
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
```

3. **Start the service (multiple ways):**
```bash
# Option 1: Unified service (recommended)
python start_unified_service.py

# Option 2: Using the installed package
python -m uvicorn spiritual_voice_agent.main:app --host 0.0.0.0 --port 8000

# Option 3: Development mode with auto-reload
uvicorn spiritual_voice_agent.main:app --reload --port 8000
```

This starts both:
- **🌐 Token API Server** (port 8000) - Issues LiveKit tokens
- **🤖 Agent Worker** - Handles voice conversations

## 🎭 Characters

### Adina - The Compassionate Guide
- **Voice:** Nova (warm, feminine)
- **Personality:** Empathetic, nurturing, gentle
- **Specialties:** Emotional support, self-compassion, healing

### Raffa - The Wise Mentor  
- **Voice:** Onyx (deep, masculine)
- **Personality:** Wise, grounded, philosophical
- **Specialties:** Life guidance, spiritual wisdom, perspective

## 🏗️ Architecture

**Professional Python Package Structure:**

```
python-voice-agent/
├── spiritual_voice_agent/           # 📦 Main package (pip installable)
│   ├── __init__.py                 # Package initialization
│   ├── main.py                     # 🌐 FastAPI application
│   ├── agents/                     # 🤖 LiveKit agent workers
│   │   ├── spiritual_worker.py     # Main production worker
│   │   └── __init__.py
│   ├── characters/                 # 🎭 Character definitions
│   │   ├── adina/                  # Compassionate guide
│   │   ├── raffa/                  # Wise mentor
│   │   ├── character_factory.py    # Character creation
│   │   └── base_character.py       # Base character interface
│   ├── services/                   # ⚙️ Core services
│   │   ├── llm/                    # 🧠 Language model services
│   │   ├── stt/                    # 🎧 Speech-to-text
│   │   ├── tts/                    # 🎙️ Text-to-speech
│   │   ├── livekit_token.py        # 🔑 Token generation
│   │   └── base_service.py         # Service interface
│   ├── routes/                     # 🛣️ API endpoints
│   │   ├── token.py                # Token generation
│   │   ├── websocket_audio.py      # WebSocket streaming
│   │   └── health.py               # Health checks
│   └── utils/                      # 🔧 Utilities
├── tests/                          # 🧪 Test suites
│   ├── integration/                # Integration tests
│   ├── unit/                       # Unit tests
│   └── conftest.py                 # Pytest configuration
├── docs/                           # 📚 Documentation
│   ├── API.md                      # API documentation
│   ├── DEPLOYMENT.md               # Deployment guide
│   └── PROJECT_STRUCTURE.md        # Architecture details
├── scripts/                        # 🚀 Deployment configs
├── pyproject.toml                  # 📋 Modern Python packaging
├── start_unified_service.py        # 🎯 Main entry point
└── README.md                       # 📖 This file
```

**Key Improvements:**
- ✅ **Proper Python package** - installable via `pip install -e .`
- ✅ **No sys.path hacks** - clean imports throughout
- ✅ **Modern packaging** - uses pyproject.toml
- ✅ **Pytest integration** - tests discoverable and runnable

## 🔧 Services

### Core Stack
- **Framework:** FastAPI
- **Real-time:** LiveKit WebRTC
- **LLM:** OpenAI GPT-4o Mini
- **STT:** Deepgram Nova-2
- **TTS:** OpenAI TTS-1 HD
- **VAD:** Silero Voice Activity Detection

### API Endpoints

- `GET /health` - Health check
- `GET /` - API information
- `POST /api/spiritual-token` - Generate LiveKit token
- `WS /ws/audio` - WebSocket audio streaming (if applicable)

## 🧪 Testing

**Modern pytest integration with proper test discovery:**

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests (auto-discovered)
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test categories
python -m pytest tests/integration/  # Integration tests
python -m pytest tests/unit/         # Unit tests

# Run with coverage
python -m pytest --cov=spiritual_voice_agent tests/

# Test collection (see what tests are found)
python -m pytest --collect-only
```

**Test Status:**
- ✅ **19 tests discoverable** (vs 0 before refactoring)
- ⚠️ **Some imports need fixing** (legacy `app.` references)
- ✅ **Pytest configuration** in pyproject.toml

## 👨‍💻 Development Workflow

### For Contributors

1. **Setup development environment:**
```bash
git clone <repository-url>
cd python-voice-agent
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"  # Installs with dev dependencies
```

2. **Code quality tools:**
```bash
# Format code
black spiritual_voice_agent/ tests/

# Sort imports
isort spiritual_voice_agent/ tests/

# Lint code
flake8 spiritual_voice_agent/

# Type checking
mypy spiritual_voice_agent/
```

3. **Run tests before commits:**
```bash
python -m pytest
```

4. **Create feature branch:**
```bash
git checkout -b feature/your-feature-name
# Make changes, commit, push, create PR
```

## 📦 Deployment

### Production Deployment (Render)

1. **Deploy to Render:**
   - Connect your repository
   - Use `render.yaml` for configuration
   - Set environment variables in Render dashboard

2. **Environment Variables:**
   Set all required variables in your deployment platform.

### Local Development

```bash
# Option 1: Unified service (both API + worker)
python start_unified_service.py

# Option 2: API only (for testing)
uvicorn spiritual_voice_agent.main:app --reload --port 8000

# Option 3: Worker only (separate terminal)
python spiritual_voice_agent/agents/spiritual_worker.py dev

# Option 4: Using installed package commands (if configured)
spiritual-agent          # FastAPI server
spiritual-worker dev     # Agent worker
```

## 🔍 Troubleshooting

### Common Issues

1. **"Illegal header value" errors:**
   - Check for trailing whitespace in API keys
   - Ensure environment variables are properly set

2. **LiveKit connection fails:**
   - Verify LIVEKIT_URL format (should start with `wss://`)
   - Check API credentials

3. **Audio issues:**
   - Ensure proper WebRTC permissions
   - Check microphone/speaker access

### Logs

Application logs are available at:
- Production: Stdout (captured by deployment platform)
- Development: `spiritual_agent.log`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review existing GitHub issues
3. Create a new issue with detailed information

---

**Built with ❤️ for spiritual guidance and human connection** 