# source ~/desktop_pet/venv/bin/activate


import sounddevice as sd
import pyaudio
import queue
import json
import time
import subprocess
import numpy as np
import wave
import io
from scipy.signal import resample
from vosk import Model, KaldiRecognizer
from langchain_ollama import ChatOllama

# ---------------- CONFIG ----------------
WAKE_WORDS = ["emo", "he moved", "a more", "email", "imo"]  # Variations due to speech recognition
USE_WAKE_WORD = False  # Set to False to respond to all questions, True to require wake word
SAMPLE_RATE = 16000
AUDIO_DEVICE = 1  # Jabra SPEAK 410 USB microphone
COMMAND_LISTEN_TIME = 4  # seconds to listen for command after wake word
SILENCE_THRESHOLD = 2  # seconds of silence to consider question complete
MODEL_PATH = "/home/alok/desktop_pet/vosk/vosk-model-small-en-us-0.15"

# ---------------- INIT ----------------
print("Loading Vosk model...")
vosk_model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)

audio_queue = queue.Queue()

# Use espeak with sox resampling and chunked playback for smooth audio
def speak_with_espeak(text):
    """Use espeak with sox resampling and chunked PyAudio playback for smooth, natural audio"""
    try:
        # Generate audio with espeak using MBROLA female voice
        # mb/mb-us1 = Natural female US English voice (MBROLA)
        # -s 160 = moderate speed for natural feel
        # -p 50 = neutral pitch (more natural)
        # -g 3 = minimal word gaps for smoother flow
        # -a 100 = normal amplitude
        espeak_cmd = ["espeak", "-v", "mb/mb-us1", "-s", "160", "-p", "50", "-g", "3", "-a", "100", text, "--stdout"]
        
        # Try using sox for better quality resampling (if available)
        TARGET_RATE = 48000
        try:
            # Use sox for high-quality resampling
            sox_cmd = ["sox", "-t", "wav", "-", "-t", "wav", "-", "rate", str(TARGET_RATE), "gain", "-1"]
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            sox_proc = subprocess.Popen(sox_cmd, stdin=espeak_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            espeak_proc.stdout.close()
            wav_data, _ = sox_proc.communicate()
            use_sox = True
        except (FileNotFoundError, subprocess.SubprocessError):
            # Fallback to scipy resampling if sox not available
            espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            wav_data, _ = espeak_proc.communicate()
            use_sox = False
        
        # Read WAV data
        wav_io = io.BytesIO(wav_data)
        with wave.open(wav_io, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Resample if needed (sox already resamples to TARGET_RATE, so only resample if sox wasn't used)
        if not use_sox and sample_rate != TARGET_RATE:
            num_samples = int(len(audio_array) * TARGET_RATE / sample_rate)
            resampled = resample(audio_array, num_samples)
        else:
            resampled = audio_array
        
        # Convert back to int16 for PyAudio
        audio_int16 = (resampled * 32767).astype(np.int16)
        
        # Convert to stereo
        audio_stereo = np.column_stack([audio_int16, audio_int16])
        
        # Play through USB speaker using PyAudio with chunked writing for smooth playback
        p_out = pyaudio.PyAudio()
        stream_out = p_out.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=TARGET_RATE,
            output=True,
            output_device_index=AUDIO_DEVICE,
            frames_per_buffer=4096  # Chunk size for smooth playback
        )
        
        # Write audio data in chunks to prevent buffer underruns
        chunk_size = 4096 * 2 * 2  # frames * channels * bytes per sample
        audio_bytes = audio_stereo.tobytes()
        
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            stream_out.write(chunk)
        
        # Wait for playback to finish
        stream_out.stop_stream()
        stream_out.close()
        p_out.terminate()
        
    except Exception as e:
        print(f"⚠ Audio error: {e}")

print("✓ Text-to-speech ready (using espeak + scipy resampling)")

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
    speak_with_espeak(text)

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
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=AUDIO_DEVICE,
        frames_per_buffer=8000,
        stream_callback=audio_callback
    )
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
