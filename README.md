# YouTube Video Downloader

A comprehensive Python GUI application for downloading YouTube videos and playlists with advanced features and user-friendly interface.

## Features

### Core Functionality
- **Single Video Downloads**: Download individual YouTube videos with ease
- **Playlist Support**: Download entire playlists or channels automatically
- **Quality Selection**: Choose from 1080p, 720p, 480p, or 360p video quality
- **Audio Extraction**: Download audio-only files in MP3 format (192kbps)
- **Batch Processing**: Queue multiple videos and playlists for sequential download

### User Interface
- **Intuitive GUI**: Clean, modern interface built with tkinter
- **Progress Tracking**: Real-time download progress with speed and ETA
- **Status Management**: Visual status indicators (Pending, Downloading, Done, Failed, Skipped)
- **Interactive Elements**: Clickable Video IDs that open YouTube videos in browser
- **Queue Management**: Add, remove, reorder, and clear download queues

### Advanced Features
- **Smart Quality Adjustment**: Automatically selects best available quality if requested quality unavailable
- **Duplicate Detection**: Skips files that already exist in download folder
- **Error Handling**: Comprehensive error reporting with troubleshooting suggestions
- **Session Persistence**: Saves and restores download queues between sessions
- **Logging System**: Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Technical Capabilities
- **Format Support**: MP4 video downloads, MP3 audio extraction
- **FFmpeg Integration**: Automatic video/audio stream merging
- **Version Checking**: Monitors yt-dlp and FFmpeg versions with update notifications
- **Cross-Platform**: Works on Windows, macOS, and Linux

![YouTube Downloader](./YD.jpg)

## Requirements

### System Requirements
- Python 3.7 or higher
- FFmpeg (for video processing)
- Internet connection

### Python Dependencies
```
yt-dlp>=2023.1.6
tkinter (usually included with Python)
```

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/matbanik/YouTube-Downloader-Video-mp3_yt-dlp_GUI-wrapper.git
cd youtube-downloader
```

### 2. Install Python Dependencies
```bash
pip install yt-dlp
```

### 3. Install FFmpeg

**⚠️ IMPORTANT**: FFmpeg is required but NOT included in the built executable. You must install it separately.

#### Windows - Multiple Options

##### Option 1: Automatic Installation (Recommended)
```cmd
winget install FFmpeg
```

##### Option 2: Manual Download and PATH Setup
1. **Download FFmpeg**:
   - Go to [FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases)
   - Download the latest `ffmpeg-master-latest-win64-gpl.zip`
   - Extract the ZIP file to a folder (e.g., `C:\ffmpeg`)

2. **Add to Windows PATH**:
   - Open System Properties (Win + R, type `sysdm.cpl`)
   - Click "Environment Variables"
   - Under "System Variables", find and select "Path"
   - Click "Edit" → "New"
   - Add the path to ffmpeg\bin folder (e.g., `C:\ffmpeg\bin`)
   - Click "OK" to save all dialogs
   - Restart Command Prompt/PowerShell

##### Option 3: Portable Installation
- Place `ffmpeg.exe` in the same folder as `yd.exe`
- No PATH modification needed

#### macOS
```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Using MacPorts
sudo port install ffmpeg

# Manual download
# Download from https://evermeet.cx/ffmpeg/
# Extract and move to /usr/local/bin/
```

#### Linux

##### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

##### CentOS/RHEL/Fedora
```bash
# Fedora
sudo dnf install ffmpeg

