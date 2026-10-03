# Title
Inference speed issue of ProPlus version.
# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
# Source type
GitHub issue thread
# Observed claims
User Aleksandar-Lazarevic reported ProPlus RTF values of 0.028 (4060Ti), 0.014 (4090), and 0.526 (M4 CPU) for a 1400-word reference yielding ~4 minutes generation. User JHP0124 measured 1.1s–1.8s total inference time for a Chinese sentence on RTX 3090, noting RTF ~1.53 in one test and 0.497 average in another, questioning how to reach 0.028.
# Relevant configuration
GPT-SoVITS v2 ProPlus; CUDA Graph acceleration mentioned; HuggingFace demo on H200 (half precision).
# Measured performance numbers
0.028 RTF (4060Ti), 0.014 RTF (4090), 0.526 RTF (M4); 1.1s–1.8s total time (3090); 0.443s first response, 1.363s total, 0.89s audio; 0.497 average RTF.
# Hardware mentioned
RTX 3090, RTX 4060 Ti, RTX 4090, Apple M4 CPU, NVIDIA H200.
# Software/version mentioned
GPT-SoVITS v2 ProPlus, CUDA Graph, HuggingFace demo.
# Evidence level
Mixed; unverified user reports and inconsistent RTF calculations.
# Useful paraphrases
ProPlus claims sub-0.05 RTF on high-end GPUs; real-world tests on 3090 yield ~0.5–1.5 RTF; CUDA Graph may help but implementation unclear.
# Confidence
Low; conflicting metrics and unclear definitions of RTF boundaries.
# Unresolved questions
Does RTF include BERT reference generation? What exactly is the “first response time” vs. total audio generation? Is CUDA Graph enabled by default?
# Last Updated
2026-10-02T23:06:12+08:00

Extraction: 2810 characters; truncated=False.
Evidence SHA256: 6d1401433d30ced0ac81d10ac43b8f5ad3f22fec0cc408a43d3b6d141411c6ef
Evidence file: research/raw/runs/20261002T150451Z-dfe7ed52/source2-evidence.json
Review status: unreviewed raw evidence.
