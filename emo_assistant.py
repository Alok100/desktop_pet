# source ~/desktop_pet/venv/bin/activate
# 
# NOTE: This script may require sudo permissions to reset USB devices.
# If you get permission errors, run with: sudo -E python emo_assistant.py
# The -E flag preserves your environment variables (including virtual env)
# 

import sounddevice as sd
import pyaudio
import queue
import json
import time
import subprocess
import numpy as np
import wave
import io
import tempfile
import os
import re
from scipy.signal import resample
from vosk import Model, KaldiRecognizer
from langchain_ollama import ChatOllama
from gtts import gTTS

# ---------------- CONFIG ----------------
WAKE_WORDS = ["Bingo"]  # Variations due to speech recognition
USE_WAKE_WORD = False  # Set to False to respond to all questions, True to require wake word
SAMPLE_RATE = 16000
# Find USB microphone device automatically
def find_usb_microphone():
    """Find the USB microphone device index"""
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            # Look for Jabra or USB device with input channels
            if (info['maxInputChannels'] > 0 and 
                ('jabra' in info['name'].lower() or 'usb' in info['name'].lower())):
                return i
        # If not found, try to find any device with input channels
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                return i
        # Fallback to default
        return None
    finally:
        p.terminate()

def find_default_output_device():
    """Find a default output device for PyAudio"""
    p = pyaudio.PyAudio()
    try:
        # First try to get system default
        try:
            default_output = p.get_default_output_device_info()
            return default_output['index']
        except:
            pass
        
        # Try to find USB speaker (Jabra) as output device
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if (info['maxOutputChannels'] > 0 and 
                ('jabra' in info['name'].lower() or 'usb' in info['name'].lower())):
                return i
        
        # Try to find any output device
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                return i
        return None
    finally:
        p.terminate()

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

def find_usb_audio_device_path():
    """Find the USB device path for audio devices (Jabra, USB audio, etc.)"""
    try:
        # Look for USB audio devices in /sys/bus/usb/devices/
        usb_devices_path = "/sys/bus/usb/devices"
        if not os.path.exists(usb_devices_path):
            return None
        
        for device in os.listdir(usb_devices_path):
            device_path = os.path.join(usb_devices_path, device)
            
            # Check if it's a valid USB device directory
            if not os.path.isdir(device_path):
                continue
                
            # Try to read product name
            try:
                product_file = os.path.join(device_path, "product")
                if os.path.exists(product_file):
                    with open(product_file, 'r') as f:
                        product_name = f.read().strip().lower()
                        # Look for audio-related USB devices
                        if any(keyword in product_name for keyword in ['jabra', 'audio', 'speaker', 'microphone', 'headset']):
                            return device
                
                # Also check manufacturer
                manufacturer_file = os.path.join(device_path, "manufacturer")
                if os.path.exists(manufacturer_file):
                    with open(manufacturer_file, 'r') as f:
                        manufacturer = f.read().strip().lower()
                        if 'jabra' in manufacturer or 'audio' in manufacturer:
                            return device
            except:
                continue
        
        return None
    except Exception as e:
        print(f"⚠ Error finding USB device: {e}")
        return None

def unbind_rebind_usb_device(device_name):
    """Unbind and rebind a USB device to reset it"""
    try:
        if not device_name:
            return False
            
        driver_path = f"/sys/bus/usb/devices/{device_name}/driver"
        
        # Check if device has a driver
        if not os.path.exists(driver_path):
            print(f"⚠ No driver found for device {device_name}")
            return False
        
        # Get the driver name
        driver_name = os.path.basename(os.path.realpath(driver_path))
        unbind_path = f"/sys/bus/usb/drivers/{driver_name}/unbind"
        bind_path = f"/sys/bus/usb/drivers/{driver_name}/bind"
        
        print(f"📤 Unbinding USB device {device_name} from driver {driver_name}...")
        
        # Unbind the device
        try:
            with open(unbind_path, 'w') as f:
                f.write(device_name)
            time.sleep(1)
            print(f"✓ Device unbound")
        except PermissionError:
            # Try with sudo
            result = subprocess.run(['sudo', 'sh', '-c', f'echo {device_name} > {unbind_path}'], 
                                  capture_output=True, timeout=5)
            if result.returncode != 0:
                print(f"⚠ Failed to unbind device (you may need sudo permissions)")
                return False
            time.sleep(1)
            print(f"✓ Device unbound (with sudo)")
        
        print(f"📥 Rebinding USB device {device_name}...")
        
        # Rebind the device
        try:
            with open(bind_path, 'w') as f:
                f.write(device_name)
            time.sleep(2)
            print(f"✓ Device rebound")
        except PermissionError:
            # Try with sudo
            result = subprocess.run(['sudo', 'sh', '-c', f'echo {device_name} > {bind_path}'], 
                                  capture_output=True, timeout=5)
            if result.returncode != 0:
                print(f"⚠ Failed to rebind device")
                return False
            time.sleep(2)
            print(f"✓ Device rebound (with sudo)")
        
        return True
        
    except Exception as e:
        print(f"⚠ Error during USB reset: {e}")
        return False

