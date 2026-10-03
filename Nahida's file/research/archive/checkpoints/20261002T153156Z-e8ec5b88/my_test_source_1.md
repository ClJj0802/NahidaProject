# about GPT-SoVITS v2 ProPlus's RTF(inference speed) a criterion

# Title
about GPT-SoVITS v2 ProPlus's RTF(inference speed) a criterion

# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2579

# Source type
GitHub issue discussion

# Observed claims
- RTF of 0.028 on RTX 4060 Ti
- RTF of 0.014 on RTX 4090 (1400 words ~4 min, 3.36 s inference)
- RTF of 0.526 on M4 CPU
- API first response time 0.3–0.4 s for long Korean sentence
- Measured RTF 1.531 (total processing 1.363 s / audio 0.89 s)
- Average RTF 0.497–0.685 across test runs
- Token generation speed ~150 it/s observed in logs

# Relevant configuration
`top_k=5`, `top_p=1`, `temperature=1`, `batch_size=4`, `parallel_infer=True`, `speed_factor=1.0`, `sample_steps=32`, `text_lang=auto`, `prompt_lang=ja`

# Measured performance numbers
RTF: 0.014–1.719 | First response: 0.339–0.443 s | Total processing: 1.363–1.668 s | Token speed: ~150 it/s

# Hardware mentioned
RTX 4060 Ti, RTX 4090, M4 CPU, H200 (HuggingFace demo)

# Software/version mentioned
GPT-SoVITS v2 ProPlus, api_v2.py

# Evidence level
User-submitted measurements; unverified

# Useful paraphrases
RTF varies widely by hardware and sentence length; Korean processing shows higher latency than English.

# Confidence
Low – single-run measurements, no controlled benchmarks

# Unresolved questions
Impact of `cuda_graph` on Korean inference; streaming mode effect; reproducibility across environments

# Last Updated
2026-10-02T23:27:05+08:00

Extraction: 4000 characters; truncated=True.
Evidence SHA256: b1ec80e1dbab6ce190563b9b83ddac53f40ae6d4968a5f0a0337d64fe8784f34
Evidence file: research/raw/runs/20261002T152619Z-b18dbfa8/source1-evidence.json
Review status: unreviewed raw evidence.
