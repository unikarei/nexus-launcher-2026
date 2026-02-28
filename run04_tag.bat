@echo off
setlocal enableextensions enabledelayedexpansion
rem ========================================================================
rem Program Overview
rem   run04_tag.bat is the release-oriented Git operation script.
rem   It supports two controlled paths:
rem     A) changes exist: stage -> commit -> tag -> push branch -> push tag
rem     B) no changes:    tag-only on current HEAD -> push branch -> push tag
rem   Use this script when tagging/release traceability is required.
rem ========================================================================
rem ========================================================================
rem Git Tag Script (run04_tag.bat)
rem - Stage, commit, tag, and push (branch + tag)
rem - Use this when you want a release-like commit + tag flow
rem ========================================================================

rem [1] Change directory to the script location (project root)
cd /d %~dp0

rem [2] Verify Git command is available
where git >nul 2>nul
if errorlevel 1 (
    echo [Error] Git is not installed or not in PATH.
    pause
    exit /b 1
)

rem [3] Ensure we are inside a Git repository
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
    echo [Error] This directory is not a Git repository.
    pause
    exit /b 1
)

rem [4] Get current branch and latest tag (for display/reference)
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set CUR_BRANCH=%%b
if "%CUR_BRANCH%"=="" set CUR_BRANCH=main

set "LATEST_TAG="
for /f "tokens=1" %%i in ('git tag --sort^=-version:refname 2^>nul') do (
    set LATEST_TAG=%%i
    goto :found_tag
)
:found_tag
if "%LATEST_TAG%"=="" set LATEST_TAG=v0.0.0

echo ========================================
echo               Git Tag Script
echo ========================================
echo Current branch : %CUR_BRANCH%
echo Latest tag     : %LATEST_TAG%
echo.

rem [5] Stage and commit changes first
echo Staging changes...
git add -A

set "HAS_CHANGES="
for /f "delims=" %%s in ('git status --porcelain') do set HAS_CHANGES=1

if defined HAS_CHANGES (
    set /p COMMIT_MSG="Enter commit message: "
    if "!COMMIT_MSG!"=="" (
        echo [Error] Commit message cannot be empty.
        pause
        exit /b 1
    )
    rem Sanitize double quotes in message (" -> ')
    set "COMMIT_MSG=!COMMIT_MSG:"='!"

    echo Creating commit with message:
    echo   !COMMIT_MSG!
    git commit -m "!COMMIT_MSG!"
    if errorlevel 1 (
        echo [Error] Commit failed.
        pause
        exit /b 1
    )
) else (
    echo [Info] No changes to commit.
    set /p TAG_ONLY="Proceed with tag+push on current HEAD without commit? [y/N]: "
    if /I not "!TAG_ONLY!"=="Y" (
        echo [Info] Cancelled.
        pause
        exit /b 1
    )
)

rem [6] Prompt for a new tag version (e.g., v1.2.3)
set /p VERSION="Please enter NEW tag version (ex: v1.2.3): "
if "!VERSION!"=="" (
    echo [Error] Version cannot be empty.
    pause
    exit /b 1
)

rem [7] Validate the tag does not already exist (abort if duplicate)
git rev-parse -q --verify refs/tags/!VERSION! >nul 2>nul
if not errorlevel 1 (
    echo [Error] Tag !VERSION! already exists.
    pause
    exit /b 1
)

rem [8] Prompt for the tag annotation message (concise release notes)
set /p TAG_MSG="Enter tag message (annotation): "
if "!TAG_MSG!"=="" (
    echo [Error] Tag message cannot be empty.
    pause
    exit /b 1
)
rem Replace double quotes (") with single quotes (') to avoid breaking command arguments
set "TAG_MSG=!TAG_MSG:"='!"

rem [9] Create the annotated tag on current HEAD
echo Creating annotated tag !VERSION! ...
git tag -a !VERSION! -m "!TAG_MSG!"
if errorlevel 1 (
    echo [Error] Tag creation failed.
    pause
    exit /b 1
)

rem [10] Push branch first
echo Pushing to origin/!CUR_BRANCH! ...
git push origin !CUR_BRANCH!
if errorlevel 1 goto :branch_push_failed
goto :branch_push_ok

:branch_push_failed
echo(
echo [Error] Branch push failed.
echo Remote may have commits that are not present locally (non-fast-forward).
set /p FORCE_PUSH="Force push to overwrite remote history? [y/N]: "
if /I "!FORCE_PUSH!"=="Y" (
    echo Force pushing to origin/!CUR_BRANCH! ...
    git push -f origin !CUR_BRANCH!
    if errorlevel 1 (
        echo [Error] Force push failed.
        echo [Info] Try: git pull --rebase origin !CUR_BRANCH! then push again.
        pause
        exit /b 1
    )
) else (
    echo [Info] Cancelled. Try: git pull --rebase origin !CUR_BRANCH! then push again.
    pause
    exit /b 1
)

:branch_push_ok

rem [11] Push tag
echo Pushing tag !VERSION! to origin ...
git push origin !VERSION!
if errorlevel 1 (
    echo [Error] Tag push failed.
    pause
    exit /b 1
)

rem [12] Completion message
echo(
echo [Success] Commit/tag/push completed on branch !CUR_BRANCH! with tag !VERSION!.
echo(
pause
exit /b 0
