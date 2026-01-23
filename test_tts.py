#!/usr/bin/env python3
"""
Simple Text-to-Speech Testing Script
Tests the current TTS configuration used in EMO
"""

import subprocess
import numpy as np
import wave
import io
import pyaudio
from scipy.signal import resample

# Configuration (same as EMO)
AUDIO_DEVICE = 1  # USB Jabra speaker
SOURCE_RATE = 16000  # espeak output rate
TARGET_RATE = 48000  # USB speaker rate

def text_to_audio(text):
    """Convert text to speech and play through USB speaker"""
    print(f"\n📝 Text: {text}")
    print("🔊 Playing audio...")
    
    try:
        # Generate audio with espeak using MBROLA female voice
        espeak_cmd = [
            "espeak",
            "-v", "mb/mb-us1",  # Female US voice
            "-s", "150",         # Speed
            "-p", "55",          # Pitch
            "-g", "5",           # Word gaps
            "-a", "110",         # Amplitude
            text,
            "--stdout"
        ]
        
        # Get audio from espeak
        espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        wav_data, _ = espeak_proc.communicate()
        
        # Read WAV data
        wav_io = io.BytesIO(wav_data)
        with wave.open(wav_io, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        print(f"  Original rate: {sample_rate} Hz")
        print(f"  Original samples: {len(audio_array)}")
        
        # Resample to match USB speaker
        num_samples = int(len(audio_array) * TARGET_RATE / sample_rate)
        resampled = resample(audio_array, num_samples)
        
        print(f"  Resampled to: {TARGET_RATE} Hz")
        print(f"  Resampled samples: {len(resampled)}")
        
        # Convert to int16 for PyAudio
        audio_int16 = (resampled * 32767).astype(np.int16)
        
        # Convert to stereo
        audio_stereo = np.column_stack([audio_int16, audio_int16])
        
        # Play through USB speaker
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=TARGET_RATE,
            output=True,
            output_device_index=AUDIO_DEVICE
        )
        
        stream.write(audio_stereo.tobytes())
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        print("✓ Audio playback complete")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Main test
print("=" * 60)
print("TEXT-TO-SPEECH TEST")
print("=" * 60)
print("\nThis tests the same TTS configuration used in EMO.")
print()

# Test 1: Simple greeting
success1 = text_to_audio("Hello! I am EMO, your friendly assistant.")

input("\nPress Enter for next test...")

# Test 2: Longer sentence
success2 = text_to_audio("The sky appears blue because molecules in the air scatter blue light from the sun.")

input("\nPress Enter for next test...")

# Test 3: Question
success3 = text_to_audio("How can I help you today? Just ask me anything!")

print("\n" + "=" * 60)
print("TEST RESULTS")
print("=" * 60)
print(f"Test 1 (Greeting):    {'✓ PASS' if success1 else '✗ FAIL'}")
print(f"Test 2 (Long text):   {'✓ PASS' if success2 else '✗ FAIL'}")
print(f"Test 3 (Question):    {'✓ PASS' if success3 else '✗ FAIL'}")
print("=" * 60)

if success1 and success2 and success3:
    print("\n✓ All tests passed! TTS is working correctly.")
    print("  The same configuration will work in EMO.")
else:
    print("\n⚠ Some tests failed. Check the errors above.")

print("\n💡 To test custom text, modify this script or run:")
print("   python test_tts.py")
