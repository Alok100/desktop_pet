# EMO Assistant - Text-to-speech (gTTS + playback)
# Generates speech with Google TTS, converts to WAV, plays via audio_handler.

import os
import tempfile
import subprocess

from gtts import gTTS

from config import SPEECH_SPEED
from audio_handler import get_audio_output_devices, play_wav


def speak(text, speed=SPEECH_SPEED):
    """
    Speak text using gTTS: generate MP3, convert to WAV with ffmpeg, play with aplay.
    Returns True on success.
    """
    try:
        use_slow = speed < 0.75
        tts = gTTS(text=text, lang="en", slow=use_slow)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_mp3 = f.name
        try:
            tts.save(tmp_mp3)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_wav = f.name
            try:
                if abs(speed - 1.0) < 0.01:
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-i", tmp_mp3,
                        "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y", tmp_wav,
                    ]
                else:
                    tempo = max(0.5, min(2.0, speed))
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-i", tmp_mp3,
                        "-af", f"atempo={tempo}", "-acodec", "pcm_s16le",
                        "-ar", "48000", "-ac", "2", "-y", tmp_wav,
                    ]
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                if r.returncode != 0:
                    if r.stderr:
                        print(f"⚠ ffmpeg: {r.stderr.decode()}")
                    return False

                return play_wav(tmp_wav, timeout=15)
            finally:
                if os.path.exists(tmp_wav):
                    os.unlink(tmp_wav)
        finally:
            if os.path.exists(tmp_mp3):
                os.unlink(tmp_mp3)
    except Exception as e:
        print(f"⚠ TTS error: {e}")
        import traceback
        traceback.print_exc()
        return False
