import json
import re
import time
import urllib.parse
import urllib.request

import sounddevice as sd


class TTSClient:
    def __init__(
        self,
        api_base="http://127.0.0.1:9880",
        gpt_weights=None,
        sovits_weights=None,
        ref_audio_path=None,
        prompt_text="",
        prompt_lang="zh",
        text_lang="zh",
    ):
        self.api_base = api_base.rstrip("/")
        self.gpt_weights = gpt_weights
        self.sovits_weights = sovits_weights
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text
        self.prompt_lang = prompt_lang
        self.text_lang = text_lang

    def _get(
        self,
        endpoint,
        params,
    ):
        query = urllib.parse.urlencode(
            params
        )

        url = (
            f"{self.api_base}"
            f"{endpoint}"
            f"?{query}"
        )

        with urllib.request.urlopen(
            url,
            timeout=60,
        ) as response:
            return response.read()

    def configure(self):
        if self.sovits_weights:
            self._get(
                "/set_sovits_weights",
                {
                    "weights_path":
                    self.sovits_weights,
                },
            )

        if self.gpt_weights:
            self._get(
                "/set_gpt_weights",
                {
                    "weights_path":
                    self.gpt_weights,
                },
            )

    def clean_text(
        self,
        text,
    ):
        text = re.sub(
            r"（.*?）",
            "",
            text,
            flags=re.DOTALL,
        )

        text = re.sub(
            r"\(.*?\)",
            "",
            text,
            flags=re.DOTALL,
        )

        text = re.sub(
            r"\*.*?\*",
            "",
            text,
            flags=re.DOTALL,
        )

        text = re.sub(
            r"[\U0001F300-\U0001FAFF"
            r"\u2600-\u26FF"
            r"\u2700-\u27BF]",
            "",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        text = re.sub(
            r"^[\s。！？!?，,、；;：:…~～]+",
            "",
            text,
        )

        return text.strip()

    def _choose_split_method(
        self,
        text,
    ):
        return "cut5"

    def _read_exact(
        self,
        response,
        size,
    ):
        chunks = []
        remaining = size

        while remaining > 0:
            chunk = response.read(
                remaining
            )

            if not chunk:
                break

            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    def _read_chunk(
        self,
        response,
        size,
    ):
        read1 = getattr(
            response,
            "read1",
            None,
        )

        if callable(read1):
            return read1(size)

        return response.read(size)

    def _parse_wav_header(
        self,
        header,
    ):
        if len(header) < 44:
            raise RuntimeError(
                "Incomplete WAV stream header."
            )

        if (
            header[0:4] != b"RIFF"
            or header[8:12] != b"WAVE"
        ):
            raise RuntimeError(
                "GPT-SoVITS did not return "
                "a WAV stream."
            )

        channels = int.from_bytes(
            header[22:24],
            "little",
        )

        sample_rate = int.from_bytes(
            header[24:28],
            "little",
        )

        bits_per_sample = int.from_bytes(
            header[34:36],
            "little",
        )

        if bits_per_sample != 16:
            raise RuntimeError(
                "Only 16-bit PCM streaming "
                "audio is supported."
            )

        return (
            sample_rate,
            channels,
        )

    def speak(
        self,
        text,
    ):
        cleaned_text = self.clean_text(
            text
        )

        if not cleaned_text:
            return

        split_method = (
            self._choose_split_method(
                cleaned_text
            )
        )

        payload = {
            "text": cleaned_text,
            "text_lang": self.text_lang,
            "ref_audio_path":
                self.ref_audio_path,
            "prompt_text":
                self.prompt_text,
            "prompt_lang":
                self.prompt_lang,
            "top_k": 15,
            "top_p": 0.7,
            "temperature": 1,
            "text_split_method":
                split_method,
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": False,
            "speed_factor": 1.0,
            "fragment_interval": 0.05,
            "seed": -1,
            "parallel_infer": False,
            "repetition_penalty": 1.35,
            "media_type": "wav",
            "streaming_mode": True,
        }

        request = urllib.request.Request(
            f"{self.api_base}/tts",
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type":
                "application/json",
            },
            method="POST",
        )

        request_start = (
            time.perf_counter()
        )

        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            header = self._read_exact(
                response,
                44,
            )

            (
                sample_rate,
                channels,
            ) = self._parse_wav_header(
                header
            )

            frame_bytes = (
                channels * 2
            )

            prebuffer_bytes = int(
                sample_rate
                * frame_bytes
                * 0.20
            )

            buffered = bytearray()

            while (
                len(buffered)
                < prebuffer_bytes
            ):
                chunk = self._read_chunk(
                    response,
                    8192,
                )

                if not chunk:
                    break

                buffered.extend(chunk)

            first_audio_delay = (
                time.perf_counter()
                - request_start
            )

            print(
                f"[TTS] First audio in "
                f"{first_audio_delay:.3f}s"
            )

            carry = b""

            with sd.RawOutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                latency="low",
            ) as stream:

                if buffered:
                    data = bytes(buffered)

                    aligned_size = (
                        len(data)
                        - (
                            len(data)
                            % frame_bytes
                        )
                    )

                    if aligned_size:
                        stream.write(
                            data[:aligned_size]
                        )

                    carry = data[
                        aligned_size:
                    ]

                while True:
                    chunk = self._read_chunk(
                        response,
                        8192,
                    )

                    if not chunk:
                        break

                    data = carry + chunk

                    aligned_size = (
                        len(data)
                        - (
                            len(data)
                            % frame_bytes
                        )
                    )

                    if aligned_size:
                        stream.write(
                            data[:aligned_size]
                        )

                    carry = data[
                        aligned_size:
                    ]