def reset_usb_audio_devices():
    """Reset USB audio devices by unbinding and rebinding them"""
    try:
        print("\n" + "="*60)
        print("🔄 Resetting USB audio devices...")
        print("="*60)
        
        # Find USB audio device
        usb_device = find_usb_audio_device_path()
        
        if usb_device:
            print(f"✓ Found USB audio device: {usb_device}")
            success = unbind_rebind_usb_device(usb_device)
            if success:
                print("✓ USB audio device reset successfully")
                print("="*60 + "\n")
                return True
        else:
            print("⚠ Could not find USB audio device to reset")
        
        # Fallback: try restarting pulseaudio
        try:
            print("🔄 Trying to restart audio system (fallback)...")
            subprocess.run(['pulseaudio', '--kill'], capture_output=True, timeout=2)
            time.sleep(0.5)
            subprocess.run(['pulseaudio', '--start'], capture_output=True, timeout=2)
            time.sleep(1)
            print("✓ Audio system restarted")
            print("="*60 + "\n")
            return True
        except:
            print(f"⚠ Could not reset audio devices automatically")
            print("   Please unplug and replug the USB audio device manually.")
            print("="*60 + "\n")
            return False
            
    except Exception as e:
        print(f"⚠ Error resetting USB audio devices: {e}")
        print("="*60 + "\n")
        return False

def set_usb_volume(volume_percent=90):
    """Set volume for USB audio device using amixer"""
    try:
        print(f"🔊 Setting USB audio volume to {volume_percent}%...")
        
        # Try to find USB audio card
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'USB' in line or 'Jabra' in line:
                    # Extract card number
                    match = re.search(r'card (\d+):', line)
                    if match:
                        card_num = match.group(1)
                        # Set volume using amixer
                        # Try different control names that might work
                        controls = ['PCM', 'Speaker', 'Master', 'Headphone']
                        for control in controls:
                            try:
                                cmd = ['amixer', '-c', card_num, 'sset', control, f'{volume_percent}%']
                                result = subprocess.run(cmd, capture_output=True, timeout=2)
                                if result.returncode == 0:
                                    print(f"✓ Volume set to {volume_percent}% on card {card_num} ({control})")
                                    return True
                            except:
                                continue
        
        # Fallback: try setting volume without card number
        try:
            subprocess.run(['amixer', 'sset', 'PCM', f'{volume_percent}%'], 
                         capture_output=True, timeout=2)
            print(f"✓ Volume set to {volume_percent}%")
            return True
        except:
            pass
            
        print(f"⚠ Could not set volume automatically")
        return False
    except Exception as e:
        print(f"⚠ Could not set volume: {e}")
        return False

