#!/usr/bin/env python3
"""
Speaker Test Script for PAM8403 Amplifier
Tests audio output through different devices and configurations
"""

import subprocess
import time
import tempfile
import os
from gtts import gTTS

def list_audio_devices():
    """List all available audio playback devices"""
    print("=" * 70)
    print("📻 AVAILABLE AUDIO DEVICES")
    print("=" * 70)
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("⚠ Could not list devices")
    except Exception as e:
        print(f"⚠ Error: {e}")
    print("=" * 70)
    print()

def test_device(device_name, device_id):
    """Test a specific audio device with a test tone"""
    print(f"\n{'='*70}")
    print(f"🔊 Testing device: {device_name} ({device_id})")
    print(f"{'='*70}")
    
    # Generate test audio using gTTS
    try:
        print("📝 Generating test audio...")
        test_text = "Testing speakers. Can you hear me clearly I am bingo your best friend can we continueˀ?"
        tts = gTTS(text=test_text, lang='en', slow=False)
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_mp3:
            tmp_mp3_path = tmp_mp3.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name
        
        try:
            # Save MP3
            tts.save(tmp_mp3_path)
            print(f"✓ Generated MP3: {os.path.getsize(tmp_mp3_path)} bytes")
            
            # Convert to WAV with different sample rates and formats
            # Try 48000Hz first (common for many audio devices)
            print("🔄 Converting to WAV (48kHz)...")
            ffmpeg_cmd = [
                "ffmpeg", "-loglevel", "error", "-i", tmp_mp3_path,
                "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
                "-y", tmp_wav_path
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=10)
            
            if result.returncode != 0:
                print(f"⚠ ffmpeg error: {result.stderr.decode()}")
                return False
            
            print(f"✓ Generated WAV: {os.path.getsize(tmp_wav_path)} bytes")
            
            # Try playing with different configurations
            configs = [
                (device_id, "Direct device"),
                (f"plughw:{device_id.split(':')[-1].split(',')[0]},0" if ',' not in device_id else device_id, "Plughw format"),
                ("default", "System default"),
                ("sysdefault", "System default (alt)"),
            ]
            
            for dev, desc in configs:
                print(f"\n🎵 Trying {desc}: {dev}")
                try:
                    aplay_cmd = ["aplay", "-D", dev, tmp_wav_path]
                    result = subprocess.run(aplay_cmd, capture_output=True, timeout=15)
                    
                    if result.returncode == 0:
                        print(f"✅ SUCCESS! Audio played on {dev}")
                        print(f"   Use this device: {dev}")
                        return dev
                    else:
                        error = result.stderr.decode() if result.stderr else "Unknown error"
                        print(f"✗ Failed: {error[:100]}")
                        
                except subprocess.TimeoutExpired:
                    print(f"✗ Timeout")
                except Exception as e:
                    print(f"✗ Error: {e}")
            
            return False
            
        finally:
            # Cleanup
            if os.path.exists(tmp_mp3_path):
                os.unlink(tmp_mp3_path)
            if os.path.exists(tmp_wav_path):
                os.unlink(tmp_wav_path)
                
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def set_full_volume():
    """Set volume to maximum (100%)"""
    print("\n" + "="*70)
    print("🔊 Setting volume to 100% (FULL)")
    print("="*70)
    
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
    
    print("="*70)

def test_default_audio_jack():
    """Test the default audio output (audio jack/headphone port)"""
    print("\n" + "="*70)
    print("🎧 Testing Default Audio Jack (for PAM8403)")
    print("="*70)
    
    # Set volume to full before testing
    set_full_volume()
    
    # Common device names for audio jack output
    devices_to_test = [
        ("default", "System default output"),
        ("sysdefault", "System default (alternative)"),
        ("plughw:0,0", "Audio jack (card 0)"),
        ("plughw:1,0", "Audio jack (card 1)"),
        ("hw:0,0", "Hardware direct (card 0)"),
        ("hw:1,0", "Hardware direct (card 1)"),
        ("plughw:Headphones", "Headphones device"),
        ("plughw:ALSA", "ALSA default"),
    ]
    
    working_devices = []
    
    for device, description in devices_to_test:
        result = test_device(description, device)
        if result:
            working_devices.append((device, description))
    
    return working_devices

def main():
    print("\n" + "="*70)
    print("🔊 SPEAKER TEST FOR PAM8403 AMPLIFIER")
    print("="*70)
    print("This script will test different audio output configurations")
    print("to find the best one for your PAM8403 amplifier.")
    print("="*70)
    print()
    
    # List all available devices
    list_audio_devices()
    
    # Wait a moment
    time.sleep(1)
    
    # Test default audio jack (most likely for PAM8403)
    working_devices = test_default_audio_jack()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    if working_devices:
        print("✅ Working audio devices found:")
        for device, description in working_devices:
            print(f"   • {description}: {device}")
        print()
        print("💡 RECOMMENDATION:")
        print(f"   Use this device in your script: {working_devices[0][0]}")
        print()
        print("   Update your TARGET_DEVICE variable to:")
        print(f"   TARGET_DEVICE = '{working_devices[0][0]}'")
    else:
        print("❌ No working audio devices found")
        print()
        print("💡 TROUBLESHOOTING:")
        print("   1. Check if PAM8403 is properly connected to audio jack")
        print("   2. Check speaker connections to PAM8403")
        print("   3. Verify power supply to PAM8403")
        print("   4. Try increasing volume: amixer set PCM 100%")
        print("   5. Check if audio is muted: amixer get PCM")
        print("   6. Test with: speaker-test -t wav -c 2")
    
    print("="*70)

if __name__ == "__main__":
    main()
