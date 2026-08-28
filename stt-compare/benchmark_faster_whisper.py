import time
from faster_whisper import WhisperModel

AUDIO_FILE = "test.wav"
RUNS = 5

print("Loading model...")

model = WhisperModel(
    "turbo",
    device="cuda",
    compute_type="float16",
)

print("Model loaded.")
print()

print("Warm up...")

segments, info = model.transcribe(
    AUDIO_FILE,
    beam_size=1,
    vad_filter=False,
    language="zh",
)

list(segments)

print("Warm up completed.")
print()

times = []

for i in range(RUNS):
    start = time.perf_counter()

    segments, info = model.transcribe(
        AUDIO_FILE,
        beam_size=1,
        vad_filter=False,
        language="zh",
    )

    segments = list(segments)

    elapsed = time.perf_counter() - start
    times.append(elapsed)

    text = "".join(segment.text for segment in segments).strip()

    print(f"Run {i + 1}: {elapsed:.3f}s")
    print(text)
    print()

average = sum(times) / len(times)

print("=== Result ===")
print(f"Average: {average:.3f}s")
print(f"Fastest: {min(times):.3f}s")
print(f"Slowest: {max(times):.3f}s")