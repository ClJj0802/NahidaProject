# Title
Inference speed issue of ProPlus version

# URL
https://github.com/RVC-Boss/GPT-SoVITS/issues/2571

# Source type
GitHub issue discussion

# Observed claims
*   Quoted, unverified RTF claims: 4060 Ti 0.028; 4090 0.014 for roughly four minutes of audio in 3.36s; M4 CPU 0.526.
*   User measurement: Inference time 1.1s–1.8s for Chinese sentence (20–25 characters) on RTX 3090 GPU, excluding BERT generation time.
*   JHP0124 comment measurement (same test as Source 1, not independent evidence): First response time 0.443s, Total processing time 1.363s, Total audio length 0.89s, Total RTF 1.531.
*   JHP0124 asks how to achieve the quoted RTF 0.028; the discussion does not establish that it is unachievable.
*   Contributor XXXXRT666 suggests CUDA Graph, then says that implementation was not open source at the time of the comment. Contributor is not verified maintainer status; no measured speedup is provided.
*   Question: Meaning of 0.028, 0.014 values (asked if seconds).

# Relevant configuration
*   Hardware: NVIDIA RTX 3090, RTX 4060 Ti, RTX 4090, Apple M4 CPU, H200 (Hugging Face demo).
*   Software: GPT-SoVITS v2 ProPlus.
*   Metrics: RTF (Real-time Factor), First response time, Total processing time, Audio length.

# Measured performance numbers
*   Promotional (claimed):
    *   RTX 4060 Ti: 0.028
    *   RTX 4090: 0.014 (1400 words in 4 min, inference time 3.36s)
    *   M4 CPU: 0.526
    *   H200 (HF demo): High speed (unspecified metric).
*   User-measured (RTX 3090):
    *   Inference time: 1.1s–1.8s (20–25 char Chinese sentence).
    *   First response time: 0.443s.
    *   Total processing time: 1.363s.
    *   Audio length: 0.89s.
    *   Total RTF: 1.531.
    *   Average RTF: 0.497.

# Hardware mentioned
*   NVIDIA GeForce RTX 4060 Ti
*   NVIDIA GeForce RTX 4090
*   NVIDIA GeForce RTX 3090
*   Apple M4 CPU
*   H200 (Hugging Face demo)

# Software/version mentioned
*   GPT-SoVITS v2 ProPlus
*   CUDA Graph (proposed acceleration method)

# Evidence level
*   Mixed: Unverified promotional benchmarks vs. specific user measurements.
*   Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# Useful paraphrases
*   "How to interpret the ProPlus speed claims?"
*   "Real-world inference times on consumer GPUs vs. claims."
*   "Is 1.5s reasonable for a 20-char sentence on RTX 3090?"
*   "How to enable CUDA Graphs in GPT-SoVITS?"

# Confidence
*   Low: Critical metric definitions (RTF base) and promotional numbers lack verification.

# Unresolved questions
*   What is the exact definition of RTF used in the 0.028/0.014 claims?
*   Is CUDA Graph acceleration available in the current public version?
*   How much overhead does BERT generation add to the total time?

# Last Updated
2026-10-02 Asia/Singapore
# Extraction scope

Fresh disposable Chromium; bounded main text (4000-character cap, not truncated). Evidence: research/raw/evidence/source_2.json. Publication dates and current CUDA Graph availability not verified. Host review corrected attributions before synthesis.
