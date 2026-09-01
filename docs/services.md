# Nahida Services

[← Back to README](../README.md)

This page describes the services used by **NahidaProject**, what each service does, and how to start each component individually.

---

## Architecture

The current NahidaProject service architecture is:

```text
                         NahidaProject
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
  Nahida Desktop Pet                       Nahida Brain
   Tauri + Live2D                               │
                                                │
                             ┌──────────────────┼──────────────────┐
                             │                  │                  │
                             ▼                  ▼                  ▼
                         Llama LLM        SenseVoice STT      TTS Client
                         Port 8080             │                  │
                                                               Port 9880
                                                                   │
                                                                   ▼
                                                              GPT-SoVITS
```

The important difference is that **Llama LLM and SenseVoice STT are managed by Nahida Brain**.

They normally do not need to be started as separate services.

---

# Service Overview

| Service            | Type                  | Default Port | Started By          |
| ------------------ | --------------------- | -----------: | ------------------- |
| Nahida Desktop Pet | Independent process   |            - | `npm run tauri dev` |
| Nahida Brain       | Independent process   |            - | `python main.py`    |
| Llama LLM          | Brain-managed process |       `8080` | Nahida Brain        |
| SenseVoice STT     | Brain module          |            - | Nahida Brain        |
| GPT-SoVITS TTS     | Independent process   |       `9880` | GPT-SoVITS API      |

---

# 1. GPT-SoVITS TTS

GPT-SoVITS provides the voice synthesis backend used by Nahida Brain.

It converts Nahida's generated text response into speech.

## Directory

```text
D:\Users\User\Desktop\NahidaProject\GPT-SoVITS
```

## Start

Open CMD and run:

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\GPT-SoVITS
conda run -n GPTSoVits --no-capture-output python api_v2.py -a 127.0.0.1 -p 9880
```

The API will listen on:

```text
http://127.0.0.1:9880
```

## Alternative

If the Conda environment has already been activated:

```cmd
conda activate GPTSoVits
cd /d D:\Users\User\Desktop\NahidaProject\GPT-SoVITS
python api_v2.py -a 127.0.0.1 -p 9880
```

## Purpose

```text
Nahida Brain
     │
     │ text
     ▼
GPT-SoVITS
     │
     │ generated audio
     ▼
Speaker
```

---

# 2. Nahida Brain

Nahida Brain is the main AI backend of the project.

It is responsible for:

* Starting and managing the local LLM
* Receiving user input
* Managing conversation history
* Managing memory
* Running SenseVoice speech recognition
* Sending requests to GPT-SoVITS
* Generating Nahida's responses

## Directory

```text
D:\Users\User\Desktop\NahidaProject\nahida_brain
```

## Python Environment

Nahida Brain currently reuses the Python virtual environment from:

```text
D:\Users\User\Desktop\NahidaProject\stt-compare\.venv
```

Do not create or use:

```text
D:\Users\User\Desktop\NahidaProject\.venv
```

## Start

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\nahida_brain
D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe main.py
```

When Nahida Brain starts, it will also start the Llama LLM automatically.

Example:

```text
[Llama] Starting with Nahida Brain...
[Llama] Endpoint: http://127.0.0.1:8080
[Llama] Ready.
```

The normal architecture is therefore:

```text
main.py
  │
  ├── Llama LLM
  ├── Memory
  ├── Conversation
  ├── SenseVoice
  └── TTS Client
```

---

# 3. Llama LLM

The Llama service hosts the local language model used by Nahida Brain.

The current model is:

```text
Qwen3.5-9B-heretic.Q6_K.gguf
```

The server listens on:

```text
http://127.0.0.1:8080
```

## Normal Usage

Normally, **do not start Llama manually**.

Starting:

```cmd
python main.py
```

inside `nahida_brain` will automatically launch the Llama server.

The equivalent Llama command is approximately:

```cmd
llama serve -m "D:\Users\User\Desktop\NahidaProject\Qwen3.5-9B-heretic.Q6_K.gguf" -ngl 99 -c 8192 --reasoning off --host 127.0.0.1 --port 8080
```

---

## Start Llama Manually

Manual startup is mainly useful for debugging.

Activate the project Python environment:

```cmd
call D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\activate.bat
```

Enter the project directory:

```cmd
cd /d D:\Users\User\Desktop\NahidaProject
```

Start the server:

```cmd
llama serve -m "Qwen3.5-9B-heretic.Q6_K.gguf" -ngl 99 -c 8192 --reasoning off --host 127.0.0.1 --port 8080
```

If port `8080` is already being used by a compatible Llama server, Nahida Brain can reuse the existing service instead of starting another one.

---

# 4. SenseVoice STT

SenseVoice is the Speech-to-Text component.

It converts microphone audio into text before sending the text to Nahida Brain.

The current implementation uses:

