import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
import winsound


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

    def synthesize(
        self,
        text,
        output_path,
    ):
        cleaned_text = (
            self.clean_text(text)
        )

        if not cleaned_text:
            return None

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
            "text_split_method": "cut5",
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": False,
            "speed_factor": 1.0,
            "fragment_interval": 0.15,
            "seed": -1,
            "parallel_infer": False,
            "repetition_penalty": 1.35,
            "media_type": "wav",
            "streaming_mode": False,
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

        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            audio = response.read()

        with open(
            output_path,
            "wb",
        ) as file:
            file.write(audio)

        return output_path

    def speak(
        self,
        text,
    ):
        cleaned_text = self.clean_text(
            text
        )

        if not cleaned_text:
            return

        file_descriptor, output_path = (
            tempfile.mkstemp(
                prefix="nahida_tts_",
                suffix=".wav",
            )
        )

        os.close(
            file_descriptor
        )

        try:
            result = self.synthesize(
                cleaned_text,
                output_path,
            )

            if result is None:
                return

            winsound.PlaySound(
                output_path,
                winsound.SND_FILENAME,
            )

        finally:
            if os.path.exists(
                output_path
            ):
                try:
                    os.remove(
                        output_path
                    )

                except OSError:
                    pass