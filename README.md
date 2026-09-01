# Nahida Pet

A desktop Live2D AI companion built with **Tauri**, **PixiJS**, **Live2D Cubism**, local LLM, speech recognition, and voice synthesis.

## Documentation

* **Home** — Project setup and Live2D desktop pet
* [Services →](docs/services.md) — Nahida Brain, Llama LLM, SenseVoice STT, GPT-SoVITS TTS, and Desktop Pet

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
* GPT-SoVITS
* Python

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

---

## Run the Desktop Pet

Start the Tauri development application:

```bash
npm run tauri dev
```

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
├── nahida_brain/
│   ├── main.py
│   └── ...
│
├── GPT-SoVITS/
│
├── stt-compare/
│   └── .venv/
│
├── docs/
│   └── services.md
│
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

---

## Next

Continue to the service documentation:

### [Nahida Services →](docs/services.md)
