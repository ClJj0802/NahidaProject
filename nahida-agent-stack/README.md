# Nahida Research Core V1 + Evidence Review V2

Host runner for the existing OpenClaw **2026.9.2**, Qwen3.5-9B, 16K/one-slot stack. It retains the internal Docker network, Squid, DNS relay and fixed LLM relay. It does not enable OpenClaw memory, skills or shell tools.

This is an optional research subsystem, separate from the desktop pet and normal Brain chat. Run commands from the `NahidaProject` repository root.

The host runner requires Python 3.11+, Docker Desktop and the existing local `openclaw.json`. To start the model itself, it also needs the `llama` executable on `PATH` and the configured GGUF: it checks the configured model-ID path, then falls back to `models/<GGUF filename>`. The credential-bearing configuration is ignored by Git, and existing Docker containers are local machine state. A fresh checkout does not include this setup; the Dockerfiles here are image recipes, not a complete automatic setup. The runner expects `nahida-research-net` (internal, `172.30.50.0/24`), `nahida-egress-net`, the fixed `nahida-research-run`, `nahida-egress-proxy`, `nahida-dns` and `nahida-llm-relay` containers, and the matching agent/browser images. It validates this existing setup rather than provisioning replacements. Offline review commands need Python and the saved research workspace, but do not need Docker or a running model.

Start a full research run:

```powershell
python nahida-agent-stack/research_runner.py "GPT-SoVITS speed optimization"
```

This runs Discovery → Source 1 → Source 2 → Synthesis. The default discovery page is the GPT-SoVITS GitHub issue search for `inference speed`. For another topic, supply a narrowly filtered public GitHub issue-list URL with `--discovery-url` and a separate artifact basename with `--prefix`. The topic is limited to 1–300 characters; prefixes start with a lowercase letter or digit, use only lowercase letters, digits and underscores, and are at most 64 characters. Synthesis filenames currently always use `<prefix>_speed.md`, including for other topics. V1 discovery supports GitHub issue lists; it is not a general search engine.

Re-run a stage independently:

```powershell
python nahida-agent-stack/research_runner.py --stage health
python nahida-agent-stack/research_runner.py --stage discovery
python nahida-agent-stack/research_runner.py --stage source1
python nahida-agent-stack/research_runner.py --stage source2
python nahida-agent-stack/research_runner.py --stage synthesis
```

Source stages consume `research/raw/<prefix>_sources.md`. Synthesis consumes only the two Raw checkpoints; it does not inherit any conversation. The default outputs are:

```text
Nahida's file/research/raw/gpt_sovits_sources.md
Nahida's file/research/raw/gpt_sovits_source_1.md
Nahida's file/research/raw/gpt_sovits_source_2.md
Nahida's file/research/knowledge/drafts/gpt_sovits_speed.md
```

Existing checkpoints are backed up under `research/archive/checkpoints/<run-id>/` before replacement. Use `--prefix core_v1_smoke` to test without replacing the reviewed Raw milestone files. The reviewed milestone Knowledge remains at `research/knowledge/gpt_sovits_speed.md`; automatic runs write only the separate `drafts` directory. Run reports, bounded page evidence, candidate lists and original model drafts are stored under `research/raw/runs/<run-id>/`.

The runner starts the existing infrastructure containers. Missing networks/images/containers are errors; it does not silently rebuild or upgrade them. On Windows it can start Docker Desktop. If port 8080 is unused, it starts the same GGUF with `-c 16384 -np 1 --reasoning off --host 127.0.0.1`. The model has moved into `models/`; an API alias preserves the model ID already configured in OpenClaw. A different model already using port 8080 is rejected. Infrastructure and the local model remain available after a run.

The host owns all navigation and persistence. For each source it creates a fresh browser with no host mounts or published ports, reads at most 4000 visible characters, saves the evidence, and removes the browser. It verifies CDP readiness through `browser doctor --deep`; it first refreshes the selected tab because Gateway retains tab references across browser replacements. Source URLs and titles must match Discovery. Discovery selects two observed browser refs; the host clicks them to obtain real URLs. The model cannot invent an accepted source URL.

Navigation verification waits for the URL and title to match in the same observation, with at most three checks. Discovery also requires the selected issue to belong to the same repository as its search page; source stages require the exact checkpoint URL. GitHub can update the URL before the title, so a new URL alone does not end the readiness check. Each run report records `navigation_checks`, including observed URLs/titles and the final verification status, to explain failures without loosening validation. An initial Discovery page-load timeout permits one fresh-browser retry before the LLM turn; other errors stop immediately, and `browser_retries` records any retry.

Each Qwen stage runs in a new disposable worker with only a read-only `/workspace` mount. A per-run config disables the browser and denies **all** LLM tools. The host supplies bounded evidence; Qwen selects, extracts or compares; the host validates and writes the checkpoint atomically. The original `openclaw.json` keeps its browser/read/write/edit allowlist. There is no Docker socket mount, host shell tool, personal memory mount, browser-profile mount or user login session.

The host renders verified metadata: Raw Title/URL/capture time and synthesis Topic/Sources/update time. Discovery asks Qwen to select only observed ref strings; the host retains the exact browser titles, including spacing. Exact, unambiguous observed titles are also accepted if Qwen returns title strings or singleton title lists; altered titles, unknown refs and duplicate selections still fail. Qwen supplies the evidence sections. A page title used as a document heading cannot erase these fields or replace the verified URL. Known evidence labels in Markdown, colon fields or table rows are normalized without inventing values. Missing or duplicated evidence fields, unverified model URLs and over-limit artifacts still stop the run.

