# Topic
GPT-SoVITS Speed Optimization

# Summary
Users report significant discrepancies between claimed GPT-SoVITS v2 ProPlus Real-Time Factors (RTF) and measured performance on consumer hardware. Promotional benchmarks (RTF 0.014–0.028) on RTX 4060 Ti and 4090 contradict user measurements (RTF 1.531) on an RTX 3090 for similar inputs. Measurements vary based on timing boundaries (first response vs. total processing), input length, and language (Chinese vs. Korean). Optimization via CUDA Graphs is mentioned but implementation status is unclear.

# Confirmed Findings
- Promotional RTF claims exist but are unverified and likely non-comparable to user tests due to undefined timing boundaries and metrics.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.
- User measurements on RTX 3090 show inference times of 1.1s–1.8s for a 20–25 character Chinese sentence, excluding BERT generation time.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.
- Korean language processing yields RTF values between 0.497 and 1.719, differing from quoted promotional RTF values (0.014, 0.028).
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.
- Iterations per second (it/s) logs show T2S decoding at ~145–151 it/s and BERT feature extraction at 48.14 it/s.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.

# Likely Findings
- Discrepancy between claimed and measured RTF is due to different timing boundaries, input lengths, and language processing complexities.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.
- BERT generation contributes significant overhead to total processing time.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.
- CUDA Graph acceleration may be available but is not definitively confirmed as implemented or open source.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# User Reports
- Inference time of 1.1s–1.8s for a 20–25 character Chinese sentence on RTX 3090.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.
- Korean processing RTF measured at 1.531 and 1.719, questioning normality before CUDA graph optimization.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.

# Recommended Experiments
- Measure total processing time with and without BERT generation included to isolate overhead.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.
- Standardize RTF measurement definitions (processing time vs. response time) and input lengths across tests.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.
- Verify CUDA Graph implementation status and measure speedup if available.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# Hardware Relevance
- Promotional benchmarks cite RTX 4060 Ti and 4090; user measurements cite RTX 3090.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
  - Evidence Level: User-reported benchmark data from GitHub issue (issue #2579 opened by user JHP0124). Data includes specific measurements and configuration parameters, but author explicitly questions validity of results, indicating self-uncertainty about benchmark accuracy.
- M4 CPU and H200 references appear in promotional/demo contexts only.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# Confidence
- Low: Critical metric definitions (RTF base) and promotional numbers lack verification.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# Evidence level
- Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.
  - Source: https://github.com/RVC-Boss/GPT-SoVITS/issues/2571
  - Evidence Level: Mixed: Unverified promotional benchmarks vs. specific user measurements. Limitations: Benchmark definitions unclear (RTF vs. seconds); CUDA Graph implementation not open; hardware/software stack variations.

# Sources
- https://github.com/RVC-Boss/GPT-SoVITS/issues/2579
- https://github.com/RVC-Boss/GPT-SoVITS/issues/2571

# Last Updated
2026-10-02 Asia/Singapore