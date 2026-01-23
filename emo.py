import sounddevice as sd
import queue
import json
import time
import pyttsx3
from vosk import Model, KaldiRecognizer
from langchain_ollama import ChatOllama

# ---------------- CONFIG ----------------
WAKE_WORD = "emo"  # Primary wake word
SAMPLE_RATE = 16000
AUDIO_DEVICE = 1
COMMAND_LISTEN_TIME = 4
SILENCE_THRESHOLD = 1.5  # seconds of silence = question complete
MODEL_PATH = "/home/alok/desktop_pet/vosk/vosk-model-small-en-us-0.15"

# ---------------- INIT ----------------
print("Loading Vosk model...")
vosk_model = Model(MODEL_PATH)

try:
    engine = pyttsx3.init('espeak')
    engine.setProperty("rate", 160)
    voices = engine.getProperty('voices')
    if voices:
        for voice in voices:
            if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                engine.setProperty('voice', voice.id)
                break
    print("✓ Text-to-speech initialized")
except Exception as e:
    print(f"⚠ TTS Warning: {e}")
    engine = None

llm = ChatOllama(model="tinyllama", temperature=0)

# ---------------- SPEAK ----------------
def speak(text):
    """Blocking TTS - returns only when speech finishes"""
    print(f"🔊 EMO Speaking: {text}")
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"⚠ TTS error: {e}")

# ---------------- WAKE WORD DETECTION ----------------
def is_wake_word(text):
    """Check if wake word is spoken as a standalone word"""
    words = text.lower().split()
    # Must be the ONLY word, or first word followed by question
    if not words:
        return False
    
    # Check if "emo" is the first word (strict matching)
    if words[0] == WAKE_WORD:
        return True
    
    return False

# ---------------- LISTEN FOR WAKE WORD ----------------
def listen_for_wake_word():
    """Listen continuously until wake word detected"""
    audio_queue = queue.Queue()
    
    def callback(indata, frames, time_info, status):
        audio_queue.put(bytes(indata))
    
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    
    print("🎧 Listening for wake word...")
    
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        device=AUDIO_DEVICE,
        callback=callback
    ):
        while True:
            try:
                data = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower().strip()
                
                if not text:
                    continue
                
                print(f"👂 Heard: {text}")
                
                # Strict wake word check
                if is_wake_word(text):
                    print("=" * 60)
                    print("🔴 WAKE WORD DETECTED!")
                    print("=" * 60)
                    return

# ---------------- LISTEN FOR COMMAND ----------------
def listen_for_command():
    """Listen for command after wake word with silence detection"""
    audio_queue = queue.Queue()
    
    def callback(indata, frames, time_info, status):
        audio_queue.put(bytes(indata))
    
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    command_parts = []
    
    speak("Yes, I am listening")
    
    print(f"🎤 Listening for command...")
    print(f"   (Will stop after {SILENCE_THRESHOLD}s of silence or {COMMAND_LISTEN_TIME}s max)")
    
    start_time = time.time()
    last_speech_time = time.time()
    
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        device=AUDIO_DEVICE,
        callback=callback
    ):
        while True:
            # Check timeouts
            current_time = time.time()
            elapsed = current_time - start_time
            silence_duration = current_time - last_speech_time
            
            # Stop if max time exceeded
            if elapsed > COMMAND_LISTEN_TIME:
                print(f"⏱️  Max time reached ({COMMAND_LISTEN_TIME}s)")
                break
            
            # Stop if silence detected and we have some speech
            if command_parts and silence_duration > SILENCE_THRESHOLD:
                print(f"🤫 Silence detected ({SILENCE_THRESHOLD}s) - question complete")
                break
            
            try:
                data = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                partial_text = result.get("text", "").strip()
                if partial_text:
                    command_parts.append(partial_text)
                    last_speech_time = time.time()  # Reset silence timer
                    print(f"  📝 {partial_text}")
        
        # Get any remaining audio
        final_result = json.loads(recognizer.FinalResult())
        final_text = final_result.get("text", "").strip()
        if final_text and final_text not in command_parts:
            command_parts.append(final_text)
            print(f"  📝 {final_text}")
    
    command_text = " ".join(command_parts).strip()
    print(f"🛑 Stopped listening")
    return command_text

# ---------------- PROCESS COMMAND ----------------
def process_command(command_text):
    """Send to LLM and speak response"""
    if not command_text:
        print("❌ No command heard")
        return
    
    print(f"📋 Question: '{command_text}'")
    print(f"🤔 Thinking (LLM processing)...")
    
    try:
        response = llm.invoke(
            f"You are EMO, a friendly desktop pet. "
            f"Reply in 1-2 short sentences.\nUser: {command_text}"
        )
        
        reply = response.content.strip()
        print()
        print(f"💬 Reply: {reply}")
        print("=" * 60)
        print()
        
        speak(reply)
        
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        speak("Sorry, I encountered an error")

# ---------------- MAIN LOOP ----------------
print("=" * 60)
print(f"🎧 EMO is ready! Say: '{WAKE_WORD}' to activate")
print("=" * 60)
print()

while True:
    try:
        # Step 1: Listen for wake word (blocks until "emo" heard)
        listen_for_wake_word()
        
        # Step 2: Listen for command (stops on silence or timeout)
        command = listen_for_command()
        
        # Step 3-6: Process and speak (blocking)
        process_command(command)
        
        # Step 7: Resume listening
        print()
        print("✅ Finished - resuming wake word detection...")
        print("=" * 60)
        print()
        
    except KeyboardInterrupt:
        print("\n👋 EMO shutting down...")
        break
    except Exception as e:
        print(f"❌ Error in main loop: {e}")
        time.sleep(1)