```text
SenseVoiceSmall
```

## Important

SenseVoice is **not a standalone HTTP service**.

There is no separate command such as:

```text
sensevoice_server.py
```

Instead, SenseVoice is loaded directly by Nahida Brain.

```text
Microphone
    │
    ▼
SenseVoice
    │
    │ recognized text
    ▼
Nahida Brain
```

---

## Enable SenseVoice

Set:

```cmd
set NAHIDA_SENSEVOICE_STT=1
```

before starting Nahida Brain.

Example:

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\nahida_brain

set NAHIDA_SENSEVOICE_STT=1

D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe main.py
```

---

# 5. Audio Device Selection

Before starting the full voice system, NahidaProject can scan all available audio input and output devices.

The system default device is selected by default.

Run:

```cmd
D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe D:\Users\User\Desktop\NahidaProject\nahida_brain\main.py --select-audio-devices "%TEMP%\NahidaProject_audio_devices.json"
```

The program will:

1. Scan available microphone devices.
2. Scan available speaker/output devices.
3. Select the system default devices initially.
4. Allow the user to choose another input device.
5. Allow the user to choose another output device.
6. Save the selected devices to a JSON configuration file.

The configuration is stored at:

```text
%TEMP%\NahidaProject_audio_devices.json
```

---

# 6. Start Nahida Brain with STT and TTS

To manually start the full Nahida Brain voice stack:

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\nahida_brain

set NAHIDA_SENSEVOICE_STT=1
set NAHIDA_TTS=1
set NAHIDA_AUDIO_CONFIG=%TEMP%\NahidaProject_audio_devices.json
set PYTHONUTF8=1

D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe main.py
```

This starts:

```text
Nahida Brain
├── Llama LLM
├── SenseVoice STT
├── Memory System
├── Conversation System
└── GPT-SoVITS Client
```

GPT-SoVITS itself must already be running separately on port `9880`.

---

# 7. Nahida Desktop Pet

The desktop pet is the graphical frontend of NahidaProject.

It uses:

* Tauri
* PixiJS
* Live2D Cubism
* TypeScript
* Rust

## Directory

```text
D:\Users\User\Desktop\NahidaProject
```

## Start

```cmd
cd /d D:\Users\User\Desktop\NahidaProject
npm run tauri dev
```

This starts the Tauri development application and loads the Live2D Nahida model.

---

# Full Manual Startup

For development and debugging, the complete system can be started manually using multiple CMD windows.

## Terminal 1 — GPT-SoVITS

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\GPT-SoVITS
conda run -n GPTSoVits --no-capture-output python api_v2.py -a 127.0.0.1 -p 9880
```

---

## Terminal 2 — Audio Device Setup

Run this when selecting or changing microphone/speaker devices:

```cmd
D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe D:\Users\User\Desktop\NahidaProject\nahida_brain\main.py --select-audio-devices "%TEMP%\NahidaProject_audio_devices.json"
```

---

## Terminal 3 — Nahida Brain

```cmd
cd /d D:\Users\User\Desktop\NahidaProject\nahida_brain

set NAHIDA_SENSEVOICE_STT=1
set NAHIDA_TTS=1
set NAHIDA_AUDIO_CONFIG=%TEMP%\NahidaProject_audio_devices.json
set PYTHONUTF8=1

D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe main.py
```

Llama will automatically start together with Nahida Brain.

---

## Terminal 4 — Desktop Pet

```cmd
cd /d D:\Users\User\Desktop\NahidaProject
npm run tauri dev
```

---

# Startup Summary

For the normal full system, only three main processes need to be started:

```text
1. GPT-SoVITS
       ↓
2. Nahida Brain
       ├── Llama
       └── SenseVoice
       ↓
3. Nahida Desktop Pet
```

You do **not** normally need to start Llama or SenseVoice separately.

---

# Ports

|   Port | Service        |
| -----: | -------------- |
| `8080` | Llama LLM      |
| `9880` | GPT-SoVITS API |

You can check whether a port is listening with:

```cmd
netstat -ano | findstr :8080
```

or:

```cmd
netstat -ano | findstr :9880
```

---

# Development Notes

When debugging a specific component, it is usually better to start only that component and its required dependencies.

For example:

### Test Desktop Pet only

```cmd
npm run tauri dev
```

### Test LLM only

```cmd
llama serve -m "Qwen3.5-9B-heretic.Q6_K.gguf" -ngl 99 -c 8192 --reasoning off --host 127.0.0.1 --port 8080
```

### Test Nahida Brain

```cmd
D:\Users\User\Desktop\NahidaProject\stt-compare\.venv\Scripts\python.exe main.py
```

### Test TTS API

```cmd
conda run -n GPTSoVits --no-capture-output python api_v2.py -a 127.0.0.1 -p 9880
```

---

[← Back to README](../README.md)
