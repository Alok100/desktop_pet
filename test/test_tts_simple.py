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
import re
from gtts import gTTS

# Function to dynamically find USB speaker device
def find_usb_speaker_device():
    """Find USB speaker device by checking ALSA cards"""
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            usb_cards = []
            for line in lines:
                # Look for USB audio devices (Jabra, USB, etc.)
                if 'USB' in line or 'Jabra' in line:
                    # Extract card number from line like "card 2: USB [Jabra SPEAK 410 USB]"
                    match = re.search(r'card (\d+):', line)
                    if match:
                        card_num = int(match.group(1))
                        if card_num not in usb_cards:
                            usb_cards.append(card_num)
            
            # If we found USB devices, use the first one found
            # We don't need to test extensively - if it's in the list, use it
            # The retry logic will handle cases where device isn't ready yet
            if usb_cards:
                return f"plughw:{usb_cards[0]},0"
            
            # Fallback: try common USB card numbers in order
            for card in [2, 3, 1, 4, 5]:
                device = f"plughw:{card},0"
                try:
                    test_result = subprocess.run(
                        ['aplay', '-D', device, '--dump-hw-params', '/dev/null'],
                        capture_output=True,
                        timeout=2
                    )
                    stderr_text = test_result.stderr.decode() if test_result.stderr else ""
                    if 'rate:' in stderr_text or 'ACCESS:' in stderr_text:
                        return device
                    # Even error 524 means device exists
                    if 'error 524' in stderr_text.lower():
                        return device
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
    except Exception as e:
        print(f"⚠ Warning: Could not auto-detect USB speaker: {e}")
    
    # Final fallback
    return "plughw:2,0"  # Changed default to 2 since that's what we're seeing

# Configuration
TARGET_DEVICE = find_usb_speaker_device()  # Dynamically detect USB speaker
print(f"✓ Detected audio output device: {TARGET_DEVICE}")
SPEECH_SPEED = 1# Speed multiplier: 0.5 = slower, 1.0 = normal, 1.5 = faster (range: 0.5 to 2.0)

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
            
            print(f"🔊 Playing through USB speaker...")
            
            # Convert MP3 to WAV using ffmpeg (with optional speed adjustment)
            # Using a temp WAV file is more reliable than piping
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name
            
            try:
                # Use ffmpeg to convert MP3 to WAV (with optional speed adjustment)
                # ffmpeg has built-in MP3 support and is more reliable than mpg123 on Raspberry Pi
                # Specify format explicitly: 16-bit PCM, 44100Hz, mono (compatible with USB speaker)
                if abs(speed - 1.0) < 0.01:  # Normal speed - no tempo change
                    ffmpeg_cmd = ["ffmpeg", "-loglevel", "error", "-i", tmp_mp3_path, 
                                  "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1", "-y", tmp_wav_path]
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
                                  "-ar", "44100", "-ac", "1", "-y", tmp_wav_path]
                
                ffmpeg_result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if ffmpeg_result.returncode != 0:
                    print(f"✗ ffmpeg failed with code {ffmpeg_result.returncode}")
                    if ffmpeg_result.stderr:
                        print(f"   Error: {ffmpeg_result.stderr.decode()}")
                    return False
                
                # Play the WAV file with aplay (with retry if device not ready)
                max_retries = 3
                retry_delay = 1.0  # Increased delay to give device time to be ready
                current_device = TARGET_DEVICE
                aplay_success = False
                
                # Small delay before first attempt to ensure device is ready
                time.sleep(0.2)
                
                for attempt in range(max_retries):
                    try:
                        aplay_cmd = ["aplay", "-D", current_device, "-q", tmp_wav_path]
                        aplay_result = subprocess.run(
                            aplay_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=30
                        )
                        
                        if aplay_result.returncode == 0:
                            aplay_success = True
                            break  # Success
                        
                        # Check if it's a device error (524 or similar)
                        error_msg = aplay_result.stderr.decode() if aplay_result.stderr else ""
                        if ("error 524" in error_msg.lower() or 
                            "audio open error" in error_msg.lower() or
                            "unknown error" in error_msg.lower()):
                            if attempt < max_retries - 1:
                                # Device might not be ready or card number changed, try re-detecting
                                print(f"⚠ Audio device error (attempt {attempt + 1}/{max_retries})")
                                print(f"   Current device: {current_device}")
                                # List available devices for debugging
                                try:
                                    list_result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=2)
                                    if list_result.returncode == 0:
                                        usb_lines = [l for l in list_result.stdout.split('\n') if 'USB' in l or 'Jabra' in l]
                                        if usb_lines:
                                            print(f"   Available USB devices: {', '.join(usb_lines[:3])}")
                                except:
                                    pass
                                
                                # Re-detect device (card number might have changed or device might be ready now)
                                new_device = find_usb_speaker_device()
                                if new_device != current_device:
                                    print(f"   Device changed from {current_device} to {new_device}")
                                    current_device = new_device
                                else:
                                    print(f"   Retrying with same device: {current_device}")
                                time.sleep(retry_delay)
                                continue
                        
                        # If it's not a device error, show the error and fail
                        print(f"✗ aplay failed with code {aplay_result.returncode}")
                        if error_msg:
                            print(f"   Error: {error_msg}")
                        return False
                        
                    except subprocess.TimeoutExpired:
                        if attempt < max_retries - 1:
                            print(f"⚠ Playback timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                            time.sleep(retry_delay)
                            continue
                        print("✗ aplay timed out after multiple retries")
                        return False
                
                if not aplay_success:
                    print("✗ aplay failed after all retries")
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
