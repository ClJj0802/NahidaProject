import os
import re
import tempfile
import time
import wave
from collections import deque

import numpy as np
import sounddevice as sd
import torch

from funasr import AutoModel


class VoiceInput:
    TEXT_CORRECTIONS = {
        "纳些达": "纳西妲",
        "纳些妲": "纳西妲",
        "纳西达": "纳西妲",
        "纳希达": "纳西妲",
        "纳希妲": "纳西妲",
    }

    EMOTION_TAGS = {
        "NEUTRAL",
        "HAPPY",
        "SAD",
        "ANGRY",
        "FEARFUL",
        "DISGUSTED",
        "SURPRISED",
    }

    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        language="auto",
        input_device=None,
        speech_threshold=0.001,
        silence_duration=1.5,
        max_duration=20.0,
        wait_timeout=10.0,
        on_speech_start=None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.language = language
        self.requested_input_device = input_device
        self.input_device = None

        self.speech_threshold = speech_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.wait_timeout = wait_timeout
        self.on_speech_start = on_speech_start

        self.last_raw_text = ""
        self.last_tags = []
        self.last_emotion = None

        self.input_device = (
            self._find_input_device(
                self.requested_input_device
            )
        )

        input_info = sd.query_devices(
            self.input_device
        )

        print(
            f"[Voice] Input device: "
            f"{self.input_device} - "
            f"{input_info['name']}"
        )

        self.device = (
            "cuda:0"
            if torch.cuda.is_available()
            else "cpu"
        )

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

        print(
            f"[Voice] SenseVoice ready in "
            f"{elapsed:.3f}s"
        )

        self._warm_up()

    def set_on_speech_start(
        self,
        callback,
    ):
        self.on_speech_start = callback

    def _is_valid_input_device(
        self,
        device_index,
    ):
        if (
            device_index is None
            or device_index < 0
        ):
            return False

        try:
            info = sd.query_devices(
                device_index
            )

            if (
                info["max_input_channels"]
                <= 0
            ):
                return False

            sd.check_input_settings(
                device=device_index,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype="float32",
            )

            return True

        except Exception:
            return False

    def _find_input_device(
        self,
        preferred_device=None,
    ):
        if preferred_device is not None:
            if self._is_valid_input_device(
                preferred_device
            ):
                return preferred_device

            print(
                f"[Voice] Requested input "
                f"device {preferred_device} "
                f"is unavailable."
            )

        try:
            default_input = (
                sd.default.device[0]
            )
        except Exception:
            default_input = -1

        if self._is_valid_input_device(
            default_input
        ):
            return default_input

        devices = sd.query_devices()

        candidates = []

        for index, info in enumerate(
            devices
        ):
            if (
                info["max_input_channels"]
                <= 0
            ):
                continue

            if not self._is_valid_input_device(
                index
            ):
                continue

            name = str(
                info["name"]
            ).lower()

            score = 0

            if "microphone" in name:
                score += 4

            if "mic" in name:
                score += 3

            if "input" in name:
                score += 1

            if "mapper" in name:
                score -= 2

            candidates.append(
                (
                    score,
                    index,
                )
            )

        if not candidates:
            raise RuntimeError(
                "No usable microphone input "
                "device was found."
            )

        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        selected_device = (
            candidates[0][1]
        )

        if default_input is None:
            default_input = -1

        if default_input < 0:
            print(
                "[Voice] Windows/PortAudio "
                "has no default microphone. "
                "Using automatic fallback."
            )

        return selected_device

    def _open_input_stream(
        self,
        block_size,
    ):
        try:
            return sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=block_size,
                device=self.input_device,
            )

        except Exception as first_error:
            print(
                "[Voice] Current microphone "
                "is unavailable. "
                "Refreshing devices..."
            )

            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass

            previous_device = (
                self.input_device
            )

            self.input_device = (
                self._find_input_device(
                    None
                )
            )

            input_info = sd.query_devices(
                self.input_device
            )

            print(
                f"[Voice] Input device changed: "
                f"{previous_device} -> "
                f"{self.input_device} - "
                f"{input_info['name']}"
            )

            try:
                return sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    blocksize=block_size,
                    device=self.input_device,
                )

            except Exception as second_error:
                raise RuntimeError(
                    "Unable to open a microphone "
                    "input stream. Check Windows "
                    "microphone permissions and "
                    "recording devices."
                ) from second_error

    def _warm_up(self):
        print("[Voice] Warming up...")

        silence = np.zeros(
            (
                self.sample_rate,
                self.channels,
            ),
            dtype=np.int16,
        )

        temp_path = self._save_temp_wav(
            silence
        )

        try:
            start = time.perf_counter()

            self.model.generate(
                input=temp_path,
                cache={},
                language=self.language,
                use_itn=True,
                batch_size_s=60,
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"[Voice] Warm-up completed in "
                f"{elapsed:.3f}s"
            )

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

    def _extract_tags(self, raw_text):
        return re.findall(
            r"<\|([^|]+)\|>",
            raw_text,
        )

    def _clean_transcription(
        self,
        raw_text,
    ):
        self.last_raw_text = raw_text

        tags = self._extract_tags(
            raw_text
        )

        self.last_tags = tags
        self.last_emotion = None

        for tag in tags:
            upper_tag = tag.upper()

            if (
                upper_tag
                in self.EMOTION_TAGS
            ):
                self.last_emotion = (
                    upper_tag
                )
                break

        text = re.sub(
            r"<\|[^|]+\|>",
            "",
            raw_text,
        )

        text = text.strip()

        for wrong, correct in (
            self.TEXT_CORRECTIONS.items()
        ):
            text = text.replace(
                wrong,
                correct,
            )

        return text

    def record_until_silence(self):
        block_duration = 0.05

        block_size = int(
            self.sample_rate
            * block_duration
        )

        pre_roll_duration = 0.3

        pre_roll_blocks = max(
            1,
            int(
                pre_roll_duration
                / block_duration
            ),
        )

        pre_roll = deque(
            maxlen=pre_roll_blocks
        )

        audio_chunks = []

        speech_started = False
        silence_time = 0.0

        waiting_start = (
            time.perf_counter()
        )

        speech_start = None

        print(
            "[Voice] Waiting for speech..."
        )

        stream = self._open_input_stream(
            block_size
        )

        with stream:

            while True:
                audio, overflowed = (
                    stream.read(
                        block_size
                    )
                )

                if overflowed:
                    print(
                        "[Voice] "
                        "Audio buffer overflow."
                    )
                    if self.on_speech_start is not None:
                        try:
                            self.on_speech_start()
                        except Exception as exc:
                            print(
                                "[Voice] Speech-start "
                                f"callback failed: {exc}"
                            )

                rms = self._calculate_rms(
                    audio
                )

                if not speech_started:
                    pre_roll.append(
                        audio.copy()
                    )

                    if (
                        rms
                        >= self.speech_threshold
                    ):
                        speech_started = True

                        speech_start = (
                            time.perf_counter()
                        )

                        audio_chunks.extend(
                            pre_roll
                        )

                        pre_roll.clear()

                        print(
                            "[Voice] "
                            "Speech detected."
                        )

                    elif (
                        time.perf_counter()
                        - waiting_start
                        >= self.wait_timeout
                    ):
                        print(
                            "[Voice] "
                            "No speech detected."
                        )

                        return None

                else:
                    audio_chunks.append(
                        audio.copy()
                    )

                    if (
                        rms
                        >= self.speech_threshold
                    ):
                        silence_time = 0.0

                    else:
                        silence_time += (
                            block_duration
                        )

                    speech_elapsed = (
                        time.perf_counter()
                        - speech_start
                    )

                    if (
                        silence_time
                        >= self.silence_duration
                    ):
                        print(
                            "[Voice] "
                            "Speech ended."
                        )
                        break

                    if (
                        speech_elapsed
                        >= self.max_duration
                    ):
                        print(
                            "[Voice] "
                            "Maximum duration "
                            "reached."
                        )
                        break

        if not audio_chunks:
            return None

        audio = np.concatenate(
            audio_chunks,
            axis=0,
        )

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        audio = (
            audio * 32767
        ).astype(np.int16)

        return audio

    def _save_temp_wav(
        self,
        audio,
    ):
        temp_file = (
            tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            )
        )

        temp_path = temp_file.name

        temp_file.close()

        with wave.open(
            temp_path,
            "wb",
        ) as wav_file:

            wav_file.setnchannels(
                self.channels
            )

            wav_file.setsampwidth(2)

            wav_file.setframerate(
                self.sample_rate
            )

            wav_file.writeframes(
                audio.tobytes()
            )

        return temp_path

    def transcribe_file(
        self,
        audio_file,
    ):
        print(
            "[Voice] Transcribing..."
        )

        start = time.perf_counter()

        result = self.model.generate(
            input=audio_file,
            cache={},
            language=self.language,
            use_itn=True,
            batch_size_s=60,
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        if not result:
            print(
                "[Voice] No result."
            )

            self.last_raw_text = ""
            self.last_tags = []
            self.last_emotion = None

            return ""

        raw_text = result[0].get(
            "text",
            "",
        )

        text = (
            self._clean_transcription(
                raw_text
            )
        )

        print(
            f"[Voice] Inference: "
            f"{elapsed:.3f}s"
        )

        print(
            f"[Voice] Tags: "
            f"{self.last_tags}"
        )

        if self.last_emotion:
            print(
                f"[Voice] Emotion: "
                f"{self.last_emotion} "
                f"(not sent to LLM)"
            )

        return text

    def transcribe(
        self,
        audio,
    ):
        temp_path = (
            self._save_temp_wav(
                audio
            )
        )

        try:
            return (
                self.transcribe_file(
                    temp_path
                )
            )

        finally:
            if os.path.exists(
                temp_path
            ):
                os.remove(
                    temp_path
                )

    def listen(self):
        self.last_raw_text = ""
        self.last_tags = []
        self.last_emotion = None

        audio = (
            self.record_until_silence()
        )

        if audio is None:
            return ""

        return self.transcribe(
            audio
        )