@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem ============================================================
rem Nahida Service Launcher
rem ============================================================

set "LAUNCHER_VERSION=2026-08-31-V6-SENSEVOICE"

set "ROOT=D:\Users\User\Desktop\NahidaProject"
set "GPT_DIR=%ROOT%\GPT-SoVITS"
set "BRAIN_DIR=%ROOT%\nahida_brain"
set "PET_DIR=%ROOT%"

set "VENV_DIR=%ROOT%\stt-compare\.venv"
set "VENV_ACTIVATE=%VENV_DIR%\Scripts\activate.bat"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

set "MODEL=%ROOT%\Qwen3.5-9B-heretic.Q6_K.gguf"
set "GPT_ENV=GPTSoVits"

set "TTS_ENABLED=1"

set "RESTART_DELAY=3"
set "READY_TIMEOUT=120"

set "WT_WINDOW=NahidaServices"

rem ============================================================
rem Worker dispatch
rem ============================================================

if /I "%~1"=="--worker-gpt" goto WORKER_GPT
if /I "%~1"=="--worker-llm" goto WORKER_LLM
if /I "%~1"=="--worker-brain" goto WORKER_BRAIN
if /I "%~1"=="--worker-pet" goto WORKER_PET

rem ============================================================
rem Interactive menu
rem ============================================================

title Nahida Service Launcher

powershell -NoProfile -ExecutionPolicy Bypass -Command "$items=@('GPT-SoVITS API       127.0.0.1:9880','Llama LLM            127.0.0.1:8080','Nahida Brain         main.py','Nahida Desktop Pet   Tauri + Live2D','SenseVoice STT       Brain voice input');$selected=@($true,$true,$true,$true,$true);$pos=0;[Console]::CursorVisible=$false;try{while($true){[Console]::Clear();Write-Host '';Write-Host '  Nahida Service Launcher';Write-Host '  =======================';Write-Host '';Write-Host '  Up / Down : Move';Write-Host '  Space     : Select / Unselect';Write-Host '  Enter     : Start';Write-Host '  Esc       : Exit';Write-Host '';for($i=0;$i-lt$items.Count;$i++){if($i-eq$pos){$cursor='>'}else{$cursor=' '};if($selected[$i]){$check='[X]'}else{$check='[ ]'};Write-Host ('  '+$cursor+' '+$check+' '+$items[$i])};$key=[Console]::ReadKey($true);if($key.Key-eq[ConsoleKey]::UpArrow){$pos--;if($pos-lt0){$pos=$items.Count-1}}elseif($key.Key-eq[ConsoleKey]::DownArrow){$pos++;if($pos-ge$items.Count){$pos=0}}elseif($key.Key-eq[ConsoleKey]::Spacebar){$selected[$pos]=-not$selected[$pos]}elseif($key.Key-eq[ConsoleKey]::Enter){$mask=0;if($selected[0]){$mask+=1};if($selected[1]){$mask+=2};if($selected[2]){$mask+=4};if($selected[3]){$mask+=8};if($selected[4]){$mask+=16};exit(100+$mask)}elseif($key.Key-eq[ConsoleKey]::Escape){exit 200}}}finally{[Console]::CursorVisible=$true}"

set "MENU_CODE=%ERRORLEVEL%"

if "%MENU_CODE%"=="200" exit /b 0
if %MENU_CODE% LSS 100 goto MENU_ERROR
if %MENU_CODE% GTR 131 goto MENU_ERROR

set /a "MASK=MENU_CODE-100"
set /a "GPT_SELECTED=MASK & 1"
set /a "LLM_SELECTED=(MASK >> 1) & 1"
set /a "BRAIN_SELECTED=(MASK >> 2) & 1"
set /a "PET_SELECTED=(MASK >> 3) & 1"
set /a "STT_SELECTED=(MASK >> 4) & 1"

