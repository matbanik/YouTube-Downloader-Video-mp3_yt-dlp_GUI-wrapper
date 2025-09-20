@echo off
echo.
echo =======================================================
echo     YouTube Downloader Build Script
echo =======================================================
echo.
echo This script will package the Python application into a single .exe file.
echo.
echo Requirements:
echo 1. Python must be installed and in your PATH.
echo 2. PyInstaller must be installed (pip install pyinstaller).
echo 3. The script 'youtube_downloader.py' must be in this directory.
echo 4. (Optional but Recommended) Download ffmpeg.exe and place it in this directory.
echo.

REM Check for ffmpeg and warn the user if it's missing
IF NOT EXIST .\\ffmpeg.exe (
    echo WARNING: ffmpeg.exe not found in this directory.
    echo Audio-only downloads and merging formats may fail without it.
    echo It is highly recommended to download it from https://ffmpeg.org/download.html
    echo and place ffmpeg.exe here before running this script.
    pause
)

echo Starting the build process with PyInstaller...
echo.

REM The PyInstaller command
pyinstaller ^
    --name yd ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-binary "ffmpeg.exe;." ^
    youtube_downloader.py

echo.
echo =======================================================
echo Build complete!
echo =======================================================
echo.
echo Look for 'yd.exe' in the 'dist' sub-directory.
echo.
pause

