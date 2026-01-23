#!/usr/bin/env python3
"""
Test different TTS voice options
"""

import subprocess
import numpy as np
import wave
import io
import sounddevice as sd
from scipy.signal import resample

test_text = "Hello! I am EMO, your friendly assistant. How can I help you today?"

def play_voice(voice_config, description):
    """Play a voice with given configuration"""
    print(f"\n{description}")
    print("-" * 60)
    print("🔊 Playing...")
    
    try:
        # Generate audio
        espeak_cmd = ["espeak"] + voice_config + [test_text, "--stdout"]
        espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        wav_data, _ = espeak_proc.communicate()
        
        # Read WAV data
        wav_io = io.BytesIO(wav_data)
        with wave.open(wav_io, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Resample to 48kHz
        TARGET_RATE = 48000
        num_samples = int(len(audio_array) * TARGET_RATE / sample_rate)
        resampled = resample(audio_array, num_samples)
        
        # Convert to stereo
        audio_stereo = np.column_stack([resampled, resampled])
        
        # Play
        sd.play(audio_stereo, TARGET_RATE, device=1)
        sd.wait()
        
        print("✓ Done")
        
    except Exception as e:
        print(f"✗ Error: {e}")

print("=" * 60)
print("VOICE COMPARISON TEST")
print("=" * 60)
print("\nYou will hear the same sentence in different voices.")
print("Choose the one that sounds most natural to you.")

# Option 1: Current improved voice
play_voice(
    ["-v", "mb/mb-us1", "-s", "150", "-p", "55", "-g", "5", "-a", "110"],
    "1. Current Voice (MBROLA US1 - improved)"
)

input("\nPress Enter for next voice...")

# Option 2: Different MBROLA female voice (Hungarian)
play_voice(
    ["-v", "mb/mb-hu1-en", "-s", "150", "-g", "5", "-a", "110"],
    "2. Hungarian Female Voice"
)

input("\nPress Enter for next voice...")

# Option 3: French female voice
play_voice(
    ["-v", "mb/mb-fr4-en", "-s", "150", "-g", "5", "-a", "110"],
    "3. French Female Voice"
)

input("\nPress Enter for next voice...")

# Option 4: Regular espeak with high pitch (no MBROLA)
play_voice(
    ["-v", "en", "-s", "150", "-p", "70", "-g", "5", "-a", "110"],
    "4. Regular espeak Female (higher pitch)"
)

input("\nPress Enter for next voice...")

# Option 5: UK female variant
play_voice(
    ["-v", "en-gb", "-s", "150", "-p", "65", "-g", "5", "-a", "110"],
    "5. UK English Female"
)

print("\n" + "=" * 60)
print("Which voice did you like best? (1-5)")
print("=" * 60)
