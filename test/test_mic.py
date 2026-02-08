#!/usr/bin/env python3
"""
Simple microphone test script.
Lists input devices, records a short clip, and saves to WAV.
Uses pyaudio (same as emo_assistant). Run from desktop_pet/test/ or project root.
"""

import pyaudio
import wave
import sys

CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16
DURATION_SEC = 10
OUTPUT_FILE = "test_mic_output.wav"
# Use device's native sample rate (many USB mics use 44100, not 16000)


def list_input_devices():
    """Print all available input devices."""
    p = pyaudio.PyAudio()
    print("Available input devices:")
    print("-" * 60)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            default = " (default)" if i == p.get_default_input_device_info()["index"] else ""
            print(f"  [{i}] {info['name']}{default} - inputs: {info['maxInputChannels']}, sr: {info['defaultSampleRate']}")
    print("-" * 60)
    p.terminate()


def get_device_sample_rate(p, device_index):
    """Get the default sample rate for the given device."""
    if device_index is not None:
        info = p.get_device_info_by_index(device_index)
    else:
        info = p.get_default_input_device_info()
    return int(info["defaultSampleRate"])


def record_from_device(device_index=None):
    """Record DURATION_SEC seconds from the given device (or default). Returns (frames, sample_rate) or (None, None)."""
    p = pyaudio.PyAudio()
    sample_rate = get_device_sample_rate(p, device_index)
    stream_kwargs = {
        "format": FORMAT,
        "channels": CHANNELS,
        "rate": sample_rate,
        "input": True,
        "frames_per_buffer": CHUNK,
    }
    if device_index is not None:
        stream_kwargs["input_device_index"] = device_index

    try:
        stream = p.open(**stream_kwargs)
    except Exception as e:
        print(f"Failed to open stream: {e}")
        p.terminate()
        return None, None

    print(f"Recording for {DURATION_SEC} seconds at {sample_rate} Hz (device {device_index or 'default'})")
    frames = []
    num_chunks = int(sample_rate / CHUNK * DURATION_SEC)
    for _ in range(num_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()
    return b"".join(frames), sample_rate


def save_wav(frames, filepath, sample_rate):
    """Save raw PCM frames to a WAV file."""
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
        wf.setframerate(sample_rate)
        wf.writeframes(frames)


def main():
    print("=" * 50)
    print("Microphone test (pyaudio)")
    print("=" * 50)
    list_input_devices()

    # Use first CLI arg as device index if provided
    device_index = None
    if len(sys.argv) > 1:
        try:
            device_index = int(sys.argv[1])
            print(f"Using device index: {device_index}")
        except ValueError:
            print("Usage: python test_mic.py [device_index]")
            print("  device_index is optional; omit to use default input.")

    frames, sample_rate = record_from_device(device_index)
    if frames is None:
        sys.exit(1)

    save_wav(frames, OUTPUT_FILE, sample_rate)
    print(f"Done. Saved to {OUTPUT_FILE} ({sample_rate} Hz)")


if __name__ == "__main__":
    main()