cls
echo.
echo ============================================================
echo   Nahida Service Launcher
echo ============================================================
echo.
echo [DEBUG] Version          : %LAUNCHER_VERSION%
echo [DEBUG] Running BAT      : %~f0
echo [DEBUG] Selection mask   : %MASK%
echo [DEBUG] GPT_SELECTED     : %GPT_SELECTED%
echo [DEBUG] LLM_SELECTED     : %LLM_SELECTED%
echo [DEBUG] BRAIN_SELECTED   : %BRAIN_SELECTED%
echo [DEBUG] PET_SELECTED     : %PET_SELECTED%
echo [DEBUG] STT_SELECTED     : %STT_SELECTED%
echo [DEBUG] VENV             : %VENV_DIR%
echo [DEBUG] TTS output       : %TTS_ENABLED%
echo.

if "%MASK%"=="0" (
    echo [INFO] Nothing selected.
    timeout /t 2 /nobreak >nul
    exit /b 0
)

set "GPT_ALREADY_RUNNING=0"
set "LLM_ALREADY_RUNNING=0"
set "PREFLIGHT_FAILED=0"

echo [1/3] Preflight checks...
echo.

call :PREFLIGHT

if errorlevel 1 (
    echo.
    echo ============================================================
    echo [FAILED] Preflight checks failed.
    echo Nothing was started.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Launching selected services...
echo.

where wt.exe >nul 2>&1

if errorlevel 1 (
    set "USE_WINDOWS_TERMINAL=0"
    echo [WARN] wt.exe was not found.
    echo [WARN] Falling back to separate CMD windows.
) else (
    set "USE_WINDOWS_TERMINAL=1"
    echo [OK] Windows Terminal found.
    echo [OK] Services will open as CMD tabs in one Terminal window.
)

echo.

if not "%GPT_SELECTED%"=="0" (
    if "%GPT_ALREADY_RUNNING%"=="1" (
        echo [SKIP] GPT-SoVITS is already listening on port 9880.
    ) else (
        call :LAUNCH_SERVICE "GPT-SoVITS" "--worker-gpt"
    )
)

if not "%LLM_SELECTED%"=="0" (
    if "%LLM_ALREADY_RUNNING%"=="1" (
        echo [SKIP] Llama is already listening on port 8080.
    ) else (
        call :LAUNCH_SERVICE "Llama LLM" "--worker-llm"
    )
)

if not "%BRAIN_SELECTED%"=="0" (
    call :LAUNCH_SERVICE "Nahida Brain" "--worker-brain %GPT_SELECTED% %LLM_SELECTED% %STT_SELECTED%"
) else (
    if "%STT_SELECTED%"=="1" (
        echo [INFO] SenseVoice STT was selected, but Nahida Brain is not selected.
        echo [INFO] SenseVoice runs inside Nahida Brain, so no STT process was started.
    )
)

if not "%PET_SELECTED%"=="0" (
    call :LAUNCH_SERVICE "Nahida Desktop Pet" "--worker-pet"
)

echo.
echo [3/3] Done.
echo.
echo ============================================================
echo   Selected services launched.
echo.
if "%STT_SELECTED%"=="1" (
    echo   SenseVoice STT : enabled
) else (
    echo   SenseVoice STT : disabled
)
echo   TTS output     : enabled
echo ============================================================
echo.

timeout /t 3 /nobreak >nul
exit /b 0

rem ============================================================
rem Menu error
rem ============================================================

:MENU_ERROR
cls
echo.
echo ============================================================
echo   Nahida Service Launcher - MENU ERROR
echo ============================================================
echo.
echo [DEBUG] Version        : %LAUNCHER_VERSION%
echo [DEBUG] Menu exit code : %MENU_CODE%
echo.
echo [ERROR] Interactive menu failed.
echo [ERROR] No service was started.
echo.
pause
exit /b 1

rem ============================================================
rem Preflight
rem ============================================================

:PREFLIGHT

if not exist "%ROOT%\" (
    echo [ERROR] Project root not found:
    echo         %ROOT%
    exit /b 1
)

echo [OK] Project root: %ROOT%

set "VENV_NEEDED=0"

if not "%LLM_SELECTED%"=="0" set "VENV_NEEDED=1"
if not "%BRAIN_SELECTED%"=="0" set "VENV_NEEDED=1"

if "%VENV_NEEDED%"=="1" call :CHECK_VENV

