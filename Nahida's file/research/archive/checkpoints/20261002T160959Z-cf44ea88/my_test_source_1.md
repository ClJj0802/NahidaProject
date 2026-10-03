# Title
about GPT-SoVITS v2 ProPlus's RTF(inference speed) a criterion

# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2579

# Source type
GitHub issue discussion on RVC-Boss repository regarding GPT-SoVITS v2 ProPlus inference speed.

# Observed claims
RTF (Real-Time Factor) varies significantly by hardware. User achieved first response times between 0.3 to 0.4 seconds using `api_v2` with sentence splitting. One user questioned if specific RTF values were normal on RTX 3090 prior to `cuda_graph` application.

# Relevant configuration
`batch_size: 4`, `parallel_infer: True`, `split_bucket: True`, `sample_steps: 32`. Sentence splitting method `cut0` used for Korean text. `super_sampling: False`. `speed_factor: 1.0`.

# Measured performance numbers
4060 Ti: RTF 0.028.
4090: RTF 0.014 (1400 words in 3.36s).
M4 CPU: RTF 0.526.
RTX 3090 (specific test): First response 0.443s, Total processing 1.363s, RTF 1.531.
Sentence API test: First response 0.339s, Average RTF 0.685.
Tokenization speed observed: ~150 tokens/s during T2S decoding.

# Hardware mentioned
RTX 4060 Ti, RTX 4090, M4 CPU, H200 (HuggingFace demo), RTX 3090.

# Software/version mentioned
GPT-SoVITS v2 ProPlus, `api_v2.py`, HuggingFace demo.

# Evidence level
Mixed: Self-reported benchmarks from users and community members. Logs provided for one specific run.

# Useful paraphrases
RTF is highly hardware-dependent. Sentence-level streaming via `api_v2` reduces latency to under 0.4 seconds for initial reaction. Batch processing and parallel inference are active in tested configs.

# Confidence
Low to Medium: Claims are user-generated without standardized validation.

# Unresolved questions
Why does the RTX 3090 show RTF 1.531 in one log while claiming 0.028 elsewhere? How does `cuda_graph` specifically impact the observed variance?

# Last Updated
2026-10-02T23:47:23+08:00

Extraction: 4000 characters; truncated=True.
Evidence SHA256: b1ec80e1dbab6ce190563b9b83ddac53f40ae6d4968a5f0a0337d64fe8784f34
Evidence file: research/raw/runs/20261002T154631Z-25c6a42b/source1-evidence.json
Review status: unreviewed raw evidence.
