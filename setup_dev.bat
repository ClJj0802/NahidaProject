@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Usagi Pet - Development Environment Setup

rem ============================================================
rem Usagi Pet development environment bootstrap for Windows x64
rem Put this file in the project root next to package.json.
rem ============================================================

rem --- Administrator check ---
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting Administrator permission...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "ROOT=%~dp0"
set "DL=%TEMP%\usagi_pet_setup"

if not exist "%DL%" mkdir "%DL%"

echo.
echo ============================================================
echo Usagi Pet Development Environment Setup
echo Project root: %ROOT%
echo ============================================================
echo.

rem ============================================================
rem 1. Node.js 22 LTS
rem ============================================================
echo [1/5] Checking Node.js...

where node >nul 2>&1
if not errorlevel 1 (
    echo Node.js is already installed:
    node -v
) else (
    echo Node.js was not found.
    echo Downloading latest Node.js 22 x64 MSI...

    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "$base='https://nodejs.org/dist/latest-v22.x/';" ^
        "$text=(Invoke-WebRequest -UseBasicParsing ($base+'SHASUMS256.txt')).Content;" ^
        "$match=[regex]::Match($text,'node-v22\.\d+\.\d+-x64\.msi');" ^
        "if(-not $match.Success){throw 'Could not find the latest Node.js 22 x64 MSI';}" ^
        "$url=$base+$match.Value;" ^
        "Write-Host ('Downloading '+$url);" ^
        "Invoke-WebRequest -UseBasicParsing $url -OutFile '%DL%\node-x64.msi'"

    if errorlevel 1 (
        echo ERROR: Node.js download failed.
        goto :fail
    )

    if not exist "%DL%\node-x64.msi" (
        echo ERROR: Node.js installer was not downloaded.
        goto :fail
    )

    echo Installing Node.js...
    start /wait "" msiexec.exe /i "%DL%\node-x64.msi" /qn /norestart
    set "RC=!ERRORLEVEL!"

    if not "!RC!"=="0" if not "!RC!"=="3010" (
        echo ERROR: Node.js installer failed with exit code !RC!.
        goto :fail
    )

    set "PATH=%ProgramFiles%\nodejs;%PATH%"

    where node >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Node.js was installed but node.exe is still not available.
        echo Try restarting Windows and run this setup again.
        goto :fail
    )

    echo Node.js installed:
    node -v
)

set "PATH=%ProgramFiles%\nodejs;%PATH%"

rem ============================================================
rem 2. Visual Studio 2022 Build Tools
rem ============================================================
echo.
echo [2/5] Checking Visual Studio C++ Build Tools...

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "HAVE_VCTOOLS=0"

if exist "%VSWHERE%" (
    "%VSWHERE%" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath >nul 2>&1
    if not errorlevel 1 set "HAVE_VCTOOLS=1"
)

if "!HAVE_VCTOOLS!"=="1" (
    echo Visual Studio C++ Build Tools are already installed.
) else (
    echo Downloading Visual Studio 2022 Build Tools...

    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "Invoke-WebRequest -UseBasicParsing 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile '%DL%\vs_BuildTools.exe'"

    if errorlevel 1 (
        echo ERROR: Visual Studio Build Tools download failed.
        goto :fail
    )

    if not exist "%DL%\vs_BuildTools.exe" (
        echo ERROR: Visual Studio Build Tools installer was not downloaded.
        goto :fail
    )

    echo Installing C++ Build Tools and Windows SDK...
    echo This step may take several minutes.

    start /wait "" "%DL%\vs_BuildTools.exe" ^
        --quiet ^
        --wait ^
        --norestart ^
        --nocache ^
        --add Microsoft.VisualStudio.Workload.VCTools ^
        --includeRecommended

    set "RC=!ERRORLEVEL!"

    if not "!RC!"=="0" if not "!RC!"=="3010" (
        echo ERROR: Visual Studio Build Tools installer failed with exit code !RC!.
        goto :fail
    )

    echo Visual Studio Build Tools installation completed.
)