# CentOS/RHEL (requires EPEL)
sudo yum install epel-release
sudo yum install ffmpeg
```

##### Arch Linux
```bash
sudo pacman -S ffmpeg
```

#### Verify Installation
After installation, verify FFmpeg is working:
```bash
ffmpeg -version
```

You should see version information. If you get "command not found", FFmpeg is not properly installed or not in your PATH.

## Building Executable

### Creating Standalone Executable
For Windows users, you can build a standalone executable:

```cmd
build.bat
```

**Important Notes**:
- The built executable does NOT include FFmpeg
- FFmpeg must be installed separately (see installation instructions above)
- The build script will display FFmpeg installation instructions after completion
- Executable size is significantly smaller without bundled FFmpeg
- Users always get the latest FFmpeg version instead of a bundled version

### Build Requirements
- Python 3.7+
- PyInstaller: `pip install pyinstaller`
- All application dependencies installed

## Usage

### Starting the Application

#### From Source
```bash
python youtube_downloader.py
```

#### From Built Executable
```cmd
yd.exe
```

### Basic Workflow
1. **Add URLs**: Paste YouTube video or playlist URLs
2. **Select Quality**: Choose video quality or audio-only option
3. **Set Download Path**: Choose destination folder
4. **Start Download**: Click "Start" to begin downloading
5. **Monitor Progress**: Watch real-time progress and status updates

### Interface Elements

#### Top Section
- **URL Input**: Enter YouTube URLs (videos, playlists, channels)
- **Quality Selection**: Dropdown menu for video quality
- **Audio Only**: Checkbox for MP3 audio extraction
- **Download Path**: Configurable destination folder

#### Main Table
- **Video Title**: Full title of the video
- **Video ID**: Clickable YouTube video identifier
- **Format**: Selected quality or "Audio" for MP3
- **Duration**: Video length in MM:SS or HH:MM:SS format
- **Status**: Current download status with color coding

#### Control Buttons
- **Add**: Add URL to download queue
- **Remove**: Remove selected items
- **Clear All**: Empty the entire queue
- **Move Up/Down**: Reorder queue items
- **Start/Stop**: Control download process
- **Reset**: Reset failed/completed items to pending

#### Status Summary
- **Total**: Total number of videos in queue
- **Done**: Successfully downloaded videos (green)
- **Pending**: Videos waiting to download (black)
- **Failed**: Videos that failed to download (red)
- **Skipped**: Videos that were skipped (purple)
- **Downloading**: Currently downloading videos (blue)

#### Progress Log
- **Real-time Logging**: Download progress and system messages
- **Log Levels**: Configurable verbosity (DEBUG to CRITICAL)
- **Error Details**: Comprehensive error reporting with solutions

## Configuration

### Settings File
The application automatically saves settings to `settings.json`:
- Download path preference
- Log level setting
- Window geometry
- Queue state (videos and their status)

### Quality Auto-Adjustment
When requested quality is unavailable:
- Automatically selects the highest available quality ≤ requested
- If no suitable quality found, uses the lowest available
- Logs quality adjustments for transparency

## Troubleshooting

### Common Issues

#### FFmpeg Not Found
**Problem**: "FFmpeg not found in system PATH" or "FFmpeg not found or not accessible"
**Solutions**:
- Verify FFmpeg installation: `ffmpeg -version`
- For built executable: Ensure FFmpeg is in PATH or same folder as yd.exe
- Restart Command Prompt/Terminal after PATH changes
- Try portable installation (place ffmpeg.exe next to yd.exe)

#### FFmpeg Errors
**Problem**: "Postprocessing: Error opening input files"
**Solutions**:
- Update FFmpeg to latest version
- Try lower quality settings
- Download as audio-only
- Check internet connection stability
- Verify FFmpeg is working: `ffmpeg -version`

#### Download Failures
**Problem**: Videos fail to download
**Solutions**:
- Verify URL is accessible
- Check for region restrictions
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Try different quality settings

#### Slow Performance
**Problem**: Application runs slowly
**Solutions**:
- Close other bandwidth-intensive applications
- Use lower quality settings for faster downloads
- Check available disk space
- Restart the application

### Version Updates

#### Updating yt-dlp
```bash
pip install --upgrade yt-dlp
```

#### Updating FFmpeg
- Windows: Download latest from [FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases)
- macOS: `brew upgrade ffmpeg`
- Linux: `sudo apt upgrade ffmpeg`

## Technical Details

### Architecture
- **GUI Framework**: tkinter with ttk widgets
- **Download Engine**: yt-dlp library
- **Video Processing**: FFmpeg for format conversion
- **Threading**: Asynchronous downloads with progress reporting
- **Data Persistence**: JSON-based settings and queue storage

### External Dependencies
- **FFmpeg**: Required for video processing, must be installed separately
- **yt-dlp**: Bundled with executable or installed via pip
- **Python libraries**: Bundled with executable when built

### Supported URLs
- Individual videos: `https://www.youtube.com/watch?v=VIDEO_ID`
- Playlists: `https://www.youtube.com/playlist?list=PLAYLIST_ID`
- Channels: `https://www.youtube.com/@CHANNEL_NAME`
- Shorts: `https://www.youtube.com/shorts/VIDEO_ID`

## Contributing

### Bug Reports
Please include:
- Operating system and version
- Python version
- yt-dlp version
- FFmpeg version
- Complete error messages
- Steps to reproduce

### Feature Requests
- Describe the desired functionality
- Explain the use case
- Consider implementation complexity

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Acknowledgments

- **yt-dlp**: The powerful YouTube downloading library
- **FFmpeg**: Essential video processing toolkit
- **Python tkinter**: Cross-platform GUI framework
- **YouTube**: For providing the content platform

## Disclaimer

This tool is for educational and personal use only. Users are responsible for complying with YouTube's Terms of Service and applicable copyright laws. The developers are not responsible for any misuse of this software.

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Compatibility**: Python 3.7+, Windows/macOS/Linux