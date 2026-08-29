import os
import tempfile
import time
import wave
from collections import deque

import numpy as np
import sounddevice as sd
import torch

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


class VoiceInput:
    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        language="auto",
        input_device=None,
        speech_threshold=0.001,
        silence_duration=0.8,
        max_duration=20.0,
        wait_timeout=10.0,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.language = language
        self.input_device = input_device

        self.speech_threshold = speech_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.wait_timeout = wait_timeout

        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        print("[Voice] Loading SenseVoiceSmall...")
        print(f"[Voice] Device: {self.device}")

        start = time.perf_counter()

        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            trust_remote_code=True,
            device=self.device,
            disable_update=True,
        )

        elapsed = time.perf_counter() - start

        print(f"[Voice] SenseVoice ready in {elapsed:.3f}s")

        self._warm_up()

    def _warm_up(self):
        print("[Voice] Warming up...")

        silence = np.zeros(
            (self.sample_rate, self.channels),
            dtype=np.int16,
        )

        temp_path = self._save_temp_wav(silence)

        try:
            start = time.perf_counter()

            self.model.generate(
                input=temp_path,
                cache={},
                language=self.language,
                use_itn=True,
                batch_size_s=60,
            )

            elapsed = time.perf_counter() - start

            print(f"[Voice] Warm-up completed in {elapsed:.3f}s")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _calculate_rms(self, audio):
        return float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

    def record_until_silence(self):
        block_duration = 0.05
        block_size = int(self.sample_rate * block_duration)

        pre_roll_duration = 0.3
        pre_roll_blocks = int(pre_roll_duration / block_duration)

        pre_roll = deque(maxlen=pre_roll_blocks)
        audio_chunks = []

        speech_started = False
        silence_time = 0.0

        waiting_start = time.perf_counter()
        speech_start = None

        print("[Voice] Waiting for speech...")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=block_size,
            device=self.input_device,
        ) as stream:

            while True:
                audio, overflowed = stream.read(block_size)

                if overflowed:
                    print("[Voice] Audio buffer overflow.")

                rms = self._calculate_rms(audio)

                if not speech_started:
                    pre_roll.append(audio.copy())

                    if rms >= self.speech_threshold:
                        speech_started = True
                        speech_start = time.perf_counter()

                        audio_chunks.extend(pre_roll)
                        pre_roll.clear()

                        print("[Voice] Speech detected.")

                    elif (
                        time.perf_counter() - waiting_start
                        >= self.wait_timeout
                    ):
                        print("[Voice] No speech detected.")
                        return None

                else:
                    audio_chunks.append(audio.copy())

                    if rms >= self.speech_threshold:
                        silence_time = 0.0
                    else:
                        silence_time += block_duration

                    speech_elapsed = (
                        time.perf_counter() - speech_start
                    )

                    if silence_time >= self.silence_duration:
                        print("[Voice] Speech ended.")
                        break

                    if speech_elapsed >= self.max_duration:
                        print("[Voice] Maximum duration reached.")
                        break

        if not audio_chunks:
            return None

        audio = np.concatenate(audio_chunks, axis=0)

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        audio = (audio * 32767).astype(np.int16)

        return audio

    def _save_temp_wav(self, audio):
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )

        temp_path = temp_file.name
        temp_file.close()

        with wave.open(temp_path, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio.tobytes())

        return temp_path

    def transcribe_file(self, audio_file):
        print("[Voice] Transcribing...")

        start = time.perf_counter()

        result = self.model.generate(
            input=audio_file,
            cache={},
            language=self.language,
            use_itn=True,
            batch_size_s=60,
        )

        elapsed = time.perf_counter() - start

        if not result:
            print("[Voice] No result.")
            return ""

        raw_text = result[0].get("text", "")

        text = rich_transcription_postprocess(
            raw_text
        ).strip()

        print(f"[Voice] Inference: {elapsed:.3f}s")

        return text

    def transcribe(self, audio):
        temp_path = self._save_temp_wav(audio)

        try:
            return self.transcribe_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def listen(self):
        audio = self.record_until_silence()

        if audio is None:
            return ""

        return self.transcribe(audio)