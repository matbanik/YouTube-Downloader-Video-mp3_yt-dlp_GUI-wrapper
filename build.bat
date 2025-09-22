@echo off
echo.
echo =======================================================
echo     YouTube Downloader Minimal Build Script
echo =======================================================
echo.

REM Clean everything
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "__pycache__" rmdir /s /q "__pycache__"
del *.spec 2>nul

echo Building minimal single-file version...
echo.

REM Absolute minimal build - just the essentials (no ffmpeg bundled)

pyinstaller ^
    --onefile ^
    --noconsole ^
    --name youtube_downloader ^
    --clean ^
    --noconfirm ^
    youtube_downloader.py

if exist "dist\yd.exe" (
    echo.
    echo SUCCESS: Minimal build completed!
    echo Executable: dist\youtube_downloader.exe
    for %%A in ("dist\yd.exe") do echo Size: %%~zA bytes
    echo.
    echo =======================================================
    echo                 IMPORTANT NOTICE
    echo =======================================================
    echo.
    echo FFmpeg is required but NOT included in this build.
    echo You must install FFmpeg separately for video processing.
    echo.
    echo INSTALLATION OPTIONS:
    echo.
    echo 1. AUTOMATIC ^(Recommended^):
    echo    winget install FFmpeg
    echo.
    echo 2. MANUAL DOWNLOAD:
    echo    - Download: https://github.com/BtbN/FFmpeg-Builds/releases
    echo    - Extract ffmpeg.exe to a folder
    echo    - Add that folder to your Windows PATH
    echo.
    echo 3. PORTABLE ^(Advanced^):
    echo    - Place ffmpeg.exe in the same folder as yd.exe
    echo.
    echo VERIFY INSTALLATION:
    echo    Open Command Prompt and run: ffmpeg -version
    echo.
    echo The application will check FFmpeg availability on startup.
    echo =======================================================
) else (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
pause