# 🎯 Interruption System Documentation

The interruption system enables real-time conversation interruptions, allowing users to cut off AI responses mid-stream for natural, bidirectional conversations.

## Overview

### What It Does
- **Real-time Detection**: Detects user speech during AI responses
- **Instant Cancellation**: Cancels ongoing TTS streaming within milliseconds
- **Natural Flow**: Returns conversation to LISTENING state for immediate user input
- **Performance Monitoring**: Tracks interruption latency and success rates

### Built on VAD Decoupling Foundation
The interruption system builds on the VAD decoupling implementation, which provides:
- Always-on VAD processing regardless of conversation state
- Speech detection during RESPONDING state
- Enhanced event structure with conversation context

## Architecture

### Core Components

#### 1. Interruption Detection (`_handle_potential_interruption`)
```python
# Triggered when speech is detected during RESPONDING state
await self._handle_potential_interruption(websocket, confidence, audio_energy, current_time)
```

**Detection Criteria:**
- Speech confidence > interruption threshold (default: 1.5)
- Not in cooldown period (default: 1.0 seconds)
- Active TTS streaming task exists
- Interruption system enabled

#### 2. TTS Cancellation (`stream_tts_chunks`)
```python
# Cancellable TTS streaming with interruption checks
self._current_tts_task = asyncio.create_task(stream_tts_chunks())
await self._current_tts_task
```

**Cancellation Points:**
- Before processing each audio chunk
- Before sending audio to client
- Via asyncio.Task.cancel() on interruption

#### 3. State Management
```python
# State transitions during interruption
RESPONDING → interruption_detected → LISTENING
```

## Configuration

### Sensitivity Settings

#### Interruption Threshold
```json
{
  "type": "configure_interruption",
  "threshold": 1.5,  // Lower = more sensitive (range: 0.5-3.0)
  "cooldown": 1.0    // Seconds between interruptions (range: 0.1-5.0)
}
```

**Threshold Guidelines:**
- `0.5-1.0`: Very sensitive (may trigger on background noise)
- `1.0-1.5`: Balanced (recommended for most users)
- `1.5-2.0`: Conservative (requires clear speech)
- `2.0+`: Very conservative (requires loud, clear speech)

#### Enable/Disable
```json
{
  "type": "enable_interruption",
  "enabled": true  // Toggle interruption system
}
```

### Default Configuration
```python
self._interruption_enabled = True
self._interruption_threshold = 1.5
self._interruption_cooldown = 1.0
```

## WebSocket API

### Control Messages

#### Configure Sensitivity
```json
{
  "type": "configure_interruption",
  "threshold": 1.2,
  "cooldown": 0.8
}
```

**Response:**
```json
{
  "type": "interruption_configured",
  "threshold": 1.2,
  "cooldown": 0.8,
  "timestamp": "2025-01-04T04:29:38.806342"
}
```

#### Toggle System
```json
{
  "type": "enable_interruption",
  "enabled": false
}
```

**Response:**
```json
{
  "type": "interruption_toggled",
  "interruption_enabled": false,
  "timestamp": "2025-01-04T04:29:38.806342"
}
```

#### Get Statistics
```json
{
  "type": "get_interruption_stats"
}
```

**Response:**
```json
{
  "type": "interruption_stats",
  "interruption_enabled": true,
  "interruption_threshold": 1.5,
  "total_interruptions": 3,
  "avg_interruption_latency_ms": 23.4,
  "has_active_tts": false,
  "timestamp": "2025-01-04T04:29:38.806342"
}
```

### Event Messages

#### Interruption Detected
```json
{
  "type": "interruption_detected",
  "confidence": 2.1,
  "energy": 21683.2,
  "chunks_interrupted": 3,
  "interruption_latency_ms": 24.5,
  "conversation_state": "LISTENING",
  "timestamp": "2025-01-04T04:29:38.806342"
}
```

#### Response Interrupted
```json
{
  "type": "response_interrupted",
  "character": "adina",
  "chunks_sent": 3,
  "total_chunks": 8,
  "conversation_turn": 5,
  "timestamp": "2025-01-04T04:29:38.806342"
}
```

## Performance

### Latency Targets

| Component | Target | Typical |
|-----------|---------|---------|
| Interruption Detection | <10ms | ~2-5ms |
| TTS Cancellation | <50ms | ~20-30ms |
| State Transition | <5ms | ~1-3ms |
| Total Interruption | <50ms | ~25-40ms |

### Monitoring

#### Performance Metrics
```python
{
  "interruption_performance": {
    "total_interruptions": 5,
    "avg_latency_ms": 28.3,
    "max_latency_ms": 45.2,
    "min_latency_ms": 18.7,
    "target_met": true,  // All interruptions <50ms
    "enabled": true,
    "threshold": 1.5,
    "cooldown": 1.0
  }
}
```

#### Memory Usage
- **Per Session**: <1KB overhead
- **Tracking Data**: ~50 latency measurements stored
- **Background Tasks**: Minimal impact

## Testing

### Test Files

#### Comprehensive Test Suite
```bash
python test_interruption_system.py
```
- Configuration controls validation
- Real interruption during AI response
- Performance measurement
- Success/failure analysis

#### Simple Validation
```bash
python test_simple_interruption.py
```
- Quick interruption test
- Basic functionality verification
- Pass/fail result

### Test Scenarios

