# EMO Assistant - Main entry point
# Voice assistant: listen (Vosk) -> LLM (Ollama) -> speak (gTTS + aplay).

import queue
import time
import pyaudio

import config
from audio_handler import (
    initialize_audio_devices,
    make_audio_callback,
)
from config import MIC_SAMPLE_RATE
from speech_recognizer import (
    load_model,
    create_recognizer,
    get_result_text,
    get_final_text,
)
from tts_handler import speak
from llm_handler import create_llm, get_reply


def main():
    # --- Init audio devices and queue ---
    audio_device, output_device = initialize_audio_devices()
    audio_queue = queue.Queue()
    callback = make_audio_callback(audio_queue)

    # --- Load Vosk model ---
    print("Loading Vosk model...")
    vosk_model = load_model()
    recognizer = create_recognizer(vosk_model)

    # --- LLM ---
    llm = create_llm(model="tinyllama", temperature=0)
    print("✓ Text-to-speech ready (using Google TTS)")

    # --- PyAudio ---
    p = pyaudio.PyAudio()

    print("=" * 60)
    if config.USE_WAKE_WORD:
        print(f"🎧 EMO is listening... Say one of: {', '.join(config.WAKE_WORDS[:2])}")
    else:
        print("🎧 EMO is listening... Ask me anything!")
    print("=" * 60)

    while True:
        # --- Open microphone stream ---
        channels = 1
        if audio_device is not None:
            try:
                di = p.get_device_info_by_index(audio_device)
                channels = 2 if di.get("maxInputChannels", 1) >= 2 else 1
            except Exception:
                channels = 2

        stream = None
        channel_configs = [1, 2]
        for ch in channel_configs:
            stream_kwargs = {
                "format": pyaudio.paInt16,
                "channels": ch,
                "rate": MIC_SAMPLE_RATE,
                "input": True,
                "frames_per_buffer": 8000,
                "stream_callback": callback,
            }
            if audio_device is not None:
                stream_kwargs["input_device_index"] = audio_device
            try:
                stream = p.open(**stream_kwargs)
                break
            except OSError as e:
                stream_kwargs_with_output = stream_kwargs.copy()
                if output_device is not None:
                    stream_kwargs_with_output["output_device_index"] = output_device
                elif audio_device is not None:
                    try:
                        di = p.get_device_info_by_index(audio_device)
                        if di.get("maxOutputChannels", 0) > 0:
                            stream_kwargs_with_output["output_device_index"] = audio_device
                    except Exception:
                        pass
                try:
                    stream = p.open(**stream_kwargs_with_output)
                    break
                except OSError as e2:
                    if ch == channel_configs[-1]:
                        print(f"\n❌ Failed to open audio stream: {e}; {e2}")
                        print("   Unplug USB mic, wait 2–3 s, plug back in, restart.")
                        raise
                    continue

        stream.start_stream()

        try:
            while not audio_queue.empty():
                audio_queue.get()

            recognizer = create_recognizer(vosk_model)
            question_detected = False
            command_text = ""

            while not question_detected:
                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    text = get_result_text(recognizer).lower()
                    if not text:
                        continue

                    print(f"👂 Heard: {text}")
                    wake_word_detected = any(
                        w in text for w in config.WAKE_WORDS
                    )
                    should_respond = (
                        (not config.USE_WAKE_WORD and len(text.split()) >= 3)
                        or wake_word_detected
                    )

                    if should_respond:
                        print()
                        print("=" * 60)
                        print("🔴 QUESTION DETECTED!")
                        print("🛑 Stopping listening...")

                        if config.USE_WAKE_WORD:
                            speak("Yes, I am listening")
                            print(f"🎤 Listening for command ({config.COMMAND_LISTEN_TIME}s)...")
                            cmd_recognizer = create_recognizer(vosk_model)
                            start_time = time.time()
                            command_parts = []
                            while time.time() - start_time < config.COMMAND_LISTEN_TIME:
                                try:
                                    cmd_audio = audio_queue.get(timeout=1)
                                    if cmd_recognizer.AcceptWaveform(cmd_audio):
                                        partial = get_result_text(cmd_recognizer)
                                        if partial:
                                            command_parts.append(partial)
                                            print(f"  📝 {partial}")
                                except queue.Empty:
                                    continue
                            final = get_final_text(cmd_recognizer)
                            if final:
                                command_parts.append(final)
                            command_text = " ".join(command_parts).strip()
                        else:
                            command_text = text

                        question_detected = True
                        break
        finally:
            stream.stop_stream()
            stream.close()

        if not command_text:
            print("❌ No question heard, resuming...")
            print("=" * 60)
            print()
            continue

        print(f"📋 Question: '{command_text}'")
        print("🤔 Thinking (this takes ~10 seconds on Raspberry Pi)...")

        try:
            reply = get_reply(
                llm,
                command_text,
                system_prompt="You are EMO, a friendly desktop pet. Reply in 1-2 short sentences.",
            )
            print()
            print(f"💬 Reply: {reply}")
            print("=" * 60)
            print()
            print(f"🔊 EMO Speaking: {reply}")
            speak(reply)
        except KeyboardInterrupt:
            print("\n⚠ Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 60)

        print()
        print("✅ Finished speaking, resuming listening...")
        print("=" * 60)

    p.terminate()


if __name__ == "__main__":
    main()
