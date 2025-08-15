FROM python:3.11-slim

WORKDIR /app

# Copy everything
COPY . .

# List files to debug
RUN echo "=== FILES AFTER COPY ===" && ls -la

# Install minimal deps
RUN pip install fastapi uvicorn python-dotenv

# Debug what files exist at runtime
CMD ["sh", "-c", "echo '=== RUNTIME FILES ===' && ls -la && echo '=== LOOKING FOR PYTHON FILES ===' && find . -name '*.py' && echo '=== TRYING TO RUN ===' && python start_unified_service.py"]