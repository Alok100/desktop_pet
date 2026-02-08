# EMO Assistant - Speech recognition (Vosk)
# Loads Vosk model and provides recognizer for streaming audio.

import json
from vosk import Model, KaldiRecognizer

from config import MODEL_PATH, VOSK_SAMPLE_RATE


def load_model(path=None):
    """Load Vosk model. Uses config.MODEL_PATH if path is None."""
    model_path = path or MODEL_PATH
    return Model(model_path)


def create_recognizer(model, sample_rate=VOSK_SAMPLE_RATE):
    """Create a KaldiRecognizer for streaming 16-bit mono at sample_rate."""
    return KaldiRecognizer(model, sample_rate)


def get_result_text(recognizer):
    """Get current result text from recognizer (partial). Returns empty string if none."""
    result = recognizer.Result()
    if not result:
        return ""
    data = json.loads(result)
    return (data.get("text") or "").strip()


def get_final_text(recognizer):
    """Get final result text. Call after feeding all chunks for an utterance."""
    data = json.loads(recognizer.FinalResult())
    return (data.get("text") or "").strip()
