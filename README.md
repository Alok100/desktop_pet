# Desktop Pet - EMO Assistant

An interactive desktop pet assistant with voice recognition and text-to-speech capabilities, designed for Raspberry Pi.

## Features

- 🎤 **Voice Recognition**: Offline speech recognition using Vosk
- 🗣️ **Text-to-Speech**: Natural-sounding speech using Google Text-to-Speech (gTTS)
- 🤖 **AI Assistant**: Powered by Ollama LLM for intelligent responses
- 🔊 **USB Audio Support**: Works with USB microphones and speakers
- ⚡ **Offline Capable**: Speech recognition works completely offline

## Hardware Requirements

- Raspberry Pi (tested on Raspberry Pi with Linux)
- USB Microphone (tested with Jabra SPEAK 410 USB)
- USB Speaker (tested with Jabra SPEAK 410 USB)
- Optional: GPIO components for servo control

## System Dependencies

Before installing Python packages, install these system dependencies:

```bash
# Audio libraries
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
sudo apt-get install -y alsa-utils alsa-tools
sudo apt-get install -y ffmpeg sox

# For audio playback
sudo apt-get install -y mpg123 aplay
```

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd ~/desktop_pet
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Download Vosk model:**
   ```bash
   # Create vosk directory
   mkdir -p vosk
   cd vosk
   
   # Download a small English model (recommended for Raspberry Pi)
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   unzip vosk-model-small-en-us-0.15.zip
   
   # Or download a larger model for better accuracy
   # wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
   # unzip vosk-model-en-us-0.22.zip
   ```

5. **Install and setup Ollama (for LLM):**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull a small model (recommended for Raspberry Pi)
   ollama pull tinyllama
   
   # Or use a larger model if you have more resources
   # ollama pull llama2
   ```

## Configuration

### Audio Device Configuration

The project automatically detects USB audio devices. If you need to manually configure:

1. **List available audio devices:**
   ```bash
   aplay -l          # List playback devices
   arecord -l        # List recording devices
   ```

2. **Update device settings in `emo_assistant.py`:**
   ```python
   AUDIO_DEVICE = 1  # USB microphone device index
   TARGET_DEVICE = "plughw:3,0"  # USB speaker (card 3, device 0)
   ```

### Speech Recognition Settings

Edit `emo_assistant.py` to customize:

```python
USE_WAKE_WORD = False  # Set to True to require wake words
WAKE_WORDS = ["emo", "he moved", "a more", "email", "imo"]
SPEECH_SPEED = 1.0     # TTS speed: 0.5=slower, 1.0=normal, 1.5=faster
```

## Usage

### Main Assistant

Run the main EMO assistant:

```bash
source venv/bin/activate
python emo_assistant.py
```

The assistant will:
1. Load the Vosk speech recognition model
2. Start listening for your voice
3. Respond to questions using the Ollama LLM
4. Speak responses using Google TTS

### Test Text-to-Speech

Test the TTS system independently:

```bash
source venv/bin/activate
python test_tts_simple.py
```

This will generate and play a test phrase through your USB speaker.

## Project Structure

```
desktop_pet/
├── emo_assistant.py      # Main assistant application
├── test_tts_simple.py     # TTS testing script
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── vosk/                # Vosk model directory
│   └── vosk-model-small-en-us-0.15/
└── test/                # Test scripts
    ├── record_and_play.py
    ├── testLLM.py
    └── servo_test.py
```

## Troubleshooting

### Audio Device Issues

**Problem**: "Invalid number of channels" or "Invalid input device"

**Solution**: 
- Check device indices with `aplay -l` and `arecord -l`
- Update `AUDIO_DEVICE` and `TARGET_DEVICE` in the code
- Try using default devices (set `AUDIO_DEVICE = None`)

**Problem**: "Unknown error 524" or playback fails

**Solution**:
- Verify USB speaker is card 3: `aplay -l`
- Update `TARGET_DEVICE = "plughw:3,0"` if needed
- Test with: `speaker-test -D plughw:3,0 -t wav -c 2 -l 1`

### MP3 Playback Issues

**Problem**: `mpg123` fails with JACK errors

**Solution**: The code now uses `ffmpeg` + `aplay` instead of `mpg123` for better compatibility.

### Speech Recognition Not Working

**Problem**: Vosk not recognizing speech

**Solution**:
- Check microphone is working: `arecord -D plughw:3,0 -f S16_LE -r 16000 test.wav`
- Verify model path in `MODEL_PATH` variable
- Try a larger Vosk model for better accuracy

### LLM Issues

**Problem**: Ollama not responding

**Solution**:
- Check Ollama is running: `ollama list`
- Verify model is downloaded: `ollama pull tinyllama`
- Check Ollama service: `systemctl status ollama`

## Dependencies

See `requirements.txt` for complete list. Main dependencies:

- **pyaudio**: Audio input/output
- **vosk**: Offline speech recognition
- **gtts**: Google Text-to-Speech
- **langchain-ollama**: LLM integration
- **numpy/scipy**: Scientific computing

## License

This project is for personal/educational use.

## Notes

- Designed for Raspberry Pi but should work on other Linux systems
- Speech recognition works completely offline (Vosk)
- Text-to-speech requires internet connection (Google TTS)
- LLM requires Ollama to be running locally
