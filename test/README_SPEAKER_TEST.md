# Speaker Test Scripts for PAM8403 Amplifier

These scripts help you find the correct audio device configuration for your PAM8403 amplifier connected to the Raspberry Pi audio jack.

## Quick Start

### Option 1: Simple Test (Recommended First)
Uses `speaker-test` utility to play tones:

```bash
cd ~/desktop_pet
source venv/bin/activate
python test/test_speakers_simple.py
```

### Option 2: Full Test with Speech
Uses Google TTS to test with actual speech:

```bash
cd ~/desktop_pet
source venv/bin/activate
python test/test_speakers.py
```

## What These Scripts Do

1. **Set volume to 90%** automatically
2. **Test multiple audio devices** to find which works with your setup
3. **Show you the correct device name** to use in your main script
4. **Provide troubleshooting tips** if nothing works

## Expected Output

When a device works, you'll see:
```
✅ SUCCESS! Device works: plughw:0,0
```

Then use that device in your main script:
```python
TARGET_DEVICE = "plughw:0,0"  # Use the device that worked
```

## Common PAM8403 Issues

### No Sound?
1. **Check power**: PAM8403 needs 5V power (can use Pi's 5V pin)
2. **Check connections**:
   - Audio jack tip (left) → PAM8403 L input
   - Audio jack ring (right) → PAM8403 R input  
   - Audio jack sleeve (ground) → PAM8403 GND
3. **Check speakers**: Connect to PAM8403 L+/L- and R+/R-
4. **Check volume**: Run `alsamixer` and unmute/increase volume

### Error 524?
This usually means the device is busy or needs to be reset. The scripts will try multiple devices automatically.

### Wrong Device?
If USB audio is being used instead of audio jack:
- Unplug USB audio devices
- Run the test script again
- It should default to the audio jack (usually `plughw:0,0` or `default`)

## Manual Testing

If scripts don't work, try manually:

```bash
# List all audio devices
aplay -l

# Test with speaker-test
speaker-test -D plughw:0,0 -t wav -c 2 -l 1

# Check volume/mute
amixer get PCM

# Set volume
amixer set PCM 90%

# Test with a file
aplay -D plughw:0,0 /usr/share/sounds/alsa/Front_Center.wav
```

## PAM8403 Wiring Reference

```
Raspberry Pi Audio Jack          PAM8403 Amplifier
├─ Tip (Left Channel)     ───→   L (Left Input)
├─ Ring (Right Channel)   ───→   R (Right Input)
└─ Sleeve (Ground)        ───→   GND

Raspberry Pi 5V Pin       ───→   VCC (Power)
Raspberry Pi GND Pin      ───→   GND (Power Ground)

Speakers
├─ Speaker 1              ───→   L+ and L-
└─ Speaker 2              ───→   R+ and R-
```

## After Finding the Working Device

Update your main script (`emo_assistant.py`) with the working device:

```python
TARGET_DEVICE = "plughw:0,0"  # Replace with your working device
```

Then test the main script to ensure audio works properly.