if not "%GPT_SELECTED%"=="0" call :CHECK_GPT
if not "%LLM_SELECTED%"=="0" call :CHECK_LLM
if not "%BRAIN_SELECTED%"=="0" call :CHECK_BRAIN
if not "%PET_SELECTED%"=="0" call :CHECK_PET

if "%PREFLIGHT_FAILED%"=="1" exit /b 1
exit /b 0

rem ============================================================
rem Shared venv check
rem ============================================================

:CHECK_VENV
echo.
echo --- Shared Python Environment ---

if not exist "%VENV_DIR%\" (
    echo [ERROR] Missing venv:
    echo         %VENV_DIR%
    set "PREFLIGHT_FAILED=1"
    exit /b 0
)

echo [OK] Venv: %VENV_DIR%

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] Missing activate.bat:
    echo         %VENV_ACTIVATE%
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] activate.bat found.
)

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Missing python.exe:
    echo         %VENV_PYTHON%
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Python executable found.
)

exit /b 0

rem ============================================================
rem GPT-SoVITS check
rem ============================================================

:CHECK_GPT
echo.
echo --- GPT-SoVITS ---

if not exist "%GPT_DIR%\api_v2.py" (
    echo [ERROR] Missing:
    echo         %GPT_DIR%\api_v2.py
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] api_v2.py found.
)

call :FIND_CONDA

if not defined CONDA_EXE (
    echo [ERROR] conda.exe not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Conda: !CONDA_EXE!

    "!CONDA_EXE!" run -n "%GPT_ENV%" python -c "import sys" >nul 2>&1

    if errorlevel 1 (
        echo [ERROR] Conda environment "%GPT_ENV%" is unavailable.
        set "PREFLIGHT_FAILED=1"
    ) else (
        echo [OK] Conda environment: %GPT_ENV%
    )
)

call :PORT_LISTENING 9880

if errorlevel 1 (
    echo [OK] Port 9880 is free.
) else (
    echo [INFO] Port 9880 is already listening.
    echo [INFO] A duplicate GPT-SoVITS server will not be started.
    set "GPT_ALREADY_RUNNING=1"
    call :SHOW_PORT_OWNER 9880
)

exit /b 0

rem ============================================================
rem Llama check
rem ============================================================

:CHECK_LLM
echo.
echo --- Llama LLM ---

if not exist "%MODEL%" (
    echo [ERROR] Model not found:
    echo         %MODEL%
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Model file found.
)

if exist "%VENV_ACTIVATE%" call "%VENV_ACTIVATE%" >nul 2>&1

where llama.exe >nul 2>&1

if errorlevel 1 (
    echo [ERROR] llama.exe not found in PATH.
    set "PREFLIGHT_FAILED=1"
) else (
    set "LLAMA_EXE="

    for /f "delims=" %%I in ('where llama.exe') do (
        if not defined LLAMA_EXE set "LLAMA_EXE=%%I"
    )

    echo [OK] llama.exe: !LLAMA_EXE!
)

call :PORT_LISTENING 8080

if errorlevel 1 (
    echo [OK] Port 8080 is free.
) else (
    echo [INFO] Port 8080 is already listening.
    echo [INFO] A duplicate Llama server will not be started.
    set "LLM_ALREADY_RUNNING=1"
    call :SHOW_PORT_OWNER 8080
)

exit /b 0

rem ============================================================
rem Brain and SenseVoice check
rem ============================================================

:CHECK_BRAIN
echo.
echo --- Nahida Brain ---

if not exist "%BRAIN_DIR%\main.py" (
    echo [ERROR] Missing:
    echo         %BRAIN_DIR%\main.py
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] main.py found.

    findstr /C:"Nahida Brain V6.10" "%BRAIN_DIR%\main.py" >nul 2>&1

    if errorlevel 1 (
        echo [ERROR] main.py is not Nahida Brain V6.10.
        echo [ERROR] Replace it with the new main_v6_10_sensevoice.py.
        set "PREFLIGHT_FAILED=1"
    ) else (
        echo [OK] Brain version: V6.10
    )
)

