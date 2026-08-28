import wave
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DURATION = 10
OUTPUT_FILE = "test.wav"

print("Recording will start now...")
print(f"Please speak for {DURATION} seconds.")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    dtype="int16",
)

sd.wait()

with wave.open(OUTPUT_FILE, "wb") as wav_file:
    wav_file.setnchannels(CHANNELS)
    wav_file.setsampwidth(2)
    wav_file.setframerate(SAMPLE_RATE)
    wav_file.writeframes(audio.tobytes())

print()
print(f"Recording finished.")
print(f"Saved to: {OUTPUT_FILE}")