def initialize_audio_devices_with_retry(max_attempts=3):
    """Initialize audio devices with retry logic and device reset"""
    # On first run, always try to reset USB devices
    print("\n" + "="*60)
    print("🚀 Starting EMO Assistant - Initializing USB Audio...")
    print("="*60)
    reset_usb_audio_devices()
    
    # Give the system time to recognize the device after reset
    print("⏳ Waiting for USB device to be ready...")
    time.sleep(5)  # Increased wait time for device to be fully recognized
    
    for attempt in range(max_attempts):
        try:
            print(f"\n{'='*60}")
            print(f"🎤 Initializing audio devices (attempt {attempt + 1}/{max_attempts})...")
            print(f"{'='*60}")
            
            # If not first attempt, try to reset the audio system again
            if attempt > 0:
                print(f"\n⚠ Device not ready, resetting USB device again...")
                reset_usb_audio_devices()
                print("⏳ Waiting for device to stabilize...")
                time.sleep(5)  # Wait longer for device to be fully ready
                print("💡 TIP: If this keeps failing, please:")
                print("   1. Unplug the USB audio device")
                print("   2. Wait 2-3 seconds") 
                print("   3. Plug it back in")
                print("   4. The program will retry automatically\n")
                time.sleep(2)
            
            # Force PyAudio to refresh its device list by creating a new instance
            # This is crucial after USB device reset
            print("🔄 Refreshing audio device list...")
            temp_p = pyaudio.PyAudio()
            temp_p.terminate()
            time.sleep(0.5)
            
            # Now create a fresh PyAudio instance with updated device list
            temp_p = pyaudio.PyAudio()
            audio_device = find_usb_microphone()
            output_device = find_default_output_device()
            
            if audio_device is None:
                print("⚠ Warning: Could not find USB microphone, using default input device")
            else:
                device_info = temp_p.get_device_info_by_index(audio_device)
                print(f"✓ Using audio input device: {device_info['name']} (index {audio_device})")
            
            temp_p.terminate()
            
            # Detect speaker
            target_device = find_usb_speaker_device()
            print(f"✓ Using audio output device: {target_device}")
            
            # Set volume
            set_usb_volume(90)
            
            # Test if we can open a stream (quick test)
            print("🧪 Testing audio stream...")
            test_p = pyaudio.PyAudio()
            stream_test_passed = False
            
            # Try opening stream without output device first (input only)
            try:
                test_kwargs = {
                    'format': pyaudio.paInt16,
                    'channels': 1,
                    'rate': SAMPLE_RATE,
                    'input': True,
                    'frames_per_buffer': 8000,
                }
                if audio_device is not None:
                    test_kwargs['input_device_index'] = audio_device
                    
                test_stream = test_p.open(**test_kwargs)
                test_stream.close()
                stream_test_passed = True
                print("✓ Audio stream test passed (input only)")
            except Exception as e1:
                # If that fails, try with output device
                try:
                    test_kwargs = {
                        'format': pyaudio.paInt16,
                        'channels': 1,
                        'rate': SAMPLE_RATE,
                        'input': True,
                        'frames_per_buffer': 8000,
                    }
                    if audio_device is not None:
                        test_kwargs['input_device_index'] = audio_device
                    if output_device is not None:
                        test_kwargs['output_device_index'] = output_device
                        
                    test_stream = test_p.open(**test_kwargs)
                    test_stream.close()
                    stream_test_passed = True
                    print("✓ Audio stream test passed (with output device)")
                except Exception as e2:
                    test_p.terminate()
                    if attempt < max_attempts - 1:
                        print(f"✗ Audio stream test failed:")
                        print(f"   First attempt: {e1}")
                        print(f"   Second attempt: {e2}")
                        continue
                    else:
                        # On final attempt, provide detailed error
                        print(f"✗ Audio stream test failed after all attempts")
                        print(f"   Error: {e2}")
                        raise
            
            test_p.terminate()
            
            if stream_test_passed:
                print(f"{'='*60}\n")
                return audio_device, output_device, target_device
                    
        except Exception as e:
            if attempt == max_attempts - 1:
                print(f"\n{'='*60}")
                print("❌ FAILED TO INITIALIZE AUDIO DEVICES")
                print(f"{'='*60}")
                print(f"Error: {e}")
                print("\n💡 SOLUTION:")
                print("   1. Unplug the USB audio device")
                print("   2. Wait 2-3 seconds")
                print("   3. Plug it back in")
                print("   4. Restart the program")
                print(f"{'='*60}\n")
                raise
    
    raise Exception("Failed to initialize audio devices after all attempts")

