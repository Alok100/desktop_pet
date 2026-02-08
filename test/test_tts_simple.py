#!/usr/bin/env python3
"""
Simple Text-to-Speech Test
Uses gTTS (Google Text-to-Speech) for natural-sounding speech

To change speech speed, modify the SPEECH_SPEED variable below:
  - 0.5 = Half speed (slower)
  - 0.75 = Slower
  - 1.0 = Normal speed (default)
  - 1.25 = Faster
  - 1.5 = 1.5x speed
  - 2.0 = Double speed
"""

import subprocess
import tempfile
import os
import time
from gtts import gTTS

# Configuration
SPEECH_SPEED = 1  # Speed multiplier: 0.5 = slower, 1.0 = normal, 1.5 = faster (range: 0.5 to 2.0)

def set_full_volume():
    """Set volume to maximum (100%)"""
    print("🔊 Setting volume to 100% (FULL)...")
    
    controls = ['PCM', 'Master', 'Speaker', 'Headphone', 'Playback']
    
    for control in controls:
        try:
            cmd = ['amixer', 'sset', control, '100%']
            result = subprocess.run(cmd, capture_output=True, timeout=2)
            if result.returncode == 0:
                print(f"✓ {control} volume set to 100%")
            
            # Also try unmuting
            cmd_unmute = ['amixer', 'sset', control, 'unmute']
            subprocess.run(cmd_unmute, capture_output=True, timeout=2)
        except:
            pass
    print()

def speak(text, speed=SPEECH_SPEED):
    """Generate speech using gTTS and play through aplay"""
    try:
        print(f"🎤 Generating speech with Google Text-to-Speech...")
        print(f"   Voice: Google's natural female voice")
        print(f"   Speed: {speed}x")
        
        # Create gTTS object (use slow=True if speed < 0.75)
        use_slow = speed < 0.75
        tts = gTTS(text=text, lang='en', slow=use_slow)
        
        # Save to temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_mp3:
            tmp_mp3_path = tmp_mp3.name
        
        try:
            tts.save(tmp_mp3_path)
            print(f"✓ Generated MP3 file: {os.path.getsize(tmp_mp3_path)} bytes")
            
            print(f"🔊 Playing through speakers...")
            
            # Convert MP3 to WAV using ffmpeg (with optional speed adjustment)
            # Using 48kHz stereo format for better compatibility with PAM8403
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name
            
            try:
                # Use ffmpeg to convert MP3 to WAV
                # Specify format: 16-bit PCM, 48000Hz, stereo (compatible with PAM8403 and audio jack)
                if abs(speed - 1.0) < 0.01:  # Normal speed - no tempo change
                    ffmpeg_cmd = ["ffmpeg", "-loglevel", "error", "-i", tmp_mp3_path, 
                                  "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y", tmp_wav_path]
                else:
                    # Apply speed adjustment using atempo filter
                    # atempo range is 0.5-2.0
                    tempo_value = speed
                    if tempo_value < 0.5:
                        tempo_value = 0.5
                    elif tempo_value > 2.0:
                        tempo_value = 2.0
                    ffmpeg_cmd = ["ffmpeg", "-loglevel", "error", "-i", tmp_mp3_path, 
                                  "-af", f"atempo={tempo_value}", "-acodec", "pcm_s16le", 
                                  "-ar", "48000", "-ac", "2", "-y", tmp_wav_path]
                
                ffmpeg_result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                
                if ffmpeg_result.returncode != 0:
                    print(f"✗ ffmpeg failed with code {ffmpeg_result.returncode}")
                    if ffmpeg_result.stderr:
                        print(f"   Error: {ffmpeg_result.stderr.decode()}")
                    return False
                
                print(f"✓ Generated WAV: {os.path.getsize(tmp_wav_path)} bytes")
                
                # Try multiple audio devices (for PAM8403 on audio jack)
                devices_to_try = [
                    ("default", "System default"),
                    ("sysdefault", "System default (alt)"),
                    ("plughw:0,0", "Audio jack (card 0)"),
                    ("plughw:1,0", "Audio jack (card 1)"),
                    ("hw:0,0", "Hardware (card 0)"),
                    ("hw:1,0", "Hardware (card 1)"),
                ]
                
                aplay_success = False
                
                # Small delay before first attempt to ensure device is ready
                time.sleep(0.2)
                
                for device, description in devices_to_try:
                    try:
                        print(f"\n🎵 Trying {description}: {device}")
                        aplay_cmd = ["aplay", "-D", device, "-q", tmp_wav_path]
                        aplay_result = subprocess.run(
                            aplay_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=15
                        )
                        
                        if aplay_result.returncode == 0:
                            aplay_success = True
                            print(f"✅ SUCCESS! Audio played on {device}")
                            break  # Success - stop trying other devices
                        else:
                            error_msg = aplay_result.stderr.decode() if aplay_result.stderr else ""
                            print(f"✗ Failed: {error_msg[:100]}")
                        
                    except subprocess.TimeoutExpired:
                        print(f"✗ Timeout")
                    except Exception as e:
                        print(f"✗ Error: {e}")
                
                if not aplay_success:
                    print("\n✗ All audio devices failed")
                    return False
                    
            finally:
                # Clean up temp WAV file
                if os.path.exists(tmp_wav_path):
                    os.unlink(tmp_wav_path)
            
            print("✓ Playback completed")
            return True
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_mp3_path):
                os.unlink(tmp_mp3_path)
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

# Main test
print("=" * 70)
print("GOOGLE TEXT-TO-SPEECH TEST")
print("=" * 70)
print()

# Set full volume first
set_full_volume()

print(f"💨 Speed setting: {SPEECH_SPEED}x (0.5=slower, 1.0=normal, 1.5=faster)")
print()

# Hard-coded test text (shorter for testing)
test_text = ("Blue light is scattered more than the other colors because "
             "it travels as shorter, smaller waves. This is why we see "
             "a blue sky most of the time.")

print("📝 Test text:")
print(f"   \"{test_text}\"")
print()

if speak(test_text, SPEECH_SPEED):
    print()
    print("=" * 70)
    print("✅ SUCCESS - Audio test passed!")
    print("=" * 70)
else:
    print()
    print("=" * 70)
    print("❌ FAILED - Check errors above")
    print("=" * 70)