rem ============================================================
rem 3. Rust stable MSVC
rem ============================================================
echo.
echo [3/5] Checking Rust...

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

where rustc >nul 2>&1
if not errorlevel 1 (
    echo Rust is already installed:
    rustc --version
    cargo --version
) else (
    echo Rust was not found.
    echo Downloading rustup-init...

    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "Invoke-WebRequest -UseBasicParsing 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe' -OutFile '%DL%\rustup-init.exe'"

    if errorlevel 1 (
        echo ERROR: Rust download failed.
        goto :fail
    )

    if not exist "%DL%\rustup-init.exe" (
        echo ERROR: rustup-init.exe was not downloaded.
        goto :fail
    )

    echo Installing Rust stable MSVC toolchain...

    "%DL%\rustup-init.exe" -y ^
        --default-host x86_64-pc-windows-msvc ^
        --default-toolchain stable ^
        --profile minimal

    if errorlevel 1 (
        echo ERROR: Rust installation failed.
        goto :fail
    )

    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

    where rustc >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Rust was installed but rustc is still not available.
        echo Try restarting Windows and run this setup again.
        goto :fail
    )

    rustc --version
    cargo --version
)

rem ============================================================
rem 4. WebView2 Runtime
rem ============================================================
echo.
echo [4/5] Installing or updating Microsoft Edge WebView2 Runtime...

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$ProgressPreference='SilentlyContinue';" ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
    "Invoke-WebRequest -UseBasicParsing 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '%DL%\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'"

if errorlevel 1 (
    echo WARNING: WebView2 download failed.
    echo Windows may already have WebView2 installed.
) else (
    start /wait "" "%DL%\MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install
    set "RC=!ERRORLEVEL!"
    if not "!RC!"=="0" if not "!RC!"=="3010" (
        echo WARNING: WebView2 installer returned exit code !RC!.
        echo Continuing because WebView2 may already be installed.
    )
)

rem ============================================================
rem 5. Project dependencies
rem ============================================================
echo.
echo [5/5] Installing project dependencies...

if not exist "%ROOT%package.json" (
    echo ERROR: package.json was not found beside this BAT file.
    echo.
    echo Expected layout:
    echo   NahidaProject\
    echo     setup_dev.bat
    echo     package.json
    echo     src\
    echo     src-tauri\
    echo     public\
    goto :fail
)

pushd "%ROOT%"

echo.
echo Environment versions:
echo ------------------------------------------------------------
node -v
call npm -v
rustc --version
cargo --version
echo ------------------------------------------------------------
echo.

if exist "package-lock.json" (
    echo Running npm ci...
    call npm ci
) else (
    echo Running npm install...
    call npm install
)

if errorlevel 1 (
    popd
    echo ERROR: npm dependency installation failed.
    goto :fail
)

echo.
echo Checking Tauri CLI...
call npx --no-install tauri --version >nul 2>&1

if errorlevel 1 (
    echo Tauri CLI was not found in the project.
    echo Installing @tauri-apps/cli...
    call npm install -D @tauri-apps/cli

    if errorlevel 1 (
        popd
        echo ERROR: Tauri CLI installation failed.
        goto :fail
    )
)

echo.
echo Tauri CLI:
call npx --no-install tauri --version

popd

echo.
echo ============================================================
echo SETUP COMPLETED SUCCESSFULLY
echo ============================================================
echo.
echo You can now run:
echo   run_pet.bat
echo.
echo Or manually:
echo   npm run tauri dev
echo.
echo If Windows requested a restart during installation,
echo restart once before running the pet.
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo SETUP FAILED
echo ============================================================
echo.
echo Review the first ERROR message above.
echo Temporary downloads are stored in:
echo   %DL%
echo.
pause
exit /b 1