# Initialize PyAudio to find devices with retry logic
AUDIO_DEVICE, OUTPUT_DEVICE, TARGET_DEVICE = initialize_audio_devices_with_retry(max_attempts=3)
SPEECH_SPEED = 1.0  # TTS speed: 0.5=slower, 1.0=normal, 1.5=faster
COMMAND_LISTEN_TIME = 4  # seconds to listen for command after wake word
SILENCE_THRESHOLD = 2  # seconds of silence to consider question complete
MODEL_PATH = "/home/alok/desktop_pet/vosk/vosk-model-small-en-us-0.15"

# ---------------- INIT ----------------
print("Loading Vosk model...")
vosk_model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)

audio_queue = queue.Queue()

# Use Google Text-to-Speech for natural voice
def speak_with_gtts(text, speed=SPEECH_SPEED):
    """Generate speech using gTTS and play through ffmpeg/aplay with retry logic"""
    try:
        # Create gTTS object (use slow=True if speed < 0.75)
        use_slow = speed < 0.75
        tts = gTTS(text=text, lang='en', slow=use_slow)
        
        # Save to temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_mp3:
            tmp_mp3_path = tmp_mp3.name
        
        try:
            tts.save(tmp_mp3_path)
            
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
                    print(f"⚠ ffmpeg failed with code {ffmpeg_result.returncode}")
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
                        print(f"⚠ aplay failed with code {aplay_result.returncode}")
                        if error_msg:
                            print(f"   Error: {error_msg}")
                        return False
                        
                    except subprocess.TimeoutExpired:
                        if attempt < max_retries - 1:
                            print(f"⚠ Playback timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                            time.sleep(retry_delay)
                            continue
                        print("⚠ aplay timed out after multiple retries")
                        return False
                
                if not aplay_success:
                    print("⚠ aplay failed after all retries")
                    return False
                    
                return True
            finally:
                # Clean up temp WAV file
                if os.path.exists(tmp_wav_path):
                    os.unlink(tmp_wav_path)
        finally:
            # Clean up temp MP3 file
            if os.path.exists(tmp_mp3_path):
                os.unlink(tmp_mp3_path)
        
    except Exception as e:
        print(f"⚠ Audio error: {e}")
        import traceback
        traceback.print_exc()
        return False

print("✓ Text-to-speech ready (using Google TTS)")

llm = ChatOllama(
    model="tinyllama",
    temperature=0
)

# ---------------- AUDIO CALLBACK (PyAudio) ----------------
def audio_callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
    return (in_data, pyaudio.paContinue)

# ---------------- SPEAK ----------------
def speak(text):
    print(f"🔊 EMO Speaking: {text}")
    speak_with_gtts(text, SPEECH_SPEED)

# ---------------- MAIN LOOP ----------------
print("=" * 60)
if USE_WAKE_WORD:
    print(f"🎧 EMO is listening... Say one of: {', '.join(WAKE_WORDS[:2])}")
else:
    print("🎧 EMO is listening... Ask me anything!")
print("=" * 60)

# Initialize PyAudio for microphone input (works better than sounddevice for USB mic)
p = pyaudio.PyAudio()

while True:
    # Start listening using PyAudio
    # Try to get device info to check available channels
    channels = 1  # Default to mono
    if AUDIO_DEVICE is not None:
        try:
            device_info = p.get_device_info_by_index(AUDIO_DEVICE)
            max_channels = device_info.get('maxInputChannels', 1)
            # Use stereo if available, otherwise mono
            channels = 2 if max_channels >= 2 else 1
        except:
            # Fallback: try stereo first, then mono
            channels = 2
    
    # Try different configurations to open the stream
    stream = None
    channel_configs = [1, 2]  # Try mono first, then stereo
    
    for channels in channel_configs:
        # First try: input only, no output device
        stream_kwargs = {
            'format': pyaudio.paInt16,
            'channels': channels,
            'rate': SAMPLE_RATE,
            'input': True,
            'frames_per_buffer': 8000,
            'stream_callback': audio_callback
        }
        
        # Only add input_device_index if we have a specific device
        if AUDIO_DEVICE is not None:
            stream_kwargs['input_device_index'] = AUDIO_DEVICE
        
        try:
            stream = p.open(**stream_kwargs)
            break  # Success, exit loop
        except OSError as e:
            # If that fails, try with output device
            # PyAudio sometimes requires an output device even when only using input
            stream_kwargs_with_output = stream_kwargs.copy()
            
            if OUTPUT_DEVICE is not None:
                stream_kwargs_with_output['output_device_index'] = OUTPUT_DEVICE
            else:
                # Try to use the same device for output if it supports it
                if AUDIO_DEVICE is not None:
                    try:
                        device_info = p.get_device_info_by_index(AUDIO_DEVICE)
                        if device_info.get('maxOutputChannels', 0) > 0:
                            stream_kwargs_with_output['output_device_index'] = AUDIO_DEVICE
                    except:
                        pass
            
            try:
                stream = p.open(**stream_kwargs_with_output)
                break  # Success, exit loop
            except OSError as e2:
                if channels == channel_configs[-1]:  # Last channel config attempt
                    print(f"\n❌ Failed to open audio stream:")
                    print(f"   First attempt (input only): {e}")
                    print(f"   Second attempt (with output): {e2}")
                    print(f"\n💡 SOLUTION:")
                    print(f"   1. Unplug the USB audio device")
                    print(f"   2. Wait 2-3 seconds")
                    print(f"   3. Plug it back in")
                    print(f"   4. Restart the program")
                    raise  # Re-raise if all attempts failed
                continue  # Try next channel configuration
    stream.start_stream()
    
    try:
        # Clear queue before listening
        while not audio_queue.empty():
            audio_queue.get()
        
        # Reset recognizer
        recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
        
        question_detected = False
        command_text = ""
        
        while not question_detected:
            data = audio_queue.get()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()

                if not text:
                    continue

                print(f"👂 Heard: {text}")

                # Wake word detection - check for any variation
                wake_word_detected = any(wake_word in text for wake_word in WAKE_WORDS)
                
                # Respond if: wake word mode is off OR wake word was detected
                should_respond = (not USE_WAKE_WORD and len(text.split()) >= 3) or wake_word_detected
                
                if should_respond:
                    print()
                    print("=" * 60)
                    print("🔴 QUESTION DETECTED!")
                    print("🛑 Stopping listening...")
                    
                    if USE_WAKE_WORD:
                        speak("Yes, I am listening")
                        
                        # Listen for additional command
                        print(f"🎤 Listening for command ({COMMAND_LISTEN_TIME}s)...")
                        command_recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
                        start_time = time.time()
                        command_parts = []
                        
                        while time.time() - start_time < COMMAND_LISTEN_TIME:
                            try:
                                command_audio = audio_queue.get(timeout=1)
                                if command_recognizer.AcceptWaveform(command_audio):
                                    result = json.loads(command_recognizer.Result())
                                    partial_text = result.get("text", "")
                                    if partial_text:
                                        command_parts.append(partial_text)
                                        print(f"  📝 {partial_text}")
                            except:
                                continue
                        
                        final_result = json.loads(command_recognizer.FinalResult())
                        final_text = final_result.get("text", "")
                        if final_text:
                            command_parts.append(final_text)
                        
                        command_text = " ".join(command_parts).strip()
                    else:
                        command_text = text
                    
                    question_detected = True
                    break
    finally:
        # Close PyAudio stream
        stream.stop_stream()
        stream.close()
    
    # Stream is now closed, process the question
    if not command_text:
        print("❌ No question heard, resuming...")
        print("=" * 60)
        print()
        continue
    
    print(f"📋 Question: '{command_text}'")
    print(f"🤔 Thinking (this takes ~10 seconds on Raspberry Pi)...")
    
    # LLM call
    try:
        import sys
        sys.stdout.flush()  # Force output to display
        
        response = llm.invoke(
            f"You are EMO, a friendly desktop pet. "
            f"Reply in 1-2 short sentences.\nUser: {command_text}"
        )
        
        reply = response.content.strip()
        print()
        print(f"💬 Reply: {reply}")
        print("=" * 60)
        print()
        sys.stdout.flush()
        
        # Speak the reply (this blocks until audio finishes)
        speak(reply)
        
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        p.terminate()
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
    
    print()
    print("✅ Finished speaking, resuming listening...")
    print("=" * 60)

# Cleanup
p.terminate()