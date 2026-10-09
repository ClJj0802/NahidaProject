# Nahida Services

[← Back to README](../README.md)

This guide describes the current launcher and manual startup paths. Nahida Brain is a terminal application; the Live2D pet runs independently.

## Architecture

```text
start_nahida.bat
├── GPT-SoVITS API             127.0.0.1:9880
├── Llama / llama.cpp          127.0.0.1:8080
├── Nahida Brain               terminal chat and personal memory
│   ├── SenseVoiceSmall        optional in-process microphone input
│   ├── TTSWorker / TTSClient  requests GPT-SoVITS and plays PCM audio
│   └── Research bridges      optional reviewed knowledge and live lookup
└── Nahida Desktop Pet        Tauri + PixiJS + Live2D
```

**The launcher starts Llama separately. Brain connects to an existing Llama service and does not start or stop it.** SenseVoice is loaded inside Brain when enabled. The pet currently renders the model and follows the mouse; Brain communication, speech-driven lip sync, and emotion-driven expressions are not implemented yet.

| Component | Local endpoint | Startup |
| --- | --- | --- |
| Llama LLM | `http://127.0.0.1:8080` | Launcher worker or manual `llama serve` |
| GPT-SoVITS TTS | `http://127.0.0.1:9880` | Launcher worker or manual `api_v2.py` |
| Nahida Brain | Terminal; no HTTP server | Launcher worker or shared-venv `main.py` |
| SenseVoice STT | In-process; no HTTP server | `NAHIDA_SENSEVOICE_STT=1` in Brain |
| Desktop Pet | Tauri window; Vite uses `1420` during development | `npm run tauri dev` |

## Local Environments and Model Files

