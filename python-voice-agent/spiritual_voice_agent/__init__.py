"""
Spiritual Voice Agent - Production-ready LiveKit voice agent for spiritual guidance.

A professional Python package providing AI-powered spiritual guidance through voice conversations 
with two distinct characters: Adina (compassionate) and Raffa (wise).

Features:
- FastAPI web server for token generation
- LiveKit agent workers for real-time voice interaction  
- Character-based personality system
- Production-ready deployment configurations
- Comprehensive test suite
- Modern Python packaging standards

Example:
    >>> from spiritual_voice_agent.main import app
    >>> from spiritual_voice_agent.characters.character_factory import CharacterFactory
    >>> characters = CharacterFactory.CHARACTER_CONFIGS.keys()
    >>> print(list(characters))
    ['adina', 'raffa']
"""

__version__ = "1.0.0"
__author__ = "Spiritual Voice Agent Team"
__email__ = "contact@spiritual-voice-agent.com"
__description__ = "Production-ready LiveKit voice agent for spiritual guidance"
__url__ = "https://github.com/yourusername/spiritual-voice-agent"

# Import key components for easier access
from spiritual_voice_agent.characters.character_factory import CharacterFactory
from spiritual_voice_agent.services.llm_service import create_gpt4o_mini

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "__url__",
    "CharacterFactory",
    "create_gpt4o_mini",
]
