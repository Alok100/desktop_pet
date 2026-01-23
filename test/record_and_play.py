import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import sys

# Configuration
SAMPLE_RATE = 16000  # Hz (Jabra SPEAK 410 USB native sample rate)
DURATION = 5  # seconds
DEVICE = 1  # Jabra SPEAK 410 USB (index from query_devices)
OUTPUT_FILE = "recording.wav"

print("=" * 50)
print("USB Microphone Recorder & Player")
print("=" * 50)
print()

print("Available audio devices:")
print(sd.query_devices())
print()

# Record audio
print(f"📼 Recording for {DURATION} seconds from device {DEVICE}...")
print("🎤 Speak into your USB microphone now!")
print()

try:
    recording = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,  # mono recording
        device=DEVICE,
        dtype='float32'
    )
    sd.wait()  # Wait until recording is finished
    
    print("✓ Recording finished!")
    
    # Save to WAV file
    # Convert float32 to int16 for WAV file
    recording_int16 = np.int16(recording * 32767)
    write(OUTPUT_FILE, SAMPLE_RATE, recording_int16)
    print(f"✓ Saved to {OUTPUT_FILE}")
    print()
    
    # Play back the recorded audio
    print("🔊 Playing back the recording...")
    
    # Option 1: Try playing through default output device (usually better quality)
    try:
        print("   Using default audio output...")
        sd.play(recording, SAMPLE_RATE)  # Use system default output
        sd.wait()
    except Exception as e:
        print(f"   Default output failed: {e}")
        print("   Trying USB device output...")
        # Option 2: Convert mono to stereo for USB device playback
        recording_stereo = np.repeat(recording, 2, axis=1)
        sd.play(recording_stereo, SAMPLE_RATE, device=DEVICE)
        sd.wait()
    
    print("✓ Playback finished!")
    print()
    print("=" * 50)
    
except KeyboardInterrupt:
    print("\n⚠ Interrupted by user")
    sys.exit(0)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
