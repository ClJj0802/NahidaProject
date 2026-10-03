# Topic
GPT-SoVITS v2 ProPlus inference speed and measurement boundaries.

# Summary
The two issues contain user reports and quoted speed claims, not a controlled comparison. Short-sentence latency cannot be compared directly with RTF for several minutes of audio. No measured optimization benefit or RTX 5060 Ti result is established here. [S1] [S2]

# Confirmed Findings
- Confirmed as source content only: both issues quote RTF claims of 0.028 on 4060 Ti, 0.014 on 4090 and 0.526 on M4 CPU. The original benchmark conditions were not independently verified. Evidence: quoted claim. [S1] [S2]
- RTF is a ratio of processing time to generated audio duration, not a duration in seconds. S1 explicitly labels its total RTF this way. Evidence: reported metric definition. [S1]
- Contributor XXXXRT666 suggests CUDA Graph in S2 and says that implementation was not open source at the time of the comment. Contributor status does not establish maintainer status. Current availability and any speedup remain unverified. Evidence: contributor suggestion. [S2]

# Likely Findings
- In S1, reported average RTF values appear to use API response time/audio duration: 0.442/0.89 is about 0.497; 0.664/0.97 is about 0.685. Total RTF uses a different numerator. This is an arithmetic inference, not a verified description of the measurement code. [S1]
- Different timing boundaries and input lengths prevent a fair comparison with the quoted long-audio benchmark. The cause of the users' latency has not been established. [S1] [S2]

# User Reports
- Aleksandar-Lazarevic reports 1.1–1.8 seconds for 20–25 Chinese characters on RTX 3090, excluding reference-audio BERT generation time. No reproducible script or complete software stack is supplied in the captured text. [S2]
- JHP0124 reports Korean tests on RTX 3090 before CUDA Graph: first responses 0.443/0.339 seconds, total processing 1.363/1.668 seconds, audio lengths 0.89/0.97 seconds, total RTF 1.531/1.719. The first test also appears in S2 from the same author; count it once. [S1] [S2]
- S1 lists batch_size=4, text_split_method=cut0 and string values for parallel_infer and streaming_mode. These are reported request settings, not validated recommendations. [S1]

# Recommended Experiments
Proposed measurements, not proven optimizations:
- On a fixed installed version, record cold and warm runs separately; fix voice, text, language, reference audio and parameters.
- Measure time to first audio, total generation time and output duration separately; report RTF with an explicit timing boundary.
- Account for reference-audio preprocessing and transport overhead before comparing latency. [S2]
- Test batch size and sentence splitting one change at a time; record latency, throughput, memory and output quality. [S1]
- Investigate CUDA Graph support for the installed version before designing any comparison; these issues provide no implementation or measured benefit. [S2]

# Hardware Relevance
Our RTX 5060 Ti 16GB, Ryzen 5 7500X3D and 16GB RAM were not tested by either source. The cited 4060 Ti result does not predict this host's latency. No installed GPT-SoVITS settings were changed.

# Confidence
Medium confidence that the captured text is represented accurately; low confidence in performance generalization or optimization effectiveness.

# Evidence level
Primary user reports, duplicated user measurements, quoted benchmark claims and a contributor suggestion. No independently reproduced benchmark or verified maintainer performance guarantee. Raw records were reviewed before this synthesis was accepted.

# Sources
- [S1](https://github.com/RVC-Boss/GPT-SoVITS/issues/2579): bounded main text, 4000-character cap; truncated near the footer.
- [S2](https://github.com/RVC-Boss/GPT-SoVITS/issues/2571): bounded main text, 4000-character cap; not truncated.
Raw: research/raw/gpt_sovits_source_1.md and research/raw/gpt_sovits_source_2.md. Publication dates and changes outside the captured content were not verified.

# Last Updated
2026-10-02 (Asia/Singapore). Review status: reviewed with corrections to the Qwen synthesis draft. Software performance knowledge needs revalidation before changing a deployment.
