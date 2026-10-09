# Nahida Pet

A Windows companion project with a **Tauri / PixiJS / Live2D desktop pet** and a separate **Python Nahida Brain** for local-model chat, memory, speech recognition, and voice synthesis.

The pet currently renders Nahida in a transparent, always-on-top 200 × 380 window at the bottom-right of the primary display, with mouse-following gaze and an FPS counter. Chat runs in the Brain terminal. Communication between the pet and Brain, speech-driven lip sync, and emotion-driven expression changes are not implemented yet.

## Documentation

* **Home** — Project setup, launcher, and Live2D desktop pet
* [Services →](docs/services.md) — Startup, model selection, Brain commands, STT, and Streaming TTS
* [Memory architecture →](docs/NAHIDA_MEMORY_ARCHITECTURE.md) — Current implementation and the longer-term design draft
* [Research in Brain →](nahida_brain/RESEARCH.md) — Reviewed knowledge, live lookup, configuration, and limits
* [Research tools →](nahida-agent-stack/README.md) — Isolated research workflow and [evidence review](nahida-agent-stack/REVIEWING.md)

---

## Tech Stack

### Desktop Pet

* Tauri v2
* TypeScript
* PixiJS 8
* untitled-pixi-live2d-engine
* Live2D Cubism Core 5
* Rust

### AI Services

* Nahida Brain
* llama.cpp
* Qwen3.5
* SenseVoiceSmall
* GPT-SoVITS v2Pro with local Nahida fine-tuned weights
* Python

Optional research and live lookup use the separately configured Docker / OpenClaw stack in `nahida-agent-stack/`.

---

## Prerequisites

Before running the project, make sure the following tools are installed.

### Node.js

Install Node.js and verify:

```bash
node --version
npm --version
```

### Rust

Tauri requires Rust and Cargo.

On Windows, Rust can be installed with:

```cmd
winget install --id Rustlang.Rustup
```

After installation, restart the terminal and verify:

```cmd
rustc --version
cargo --version
rustup --version
```

Use the MSVC toolchain:

```cmd
rustup default stable-msvc
```

### Microsoft C++ Build Tools

Tauri on Windows also requires Microsoft C++ Build Tools.

Install **Visual Studio Build Tools** and enable:

```text
Desktop development with C++
```

Make sure the following components are available:

* MSVC C++ Build Tools
* Windows SDK

---

## Installation

Clone the repository:

```bash
git clone <repository-url>
```

Enter the project directory:

```bash
cd NahidaProject
```

Install all Node.js dependencies:

```bash
npm install
```

The required packages, including PixiJS and the Live2D engine, will automatically be installed from `package.json`.