The examples below use the current checkout at `D:\Users\User\Desktop\NahidaProject` and CMD syntax. Node.js, Rust/MSVC, and desktop dependency setup are covered in the [README](../README.md#prerequisites).

| Component | Current local setup |
| --- | --- |
| Brain / SenseVoice | `stt-compare\.venv\Scripts\python.exe`; includes `numpy`, `sounddevice`, `torch`, and `funasr` for voice input |
| Llama | `llama.exe` available in PATH after activating the shared venv |
| GPT-SoVITS | Separate checkout in `GPT-SoVITS\`, using Conda environment `GPTSoVits` |
| Default LLM weights | `models\Qwen3.5-9B-heretic.Q6_K.gguf` |
| GPT voice weights | `GPT-SoVITS\GPT_weights_v2Pro\Nahida-e15.ckpt` |
| SoVITS voice weights | `GPT-SoVITS\SoVITS_weights_v2Pro\Nahida_e8_s152.pth` |
| Reference voice | `GPT-SoVITS\output\slicer_opt\Nahida_Voice_Example.wav_0000697280_0000824640.wav` |

The launcher and Brain use the shared `stt-compare/.venv`; a root-level `.venv` is not selected by the launcher. Node installation does not create the Python environments or download the model weights. `stt-compare/requirements-lock-before.txt` is a historical environment snapshot, not a maintained installation manifest for the whole project.

If moving the checkout or changing voice weights, update:

- `ROOT` and, if needed, `GPT_ENV` / `DEFAULT_MODEL` in [start_nahida.bat](../start_nahida.bat).
- `TTS_GPT_WEIGHTS`, `TTS_SOVITS_WEIGHTS`, `TTS_REFERENCE_AUDIO`, and the matching reference text in [main.py](../nahida_brain/main.py).
- The `custom` section in [tts_infer.yaml](../GPT-SoVITS/GPT_SoVITS/configs/tts_infer.yaml), used when the API initially loads its models.

The current voice is **v2Pro**, configured for **CUDA and FP16**. Brain explicitly selects its configured GPT/SoVITS weights and performs a streaming warm-up before accepting input.

## Service Launcher

From the project root:

```cmd
start_nahida.bat
```

The interactive menu selects GPT-SoVITS, Llama, Brain, the pet, SenseVoice STT, and an optional alternative GGUF model. The first five entries are selected by default.

- **Up / Down** moves the selection.
- **Space** toggles an entry.
- **Enter** runs preflight checks and launches the selected components.
- **Esc** exits; inside the model picker it returns to the service menu.

The model picker scans `models/**/*.gguf`, including subfolders. Selecting SenseVoice only enables it in a selected Brain process; it does not launch a separate STT server.

The launcher uses CMD tabs in Windows Terminal when available, otherwise separate CMD windows. Brain waits for ports `9880` / `8080` when those services were selected. Port checks establish that something is listening; confirm an existing listener is the intended service. If Llama is already listening, the selected GGUF does not replace its loaded model. Stop that server before selecting another model.

Workers restart after nonzero exit codes with a three-second delay. Normal exits stop the corresponding worker; Brain's `/exit` does not restart it. Exiting Brain leaves separately launched Llama, GPT-SoVITS, and the pet running.

## Manual Startup

Use separate CMD windows for the components below. Start Llama before chatting, and GPT-SoVITS before starting Brain with TTS enabled.

### 1. Llama LLM

```cmd
cd /d "D:\Users\User\Desktop\NahidaProject"
call "stt-compare\.venv\Scripts\activate.bat"
llama serve -m "models\Qwen3.5-9B-heretic.Q6_K.gguf" -ngl 99 -c 16384 -np 1 --reasoning off --host 127.0.0.1 --port 8080
```

These are the launcher's current parameters: a 16384-token context, one slot, and reasoning disabled. To use another GGUF, change the model path or select it through the launcher. Brain always sends chat requests to `http://127.0.0.1:8080/v1/chat/completions`.

### 2. GPT-SoVITS TTS

```cmd
cd /d "D:\Users\User\Desktop\NahidaProject\GPT-SoVITS"
conda run -n GPTSoVits --no-capture-output python api_v2.py -a 127.0.0.1 -p 9880
```

If that Conda environment is already active, the equivalent command is:

```cmd
python api_v2.py -a 127.0.0.1 -p 9880
```

### 3. Nahida Brain

For microphone input and spoken replies:

```cmd
cd /d "D:\Users\User\Desktop\NahidaProject\nahida_brain"
set NAHIDA_SENSEVOICE_STT=1
set NAHIDA_TTS=1
set PYTHONUTF8=1
"..\stt-compare\.venv\Scripts\python.exe" main.py
```

For keyboard input without speech output, set both `NAHIDA_SENSEVOICE_STT` and `NAHIDA_TTS` to `0` before running the same command. Llama is still required for chat. When launched directly, STT defaults to disabled and TTS defaults to enabled. If microphone/model initialization fails, Brain retains keyboard input; if TTS setup fails, it retains text replies.

### 4. Desktop Pet

```cmd
cd /d "D:\Users\User\Desktop\NahidaProject"
npm run tauri dev
```

`run_Nahida_desktop_pet_only.bat` runs the same command and must also be invoked with the project root as the working directory. It starts the graphical pet independently of Brain.

## Brain Input and Commands

Type a message at `You >`. With SenseVoice enabled, press **Enter on an empty line** to start recording. Recording is triggered by this action, rather than by continuous background listening.

| Command | Behavior |
| --- | --- |
| `/memory` | Display current personal memories |
| `/history` | Display recent conversation messages |
| `/summary` | Generate or update today's summary |
| `/summaries` | Display recent daily summaries |
| `/events` | Display structured events |
| `/exit` | End the session and exit Brain |

Personal conversation and memory use `nahida_brain/data/nahida.db`. See [memory implementation and design](NAHIDA_MEMORY_ARCHITECTURE.md#0-current-implementation-2026-10-09) for the implemented behavior and planned layers.

### SenseVoice and Audio Devices

[voice_input.py](../nahida_brain/voice_input.py) uses `iic/SenseVoiceSmall` on CUDA when available, otherwise CPU. Defaults are 16 kHz mono input, 1.5 seconds of silence to end a recording, a 20-second maximum recording, and a 10-second wait for speech. Emotion tags are printed in diagnostics; they do not control the pet's expressions.

The current main entry point does not provide `--select-audio-devices` or read `NAHIDA_AUDIO_CONFIG`. STT tries the system-default microphone and falls back to a usable input device; TTS uses the system-default output device. Device indices can be supplied to `VoiceInput(input_device=...)` and `TTSClient(output_device=...)` in code, but there is no integrated device-picker CLI.

### Streaming TTS

The active path is `main.py` → `TTSWorker` → [tts_client.py](../nahida_brain/src/tts_client.py) → GPT-SoVITS `/tts`. Completed response text is submitted to a background playback worker; the LLM request itself is not streamed.

Current request settings:

```text
top_k=15, top_p=0.7, temperature=0.7
text_split_method=cut5, batch_size=1, batch_threshold=0.75
split_bucket=False, parallel_infer=False, repetition_penalty=1.35
speed_factor=1.0, fragment_interval=0.05, seed=-1
media_type=wav, streaming_mode=1
```

`seed=-1` causes GPT-SoVITS to choose and log an actual random seed. In this API version, `streaming_mode=1` returns each completed sentence fragment over HTTP; it does not emit audio while that sentence's semantic tokens are still being generated. The client reads 16-bit PCM WAV data and uses a 0.06-second prebuffer before playback.

Text cleanup removes bracketed actions, asterisk-delimited actions, emoji, and leading punctuation. It also converts full-width `～` and ASCII `~` to Chinese commas **before** `cut5` segmentation. This lets the backend split at those pauses instead of converting a wave sign into an internal ellipsis after segmentation. Runs of two or more ASCII periods, such as `...` or `.....`, become a single Chinese full stop `。`; single periods and decimal points such as `3.14` are preserved. The displayed and stored reply keeps its original text.

On the next chat message, Brain cancels queued/playing TTS and waits up to three seconds for the worker to become idle. Cancellation is cooperative: a blocking network read can delay it, and the client does not send a backend inference-stop request.

#### Long Delay or `1499/1500`

The semantic decoder has a hardcoded 1500-iteration limit. A short sentence running to that limit can produce a long, mostly quiet audio tail even though tokens are generated quickly. Sentence-fragment streaming can therefore play the first sentence promptly while a later sentence remains blocked.

The wave-to-comma cleanup addresses the reproduced punctuation trigger. There is currently no automatic semantic repetition guard, failed-sentence retry, or skip mechanism. The 180-second network timeout is not a per-sentence generation budget. For diagnosis, record the processed sentence, actual seed, semantic-generation duration, and returned audio duration; a `200 OK` response alone does not establish normal completion.

Logs include `Header ready`, `First playable audio`, and completion wall/audio durations. The final wall/audio ratio includes playback time and is not a synthesis-only benchmark. The client and API print to their terminals; the standard startup does not capture inference logs to a file.

## Environment Flags

Set these before starting Brain, then restart it to load changed settings:

| Variable | Direct Brain default | Effect |
| --- | --- | --- |
| `NAHIDA_SENSEVOICE_STT` | `0` | Enable in-process microphone transcription |
| `NAHIDA_TTS` | `1` | Enable GPT-SoVITS speech output |
| `NAHIDA_RESEARCH_KNOWLEDGE` | `1` | Retrieve available reviewed research knowledge |
| `NAHIDA_LIVE_LOOKUP` | `1` | Enable routing to the optional live lookup helper |

The launcher sets the first two flags from its STT selection and `TTS_ENABLED` setting. Research and lookup flags are inherited from the launching environment.

## Optional Research and Live Lookup

Reviewed research is stored separately under `Nahida's file/research/`; it is not the personal memory database. Brain can retrieve reviewed statements and display their classifications and source links. Real-time lookup has separate bounded weather, public-page, and search routes.

Reviewed-knowledge retrieval uses local files and the existing Llama service. Live lookup and new research runs additionally require the separately configured Docker / OpenClaw infrastructure, local configuration, containers, and images. The helpers do not make Brain start Llama. Weather/public-page lookup is supported; general restaurant search can be blocked or fail, and no Google Maps integration is implemented.

Use the dedicated guides for prerequisites, commands, evidence boundaries, and live checks:

- [Research tools](../nahida-agent-stack/README.md)
- [Evidence review](../nahida-agent-stack/REVIEWING.md)
- [Research and live lookup in Brain](../nahida_brain/RESEARCH.md)

## Validation

From the project root, offline Brain and research unit tests are:

```cmd
"stt-compare\.venv\Scripts\python.exe" -B -m unittest discover -s nahida_brain/tests -v
"stt-compare\.venv\Scripts\python.exe" -B -m unittest discover -s nahida-agent-stack/tests -v
```

Frontend type checking and bundling:

```cmd
npm run build
```

Live smoke checks are documented in [RESEARCH.md](../nahida_brain/RESEARCH.md); they require existing local services and/or research artifacts. `nahida_brain/test_voice_input.py`, `test_mic_level.py`, and the scripts in `stt-compare/` are manual audio/model diagnostics and require devices or model files.

`nahida_brain/test_tts_api.py` makes a real non-streaming request and writes `nahida_test.wav` in its working directory. Its omitted request fields use API defaults, so it is not a like-for-like benchmark of the active streaming client.

Check listening ports without starting services:

```cmd
netstat -ano | findstr :8080
netstat -ano | findstr :9880
netstat -ano | findstr :1420
```

[← Back to README](../README.md)
