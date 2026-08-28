import time
from faster_whisper import WhisperModel

AUDIO_FILE = "test.wav"

print("Loading Faster-Whisper Turbo...")

load_start = time.perf_counter()

model = WhisperModel(
    "turbo",
    device="cuda",
    compute_type="float16",
)

load_time = time.perf_counter() - load_start

print(f"Model load time: {load_time:.3f} seconds")
print()
print("Transcribing...")

start = time.perf_counter()

segments, info = model.transcribe(
    AUDIO_FILE,
    beam_size=1,
    vad_filter=False,
)

segments = list(segments)

elapsed = time.perf_counter() - start

text = "".join(segment.text for segment in segments).strip()

print()
print("=== Faster-Whisper Turbo ===")
print(f"Detected language: {info.language}")
print(f"Language probability: {info.language_probability:.3f}")
print(f"Inference time: {elapsed:.3f} seconds")
print()
print("Text:")
print(text)