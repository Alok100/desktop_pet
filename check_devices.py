#!/usr/bin/env python3
import sounddevice as sd

print("Current audio devices:")
devices = sd.query_devices()
for i, dev in enumerate(devices):
    print(f"\nDevice {i}: {dev['name']}")
    print(f"  Max input channels: {dev['max_input_channels']}")
    print(f"  Max output channels: {dev['max_output_channels']}")
    print(f"  Default sample rate: {dev['default_samplerate']}")
