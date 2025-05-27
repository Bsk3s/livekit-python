#!/bin/bash

echo "🚀 Setting up Heavenly Hub Voice Agent - Expo Client"
echo "=================================================="

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install Node.js first."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Check if Expo CLI is installed
if ! command -v expo &> /dev/null; then
    echo "📱 Installing Expo CLI..."
    npm install -g @expo/cli
fi

# Get local IP address
echo "🌐 Detecting your local IP address..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    LOCAL_IP=$(hostname -I | awk '{print $1}')
else
    echo "⚠️  Please manually find your local IP address and update App.js"
    LOCAL_IP="YOUR_SERVER_IP"
fi

echo "📝 Your local IP address appears to be: $LOCAL_IP"
echo ""
echo "🔧 Next steps:"
echo "1. Update App.js with your server IP:"
echo "   Replace 'http://localhost:8000' with 'http://$LOCAL_IP:8000'"
echo ""
echo "2. Start your Python voice agent backend:"
echo "   cd ../python-voice-agent"
echo "   source venv311/bin/activate"
echo "   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "3. Start LiveKit agent (in another terminal):"
echo "   cd python-voice-agent"
echo "   source venv311/bin/activate"
echo "   python app/agents/spiritual_session.py dev"
echo ""
echo "4. Start Expo development server:"
echo "   npm start"
echo ""
echo "✅ Setup complete! Follow the steps above to start testing." 