if "%STT_SELECTED%"=="1" (
    echo.
    echo --- SenseVoice STT ---

    if not exist "%BRAIN_DIR%\voice_input.py" (
        echo [ERROR] Missing:
        echo         %BRAIN_DIR%\voice_input.py
        set "PREFLIGHT_FAILED=1"
    ) else (
        echo [OK] voice_input.py found.
    )

    if exist "%VENV_PYTHON%" (
        "%VENV_PYTHON%" -c "import funasr" >nul 2>&1

        if errorlevel 1 (
            echo [ERROR] funasr cannot be imported from:
            echo         %VENV_DIR%
            set "PREFLIGHT_FAILED=1"
        ) else (
            echo [OK] funasr import succeeded.
        )
    )

    echo [INFO] SenseVoice STT will start inside Nahida Brain.
    echo [INFO] If microphone initialization fails, Brain will fall back to keyboard input.
) else (
    echo [INFO] SenseVoice STT is disabled.
    echo [INFO] Nahida Brain will use keyboard input only.
)

if "%GPT_SELECTED%"=="0" (
    echo [INFO] GPT-SoVITS is not selected.
    echo [INFO] TTS will disable itself if port 9880 is unavailable.
)

if "%LLM_SELECTED%"=="0" (
    echo [WARN] Llama is not selected.
    echo [WARN] Brain can start, but chat requires an available LLM backend.
)

exit /b 0

rem ============================================================
rem Desktop Pet check
rem ============================================================

:CHECK_PET
echo.
echo --- Nahida Desktop Pet ---

if not exist "%PET_DIR%\package.json" (
    echo [ERROR] package.json not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] package.json found.
)

if not exist "%PET_DIR%\src-tauri\tauri.conf.json" (
    echo [ERROR] Tauri config not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Tauri config found.
)

where node.exe >nul 2>&1

if errorlevel 1 (
    echo [ERROR] node.exe not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Node.js found.
)

where npm.cmd >nul 2>&1

if errorlevel 1 (
    echo [ERROR] npm.cmd not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] npm found.
)

where cargo.exe >nul 2>&1

if errorlevel 1 (
    echo [ERROR] cargo.exe not found.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] Cargo found.
)

if not exist "%PET_DIR%\node_modules\" (
    echo [ERROR] node_modules missing.
    set "PREFLIGHT_FAILED=1"
) else (
    echo [OK] node_modules found.
)

if exist "%PET_DIR%\package.json" (
    node -e "const p=require(process.argv[1]);process.exit(p.scripts&&p.scripts.tauri?0:1)" "%PET_DIR%\package.json" >nul 2>&1

    if errorlevel 1 (
        echo [ERROR] package.json has no "tauri" script.
        set "PREFLIGHT_FAILED=1"
    ) else (
        echo [OK] npm "tauri" script found.
    )
)

set "NAHIDA_MODEL_FOUND=0"

if exist "%PET_DIR%\public\models\Nahida\Nahida.model3.json" set "NAHIDA_MODEL_FOUND=1"
if exist "%PET_DIR%\models\Nahida\Nahida.model3.json" set "NAHIDA_MODEL_FOUND=1"
if exist "%PET_DIR%\src\models\Nahida\Nahida.model3.json" set "NAHIDA_MODEL_FOUND=1"

if "!NAHIDA_MODEL_FOUND!"=="1" (
    echo [OK] Nahida Live2D model found.
) else (
    echo [WARN] Nahida.model3.json not found in common locations.
)

exit /b 0

rem ============================================================
rem Open service as CMD tab in one Windows Terminal window
rem ============================================================

:LAUNCH_SERVICE
set "SERVICE_TITLE=%~1"
set "SERVICE_ARGS=%~2"

if "%USE_WINDOWS_TERMINAL%"=="1" (
    echo [TAB] %SERVICE_TITLE%

    wt.exe -w "%WT_WINDOW%" new-tab --title "%SERVICE_TITLE%" cmd.exe /d /k call "%~f0" %SERVICE_ARGS%

    timeout /t 1 /nobreak >nul
) else (
    echo [CMD] %SERVICE_TITLE%

    start "%SERVICE_TITLE%" "%ComSpec%" /d /k call "%~f0" %SERVICE_ARGS%
)

exit /b 0

rem ============================================================
rem GPT-SoVITS watchdog
rem ============================================================

