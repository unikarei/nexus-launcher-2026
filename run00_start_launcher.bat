@echo off
setlocal EnableDelayedExpansion

if /i "%LAUNCHER_DEBUG%"=="1" (
	echo [DEBUG] Batch started: %~f0
	echo [DEBUG] Args: %*
	echo on
)

REM Args:
REM   --preflight : Docker readiness check only (no Python server)
REM   --pause     : Pause at the end (useful when double-clicking)
if /i "%~1"=="--preflight" (
	set "LAUNCHER_PREFLIGHT_ONLY=1"
)
if /i "%~1"=="--pause" (
	set "LAUNCHER_PAUSE=1"
)

REM Preflight: YouTube Transcripter depends on Docker (via WSL).
REM Goal: user runs THIS batch only; Docker Desktop is started automatically if needed.

echo [INFO] Checking Docker CLI / Engine...
call :docker_ping 2
if /i "%LAUNCHER_DEBUG%"=="1" echo [DEBUG] docker_ping errorlevel=!errorlevel!
if %errorlevel%==0 (
	REM Docker Engine is reachable
	goto docker_ready
)

echo.
echo [INFO] Docker is not ready. Starting Docker Desktop...

REM Avoid spawning multiple Docker Desktop GUI instances if already running.
tasklist /fi "imagename eq Docker Desktop.exe" 2>nul | find /i "Docker Desktop.exe" >nul
if /i "%LAUNCHER_DEBUG%"=="1" echo [DEBUG] tasklist/find errorlevel=!errorlevel!
if !errorlevel!==0 (
	echo [INFO] Docker Desktop is already running.
	goto docker_wait_loop
)

if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
	start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" (
	start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
) else (
	echo [WARN] Docker Desktop executable not found.
	echo        Please install/start Docker Desktop manually.
	echo.
	goto docker_ready
)

:docker_wait_loop
REM Wait up to ~180 seconds for Docker Engine to become reachable.
for /l %%i in (1,1,90) do (
	if %%i==1 echo [INFO] Waiting for Docker Engine (up to ~180s)...
	if %%i==1 echo [INFO] (Tip) Each check uses a short timeout.
	if %%i==1 echo.
	set /a _mod=%%i %% 10
	if "!_mod!"=="" if /i "%LAUNCHER_DEBUG%"=="1" echo [DEBUG] set /a failed at i=%%i
	if %%i==1 echo [INFO] Docker check: %%i/90
	if !_mod! EQU 0 echo [INFO] Docker check: %%i/90
	call :docker_ping 2
	if !errorlevel!==0 goto docker_ready
	timeout /t 2 /nobreak >nul
)

echo.
echo [WARN] Docker is still not ready after ~180 seconds.
echo        YouTube Transcripter may fail to start until Docker finishes booting.
echo.

:docker_ready

REM Testing hook: set LAUNCHER_PREFLIGHT_ONLY=1 to verify Docker readiness without starting the launcher.
if /i "%LAUNCHER_PREFLIGHT_ONLY%"=="1" (
	echo [INFO] Preflight complete.
	exit /b 0
)

cd /d "%~dp0launcher"
python main.py

REM Avoid looking "frozen" in VS Code terminals; allow explicit --pause.
if /i "%LAUNCHER_PAUSE%"=="1" (
	pause
) else (
	if /i not "%TERM_PROGRAM%"=="vscode" pause
)

exit /b %errorlevel%

:docker_ping
REM Usage: call :docker_ping <seconds>
set "_DOCKER_PING_SECS=%~1"
if "%_DOCKER_PING_SECS%"=="" set "_DOCKER_PING_SECS=2"

REM Run docker with a short timeout to avoid hanging when the engine isn't ready.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$timeoutMs = [int]('%_DOCKER_PING_SECS%')*1000; $out = Join-Path $env:TEMP 'launcher_docker_ping_out.txt'; $err = Join-Path $env:TEMP 'launcher_docker_ping_err.txt'; try { $p = Start-Process -FilePath 'docker' -ArgumentList @('version','--format','{{.Server.Version}}') -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err; if ($p.WaitForExit($timeoutMs)) { exit $p.ExitCode } else { try { $p.Kill() } catch {} ; exit 1 } } catch { exit 1 }"
exit /b %errorlevel%
