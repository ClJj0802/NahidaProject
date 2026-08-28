import time
import torch

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

AUDIO_FILE = "test.wav"
RUNS = 5

print("Loading model...")

model = AutoModel(
    model="iic/SenseVoiceSmall",
    trust_remote_code=True,
    device="cuda:0",
    disable_update=True,
)

print("Model loaded.")
print()

print("Warm up...")

result = model.generate(
    input=AUDIO_FILE,
    cache={},
    language="zh",
    use_itn=True,
    batch_size_s=60,
)

print("Warm up completed.")
print()

times = []

for i in range(RUNS):
    start = time.perf_counter()

    result = model.generate(
        input=AUDIO_FILE,
        cache={},
        language="zh",
        use_itn=True,
        batch_size_s=60,
    )

    elapsed = time.perf_counter() - start
    times.append(elapsed)

    raw_text = result[0]["text"]
    text = rich_transcription_postprocess(raw_text)

    print(f"Run {i + 1}: {elapsed:.3f}s")
    print(text)
    print()

average = sum(times) / len(times)

print("=== Result ===")
print(f"Average: {average:.3f}s")
print(f"Fastest: {min(times):.3f}s")
print(f"Slowest: {max(times):.3f}s")