:WORKER_GPT
title GPT-SoVITS
chcp 65001 >nul

call :FIND_CONDA

if not defined CONDA_EXE (
    echo [FATAL] conda.exe not found.
    exit /b 1
)

cd /d "%GPT_DIR%"

:WORKER_GPT_LOOP
cls

echo ============================================================
echo   GPT-SoVITS API - WATCHDOG
echo ============================================================
echo   Environment : %GPT_ENV%
echo   Address     : http://127.0.0.1:9880
echo   Started     : %date% %time%
echo ============================================================
echo.

"%CONDA_EXE%" run -n "%GPT_ENV%" --no-capture-output python api_v2.py -a 127.0.0.1 -p 9880

set "SERVICE_EXIT=%ERRORLEVEL%"

echo.

if "%SERVICE_EXIT%"=="0" (
    echo [WATCHDOG] GPT-SoVITS exited normally.
    exit /b 0
)

echo [WATCHDOG] GPT-SoVITS exited with code %SERVICE_EXIT%.
echo [WATCHDOG] Restarting in %RESTART_DELAY% seconds...

timeout /t %RESTART_DELAY% /nobreak >nul

goto WORKER_GPT_LOOP

rem ============================================================
rem Llama watchdog
rem ============================================================

:WORKER_LLM
title Llama LLM
chcp 65001 >nul

if not exist "%VENV_ACTIVATE%" (
    echo [FATAL] Missing:
    echo %VENV_ACTIVATE%
    exit /b 1
)

call "%VENV_ACTIVATE%"

cd /d "%ROOT%"

:WORKER_LLM_LOOP
cls

echo ============================================================
echo   Llama LLM - WATCHDOG
echo ============================================================
echo   Venv    : %VENV_DIR%
echo   Model   : %MODEL%
echo   Address : http://127.0.0.1:8080
echo   Context : 8192
echo   Started : %date% %time%
echo ============================================================
echo.

llama serve -m "%MODEL%" -ngl 99 -c 8192 --reasoning off --host 127.0.0.1 --port 8080

set "SERVICE_EXIT=%ERRORLEVEL%"

echo.

if "%SERVICE_EXIT%"=="0" (
    echo [WATCHDOG] Llama exited normally.
    exit /b 0
)

echo [WATCHDOG] Llama exited with code %SERVICE_EXIT%.
echo [WATCHDOG] Restarting in %RESTART_DELAY% seconds...

timeout /t %RESTART_DELAY% /nobreak >nul

goto WORKER_LLM_LOOP

rem ============================================================
rem Nahida Brain watchdog
rem ============================================================

:WORKER_BRAIN
title Nahida Brain
chcp 65001 >nul

set "WAIT_GPT=%~2"
set "WAIT_LLM=%~3"
set "ENABLE_STT=%~4"

if not defined WAIT_GPT set "WAIT_GPT=0"
if not defined WAIT_LLM set "WAIT_LLM=0"
if not defined ENABLE_STT set "ENABLE_STT=0"

if not exist "%VENV_PYTHON%" (
    echo [FATAL] Missing:
    echo %VENV_PYTHON%
    exit /b 1
)

cd /d "%BRAIN_DIR%"

set "NAHIDA_SENSEVOICE_STT=%ENABLE_STT%"
set "NAHIDA_TTS=%TTS_ENABLED%"
set "PYTHONUTF8=1"

:WORKER_BRAIN_LOOP

if "%WAIT_GPT%"=="1" (
    call :WAIT_FOR_PORT 9880 %READY_TIMEOUT% "GPT-SoVITS API"

    if errorlevel 1 (
        echo [WATCHDOG] GPT-SoVITS unavailable. Retrying...

        timeout /t %RESTART_DELAY% /nobreak >nul

        goto WORKER_BRAIN_LOOP
    )
)

if "%WAIT_LLM%"=="1" (
    call :WAIT_FOR_PORT 8080 %READY_TIMEOUT% "Llama LLM"

    if errorlevel 1 (
        echo [WATCHDOG] Llama unavailable. Retrying...

        timeout /t %RESTART_DELAY% /nobreak >nul

        goto WORKER_BRAIN_LOOP
    )
)

