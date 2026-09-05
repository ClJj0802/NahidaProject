import json
import re
import threading
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
        output_device=None,
        prebuffer_seconds=0.12,
        parallel_infer=True,
    ):
        self.api_base = api_base.rstrip("/")
        self.gpt_weights = gpt_weights
        self.sovits_weights = sovits_weights
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text
        self.prompt_lang = prompt_lang
        self.text_lang = text_lang
        self.output_device = output_device
        self.prebuffer_seconds = prebuffer_seconds
        self.parallel_infer = parallel_infer

    def _get(
        self,
        endpoint,
        params,
    ):
        query = urllib.parse.urlencode(params)
        url = f"{self.api_base}{endpoint}?{query}"

        start = time.perf_counter()

        with urllib.request.urlopen(
            url,
            timeout=120,
        ) as response:
            data = response.read()

        elapsed = time.perf_counter() - start
        print(f"[TTS] {endpoint}: {elapsed:.3f}s")

        return data

    def configure(self):
        configure_start = time.perf_counter()

        if self.sovits_weights:
            self._get(
                "/set_sovits_weights",
                {
                    "weights_path": self.sovits_weights,
                },
            )

        if self.gpt_weights:
            self._get(
                "/set_gpt_weights",
                {
                    "weights_path": self.gpt_weights,
                },
            )

        elapsed = time.perf_counter() - configure_start
        print(f"[TTS] Configure total: {elapsed:.3f}s")

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

    def _build_payload(
        self,
        text,
        streaming_mode,
    ):
        return {
            "text": text,
            "text_lang": self.text_lang,
            "ref_audio_path": self.ref_audio_path,
            "prompt_text": self.prompt_text,
            "prompt_lang": self.prompt_lang,
            "top_k": 15,
            "top_p": 0.7,
            "temperature": 0.7,
            "text_split_method": "cut5",
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": False,
            "speed_factor": 1.0,
            "fragment_interval": 0.05,
            "seed": -1,
            "parallel_infer": self.parallel_infer,
            "repetition_penalty": 1.35,
            "media_type": "wav",
            "streaming_mode": streaming_mode,
        }

    def _request(
        self,
        payload,
    ):
        return urllib.request.Request(
            f"{self.api_base}/tts",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

    def warm_up(
        self,
        text="嗯，我在这里。",
    ):
        cleaned_text = self.clean_text(text)

        if not cleaned_text:
            return

        print("[TTS] Streaming warm-up...")
        start = time.perf_counter()

        payload = self._build_payload(
            cleaned_text,
            streaming_mode=True,
        )

        request = self._request(payload)

        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            while response.read(8192):
                pass

        elapsed = time.perf_counter() - start
        print(
            f"[TTS] Streaming warm-up complete: "
            f"{elapsed:.3f}s"
        )

    def _read_exact(
        self,
        response,
        size,
    ):
        chunks = []
        remaining = size

        while remaining > 0:
            chunk = response.read(remaining)

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
                "GPT-SoVITS did not return a WAV stream."
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
                "Only 16-bit PCM streaming audio is supported."
            )

        return sample_rate, channels

    def speak(
        self,
        text,
        stop_event=None,
    ):
        cleaned_text = self.clean_text(text)

        if not cleaned_text:
            return

        if stop_event is None:
            stop_event = threading.Event()

        print(
            f"[TTS] Text chars: "
            f"{len(cleaned_text)}"
        )

        payload = self._build_payload(
            cleaned_text,
            streaming_mode=True,
        )

        request = self._request(payload)
        request_start = time.perf_counter()

        total_written_bytes = 0

        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            header = self._read_exact(
                response,
                44,
            )

            header_delay = (
                time.perf_counter()
                - request_start
            )

            sample_rate, channels = (
                self._parse_wav_header(header)
            )

            frame_bytes = channels * 2

            prebuffer_bytes = int(
                sample_rate
                * frame_bytes
                * self.prebuffer_seconds
            )

            buffered = bytearray()

            while (
                len(buffered) < prebuffer_bytes
                and not stop_event.is_set()
            ):
                chunk = self._read_chunk(
                    response,
                    8192,
                )

                if not chunk:
                    break

                buffered.extend(chunk)

            playable_delay = (
                time.perf_counter()
                - request_start
            )

            print(
                f"[TTS] Header ready: "
                f"{header_delay:.3f}s"
            )
            print(
                f"[TTS] First playable audio: "
                f"{playable_delay:.3f}s"
            )

            if stop_event.is_set():
                print(
                    "[TTS] Cancelled before playback."
                )
                return

            carry = b""

            stream_kwargs = {
                "samplerate": sample_rate,
                "channels": channels,
                "dtype": "int16",
                "latency": "low",
            }

            if self.output_device is not None:
                stream_kwargs["device"] = (
                    self.output_device
                )

            with sd.RawOutputStream(
                **stream_kwargs
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
                        total_written_bytes += (
                            aligned_size
                        )

                    carry = data[
                        aligned_size:
                    ]

                while not stop_event.is_set():
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
                        total_written_bytes += (
                            aligned_size
                        )

                    carry = data[
                        aligned_size:
                    ]

        total_wall = (
            time.perf_counter()
            - request_start
        )

        bytes_per_second = (
            sample_rate
            * channels
            * 2
        )

        audio_seconds = (
            total_written_bytes
            / bytes_per_second
            if bytes_per_second
            else 0.0
        )

        if audio_seconds > 0:
            wall_to_audio = (
                total_wall
                / audio_seconds
            )
        else:
            wall_to_audio = 0.0

        if stop_event.is_set():
            print(
                f"[TTS] Interrupted: "
                f"wall={total_wall:.3f}s, "
                f"played={audio_seconds:.3f}s"
            )
        else:
            print(
                f"[TTS] Complete: "
                f"wall={total_wall:.3f}s, "
                f"audio={audio_seconds:.3f}s, "
                f"wall/audio={wall_to_audio:.2f}x"
            )