Hard limits: exactly two sources, 4000 characters per page, 6000 characters per model artifact, 48 browser commands per run, two source-browser attempts, zero LLM tool calls, one assistant turn per stage, 120 seconds per model stage and 900 seconds per run. Over-limit or malformed output fails instead of being silently truncated or retried through an unlimited agent loop. The host removes owned containers after failure or interruption and records cleanup failures. A workspace lock prevents two runner invocations sharing the fixed browser IP.

Every run checks the configured model through the relay and tests Squid: `example.com` must work; `192.168.1.1`, `10.0.0.1` and `172.17.0.1` must return proxy denial. These are rejection checks at the proxy, not LAN scanning. Container networks, mounts, images and privilege settings are also checked. DNS and redirect destinations remain subject to Squid's ACL.

**Generated synthesis remains a review-required draft.** Structure and citation validation cannot prove factual correctness. The live milestone exposed URL hallucination, misattributed benchmark claims, duplicated tests and a misleading synthesized comparison. Human/host evidence review corrected the milestone Knowledge before accepting it. Automatic drafts stay in `research/knowledge/drafts`; the runner never promotes them or overwrites reviewed Knowledge. Reports distinguish `knowledge_drafts` from `knowledge_created`. Future knowledge readers must exclude drafts. Do not feed automatic drafts into Nahida Brain or treat quoted performance figures as verified recommendations.

Completed full runs now save immutable host-rendered artifacts alongside their original model output and bounded captures, index an independent SQLite database at `research/db/research.db`, and prepare `research/reviews/<run-id>/packet.json`. Failed and individual-stage runs are indexed as run records without automatically proposing new knowledge. Legacy full runs import their original `synthesis-draft.txt`, never the mutable `<prefix>_speed.md` file. Repeating a prefix cannot change an older review's inputs.

Evidence Review V2 provides offline `index`, `prepare`, `check`, `apply`, `search`, `context`, `retrieve` and `export` commands. See [REVIEWING.md](REVIEWING.md) for the review procedure and the reviewed example from the user's run. Applying a named review promotes only explicitly approved claims; exact excerpts, source hashes and character offsets are checked and stored. Text matching proves provenance, not the truth of a paraphrase or benchmark. Classification and semantic checking remain the reviewer's responsibility.

`search` is a read-only audit query that returns only reviewed statements and their evidence. It excludes pending/rejected/archived entries and the original unreviewed proposed text. `context` supplies a compact JSON string of at most 4000 Unicode characters with evidence type, confidence and source links. `retrieve` accepts a bounded UTF-8 JSON request on stdin and scopes results to a recognized reviewed topic or a short technical follow-up. Queries add no model turn and perform no writes.

Nahida Brain now calls `retrieve` during chat. A single existing chat inference selects relevant knowledge IDs; the host displays the approved statements, classifications and source links instead of accepting rewritten technical claims. Actual template/tokenizer checks enforce the local context capacity before adding optional research. See [Brain integration](../nahida_brain/RESEARCH.md) for startup, boundaries, failure behavior and tests. The previous reviewed milestone is retained. Retention/decay and autonomous scheduling remain later work; milestones are recorded in `MILESTONE.md`.

Brain's separate live lookup bridge now calls `live_lookup.py` with bounded UTF-8 JSON stdin containing only `kind` (`weather`, `page`, or `search`) and a public `query`. It reuses the same infrastructure checks, exclusive browser lock, disposable Chromium and Squid. External data is accessed only through browser navigation/extraction, never host HTTP fetching or new Research Agent shell tools. A local port-8080 readiness check does not start a model or make an inference. Lookups have a 110-second deadline, 18 browser-call budget, 4000 characters per page and at most two sources; the parent waits at most 145 seconds including cleanup. Owned browser containers are removed and reports/captures stay in `research/raw/lookups/<id>/`, outside the reviewed database and four-stage research workflow.

Current weather through Open-Meteo and direct public-page navigation passed real Brain synthetic tests. Weather results are model estimates, with geographic ambiguity handling, units/range checks, timezone-aware timestamps and rejection of data older than three hours. Brain renders source-backed values and keeps ephemeral execution receipts for follow-ups; it never sends private memories, assistant-invented locations or active-context text to the helper. Nearby-food requests ask for an explicit city or area. The current Mojeek/Bing search attempt rejects access challenges and unrelated title links; real restaurant search is **not yet usable in this environment**. Earlier Google, DuckDuckGo and Brave probes also met challenges. No verification challenge was solved or personal browser session used. Direct page snippets are unreviewed evidence and cannot establish current opening/ratings/distance by themselves. See [Brain usage](../nahida_brain/RESEARCH.md) for examples, the disable flag and smoke scripts.

Validation:

```powershell
python -m unittest discover -s nahida-agent-stack/tests -v
python -m py_compile nahida-agent-stack/research_runner.py nahida-agent-stack/research_review.py nahida-agent-stack/live_lookup.py
```

Keep the existing credential-bearing `openclaw.json`, logs, state and vendor checkout local; they are ignored by this directory's `.gitignore`. Never paste CDP or Gateway tokens into documentation.
