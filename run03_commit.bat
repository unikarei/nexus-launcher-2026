@echo off
setlocal enableextensions enabledelayedexpansion
set "RUN03_SCRIPT_VERSION=v0.0.1"
rem ========================================================================
rem Program Overview
rem   run03_commit.bat is the standard day-to-day Git operation script.
rem   It performs a safe interactive workflow for:
rem     1) staging all changes,
rem     2) creating one commit, and
rem     3) pushing the current branch to origin.
rem   It intentionally does NOT create tags. Use run04_tag.bat for tagging.
rem ========================================================================
rem ========================================================================
rem Git Commit Script (run03_commit.bat)
rem - Stage, commit, and push changes (no tagging)
rem - Interactive commit message input
rem ========================================================================

rem Move to script directory (project root)
cd /d %~dp0

rem Check Git availability
where git >nul 2>nul
if errorlevel 1 (
    echo [Error] Git is not installed or not in PATH.
    pause
    exit /b 1
)

rem Check inside a Git repository
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
    echo [Error] This directory is not a Git repository.
    pause
    exit /b 1
)

rem Detect current branch
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set CUR_BRANCH=%%b
if "%CUR_BRANCH%"=="" set CUR_BRANCH=main

rem Get latest tag as reference
set "LATEST_TAG="
for /f "tokens=1" %%i in ('git tag --sort^=-version:refname 2^>nul') do (
    set LATEST_TAG=%%i
    goto :found_tag
)
:found_tag
if "%LATEST_TAG%"=="" set LATEST_TAG=v0.0.0

echo ========================================
echo            Git Commit Script
echo ========================================
echo Script version : !RUN03_SCRIPT_VERSION!
echo Current branch : %CUR_BRANCH%
echo Latest tag     : %LATEST_TAG%
echo.

rem Ask user to input commit message (interactive)
set /p COMMIT_MSG="Enter commit message: "
if "%COMMIT_MSG%"=="" (
    echo [Error] Commit message cannot be empty.
    pause
    exit /b 1
)
rem Sanitize double quotes in message (" -> ')
set "COMMIT_MSG=%COMMIT_MSG:"='%"

echo.
echo Staging changes...
rem Stage all changes
git add -A

rem Check if there are staged changes
set "HAS_CHANGES="
for /f "delims=" %%s in ('git status --porcelain') do set HAS_CHANGES=1
if not defined HAS_CHANGES (
    echo [Info] No changes to commit.
    pause
    exit /b 0
)

echo Creating commit with message:
echo   %COMMIT_MSG%
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo [Error] Commit failed.
    pause
    exit /b 1
)

echo Pushing to origin/%CUR_BRANCH% ...
git push origin %CUR_BRANCH%
if errorlevel 1 (
    echo.
    echo [Error] Push failed.
    echo Remote may have commits that are not present locally (non-fast-forward).
    set /p FORCE_PUSH="Force push to overwrite remote history? [y/N]: "
    if /I "%FORCE_PUSH%"=="Y" (
        echo Force pushing to origin/%CUR_BRANCH% ...
        git push -f origin %CUR_BRANCH%
        if errorlevel 1 (
            echo [Error] Force push failed.
            echo [Info] Try: git pull --rebase origin %CUR_BRANCH% then push again.
            pause
            exit /b 1
        ) else (
            echo.
            echo [Success] Force push completed on branch %CUR_BRANCH%.
        )
    ) else (
        echo [Info] Cancelled. Try: git pull --rebase origin %CUR_BRANCH% then push again.
        pause
        exit /b 1
    )
)

echo.
echo [Success] Commit and push completed on branch %CUR_BRANCH%.
echo (Tagging is now separated. Use run04_tag.bat to create/push a tag.)
echo.
pause
exit /b 0
