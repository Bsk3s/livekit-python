# Contributing to Spiritual Voice Agent

Thank you for your interest in contributing to the Spiritual Voice Agent! This guide will help you get started with contributing to our professional Python package.

## 🚀 Quick Start for Contributors

### 1. Development Environment Setup

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/your-username/spiritual-voice-agent.git
cd spiritual-voice-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"
```

### 2. Environment Configuration

```bash
# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys (see README.md for details)
```

### 3. Verify Installation

```bash
# Test that imports work
python -c "from spiritual_voice_agent import __version__; print(f'Version: {__version__}')"

# Run tests to ensure everything works
python -m pytest --collect-only
```

## 🛠️ Development Workflow

### Code Quality Standards

We maintain high code quality standards. Please follow these guidelines:

#### 1. Code Formatting
```bash
# Format code with black
black spiritual_voice_agent/ tests/

# Sort imports with isort
isort spiritual_voice_agent/ tests/
```

#### 2. Linting
```bash
# Lint with flake8
flake8 spiritual_voice_agent/
```

#### 3. Type Checking
```bash
# Type check with mypy (when implemented)
mypy spiritual_voice_agent/
```

### Testing Requirements

- **All new code must have tests**
- **Existing tests must pass**
- **Aim for >80% code coverage**

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=spiritual_voice_agent

# Run specific test files
python -m pytest tests/unit/test_your_feature.py
```

### Git Workflow

1. **Create a feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make small, focused commits:**
```bash
git add .
git commit -m "feat: add new character personality system"
```

3. **Keep your branch up to date:**
```bash
git fetch origin
git rebase origin/main
```

4. **Push and create PR:**
```bash
git push origin feature/your-feature-name
# Create Pull Request on GitHub
```

## 📝 Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add support for custom TTS voices
fix: resolve import errors in character factory
docs: update API documentation for new endpoints
test: add integration tests for websocket audio
```

## 🏗️ Project Structure Understanding

### Key Components

- **`spiritual_voice_agent/main.py`** - FastAPI application
- **`spiritual_voice_agent/agents/`** - LiveKit agent workers
- **`spiritual_voice_agent/characters/`** - Character personality system
- **`spiritual_voice_agent/services/`** - Core services (LLM, STT, TTS)
- **`spiritual_voice_agent/routes/`** - API endpoints

### Architecture Principles

1. **Clean imports** - No `sys.path` hacks
2. **Service layer pattern** - Abstract interfaces with concrete implementations
3. **Character factory pattern** - Extensible character system
4. **Dependency injection** - Services configured via factory functions
5. **Async/await** - Non-blocking operations throughout

## 🎯 Contribution Areas

### High Priority
- [ ] Fix remaining test imports (legacy `app.` references)
- [ ] Add type hints throughout codebase
- [ ] Implement proper logging configuration
- [ ] Add monitoring and metrics
- [ ] Performance optimization

### Medium Priority
- [ ] Add new character personalities
- [ ] Improve TTS voice quality
- [ ] Add conversation memory
- [ ] Database integration for user sessions
- [ ] Rate limiting implementation

### Documentation
- [ ] API documentation improvements
- [ ] Code comment improvements
- [ ] Tutorial creation
- [ ] Video guides

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Environment details:**
   - Python version
   - Operating system
   - Package version

2. **Reproduction steps:**
   - Minimal code to reproduce
   - Expected vs actual behavior
   - Error messages/stack traces

3. **Context:**
   - What you were trying to accomplish
   - Any recent changes

## 💡 Feature Requests

For new features:

1. **Check existing issues** to avoid duplicates
2. **Describe the use case** clearly
3. **Explain the expected behavior**
4. **Consider backward compatibility**
5. **Volunteer to implement** if possible

## 📋 Pull Request Guidelines

### Before Submitting

- [ ] Tests pass: `python -m pytest`
- [ ] Code is formatted: `black . && isort .`
- [ ] Linting passes: `flake8 spiritual_voice_agent/`
- [ ] Documentation updated if needed
- [ ] Changes described in PR description

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Tests pass locally
- [ ] Documentation updated
```

## 🤝 Code Review Process

1. **All PRs require review** before merging
2. **Address feedback promptly**
3. **Keep PRs focused and small**
4. **Explain complex changes** in comments

## 📞 Getting Help

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Questions and general discussion
- **Documentation** - Check README.md and docs/ folder

## 🙏 Recognition

Contributors will be:
- Listed in the CONTRIBUTORS.md file
- Mentioned in release notes
- Given credit in documentation

Thank you for contributing to making spiritual guidance more accessible through technology! 🌟 