#### 1. Successful Interruption
1. AI starts long response
2. User speaks after 2 audio chunks
3. System detects interruption within 50ms
4. TTS cancelled, state → LISTENING
5. User can immediately speak again

#### 2. Sensitivity Testing
1. Configure different thresholds (0.5, 1.0, 1.5, 2.0)
2. Test with various audio energy levels
3. Verify appropriate triggering behavior

#### 3. Performance Validation
1. Measure interruption latency over multiple tests
2. Verify <50ms target consistently met
3. Monitor memory and CPU impact

## Implementation Details

### Code Structure

#### Session Variables
```python
# Interruption state tracking
self._interruption_enabled = True
self._current_tts_task: Optional[asyncio.Task] = None
self._response_chunks_sent = 0
self._interruption_threshold = 1.5
self._interruption_cooldown = 1.0
self._last_interruption_time = 0
self._stream_cancelled = False
```

#### Core Detection Logic
```python
async def _handle_potential_interruption(self, websocket, confidence, audio_energy, current_time):
    # Validate interruption criteria
    if not self._interruption_enabled:
        return
    if current_time - self._last_interruption_time < self._interruption_cooldown:
        return
    if confidence < self._interruption_threshold:
        return
    if not self._current_tts_task or self._current_tts_task.done():
        return
    
    # Execute interruption
    self._stream_cancelled = True
    self._current_tts_task.cancel()
    self._set_state("LISTENING")
    
    # Send interruption event
    await websocket.send_json({
        "type": "interruption_detected",
        "confidence": confidence,
        "interruption_latency_ms": latency_ms,
        # ... additional data
    })
```

#### TTS Streaming with Cancellation
```python
async def stream_tts_chunks():
    for i, chunk_text in enumerate(chunks):
        # Check for cancellation
        if self._stream_cancelled:
            break
            
        # Generate audio
        wav_audio = await self.synthesize_speech_chunk(chunk_text)
        
        # Final cancellation check
        if self._stream_cancelled:
            break
            
        # Send to client
        await websocket.send_json({...})
        self._response_chunks_sent += 1

# Execute with cancellation support
self._current_tts_task = asyncio.create_task(stream_tts_chunks())
try:
    await self._current_tts_task
except asyncio.CancelledError:
    logger.info("TTS streaming cancelled by interruption")
```

## Troubleshooting

### Common Issues

#### 1. Interruptions Not Detected
**Symptoms:** Speech during AI response doesn't trigger interruption

**Solutions:**
- Check interruption system enabled: `{"type": "get_interruption_stats"}`
- Lower threshold: `{"type": "configure_interruption", "threshold": 1.0}`
- Verify audio energy levels in logs
- Check cooldown period hasn't expired

#### 2. False Positive Interruptions
**Symptoms:** Background noise triggers interruptions

**Solutions:**
- Raise threshold: `{"type": "configure_interruption", "threshold": 2.0}`
- Check microphone sensitivity
- Improve audio environment
- Adjust VAD threshold in AudioSession

#### 3. High Interruption Latency
**Symptoms:** >50ms interruption response time

**Solutions:**
- Check system performance
- Verify TTS chunk sizes aren't too large
- Monitor asyncio event loop health
- Review network latency to client

#### 4. TTS Not Cancelling
**Symptoms:** AI continues speaking after interruption

**Solutions:**
- Verify TTS task tracking in logs
- Check asyncio.CancelledError handling
- Ensure state transitions working
- Review WebSocket connection stability

### Debug Information

#### Logging Levels
```python
# Enable detailed interruption logging
logger.setLevel(logging.DEBUG)
```

**Key Log Messages:**
- `🎯 🚨 INTERRUPTION DETECTED!`
- `🎯 ✂️ TTS streaming cancelled`
- `🎯 ✅ Interruption handled in X.Xms`

#### Performance Monitoring
```json
{
  "type": "get_performance_summary"
}
```

Monitor `interruption_performance` section for:
- Total interruption count
- Average/max latency
- Target achievement rate

## Future Enhancements

### Planned Features

#### 1. Smart Sensitivity Adjustment
- Automatic threshold adjustment based on user patterns
- Environmental noise adaptation
- Per-user sensitivity learning

#### 2. Interruption Context Awareness
- Different thresholds for different conversation contexts
- Emotion-aware interruption sensitivity
- Content-based interruption filtering

#### 3. Advanced TTS Control
- Partial chunk completion before interruption
- Smooth audio fadeout instead of abrupt stop
- Resume-from-interruption capability

#### 4. Analytics and Insights
- User interruption patterns analysis
- Conversation flow optimization
- A/B testing of interruption parameters

### Integration Possibilities

#### Voice Activity Classification
- Distinguish speech types (question, statement, interjection)
- Context-aware interruption decisions
- Multi-speaker conversation support

#### Conversation Flow Analysis
- Track interruption impact on conversation quality
- Optimize response timing based on interruption patterns
- Improve turn-taking naturalness

## Conclusion

The interruption system provides the foundation for natural, bidirectional conversations by enabling real-time response cancellation. Built on the VAD decoupling architecture, it maintains excellent performance while adding sophisticated interruption capabilities.

Key benefits:
- **Natural Conversations**: Users can interrupt like in human conversation
- **Low Latency**: <50ms interruption response time
- **Configurable**: Adjustable sensitivity and behavior
- **Reliable**: Robust error handling and state management
- **Monitored**: Comprehensive performance tracking

The system is ready for production use and provides the groundwork for advanced conversational AI interactions. 