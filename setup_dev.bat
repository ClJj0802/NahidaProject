@echo off
setlocal EnableExtensions
title Usagi Pet - Full Development Environment Setup
chcp 65001 >nul

rem ============================================================
rem Usagi Pet development environment bootstrap for Windows x64
rem Installs:
rem   - Node.js 22 LTS
rem   - Visual Studio 2022 Build Tools (C++ workload + SDK)
rem   - Rust stable MSVC toolchain
rem   - Microsoft Edge WebView2 Runtime
rem   - Project npm dependencies
rem
rem Put this BAT in the project root next to package.json.
rem Run it by double-clicking.
rem ============================================================

rem Elevate to Administrator.
net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator permission...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process -FilePath '%~f0' -Verb RunAs"
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

rem ------------------------------------------------------------
rem 1. Node.js 22 LTS
rem ------------------------------------------------------------
echo [1/5] Checking Node.js...

where node >nul 2>&1
if "%errorlevel%"=="0" (
    echo Node.js is already installed.
    node -v
) else (
    echo Downloading latest Node.js 22 x64 MSI...

    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "$base='https://nodejs.org/dist/latest-v22.x/';" ^
        "$s=(Invoke-WebRequest -UseBasicParsing ($base+'SHASUMS256.txt')).Content;" ^
        "$m=[regex]::Match($s,'node-v22\.\d+\.\d+-x64\.msi');" ^
        "if(-not $m.Success){throw 'Could not find the latest Node.js 22 x64 MSI';}" ^
        "$url=$base+$m.Value;" ^
        "Write-Host ('Downloading '+$url);" ^
        "Invoke-WebRequest -UseBasicParsing $url -OutFile '%DL%\node-x64.msi'"

    if not "%errorlevel%"=="0" goto :fail

    echo Installing Node.js...
    start /wait "" msiexec.exe /i "%DL%\node-x64.msi" /qn /norestart
    set "RC=%errorlevel%"

    if not "%RC%"=="0" if not "%RC%"=="3010" (
        echo Node.js installer failed with exit code %RC%.
        goto :fail
    )
)

set "PATH=%ProgramFiles%\nodejs;%PATH%"

rem ------------------------------------------------------------
rem 2. Visual Studio 2022 Build Tools
rem ------------------------------------------------------------
echo.
echo [2/5] Checking Visual Studio C++ Build Tools...

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "HAVE_VCTOOLS=0"

if exist "%VSWHERE%" (
    "%VSWHERE%" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath >nul 2>&1
    if "%errorlevel%"=="0" set "HAVE_VCTOOLS=1"
)

if "%HAVE_VCTOOLS%"=="1" (
    echo Visual Studio C++ Build Tools are already installed.
) else (
    echo Downloading Visual Studio 2022 Build Tools...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "Invoke-WebRequest -UseBasicParsing 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile '%DL%\vs_BuildTools.exe'"

    if not "%errorlevel%"=="0" goto :fail

    echo Installing C++ build tools and Windows SDK...
    echo This can take quite a while.
    start /wait "" "%DL%\vs_BuildTools.exe" ^
        --quiet ^
        --wait ^
        --norestart ^
        --nocache ^
        --add Microsoft.VisualStudio.Workload.VCTools ^
        --includeRecommended

    set "RC=%errorlevel%"

    if not "%RC%"=="0" if not "%RC%"=="3010" (
        echo Visual Studio Build Tools installer failed with exit code %RC%.
        goto :fail
    )
)

rem ------------------------------------------------------------
rem 3. Rust stable MSVC toolchain
rem ------------------------------------------------------------
echo.
echo [3/5] Checking Rust...

if exist "%USERPROFILE%\.cargo\bin\rustc.exe" (
    echo Rust is already installed.
) else (
    echo Downloading rustup...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
        "Invoke-WebRequest -UseBasicParsing 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe' -OutFile '%DL%\rustup-init.exe'"

    if not "%errorlevel%"=="0" goto :fail

    echo Installing Rust stable MSVC toolchain...
    "%DL%\rustup-init.exe" -y ^
        --default-host x86_64-pc-windows-msvc ^
        --default-toolchain stable ^
        --profile minimal

    if not "%errorlevel%"=="0" goto :fail
)

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

rem ------------------------------------------------------------
rem 4. Microsoft Edge WebView2 Runtime
rem ------------------------------------------------------------
echo.
echo [4/5] Installing or updating WebView2 Runtime...

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$ProgressPreference='SilentlyContinue';" ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
    "Invoke-WebRequest -UseBasicParsing 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '%DL%\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'"

if not "%errorlevel%"=="0" goto :fail

start /wait "" "%DL%\MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install
set "RC=%errorlevel%"

if not "%RC%"=="0" if not "%RC%"=="3010" (
    echo WebView2 installer returned exit code %RC%.
    echo Continuing because WebView2 may already be installed.
)

rem ------------------------------------------------------------
rem 5. Project dependencies
rem ------------------------------------------------------------
echo.
echo [5/5] Installing project dependencies...

echo.
echo Environment versions:
echo ------------------------------------------------------------
where node >nul 2>&1 && node -v
where npm >nul 2>&1 && call npm -v
where rustc >nul 2>&1 && rustc --version
where cargo >nul 2>&1 && cargo --version
echo ------------------------------------------------------------
echo.

if not exist "%ROOT%package.json" (
    echo WARNING: package.json was not found.
    echo.
    echo Put this BAT file in the project root, for example:
    echo.
    echo   NahidaProject\
    echo     setup_usagi_dev.bat
    echo     package.json
    echo     src\
    echo     src-tauri\
    echo     public\
    echo.
    goto :success_no_project
)

pushd "%ROOT%"

if exist "package-lock.json" (
    echo Running npm ci...
    call npm ci
) else (
    echo Running npm install...
    call npm install
)

if not "%errorlevel%"=="0" (
    popd
    goto :fail
)

echo.
echo Checking Tauri CLI...
call npx --no-install tauri --version >nul 2>&1

if not "%errorlevel%"=="0" (
    echo Tauri CLI was not found in the project.
    echo Installing @tauri-apps/cli as a development dependency...
    call npm install -D @tauri-apps/cli

    if not "%errorlevel%"=="0" (
        popd
        goto :fail
    )
)

echo.
call npx --no-install tauri --version
popd

goto :success

:success_no_project
echo.
echo ============================================================
echo System prerequisites were installed successfully.
echo Project dependencies were skipped because package.json
echo was not found beside this BAT file.
echo ============================================================
echo.
pause
exit /b 0

:success
echo.
echo ============================================================
echo Setup completed successfully.
echo ============================================================
echo.
echo To start the development version:
echo.
echo   cd /d "%ROOT%"
echo   npm run tauri dev
echo.
echo To build an installer:
echo.
echo   cd /d "%ROOT%"
echo   npm run tauri build
echo.
echo If Windows asks for a restart, restart once before building.
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo SETUP FAILED
echo ============================================================
echo.
echo Review the error above.
echo Temporary downloads are stored in:
echo   %DL%
echo.
pause
exit /b 1
