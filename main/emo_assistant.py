# source ~/desktop_pet/venv/bin/activate
# 
# EMO Assistant - Voice assistant with USB microphone and PAM8403 speakers
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
MIC_SAMPLE_RATE = 48000  # USB microphone sample rate (48kHz is commonly supported)
VOSK_SAMPLE_RATE = 16000  # Vosk model sample rate (required by the model)
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

# Function to get audio output devices for PAM8403 (audio jack)
def get_audio_output_devices():
    """Get list of audio output devices to try (for PAM8403 on audio jack)"""
    # Try these devices in order - same as test_speakers.py
    return [
        ("default", "System default"),
        ("sysdefault", "System default (alt)"),
        ("plughw:0,0", "Audio jack (card 0)"),
        ("plughw:1,0", "Audio jack (card 1)"),
        ("hw:0,0", "Hardware (card 0)"),
        ("hw:1,0", "Hardware (card 1)"),
    ]

# Removed USB device reset functions - not needed for PAM8403 speakers on audio jack

def set_usb_volume(volume_percent=100):
    """Set volume for audio device using amixer"""
    try:
        print(f"🔊 Setting audio volume to {volume_percent}% (FULL)...")
        
        # Try all common audio controls
        controls = ['PCM', 'Master', 'Speaker', 'Headphone', 'Playback']
        volume_set = False
        
        # Try to find USB audio card first
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
                        for control in controls:
                            try:
                                cmd = ['amixer', '-c', card_num, 'sset', control, f'{volume_percent}%']
                                result = subprocess.run(cmd, capture_output=True, timeout=2)
                                if result.returncode == 0:
                                    print(f"✓ Volume set to {volume_percent}% on card {card_num} ({control})")
                                    volume_set = True
                                # Also unmute
                                subprocess.run(['amixer', '-c', card_num, 'sset', control, 'unmute'], 
                                             capture_output=True, timeout=2)
                            except:
                                continue
        
        # Fallback: try setting volume without card number (for all devices)
        for control in controls:
            try:
                result = subprocess.run(['amixer', 'sset', control, f'{volume_percent}%'], 
                                      capture_output=True, timeout=2)
                if result.returncode == 0:
                    print(f"✓ {control} volume set to {volume_percent}%")
                    volume_set = True
                # Also unmute
                subprocess.run(['amixer', 'sset', control, 'unmute'], 
                             capture_output=True, timeout=2)
            except:
                pass
        
        if not volume_set:
            print(f"⚠ Could not set volume automatically")
            return False
        
        return True
    except Exception as e:
        print(f"⚠ Could not set volume: {e}")
        return False

def initialize_audio_devices():
    """Initialize audio devices - USB microphone and PAM8403 speakers"""
    print("\n" + "="*60)
    print("🚀 Starting EMO Assistant")
    print("="*60)
    
    # Detect USB microphone
    temp_p = pyaudio.PyAudio()
    audio_device = find_usb_microphone()
    output_device = find_default_output_device()
    
    if audio_device is None:
        print("⚠ Warning: Could not find USB microphone, using default input device")
    else:
        device_info = temp_p.get_device_info_by_index(audio_device)
        print(f"✓ USB microphone: {device_info['name']} (index {audio_device})")
    
    temp_p.terminate()
    
    # Set volume to maximum for PAM8403 speakers
    print("✓ Audio output: PAM8403 speakers on audio jack")
    set_usb_volume(100)
    
    # Test microphone stream with correct sample rate
    print(f"🧪 Testing microphone at {MIC_SAMPLE_RATE}Hz...")
    test_p = pyaudio.PyAudio()
    try:
        test_kwargs = {
            'format': pyaudio.paInt16,
            'channels': 1,
            'rate': MIC_SAMPLE_RATE,
            'input': True,
            'frames_per_buffer': 8000,
        }
        if audio_device is not None:
            test_kwargs['input_device_index'] = audio_device
            
        test_stream = test_p.open(**test_kwargs)
        test_stream.close()
        test_p.terminate()
        print("✓ Microphone test passed")
        print(f"{'='*60}\n")
        return audio_device, output_device
    except Exception as e:
        test_p.terminate()
        print(f"\n{'='*60}")
        print("❌ FAILED TO INITIALIZE MICROPHONE")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print("\n💡 SOLUTION:")
        print("   1. Check USB microphone connection")
        print("   2. Try unplugging and replugging the USB microphone")
        print("   3. Restart the program")
        print(f"{'='*60}\n")
        raise

# Initialize PyAudio to find devices
AUDIO_DEVICE, OUTPUT_DEVICE = initialize_audio_devices()
SPEECH_SPEED = 1.0  # TTS speed: 0.5=slower, 1.0=normal, 1.5=faster
COMMAND_LISTEN_TIME = 4  # seconds to listen for command after wake word
SILENCE_THRESHOLD = 2  # seconds of silence to consider question complete
MODEL_PATH = "/home/alok/desktop_pet/vosk/vosk-model-small-en-us-0.15"

# ---------------- INIT ----------------
print("Loading Vosk model...")
vosk_model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(vosk_model, VOSK_SAMPLE_RATE)

audio_queue = queue.Queue()

# ---------------- AUDIO CALLBACK (PyAudio) ----------------
def audio_callback(in_data, frame_count, time_info, status):
    """Callback that receives audio from microphone and resamples for Vosk"""
    # Convert bytes to numpy array
    audio_np = np.frombuffer(in_data, dtype=np.int16)
    
    # Resample from MIC_SAMPLE_RATE to VOSK_SAMPLE_RATE
    if MIC_SAMPLE_RATE != VOSK_SAMPLE_RATE:
        # Calculate number of samples after resampling
        num_samples = int(len(audio_np) * VOSK_SAMPLE_RATE / MIC_SAMPLE_RATE)
        # Resample
        audio_resampled = resample(audio_np, num_samples).astype(np.int16)
        # Convert back to bytes
        resampled_data = audio_resampled.tobytes()
        audio_queue.put(resampled_data)
    else:
        audio_queue.put(in_data)
    
    return (in_data, pyaudio.paContinue)

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
                # Specify format: 16-bit PCM, 48000Hz, stereo (compatible with PAM8403)
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
                    print(f"⚠ ffmpeg failed with code {ffmpeg_result.returncode}")
                    if ffmpeg_result.stderr:
                        print(f"   Error: {ffmpeg_result.stderr.decode()}")
                    return False
                
                # Play the WAV file with aplay - try multiple devices (PAM8403 on audio jack)
                devices_to_try = get_audio_output_devices()
                aplay_success = False
                
                # Small delay before first attempt to ensure device is ready
                time.sleep(0.2)
                
                for device, description in devices_to_try:
                    try:
                        aplay_cmd = ["aplay", "-D", device, "-q", tmp_wav_path]
                        aplay_result = subprocess.run(
                            aplay_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=15
                        )
                        
                        if aplay_result.returncode == 0:
                            aplay_success = True
                            break  # Success - stop trying other devices
                        
                    except subprocess.TimeoutExpired:
                        continue
                    except Exception:
                        continue
                
                if not aplay_success:
                    print("⚠ Audio playback failed on all devices")
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
            'rate': MIC_SAMPLE_RATE,
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
        recognizer = KaldiRecognizer(vosk_model, VOSK_SAMPLE_RATE)
        
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
                        command_recognizer = KaldiRecognizer(vosk_model, VOSK_SAMPLE_RATE)
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