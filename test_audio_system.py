#!/usr/bin/env python3
"""
Audio System Test Script
Tests microphone input and speaker output
"""

import sounddevice as sd
import subprocess
import time
import numpy as np
from scipy.signal import resample

print("=" * 60)
print("AUDIO SYSTEM TEST")
print("=" * 60)
print()

# Configuration
USB_MIC_DEVICE = 1  # Jabra USB device for recording
SAMPLE_RATE = 16000
DURATION = 10

def test_speaker():
    """Test speaker output with female voice"""
    print("TEST 1: Testing Speaker Output")
    print("-" * 60)
    print("🔊 Playing test message through USB speaker...")
    
    try:
        text = "Hello! This is a test of the audio system. Can you hear me clearly?"
        
        # Generate speech with female voice
        espeak_cmd = ["espeak", "-v", "mb/mb-us1", "-s", "200", text, "--stdout"]
        sox_cmd = ["sox", "-t", "wav", "-", "-t", "wav", "-", "rate", "48000"]
        aplay_cmd = ["aplay", "-D", "plughw:1,0", "-q"]
        
        # Pipeline
        espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        sox_proc = subprocess.Popen(sox_cmd, stdin=espeak_proc.stdout, stdout=subprocess.PIPE, 
                                    stderr=subprocess.DEVNULL)
        espeak_proc.stdout.close()
        aplay_proc = subprocess.Popen(aplay_cmd, stdin=sox_proc.stdout, 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
        sox_proc.stdout.close()
        aplay_proc.communicate()
        
        print("✓ Speaker test complete")
        return True
    except Exception as e:
        print(f"✗ Speaker test failed: {e}")
        return False

def test_microphone():
    """Test microphone input"""
    print()
    print("TEST 2: Testing Microphone Input")
    print("-" * 60)
    print(f"🎤 Recording {DURATION} seconds from USB microphone...")
    print("   Please speak into the microphone now!")
    print()
    
    try:
        # Record audio
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            device=USB_MIC_DEVICE,
            dtype='float32'
        )
        sd.wait()
        
        # Analyze recording
        max_level = np.max(np.abs(recording))
        rms_level = np.sqrt(np.mean(recording**2))
        
        print(f"✓ Recording complete")
        print(f"  Max amplitude: {max_level:.4f}")
        print(f"  RMS level: {rms_level:.4f}")
        
        if max_level < 0.01:
            print("  ⚠ WARNING: Very low audio level - microphone might not be working")
            return False
        else:
            print("  ✓ Microphone is capturing audio")
            return True
            
    except Exception as e:
        print(f"✗ Microphone test failed: {e}")
        return False

def test_record_and_playback():
    """Record from mic and play back through speaker"""
    print()
    print("TEST 3: Record & Playback Test")
    print("-" * 60)
    print(f"🎤 Recording {DURATION} seconds...")
    print("   Say something into the microphone!")
    print()
    
    try:
        # Record
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            device=USB_MIC_DEVICE,
            dtype='float32'
        )
        sd.wait()
        print("✓ Recording complete")
        
        time.sleep(1)
        
        # Playback through USB speaker
        print("🔊 Playing back what you said...")
        
        # Resample from 16kHz to 48kHz to match USB speaker rate
        TARGET_RATE = 48000  # USB speaker rate
        num_samples = int(len(recording) * TARGET_RATE / SAMPLE_RATE)
        resampled = resample(recording, num_samples)
        
        # Convert to stereo for USB speaker
        recording_stereo = np.repeat(resampled, 2, axis=1)
        sd.play(recording_stereo, TARGET_RATE, device=USB_MIC_DEVICE)
        sd.wait()
        
        print("✓ Playback complete")
        return True
        
    except Exception as e:
        print(f"✗ Record & playback failed: {e}")
        return False

# Run tests
print("Available audio devices:")
print(sd.query_devices())
print()
print("=" * 60)
print()

test1 = test_speaker()
test2 = test_microphone()
test3 = test_record_and_playback()

print()
print("=" * 60)
print("TEST RESULTS")
print("=" * 60)
print(f"Speaker Test:          {'✓ PASS' if test1 else '✗ FAIL'}")
print(f"Microphone Test:       {'✓ PASS' if test2 else '✗ FAIL'}")
print(f"Record & Playback:     {'✓ PASS' if test3 else '✗ FAIL'}")
print("=" * 60)

if test1 and test2 and test3:
    print("✓ All tests passed! Audio system is working.")
else:
    print("⚠ Some tests failed. Check the errors above.")
