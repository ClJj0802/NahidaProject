# Title
about GPT-SoVITS v2 ProPlus's RTF(inference speed) a criterion

# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2579

# Source type
GitHub Issue #2579 on RVC-Boss repository discussing GPT-SoVITS v2 ProPlus inference speed (RTF).

# Observed claims
- Author claims RTF of 0.028 on RTX 4060 Ti, 0.014 on RTX 4090 (4min audio), and 0.526 on M4 CPU.
- Author reports first reaction times of 0.3–0.4 seconds and total processing times between 1.36–1.67 seconds in API tests.
- Author questions if observed RTF values are normal on RTX 3090 before CUDA Graph optimization for Korean input.

# Relevant configuration
- `top_k=5`, `top_p=1`, `temperature=1`
- `batch_size=4`, `parallel_infer=True`, `streaming_mode=False`
- `text_split_method=cut0`, `split_bucket=True`
- `repetition_penalty=1.35`, `sample_steps=32`, `super_sampling=False`
- `prompt_lang=ja`, `text_lang=auto`

# Measured performance numbers
- **RTF (RTF):** 0.028 (4060 Ti), 0.014 (4090), 0.526 (M4 CPU)
- **First Response Time:** 0.339–0.443 seconds
- **Total Processing Time:** 1.363–1.668 seconds
- **Average RTF (API tests):** 0.497–0.685

# Hardware mentioned
- NVIDIA RTX 4060 Ti, 4090, M4 CPU, RTX 3090

# Software/version mentioned
- GPT-SoVITS v2 ProPlus, `api_v2.py`

# Evidence level
Self-reported benchmarking by user contributors; no verified maintainer endorsement.

# Useful paraphrases
- GPT-SoVITS v2 ProPlus can achieve low latency responses (~0.4s) with parallel inference enabled.
- Total RTF varies significantly between hardware (0.014–0.526).

# Confidence
Low to medium; data comes from unverified user experiments.

# Unresolved questions
- Is CUDA Graph optimization required for Korean input to achieve acceptable RTF?
- Are API overheads included in total processing times?

# Last Updated
2026-10-03T00:10:56+08:00

Extraction: 4000 characters; truncated=True.
Evidence SHA256: b1ec80e1dbab6ce190563b9b83ddac53f40ae6d4968a5f0a0337d64fe8784f34
Evidence file: research/raw/runs/20261002T160959Z-cf44ea88/source1-evidence.json
Review status: unreviewed raw evidence.