cls

echo ============================================================
echo   Nahida Brain - WATCHDOG
echo ============================================================
echo   Venv           : %VENV_DIR%
echo   Working dir    : %BRAIN_DIR%
echo   SenseVoice STT : %NAHIDA_SENSEVOICE_STT%
echo   TTS output     : %NAHIDA_TTS%
echo   Started        : %date% %time%
echo ============================================================
echo.

"%VENV_PYTHON%" main.py

set "SERVICE_EXIT=%ERRORLEVEL%"

echo.

if "%SERVICE_EXIT%"=="0" (
    echo [WATCHDOG] Nahida Brain exited normally.
    echo [WATCHDOG] /exit will not restart it.
    exit /b 0
)

echo [WATCHDOG] Nahida Brain exited with code %SERVICE_EXIT%.
echo [WATCHDOG] Restarting in %RESTART_DELAY% seconds...

timeout /t %RESTART_DELAY% /nobreak >nul

goto WORKER_BRAIN_LOOP

rem ============================================================
rem Desktop Pet watchdog
rem ============================================================

:WORKER_PET
title Nahida Desktop Pet
chcp 65001 >nul

cd /d "%PET_DIR%"

:WORKER_PET_LOOP
cls

echo ============================================================
echo   Nahida Desktop Pet - WATCHDOG
echo ============================================================
echo   Working dir : %PET_DIR%
echo   Command     : npm run tauri dev
echo   Started     : %date% %time%
echo ============================================================
echo.

call npm run tauri dev

set "SERVICE_EXIT=%ERRORLEVEL%"

echo.

if "%SERVICE_EXIT%"=="0" (
    echo [WATCHDOG] Desktop Pet exited normally.
    exit /b 0
)

echo [WATCHDOG] Desktop Pet exited with code %SERVICE_EXIT%.
echo [WATCHDOG] Restarting in %RESTART_DELAY% seconds...

timeout /t %RESTART_DELAY% /nobreak >nul

goto WORKER_PET_LOOP

rem ============================================================
rem Find conda.exe
rem ============================================================

:FIND_CONDA
set "CONDA_EXE="

for /f "delims=" %%I in ('where conda.exe 2^>nul') do (
    if not defined CONDA_EXE set "CONDA_EXE=%%I"
)

if defined CONDA_EXE exit /b 0

for %%I in (
    "%USERPROFILE%\miniconda3\Scripts\conda.exe"
    "%USERPROFILE%\anaconda3\Scripts\conda.exe"
    "%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
    "%LOCALAPPDATA%\anaconda3\Scripts\conda.exe"
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
    "C:\ProgramData\anaconda3\Scripts\conda.exe"
) do (
    if exist "%%~I" (
        set "CONDA_EXE=%%~I"
        exit /b 0
    )
)

exit /b 1

rem ============================================================
rem Port helpers
rem ============================================================

:PORT_LISTENING
netstat -ano -p TCP 2>nul | findstr /C:":%~1 " | findstr /I "LISTENING" >nul 2>&1

if errorlevel 1 exit /b 1

exit /b 0

:SHOW_PORT_OWNER
echo         Listener:

netstat -ano -p TCP 2>nul | findstr /C:":%~1 " | findstr /I "LISTENING"

exit /b 0

:WAIT_FOR_PORT
set "WAIT_PORT=%~1"
set "WAIT_SECONDS=%~2"
set "WAIT_NAME=%~3"
set /a "WAIT_ELAPSED=0"

echo [WAIT] %WAIT_NAME% on 127.0.0.1:%WAIT_PORT% ...

:WAIT_FOR_PORT_LOOP
call :PORT_LISTENING %WAIT_PORT%

if not errorlevel 1 (
    echo [READY] %WAIT_NAME% is listening on port %WAIT_PORT%.
    exit /b 0
)

if %WAIT_ELAPSED% GEQ %WAIT_SECONDS% (
    echo [ERROR] %WAIT_NAME% did not become ready within %WAIT_SECONDS% seconds.
    exit /b 1
)

timeout /t 2 /nobreak >nul

set /a "WAIT_ELAPSED+=2"

goto WAIT_FOR_PORT_LOOP
