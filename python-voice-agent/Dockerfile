FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Copy code
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start app
CMD ["uvicorn", "spiritual_voice_agent.main:app", "--host", "0.0.0.0", "--port", "8080"] 