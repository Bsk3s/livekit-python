# Render Worker Deployment Fix

## Issue
The LiveKit agent worker deployment is failing with:
```
python: can't open file '/opt/render/project/src/python-voice-agent/python-voice-agent/app/agents/spiritual_worker.py': [Errno 2] No such file or directory
```

## Root Cause
The issue is that Render is creating a nested directory structure and the start command is using the wrong path.

## Solutions

### Option 1: Use Corrected Configuration
Use the `python-voice-agent/render-corrected.yaml` configuration file which properly handles the directory structure:

1. In your Render dashboard, go to your worker service settings
2. Update the start command to:
   ```bash
   cd python-voice-agent && python app/agents/spiritual_worker.py
   ```
3. Ensure the build command is:
   ```bash
   pip install --upgrade pip && pip install -r python-voice-agent/requirements.txt
   ```

### Option 2: Use Absolute Paths
Use the `render-absolute-paths.yaml` configuration which uses absolute paths:

1. Start command:
   ```bash
   export PYTHONPATH=/opt/render/project/src/python-voice-agent:$PYTHONPATH && cd /opt/render/project/src/python-voice-agent && python app/agents/spiritual_worker.py
   ```

### Option 3: Manual Fix in Render Dashboard
1. Go to your Render dashboard
2. Navigate to the failing worker service
3. Go to Settings → Build & Deploy
4. Update the start command to:
   ```bash
   cd python-voice-agent && python app/agents/spiritual_worker.py
   ```
5. Redeploy the service

### Option 4: Simpler Directory Structure (Recommended)
Move files to avoid nested structure:

1. Create a simple start script in the root directory
2. Use this as the start command:
   ```bash
   python -c "import sys; sys.path.append('python-voice-agent'); from python_voice_agent.app.agents.spiritual_worker import main; main()"
   ```

## Verification
After applying any fix, the worker should start successfully and you should see logs like:
```
🌟 Spiritual Guidance Agent Worker starting...
✅ Environment variables loaded
🔗 Connecting to LiveKit...
```

## Current Status
- ✅ Token API: Working at https://heavenly-new.onrender.com
- ❌ Worker Service: Needs path fix
- ✅ Dependencies: All installed correctly

## Next Steps
1. Apply one of the solutions above
2. Redeploy the worker service
3. Check logs for successful startup
4. Test with mobile client 