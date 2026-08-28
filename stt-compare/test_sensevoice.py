import time
import torch

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

AUDIO_FILE = "test.wav"

print("=== System ===")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
else:
    print("GPU unavailable.")

print()
print("Loading SenseVoiceSmall...")

load_start = time.perf_counter()

model = AutoModel(
    model="iic/SenseVoiceSmall",
    trust_remote_code=True,
    device="cuda:0" if torch.cuda.is_available() else "cpu",
)

load_time = time.perf_counter() - load_start

print(f"Model load time: {load_time:.3f} seconds")
print()
print("Transcribing...")

start = time.perf_counter()

result = model.generate(
    input=AUDIO_FILE,
    cache={},
    language="auto",
    use_itn=True,
    batch_size_s=60,
)

elapsed = time.perf_counter() - start

raw_text = result[0]["text"]
processed_text = rich_transcription_postprocess(raw_text)

print()
print("=== SenseVoiceSmall ===")
print(f"Inference time: {elapsed:.3f} seconds")

print()
print("Raw result:")
print(raw_text)

print()
print("Processed text:")
print(processed_text)