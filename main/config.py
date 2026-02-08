# EMO Assistant - Configuration
# Central place for wake words, sample rates, paths, and behavior flags.

import os

# Wake word and listening behavior
WAKE_WORDS = ["Bingo"]
USE_WAKE_WORD = False  # False = respond to any question; True = require wake word first

# Audio rates (Hz)
MIC_SAMPLE_RATE = 48000
VOSK_SAMPLE_RATE = 16000

# Timing
SPEECH_SPEED = 1.0  # TTS: 0.5=slower, 1.0=normal, 1.5=faster
COMMAND_LISTEN_TIME = 4  # seconds to listen for command after wake word
SILENCE_THRESHOLD = 2  # seconds of silence to consider question complete

# Paths: Vosk model (resolve relative to project root = parent of main/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(_PROJECT_ROOT, "vosk", "vosk-model-small-en-us-0.15")
