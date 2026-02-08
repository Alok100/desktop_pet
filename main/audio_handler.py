# EMO Assistant - Audio handler
# Microphone detection, PyAudio stream, volume, and WAV playback (e.g. for TTS).

import os
import re
import queue
import time
import subprocess
import numpy as np
import pyaudio
from scipy.signal import resample

from config import MIC_SAMPLE_RATE, VOSK_SAMPLE_RATE


def get_audio_output_devices():
    """List of (ALSA device, description) for playback (e.g. PAM8403 on audio jack)."""
    return [
        ("default", "System default"),
        ("sysdefault", "System default (alt)"),
        ("plughw:0,0", "Audio jack (card 0)"),
        ("plughw:1,0", "Audio jack (card 1)"),
        ("hw:0,0", "Hardware (card 0)"),
        ("hw:1,0", "Hardware (card 1)"),
    ]


def find_usb_microphone():
    """Return PyAudio input device index for USB/Jabra mic, or None."""
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and (
                "jabra" in info["name"].lower() or "usb" in info["name"].lower()
            ):
                return i
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                return i
        return None
    finally:
        p.terminate()


def find_default_output_device():
    """Return PyAudio default output device index, or None."""
    p = pyaudio.PyAudio()
    try:
        try:
            default_output = p.get_default_output_device_info()
            return default_output["index"]
        except Exception:
            pass
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0 and (
                "jabra" in info["name"].lower() or "usb" in info["name"].lower()
            ):
                return i
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0:
                return i
        return None
    finally:
        p.terminate()


def set_volume(volume_percent=100):
    """Set system/ALSA volume (e.g. for PAM8403). Returns True if any control was set."""
    try:
        print(f"🔊 Setting audio volume to {volume_percent}% (FULL)...")
        controls = ["PCM", "Master", "Speaker", "Headphone", "Playback"]
        volume_set = False
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "USB" in line or "Jabra" in line:
                    match = re.search(r"card (\d+):", line)
                    if match:
                        card_num = match.group(1)
                        for control in controls:
                            try:
                                r = subprocess.run(
                                    ["amixer", "-c", card_num, "sset", control, f"{volume_percent}%"],
                                    capture_output=True,
                                    timeout=2,
                                )
                                if r.returncode == 0:
                                    print(f"✓ Volume set to {volume_percent}% on card {card_num} ({control})")
                                    volume_set = True
                                subprocess.run(
                                    ["amixer", "-c", card_num, "sset", control, "unmute"],
                                    capture_output=True,
                                    timeout=2,
                                )
                            except Exception:
                                continue
        for control in controls:
            try:
                r = subprocess.run(
                    ["amixer", "sset", control, f"{volume_percent}%"],
                    capture_output=True,
                    timeout=2,
                )
                if r.returncode == 0:
                    print(f"✓ {control} volume set to {volume_percent}%")
                    volume_set = True
                subprocess.run(
                    ["amixer", "sset", control, "unmute"],
                    capture_output=True,
                    timeout=2,
                )
            except Exception:
                pass
        if not volume_set:
            print("⚠ Could not set volume automatically")
        return volume_set
    except Exception as e:
        print(f"⚠ Could not set volume: {e}")
        return False


def initialize_audio_devices():
    """
    Detect microphone and output device, set volume.
    Returns (audio_device_index, output_device_index).
    Raises on microphone test failure.
    """
    print("\n" + "=" * 60)
    print("🚀 Starting EMO Assistant")
    print("=" * 60)

    temp_p = pyaudio.PyAudio()
    audio_device = find_usb_microphone()
    output_device = find_default_output_device()

    if audio_device is None:
        print("⚠ Warning: Could not find USB microphone, using default input device")
    else:
        device_info = temp_p.get_device_info_by_index(audio_device)
        print(f"✓ USB microphone: {device_info['name']} (index {audio_device})")

    temp_p.terminate()

    print("✓ Audio output: PAM8403 speakers on audio jack")
    set_volume(100)

    print(f"🧪 Testing microphone at {MIC_SAMPLE_RATE}Hz...")
    test_p = pyaudio.PyAudio()
    try:
        test_kwargs = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": MIC_SAMPLE_RATE,
            "input": True,
            "frames_per_buffer": 8000,
        }
        if audio_device is not None:
            test_kwargs["input_device_index"] = audio_device
        test_stream = test_p.open(**test_kwargs)
        test_stream.close()
        test_p.terminate()
        print("✓ Microphone test passed")
    except Exception as e:
        test_p.terminate()
        print("\n" + "=" * 60)
        print("❌ FAILED TO INITIALIZE MICROPHONE")
        print("=" * 60)
        print(f"Error: {e}")
        print("   Check USB microphone connection and try again.")
        print("=" * 60 + "\n")
        raise
    print("=" * 60 + "\n")
    return audio_device, output_device


def make_audio_callback(audio_queue, mic_rate=MIC_SAMPLE_RATE, vosk_rate=VOSK_SAMPLE_RATE):
    """Return a PyAudio stream callback that resamples and pushes bytes into audio_queue."""

    def callback(in_data, frame_count, time_info, status):
        audio_np = np.frombuffer(in_data, dtype=np.int16)
        if mic_rate != vosk_rate:
            num_samples = int(len(audio_np) * vosk_rate / mic_rate)
            audio_resampled = resample(audio_np, num_samples).astype(np.int16)
            audio_queue.put(audio_resampled.tobytes())
        else:
            audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)

    return callback


def play_wav(wav_path, timeout=15):
    """
    Play a WAV file using aplay, trying devices from get_audio_output_devices().
    Returns True if playback succeeded on at least one device.
    """
    devices = get_audio_output_devices()
    time.sleep(0.2)
    for device, _ in devices:
        try:
            r = subprocess.run(
                ["aplay", "-D", device, "-q", wav_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            if r.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, Exception):
            continue
    return False
