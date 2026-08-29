import time

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
BLOCK_DURATION = 0.05
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)


print("Default devices:")
print(sd.default.device)

print()
print("Speak normally for 10 seconds...")
print()

start = time.perf_counter()
max_rms = 0.0

with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    blocksize=BLOCK_SIZE,
) as stream:

    while time.perf_counter() - start < 10:
        audio, overflowed = stream.read(BLOCK_SIZE)

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

        max_rms = max(max_rms, rms)

        print(
            f"\rRMS: {rms:.6f}    Max: {max_rms:.6f}",
            end="",
        )

print()
print()
print(f"Peak RMS: {max_rms:.6f}")