#!/usr/bin/env python3
"""
Interactive Text-to-Speech Testing
Type any text and hear it spoken
"""

import subprocess
import numpy as np
import wave
import io
import pyaudio
from scipy.signal import resample

AUDIO_DEVICE = 1
TARGET_RATE = 48000

def speak(text):
    """Speak the given text with smooth, natural audio"""
    try:
        # Generate audio with espeak using MBROLA female voice
        # -s 160 = moderate speed for natural feel
        # -p 50 = neutral pitch (more natural)
        # -g 3 = minimal word gaps for smoother flow
        # -a 100 = normal amplitude
        espeak_cmd = [
            "espeak", "-v", "mb/mb-us1", "-s", "160", 
            "-p", "50", "-g", "3", "-a", "100", 
            text, "--stdout"
        ]
        
        # Try using sox for better quality resampling (if available)
        try:
            # Use sox for high-quality resampling
            sox_cmd = ["sox", "-t", "wav", "-", "-t", "wav", "-", "rate", str(TARGET_RATE), "gain", "-1"]
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            sox_proc = subprocess.Popen(sox_cmd, stdin=espeak_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            espeak_proc.stdout.close()
            wav_data, _ = sox_proc.communicate()
            use_sox = True
        except (FileNotFoundError, subprocess.SubprocessError):
            # Fallback to scipy resampling if sox not available
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            wav_data, _ = espeak_proc.communicate()
            use_sox = False
        
        wav_io = io.BytesIO(wav_data)
        with wave.open(wav_io, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Resample if needed (sox already resamples to TARGET_RATE, so only resample if sox wasn't used)
        if not use_sox and sample_rate != TARGET_RATE:
            num_samples = int(len(audio_array) * TARGET_RATE / sample_rate)
            resampled = resample(audio_array, num_samples)
        else:
            resampled = audio_array
        
        audio_int16 = (resampled * 32767).astype(np.int16)
        audio_stereo = np.column_stack([audio_int16, audio_int16])
        
        # Play through USB speaker using PyAudio with chunked writing for smooth playback
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16, 
            channels=2, 
            rate=TARGET_RATE,
            output=True, 
            output_device_index=AUDIO_DEVICE,
            frames_per_buffer=4096  # Chunk size for smooth playback
        )
        
        # Write audio data in chunks to prevent buffer underruns
        chunk_size = 4096 * 2 * 2  # frames * channels * bytes per sample
        audio_bytes = audio_stereo.tobytes()
        
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            stream.write(chunk)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

print("=" * 60)
print("INTERACTIVE TEXT-TO-SPEECH TEST")
print("=" * 60)
print("\nType any text and press Enter to hear it spoken.")
print("Type 'quit' or 'exit' to stop.")
print("=" * 60)
print()

while True:
    text = input("💬 Enter text: ").strip()
    
    if text.lower() in ['quit', 'exit', 'q']:
        print("👋 Goodbye!")
        break
    
    if not text:
        print("⚠ Please enter some text")
        continue
    
    print(f"🔊 Speaking: {text}")
    if speak(text):
        print("✓ Done\n")
    else:
        print("✗ Failed\n")
