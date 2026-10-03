# Title

about GPT-SoVITS v2 ProPlus's RTF(inference speed) a criterion

# URL

https://github.com/RVC-Boss/GPT-SoVITS/issues/2579

# Source type

GitHub issue (user report)

# Observed claims

- The issue author quotes existing GPT-SoVITS v2 ProPlus RTF claims (not their own measurements; original benchmark conditions not verified here):
  - 0.028 on 4060Ti
  - 0.014 on 4090 (tested with ~1400 words over ~4 minutes; inference time 3.36s)
  - 0.526 on M4 CPU
  - Huggingface demo claimed to run on half H200 (high-speed inference)
- First response time: 0.3–0.4 seconds claimed
- Korean language processing performance:
  - First response time: 0.443 seconds
  - Total processing time: 1.363 seconds
  - Total audio length: 0.89 seconds
  - Total RTF: 1.531 (processing time / audio length)
- Average RTF: 0.497 (minimum and maximum both 0.497 in one test)
- Second test set:
  - First Response Time: 0.339 seconds
  - Total Processing Time: 1.668 seconds
  - Total Audio Length: 0.97 seconds
  - Total RTF: 1.719
  - Average RTF: 0.685
- The author questions whether these results are normal for RTX 3090 before CUDA graph optimization when processing Korean.
- Iterations per second (it/s) from logs: 48.14 it/s (BERT feature extraction), 151.66 it/s (T2S decoding), 145.65 it/s (T2S decoding), audio generation timings reported as 0.000 0.022 0.180 0.133 (units unclear).

# Relevant configuration

```python
self.default_params = {
    "text_lang": "auto",
    "ref_audio_path": " secret my path haha ",
    "prompt_lang": "ja",
    "prompt_text": " nothing ",
    "top_k": 5,
    "top_p": 1,
    "temperature": 1,
    "text_split_method": "cut0",
    "batch_size": 4,
    "batch_threshold": 2,
    "split_bucket": "True",
    "speed_factor": 1.0,
    "fragment_interval": 0.0001,
    "seed": -1,
    "media_type": "wav",
    "streaming_mode": "False",
    "parallel_infer": "True",
    "repetition_penalty": 1.35,
    "sample_steps": 32,
    "super_sampling": "False"
}
```

Log output from api_v2.py includes:
- Text segmentation
- BERT feature extraction (100% | 1/1 [00:00<00:00, 48.14 it/s])
- Front-end processing (sentence by sentence)
- Semantic-based token prediction / T2S decoding (1% | 16/1500 [00:00<00:09, 151.66 it/s] and 2% | 26/1500 [00:00<00:10, 145.65 it/s])
- Audio generation (Parallel Audio Generation...)

# Measured performance numbers

**Quoted GPT-SoVITS v2 ProPlus RTF claims (not author measurements):**
- 0.028 (4060Ti)
- 0.014 (4090, inference time 3.36s for ~1400 words/~4min)
- 0.526 (M4 CPU)

**Korean processing tests:**
- First response time: 0.443 seconds
- Total processing time: 1.363 seconds
- Total audio length: 0.89 seconds
- Total RTF: 1.531
- Average RTF: 0.497

**Second test set:**
- First Response Time: 0.339 seconds
- Total Processing Time: 1.668 seconds
- Total Audio Length: 0.97 seconds
- Total RTF: 1.719
- Average RTF: 0.685

**Iterations per second (from logs):**
- BERT feature extraction: 48.14 it/s
- T2S decoding: 151.66 it/s and 145.65 it/s

**Audio generation timing:**
- Reported as 0.000 0.022 0.180 0.133 (units not specified)

# Hardware mentioned

- RTX 4060 Ti
- RTX 4090
- M4 CPU
- H200 (claimed "half H200" in Huggingface demo)
- RTX 3090 (mentioned by author as test environment)

# Software/version mentioned

- GPT-SoVITS v2 ProPlus
- api_v2.py
- CUDA graph (mentioned in context of optimization not yet applied)

# Evidence level

User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.

# Useful paraphrases

- The user quotes pre-existing RTF claims of 0.014–0.526; their own short-sentence measurements use different timing boundaries.
- Korean text-to-speech processing on api_v2 shows first response times around 0.3–0.4 seconds but RTF values between 0.497 and 1.719.
- The author observes that iterations per second during T2S decoding (~145–151 it/s) seem slower than expected.

# Confidence

Medium – Contains specific numerical data and configuration details, but author explicitly questions validity of results for Korean processing on RTX 3090 before CUDA graph optimization. Some RTF values (0.014, 0.028) differ substantially from Korean test RTF values (0.497–1.719), so they are not comparable without common timing boundaries, input lengths, and settings. The stated averages appear to use API response time/audio length (0.442/0.89 and 0.664/0.97), whereas total RTF uses total processing time/audio length; this is an inference from the reported arithmetic.

# Unresolved questions

- Is the discrepancy between claimed RTF values (0.014–0.526) and Korean test RTF values (0.497–1.719) due to different hardware, configurations, or test methodologies?
- Does CUDA graph optimization significantly improve Korean processing performance on RTX 3090?
- Are the very low RTF values (0.014, 0.028) measured under comparable conditions to the Korean tests?

# Last Updated

2026-10-02 Asia/Singapore

# Extraction scope

Bounded main text: 4000 characters, truncated near the conversation footer. Publication date, complete discussion and later changes were not verified. Evidence: research/raw/evidence/manual-t2.json. Host review corrected benchmark attribution before synthesis.
