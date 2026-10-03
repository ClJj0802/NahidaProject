# Title
Windows 24H2 update causes slow inference / windows 24H2更新导致推理慢

# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2278

# Source type
GitHub Issue Report (RVC-Boss repository, Issue #2278).

# Observed claims
Windows 11 24H2 causes severe performance regression on NVIDIA RTX 4090 for GPT-SoVITS inference. GPU utilization drops below 30%, and speed falls below expectations (slower than RTX 4070). Downgrading to Windows 11 23H2 or using Linux restores full performance.

# Relevant configuration
- **OS:** Windows 11 24H2 (affected), 23H2 (normal), Ubuntu 20.04/22.04 (normal).
- **GPU:** NVIDIA RTX 4090 (affected), RTX 4070 (normal).
- **Software:** PyTorch 2.0.0 + cu118, cuDNN 8.7.0, CUDA 11.8/12.8, Drivers 537.58–572.83.
- **Inference:** AMP enabled (autocast, fp16), `inference_webui.py`.

# Measured performance numbers
- **Windows 11 24H2 + RTX 4090:** GPU utilization ~30–40%, speed slower than RTX 4070.
- **Windows 11 23H2 + RTX 4090:** GPU utilization ~90–100%.
- **Linux:** GPU utilization normal.

# Hardware mentioned
NVIDIA RTX 4090, NVIDIA RTX 4070.

# Software/version mentioned
Windows 11 24H2, Windows 11 23H2, PyTorch 2.0.0, cuDNN 8.7.0, CUDA 11.8, CUDA 12.1, NVIDIA Driver 537.58–572.83, psutil.

# Evidence level
Moderate. Multiple contributors tested; one verified a code patch (psutil priority change) resolved throttling.

# Useful paraphrases
Set Python process priority to `HIGH_PRIORITY_CLASS` using `psutil` before inference.

# Confidence
Medium. Specific to Windows 11 24H2 and RTX 4090; workaround effective for reported case.

# Unresolved questions
Whether priority adjustment is the root cause or a workaround for a driver/kernel issue.

# Last Updated
2026-10-03T00:11:24+08:00

Extraction: 3994 characters; truncated=True.
Evidence SHA256: 1ed48bfd44db211c5b0cb44ad77d516c1f71def2dd77e4b9ac5e9e737789158c
Evidence file: research/raw/runs/20261002T160959Z-cf44ea88/source2-evidence.json
Review status: unreviewed raw evidence.
