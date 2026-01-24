# source ~/desktop_pet/venv/bin/activate
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
from scipy.signal import resample
from vosk import Model, KaldiRecognizer
from langchain_ollama import ChatOllama
from gtts import gTTS

# ---------------- CONFIG ----------------
WAKE_WORDS = ["emo", "he moved", "a more", "email", "imo"]  # Variations due to speech recognition
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

# Initialize PyAudio to find devices
_temp_p = pyaudio.PyAudio()
AUDIO_DEVICE = find_usb_microphone()
OUTPUT_DEVICE = find_default_output_device()  # For PyAudio compatibility
if AUDIO_DEVICE is None:
    print("⚠ Warning: Could not find USB microphone, using default input device")
    AUDIO_DEVICE = None  # Use default
else:
    device_info = _temp_p.get_device_info_by_index(AUDIO_DEVICE)
    print(f"✓ Using audio input device: {device_info['name']} (index {AUDIO_DEVICE})")
_temp_p.terminate()
TARGET_DEVICE = "plughw:3,0"  # USB speaker for TTS output (Jabra SPEAK 410 USB)
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
    """Generate speech using gTTS and play through ffmpeg/aplay"""
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
                
                subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                # Play the WAV file with aplay
                aplay_cmd = ["aplay", "-D", TARGET_DEVICE, "-q", tmp_wav_path]
                subprocess.run(aplay_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
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
        
        # PyAudio sometimes requires an output device even when only using input
        # Use USB speaker (device 1) as output device if available, or any output device
        if OUTPUT_DEVICE is not None:
            stream_kwargs['output_device_index'] = OUTPUT_DEVICE
        else:
            # Try to use the same device for output if it supports it
            if AUDIO_DEVICE is not None:
                try:
                    device_info = p.get_device_info_by_index(AUDIO_DEVICE)
                    if device_info.get('maxOutputChannels', 0) > 0:
                        stream_kwargs['output_device_index'] = AUDIO_DEVICE
                except:
                    pass
        
        try:
            stream = p.open(**stream_kwargs)
            break  # Success, exit loop
        except OSError as e:
            if channels == channel_configs[-1]:  # Last attempt
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