`npm install` prepares the desktop dependencies. AI services also need the existing `stt-compare/.venv` Python environment, a `GPTSoVits` Conda environment, a `llama` executable available after activating the shared venv, and local model files. See [service setup](docs/services.md#local-environments-and-model-files).

Place GGUF models under `models/`; the launcher defaults to `models/Qwen3.5-9B-heretic.Q6_K.gguf` and can select other models in subfolders. GGUF files and Python environments are ignored by Git. `GPT-SoVITS/` is a separate Git checkout recorded as a gitlink; this repository currently has no `.gitmodules` configuration, so a fresh clone also needs that checkout and its local weights prepared separately.

## Start with the Service Launcher

From the project root, run:

```cmd
start_nahida.bat
```

Use **Up / Down** to move, **Space** to toggle services, **Enter** to launch, and **Esc** to exit. The default selection starts GPT-SoVITS, Llama, Nahida Brain, the desktop pet, and enables SenseVoice inside Brain. Select **Choose other model to start** to choose a GGUF under `models/`.

The launcher manages Llama and GPT-SoVITS as separate processes. Running `nahida_brain/main.py` alone requires an existing Llama service on port `8080`; it does not start one. See [manual startup](docs/services.md#manual-startup) for individual components.

The launcher currently hardcodes `D:\Users\User\Desktop\NahidaProject` in its `ROOT` setting. If the checkout moves, update that setting, the TTS paths in `nahida_brain/main.py`, and the custom GPT-SoVITS inference configuration before starting. A listening Llama service is retained; stop it before using the launcher to load a different model.

---

## Run the Desktop Pet

Start the Tauri development application:

```bash
npm run tauri dev
```

Run this command from the project root. `run_Nahida_desktop_pet_only.bat` runs the same command and also expects that working directory.

Tauri will:

1. Start the frontend development server.
2. Compile the Rust/Tauri backend.
3. Open the desktop application.
4. Load the Live2D model through PixiJS.

> This command only starts the desktop pet.
>
> For the AI backend, STT, TTS, and local LLM, see the [Services documentation](docs/services.md).

---

## Project Structure

```text
NahidaProject/
├── public/
│   ├── cubism/
│   │   └── live2dcubismcore.min.js
│   │
│   └── models/
│       └── Nahida/
│           ├── Nahida.model3.json
│           ├── Nahida.moc3
│           ├── Nahida.physics3.json
│           ├── Nahida.8192/
│           ├── *.motion3.json
│           └── *.exp3.json
│
├── src/
│   ├── main.ts
│   └── styles.css
│
├── src-tauri/
│
├── models/
│   └── *.gguf                  # Local LLM weights, including subfolders
│
├── nahida_brain/
│   ├── main.py
│   ├── src/
│   ├── tests/
│   ├── persona/
│   ├── data/nahida.db          # Local conversation and personal memory
│   └── RESEARCH.md
│
├── GPT-SoVITS/                 # Separate checkout, environment, and voice weights
│
├── nahida-agent-stack/
│   ├── research_runner.py
│   ├── research_review.py
│   ├── live_lookup.py
│   └── README.md
│
├── Nahida's file/
│   └── research/              # Independent research artifacts and database
│
├── stt-compare/
│   └── .venv/                 # Shared Brain / STT Python environment
│
├── docs/
│   ├── services.md
│   └── NAHIDA_MEMORY_ARCHITECTURE.md
│
├── start_nahida.bat
├── run_Nahida_desktop_pet_only.bat
├── package.json
└── README.md
```

---

## Live2D Cubism Core

This project currently uses **Live2D Cubism Core 5.x**.

The currently used Live2D engine may not work correctly with Cubism Core 6.x.

If the following error appears:

```text
Cannot read properties of undefined (reading '0')
at CubismRenderer_WebGL.doDrawModel
```

check the console and make sure the application is loading Cubism Core 5.x instead of Core 6.x.

The Core file is expected at:

```text
public/cubism/live2dcubismcore.min.js
```

---

## Troubleshooting

### `cargo` is not found

If you see:

```text
failed to run 'cargo metadata'
program not found
```

install Rust and restart your terminal:

```cmd
winget install --id Rustlang.Rustup
```

Then verify:

```cmd
cargo --version
```

---

### `link.exe` or MSVC is not found

Install **Visual Studio Build Tools** and enable:

```text
Desktop development with C++
```

---

### Live2D model does not appear

Open the Tauri DevTools:

```text
Ctrl + Shift + I
```

Check the **Console** and **Network** tabs for:

```text
404
Failed to fetch
Live2DCubismCore
moc3
texture
model3.json
```

The model entry file should be available at:

```text
public/models/Nahida/Nahida.model3.json
```

---

## Development

After modifying the frontend or Tauri code, run:

```bash
npm run tauri dev
```

again to test the application.

For Node.js dependencies, normally only this command is required after cloning:

```bash
npm install
```

Check TypeScript and build the frontend with:

```cmd
npm run build
```

Build the desktop application with:

```cmd
npm run tauri build
```

`npm run dev` starts Vite alone. The pet uses Tauri window APIs, so use `npm run tauri dev` to test desktop behavior.

Brain and research have separate offline test commands and optional live smoke checks; see [service validation](docs/services.md#validation) and [research usage](nahida_brain/RESEARCH.md).

---

## Next

Continue to the service documentation:

### [Nahida Services →](docs/services.md)
