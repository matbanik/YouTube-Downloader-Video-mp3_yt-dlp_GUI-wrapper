#!/usr/bin/env python3
"""
Test script for SABR detection functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloaderApp
import tkinter as tk
import threading
import time

def test_sabr_detection():
    """Test SABR detection with a sample YouTube URL"""
    
    # Create a minimal app instance for testing
    root = tk.Tk()
    root.withdraw()  # Hide the main window for testing
    
    app = YouTubeDownloaderApp(root)
    
    # Test URL (use a short video for quick testing)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - short and reliable
    
    print("Testing SABR detection...")
    print(f"Test URL: {test_url}")
    
    # Run SABR detection
    try:
        is_sabr_detected, detection_details = app.detect_sabr_mode(test_url)
        
        print(f"\nSABR Detection Results:")
        print(f"SABR Detected: {is_sabr_detected}")
        print(f"Web Client SABR: {detection_details.get('web_client_sabr', 'Unknown')}")
        print(f"TV Client Working: {detection_details.get('tv_client_working', 'Unknown')}")
        print(f"Warnings: {detection_details.get('warnings_detected', [])}")
        
        if is_sabr_detected:
            print("\n✅ SABR detected - Bypass mode would be activated")
            print("Available video qualities would be: 360p, 240p, 144p, Lowest")
            print("Available audio formats would be: standard_mp3, high_m4a")
        else:
            print("\n✅ No SABR detected - Normal mode would be used")
            print("All quality options would be available")
            
    except Exception as e:
        print(f"❌ SABR detection failed: {e}")
        import traceback
        traceback.print_exc()
    
    root.destroy()

if __name__ == "__main__":
    test_sabr_detection()