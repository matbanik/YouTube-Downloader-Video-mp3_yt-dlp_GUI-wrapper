import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import tkinter.font as tkFont
import threading
import json
import os
import sys
import subprocess
import time
import re
import tempfile
import atexit
import webbrowser
from queue import Queue
import yt_dlp
import logging

# --- Configuration ---
SETTINGS_FILE = 'settings.json'
DEFAULT_DOWNLOAD_PATH = os.path.join(os.path.expanduser('~'), 'Downloads')

class YouTubeDownloaderApp:
    """
    A GUI application for downloading YouTube videos and playlists using yt-dlp.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("800x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- State Variables ---
        self.download_queue = []
        self.download_thread = None
        self.is_downloading = False
        self.stop_event = threading.Event()
        self.progress_queue = Queue()
        self.is_updating_from_selection = False # Flag to prevent update loops
        self.ydl_process = None  # Store yt-dlp process for stopping
        self.sort_column = None
        self.sort_reverse = False
        self.last_progress_time = 0  # Track last progress update time
        self.stop_message_logged = False  # Flag to prevent repeated stop messages

        # --- GUI Variables ---
        self.download_path = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        self.log_level_var = tk.StringVar(value='INFO')

        # --- GUI Setup ---
        self.setup_gui()
        self.load_settings()
        self.process_progress_queue()

    def setup_gui(self):
        """Creates and arranges all the GUI widgets."""
        # --- Main Frames ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X, side=tk.TOP)

        list_frame = ttk.Frame(self.root, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        console_frame = ttk.Frame(self.root, padding="10")
        console_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # --- Top Frame: URL Input and Controls ---
        ttk.Label(top_frame, text="YouTube URL:").grid(row=0, column=0, padx=(0, 5), sticky='w')
        self.url_entry = ttk.Entry(top_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky='ew')
        
        self.add_button = ttk.Button(top_frame, text="Add", command=self.add_url)
        self.add_button.grid(row=0, column=2, padx=5)
        
        top_frame.grid_columnconfigure(1, weight=1)

        # --- Options Frame: Quality and Audio-Only ---
        options_frame = ttk.Frame(top_frame)
        options_frame.grid(row=1, column=1, sticky='w', pady=5)
        
        ttk.Label(options_frame, text="Quality:").pack(side=tk.LEFT, padx=(0, 5))
        self.quality_var = tk.StringVar(value='1080p')
        quality_options = ['Best', '1080p', '720p', '480p', '360p']
        self.quality_menu = ttk.OptionMenu(options_frame, self.quality_var, quality_options[1], *quality_options)  # Default to 1080p, not Best
        self.quality_menu.pack(side=tk.LEFT, padx=(0, 20))
        
        self.audio_only_var = tk.BooleanVar()
        self.audio_only_check = ttk.Checkbutton(options_frame, text="Audio Only", variable=self.audio_only_var, command=self.on_audio_only_change)
        self.audio_only_check.pack(side=tk.LEFT)
        
        # Audio format dropdown (initially hidden)
        self.audio_format_var = tk.StringVar(value='default')
        self.audio_format_options = ['default (YouTube)', 'best (YouTube)', 'mp3 (FFmpeg)']
        self.audio_format_menu = ttk.OptionMenu(options_frame, self.audio_format_var, self.audio_format_options[0], *self.audio_format_options)
        self.audio_format_menu.pack(side=tk.LEFT, padx=(5, 0))
        self.audio_format_menu.pack_forget()  # Hide initially
        
        # Check FFmpeg availability and update audio options
        self.check_ffmpeg_availability()
        
        self.quality_var.trace_add('write', self.on_setting_change)
        self.audio_format_var.trace_add('write', self.on_setting_change)

        # --- Download Path Frame ---
        path_frame = ttk.Frame(top_frame)
        path_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=5)
        ttk.Label(path_frame, text="Download Folder:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.download_path, state='readonly')
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.change_path_button = ttk.Button(path_frame, text="Change...", command=self.change_download_path)
        self.change_path_button.pack(side=tk.LEFT, padx=5)


        # --- List Frame: Download Queue ---
        # Status summary frame with colored labels (above the table)
        status_summary_frame = ttk.Frame(list_frame)
        status_summary_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Individual status labels with colors
        self.total_label = tk.Label(status_summary_frame, text="Total: 0", font=("Arial", 9, "bold"), fg="black")
        self.total_label.pack(side=tk.LEFT, padx=(5, 10))
        
        self.done_label = tk.Label(status_summary_frame, text="Done: 0", font=("Arial", 9, "bold"), fg="green")
        self.done_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.pending_label = tk.Label(status_summary_frame, text="Pending: 0", font=("Arial", 9, "bold"), fg="black")
        self.pending_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.failed_label = tk.Label(status_summary_frame, text="Failed: 0", font=("Arial", 9, "bold"), fg="red")
        self.failed_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.skipped_label = tk.Label(status_summary_frame, text="Skipped: 0", font=("Arial", 9, "bold"), fg="purple")
        self.skipped_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.quality_blocked_label = tk.Label(status_summary_frame, text="QualityBlocked: 0", font=("Arial", 9, "bold"), fg="orange")
        self.quality_blocked_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.age_restricted_label = tk.Label(status_summary_frame, text="AgeRestricted: 0", font=("Arial", 9, "bold"), fg="brown")
        self.age_restricted_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.downloading_label = tk.Label(status_summary_frame, text="Downloading: 0", font=("Arial", 9, "bold"), fg="blue")
        self.downloading_label.pack(side=tk.LEFT)
        
        # Container for table and buttons
        table_container = ttk.Frame(list_frame)
        table_container.pack(fill=tk.BOTH, expand=True)
        
        # Create a frame for the treeview and scrollbar
        tree_frame = ttk.Frame(table_container)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, columns=('Name', 'ID', 'Quality', 'Duration', 'Status'), show='headings')
        self.tree.heading('Name', text='Video Title', command=lambda: self.sort_treeview('Name'))
        self.tree.heading('ID', text='Video ID', command=lambda: self.sort_treeview('ID'))
        self.tree.heading('Quality', text='Format', command=lambda: self.sort_treeview('Quality'))
        self.tree.heading('Duration', text='Duration', command=lambda: self.sort_treeview('Duration'))
        self.tree.heading('Status', text='Status', command=lambda: self.sort_treeview('Status'))
        self.tree.column('Name', width=300)
        self.tree.column('ID', width=120)
        self.tree.column('Quality', width=100, anchor='center')
        self.tree.column('Duration', width=80, anchor='center')
        self.tree.column('Status', width=100, anchor='center')
        self.tree.bind('<<TreeviewSelect>>', self.on_video_select)
        self.tree.bind('<Button-1>', self.on_tree_click)  # Handle mouse clicks
        self.tree.bind('<Motion>', self.on_tree_motion)  # Handle mouse motion for cursor changes
        
        # Configure status colors
        self.setup_status_colors()
        
        # Scrollbar for the treeview
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=tree_scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- List Control Buttons ---
        list_button_frame = ttk.Frame(table_container)
        list_button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        self.remove_button = ttk.Button(list_button_frame, text="Remove", command=self.remove_selected)
        self.remove_button.pack(pady=2, fill=tk.X)

        self.clear_all_button = ttk.Button(list_button_frame, text="Clear All", command=self.clear_all)
        self.clear_all_button.pack(pady=2, fill=tk.X)

        # Separator
        ttk.Separator(list_button_frame, orient='horizontal').pack(pady=5, fill=tk.X)

        self.move_up_button = ttk.Button(list_button_frame, text="Move Up", command=self.move_up)
        self.move_up_button.pack(pady=2, fill=tk.X)

        self.move_down_button = ttk.Button(list_button_frame, text="Move Down", command=self.move_down)
        self.move_down_button.pack(pady=2, fill=tk.X)

        # Separator
        ttk.Separator(list_button_frame, orient='horizontal').pack(pady=5, fill=tk.X)

        self.start_button = ttk.Button(list_button_frame, text="Start", command=self.start_download)
        self.start_button.pack(pady=2, fill=tk.X)

        self.stop_button = ttk.Button(list_button_frame, text="Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(pady=2, fill=tk.X)

        # Separator
        ttk.Separator(list_button_frame, orient='horizontal').pack(pady=5, fill=tk.X)

        self.reset_button = ttk.Button(list_button_frame, text="Reset", command=self.reset_selected, state=tk.DISABLED)
        self.reset_button.pack(pady=2, fill=tk.X)

        # --- Console Frame: Progress Output ---
        console_header_frame = ttk.Frame(console_frame)
        console_header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(console_header_frame, text="Progress Log:").pack(side=tk.LEFT)
        
        # Log level dropdown - moved to left side
        log_level_frame = ttk.Frame(console_header_frame)
        log_level_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        ttk.Label(log_level_frame, text="Log Level:").pack(side=tk.LEFT, padx=(0, 5))
        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.log_level_menu = ttk.OptionMenu(log_level_frame, self.log_level_var, 'INFO', *log_levels, command=self.on_log_level_change)
        self.log_level_menu.pack(side=tk.LEFT)
        
        # Check Dependencies button
        self.check_deps_button = ttk.Button(console_header_frame, text="Check Dependencies", command=self.check_dependencies)
        self.check_deps_button.pack(side=tk.LEFT, padx=(20, 0))
        
        self.console = scrolledtext.ScrolledText(console_frame, height=14, state=tk.DISABLED, bg='black', fg='white', font=("Courier", 9))
        self.console.pack(fill=tk.X, expand=True)
        


    def setup_status_colors(self):
        """Configure treeview tags for status colors."""
        self.tree.tag_configure('pending', foreground='black')
        self.tree.tag_configure('downloading', foreground='blue')
        self.tree.tag_configure('done', foreground='green')
        self.tree.tag_configure('failed', foreground='red')
        self.tree.tag_configure('skipped', foreground='purple')
        self.tree.tag_configure('qualityblocked', foreground='orange')
        self.tree.tag_configure('agerestricted', foreground='brown')

    def change_download_path(self):
        """Opens a dialog to choose a new download directory."""
        new_path = filedialog.askdirectory(title="Select Download Folder", initialdir=self.download_path.get())
        if new_path:
            self.download_path.set(new_path)
            self.log_message(f"Download path set to: {new_path}")
            self.save_settings()

    def on_video_select(self, event):
        """Updates quality controls when a video is selected in the list."""
        if self.url_entry.get().strip(): # Do nothing if user is typing a new URL
            return
            
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0] # Handle only the first selected item
        
        video_entry = None
        for v in self.download_queue:
            if v['item_id'] == item_id:
                video_entry = v
                break

        if video_entry:
            self.is_updating_from_selection = True # Set flag to prevent trace callback
            
            quality = video_entry['quality']
            if quality.startswith('Audio-'):
                self.audio_only_var.set(True)
                audio_format = quality.split('-')[1]  # Extract 'default', 'best' or 'mp3'
                if audio_format == 'default':
                    self.audio_format_var.set('default (YouTube)')
                elif audio_format == 'best':
                    self.audio_format_var.set('best (YouTube)')
                else:
                    self.audio_format_var.set('mp3 (FFmpeg)')
                self.audio_format_menu.pack(side=tk.LEFT, padx=(5, 0), after=self.audio_only_check)
                self.quality_menu.config(state=tk.DISABLED)
            else:
                self.audio_only_var.set(False)
                self.audio_format_menu.pack_forget()
                self.quality_var.set(quality)
                self.quality_menu.config(state=tk.NORMAL)
            
            self.is_updating_from_selection = False # Unset flag
        
        # Update reset button state and status summary
        self.update_reset_button_state()
        self.update_status_summary()

    def on_tree_click(self, event):
        """Handle mouse clicks on the treeview to detect Video ID column clicks."""
        # Identify what was clicked
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            # Get the column that was clicked
            column = self.tree.identify_column(event.x)
            # Column #2 is the Video ID column (columns are 1-indexed)
            if column == '#2':
                # Get the item that was clicked
                item = self.tree.identify_row(event.y)
                if item:
                    # Get the video ID from the item
                    values = self.tree.item(item, 'values')
                    if len(values) > 1:
                        video_id = values[1]  # Video ID is at index 1
                        if video_id and video_id != 'N/A':
                            # Open YouTube URL in default browser
                            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                            try:
                                webbrowser.open(youtube_url)
                                self.log_message(f"Opened YouTube video: {video_id}")
                            except Exception as e:
                                self.log_message(f"Failed to open browser: {e}", "ERROR")

    def on_tree_motion(self, event):
        """Handle mouse motion over treeview to change cursor for Video ID column."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            # Column #2 is the Video ID column
            if column == '#2':
                item = self.tree.identify_row(event.y)
                if item:
                    values = self.tree.item(item, 'values')
                    if len(values) > 1 and values[1] and values[1] != 'N/A':
                        # Change cursor to hand pointer
                        self.tree.config(cursor="hand2")
                        return
        
        # Reset cursor to default
        self.tree.config(cursor="")

    def on_audio_only_change(self):
        """Handles audio only checkbox changes and shows/hides audio format dropdown."""
        if self.audio_only_var.get():
            # Show audio format dropdown and disable quality dropdown
            self.audio_format_menu.pack(side=tk.LEFT, padx=(5, 0), after=self.audio_only_check)
            self.quality_menu.config(state=tk.DISABLED)
        else:
            # Hide audio format dropdown and enable quality dropdown
            self.audio_format_menu.pack_forget()
            self.quality_menu.config(state=tk.NORMAL)
        self.on_setting_change()

    def on_setting_change(self, *args):
        """Updates a selected video's settings when controls are changed."""
        if self.is_updating_from_selection: # Do nothing if change was triggered by selection
            return
            
        selected_items = self.tree.selection()
        if not selected_items:
            return

        if self.audio_only_var.get():
            audio_format = self.audio_format_var.get()
            new_quality = f'Audio-{audio_format.split()[0]}'  # 'Audio-default', 'Audio-best' or 'Audio-mp3'
        else:
            new_quality = self.quality_var.get()

        for item_id in selected_items:
            # Update internal data
            for video in self.download_queue:
                if video['item_id'] == item_id:
                    video['quality'] = new_quality
                    break
            
            # Update GUI
            current_values = self.tree.item(item_id, 'values')
            status = current_values[4] if len(current_values) > 4 else 'Pending'
            self.tree.item(item_id, values=(current_values[0], current_values[1], new_quality, current_values[3] if len(current_values) > 3 else 'N/A', status))
        
        self.log_message(f"Updated settings for {len(selected_items)} selected item(s).")
        self.save_settings()

    def on_log_level_change(self, selected_level):
        """Handles log level dropdown changes."""
        self.log_message(f"Log level changed to: {selected_level}")
        self.save_settings()  # Save the new log level setting

    def check_dependencies(self):
        """Check yt-dlp and FFmpeg versions manually when button is clicked."""
        self.log_message("Checking dependencies...", "INFO")
        
        # Check yt-dlp version
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                current_version = result.stdout.strip()
                self.log_message(f"yt-dlp version: {current_version}")
            else:
                self.log_message("yt-dlp not found or not accessible", "WARNING")
                self.log_message("Install with: pip install yt-dlp", "INFO")
        except FileNotFoundError:
            self.log_message("yt-dlp not found in system PATH", "WARNING")
            self.log_message("Install with: pip install yt-dlp", "INFO")
        except Exception as e:
            self.log_message(f"Error checking yt-dlp: {e}", "ERROR")
        
        # Check FFmpeg version
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                first_line = result.stdout.split('\n')[0]
                if 'ffmpeg version' in first_line.lower():
                    version_info = first_line.split('ffmpeg version')[1].split()[0]
                    self.log_message(f"FFmpeg version: {version_info}")
                else:
                    self.log_message("FFmpeg detected but version format unexpected")
            else:
                self.log_message("FFmpeg not found or not accessible", "WARNING")
                self.log_message("Download from: https://ffmpeg.org/download.html", "INFO")
        except FileNotFoundError:
            self.log_message("FFmpeg not found in system PATH", "WARNING")
            self.log_message("Download from: https://ffmpeg.org/download.html", "INFO")
            self.log_message("For Windows: https://github.com/BtbN/FFmpeg-Builds/releases", "INFO")
        except Exception as e:
            self.log_message(f"Error checking FFmpeg: {e}", "ERROR")
        
        self.log_message("Dependency check complete.", "INFO")
        
        # Refresh audio format options after dependency check
        self.check_ffmpeg_availability()

    def check_ffmpeg_availability(self):
        """Check if FFmpeg is available and update audio format options accordingly."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # FFmpeg is available, keep all options
                self.ffmpeg_available = True
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # FFmpeg not available, disable mp3 option
        self.ffmpeg_available = False
        self.audio_format_options = ['default (YouTube)', 'best (YouTube)']
        
        # Update the menu
        menu = self.audio_format_menu['menu']
        menu.delete(0, 'end')
        for option in self.audio_format_options:
            menu.add_command(label=option, command=tk._setit(self.audio_format_var, option))
        
        # Reset to available option if currently set to unavailable one
        if self.audio_format_var.get() == 'mp3 (FFmpeg)':
            self.audio_format_var.set('default (YouTube)')
            
        self.log_message("FFmpeg not detected. MP3 transcoding disabled. Using native audio formats only.", "INFO")

    def add_url(self):
        """Handles adding a URL to the download queue."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "URL field cannot be empty.")
            return

        if self.audio_only_var.get():
            audio_format = self.audio_format_var.get()
            quality = f'Audio-{audio_format.split()[0]}'  # 'Audio-default', 'Audio-best' or 'Audio-mp3'
        else:
            quality = self.quality_var.get()
        self.url_entry.delete(0, tk.END)
        self.log_message("Processing URL... (This may take a moment for playlists)")
        threading.Thread(target=self._process_url, args=(url, quality), daemon=True).start()

    def _process_url(self, url, quality):
        """Worker function to fetch video info without blocking the GUI."""
        self.log_message(f"Starting to process URL: {url}", "DEBUG")
        
        # Use extract_flat for initial processing to avoid hanging
        ydl_opts = {
            'quiet': True, 
            'extract_flat': 'in_playlist',  # Extract flat for playlists/channels
            'skip_download': True,
            'ignoreerrors': True
            # No playlistend limit - get all videos
        }
        
        try:
            self.log_message("Extracting video information...", "DEBUG")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            self.log_message("Extraction completed", "DEBUG")
            
            if not info:
                self.log_message("No information extracted from URL", "ERROR")
                return
            
            videos_to_add = []
            
            if 'entries' in info: # Playlist or channel
                all_entries = info['entries']
                valid_entries = [e for e in all_entries if e and e.get('id')]  # TODO: Support nested playlists
                total_entries = len(valid_entries)
                
                self.log_message(f"Found {total_entries} videos in playlist/channel")
                self.log_message("Processing videos... This may take a while for large channels", "INFO")
                
                for i, entry in enumerate(valid_entries):
                    # For flat extraction, we get basic info
                    video_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                    videos_to_add.append({
                        'title': entry.get('title', 'N/A'), 
                        'id': entry.get('id', 'N/A'), 
                        'url': video_url, 
                        'quality': quality,
                        'duration': self.format_duration(entry.get('duration')),
                        'info': entry  # Store the flat info object
                    })
                    
                    # Update progress every 25 videos and show in console
                    if (i + 1) % 25 == 0:
                        progress_msg = f"Processed {i + 1}/{total_entries} videos..."
                        self.log_message(progress_msg)
                        # Also update GUI immediately for user feedback
                        self.root.after(0, lambda msg=progress_msg: self.log_message(msg, overwrite=True))
                
                self.log_message(f"Successfully processed all {len(videos_to_add)} videos from playlist/channel")
                
            else: # Single video - need full extraction
                self.log_message("Processing single video", "DEBUG")
                # For single videos, do a full extraction to get duration
                ydl_opts_full = {
                    'quiet': True, 
                    'extract_flat': False, 
                    'skip_download': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_full) as ydl_full:
                    full_info = ydl_full.extract_info(url, download=False)
                
                if full_info:
                    duration = self.format_duration(full_info.get('duration'))
                    
                    # Auto-adjust quality for single video
                    adjusted_quality = quality
                    if not quality.startswith('Audio-'):
                        adjusted_quality = self.check_and_adjust_single_video_quality(full_info, quality)
                    
                    videos_to_add.append({
                        'title': full_info.get('title', 'N/A'), 
                        'id': full_info.get('id', 'N/A'), 
                        'url': full_info.get('webpage_url', url), 
                        'quality': adjusted_quality,
                        'duration': duration,
                        'info': full_info  # Store complete info object
                    })
                    self.log_message(f"Added video: {full_info.get('title')}")
            
            if videos_to_add:
                # For playlists, we'll check quality during download to avoid long processing times
                # For single videos, quality was already adjusted above
                if len(videos_to_add) == 1 and quality != 'Audio':
                    self.log_message("Quality check completed for single video", "DEBUG")
                elif len(videos_to_add) > 1:
                    self.log_message(f"Quality will be auto-adjusted during download for {len(videos_to_add)} videos", "INFO")
                
                self.log_message(f"Adding {len(videos_to_add)} videos to GUI", "DEBUG")
                self.root.after(0, self.add_videos_to_gui, videos_to_add)
            else:
                self.log_message("No videos were extracted from the URL", "WARNING")
                
        except Exception as e:
            self.log_message(f"Error fetching video info: {e}", "ERROR")
            import traceback
            self.log_message(f"Traceback: {traceback.format_exc()}", "DEBUG")

    def auto_adjust_quality(self, videos_to_add, requested_quality):
        """Auto-adjust video quality based on available formats."""
        quality_hierarchy = ['Best', '1080p', '720p', '480p', '360p']
        adjusted_videos = []
        
        for video in videos_to_add:
            if video['quality'].startswith('Audio-'):
                adjusted_videos.append(video)
                continue
            
            # If "Best" is requested, no adjustment needed
            if video['quality'] == 'Best':
                adjusted_videos.append(video)
                continue
                
            try:
                # Get available formats for this video
                ydl_opts = {
                    'quiet': True,
                    'skip_download': True,
                    'listformats': False
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video['info'] = info = ydl.process_ie_result(video['info'], download=False)
                    
                if info and 'formats' in info:
                    available_resolutions = set()
                    
                    # Extract available video resolutions
                    for fmt in info['formats']:
                        if fmt.get('vcodec') != 'none' and (height := fmt.get('height')) and (width := fmt.get('width')):
                            available_resolutions.add(min(height, width))  # Use the smaller dimension
                    
                    # Convert to quality strings
                    available_qualities = []
                    max_resolution = max(available_resolutions) if available_resolutions else 0
                    
                    # Add "Best" if there are high-resolution formats available
                    if max_resolution >= 1440:  # 1440p or higher
                        available_qualities.append('Best')
                    
                    for resolution in available_resolutions:
                        if resolution >= 1080:
                            available_qualities.append('1080p')
                        elif resolution >= 720:
                            available_qualities.append('720p')
                        elif resolution >= 480:
                            available_qualities.append('480p')
                        elif resolution >= 360:
                            available_qualities.append('360p')
                    
                    # Remove duplicates and sort by quality hierarchy
                    available_qualities = list(set(available_qualities))
                    available_qualities.sort(key=lambda x: quality_hierarchy.index(x) if x in quality_hierarchy else 999)
                    
                    # Find the best available quality that's <= requested quality
                    requested_index = quality_hierarchy.index(requested_quality) if requested_quality in quality_hierarchy else 0
                    best_quality = requested_quality
                    
                    for quality in quality_hierarchy[requested_index:]:
                        if quality in available_qualities:
                            best_quality = quality
                            break
                    
                    # If requested quality is not available, use the highest available
                    if requested_quality not in available_qualities and available_qualities:
                        best_quality = available_qualities[0]  # Highest available
                        self.log_message(f"Quality adjusted for '{video['title'][:50]}...': {requested_quality} → {best_quality}", "INFO")
                    
                    video['quality'] = best_quality
                else:
                    # If we can't get format info, keep original quality
                    self.log_message(f"Could not check formats for '{video['title'][:50]}...', keeping {requested_quality}", "DEBUG")
                    
            except Exception as e:
                # If quality check fails, keep original quality
                self.log_message(f"Quality check failed for '{video['title'][:50]}...': {e}", "DEBUG")
                
            adjusted_videos.append(video)
        
        return adjusted_videos

    def check_and_adjust_single_video_quality(self, video_info, requested_quality):
        """Check and adjust quality for a single video based on available formats."""
        if not video_info.get('formats'):
            return requested_quality
        
        # If "Best" is requested, return it as-is (no adjustment needed)
        if requested_quality == 'Best':
            return requested_quality
            
        quality_hierarchy = ['Best', '1080p', '720p', '480p', '360p']
        quality_to_resolution = {'1080p': 1080, '720p': 720, '480p': 480, '360p': 360}
        requested_resolution = quality_to_resolution.get(requested_quality, 1080)
        
        available_resolutions = set()
        has_audio = False
        
        # First, check what video resolutions are available and if there's audio
        for fmt in video_info['formats']:
            # Check for video formats (including video-only)
            if fmt.get('vcodec') != 'none' and (height := fmt.get('height')) and (width := fmt.get('width')):
                available_resolutions.add(min(height, width))  # Use the smaller dimension
            
            # Check if there's any audio available
            if fmt.get('acodec') != 'none':
                has_audio = True
        
        if not available_resolutions:
            self.log_message(f"No video formats found for '{video_info.get('title', 'Unknown')[:50]}...', keeping {requested_quality}", "DEBUG")
            return requested_quality
        
        if not has_audio:
            self.log_message(f"No audio formats found for '{video_info.get('title', 'Unknown')[:50]}...', but proceeding with video-only", "DEBUG")
        
        # Find the best available resolution that matches or is closest to requested
        # First try to find exact match or higher
        suitable_resolutions = [h for h in available_resolutions if h >= requested_resolution]
        
        if suitable_resolutions:
            # Use the lowest resolution that's >= requested (closest match)
            best_resolution = min(suitable_resolutions)
        else:
            # If no resolution >= requested, use the highest available
            best_resolution = max(available_resolutions)
        
        # Convert back to quality string
        if best_resolution >= 2160:
            best_quality = 'Best'  # 4K or higher, use Best
        elif best_resolution >= 1440:
            best_quality = 'Best'  # 1440p, use Best
        elif best_resolution >= 1080:
            best_quality = '1080p'
        elif best_resolution >= 720:
            best_quality = '720p'
        elif best_resolution >= 480:
            best_quality = '480p'
        else:
            best_quality = '360p'
        
        # Only log adjustment if it actually changed and it's a significant change
        if best_quality != requested_quality:
            self.log_message(f"Quality auto-adjusted: '{video_info.get('title', 'Unknown')[:50]}...' {requested_quality} → {best_quality} (available: {sorted(available_resolutions, reverse=True)})", "INFO")
        
        return best_quality

    def check_quality_before_download(self, video_entry):
        """Check and adjust quality just before download."""
        # Skip quality check for audio formats
        if video_entry['quality'].startswith('Audio-'):
            return video_entry['quality']
            
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                video_entry['info'] = info = ydl.process_ie_result(video_entry['info'], download=False)
                
            if info:
                return self.check_and_adjust_single_video_quality(info, video_entry['quality'])
        except Exception as e:
            self.log_message(f"Could not check quality for {video_entry['title']}: {e}", "DEBUG")
        
        return video_entry['quality']

    def update_video_quality_in_gui(self, item_id, new_quality):
        """Update the quality display in the GUI."""
        if not self.tree.exists(item_id):
            return
            
        current_values = list(self.tree.item(item_id, 'values'))
        if len(current_values) >= 3:
            current_values[2] = new_quality  # Quality is at index 2
            self.tree.item(item_id, values=current_values)

    def format_duration(self, duration_seconds):
        """Format duration from seconds to HH:MM:SS or MM:SS format."""
        if duration_seconds is None:
            return 'N/A'
        
        try:
            duration_seconds = int(duration_seconds)
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            return 'N/A'

    def add_videos_to_gui(self, videos):
        """Adds video information to the Treeview and internal queue."""
        for video in videos:
            duration = video.get('duration', 'N/A')
            status = video.get('status', 'Pending')  # Use existing status or default to Pending
            item_id = self.tree.insert('', tk.END, values=(video['title'], video['id'], video['quality'], duration, status), tags=('pending',))
            video['item_id'] = item_id
            video['status'] = status
            self.download_queue.append(video)
            
            # Set appropriate color tag based on status
            if status == 'Downloading':
                self.tree.item(item_id, tags=('downloading',))
            elif status == 'Done':
                self.tree.item(item_id, tags=('done',))
            elif status == 'Failed':
                self.tree.item(item_id, tags=('failed',))
            elif status == 'Skipped':
                self.tree.item(item_id, tags=('skipped',))
            else:
                self.tree.item(item_id, tags=('pending',))
        self.update_status_summary()  # Update status summary after adding videos
        self.save_settings()

    def remove_selected(self):
        """Removes the selected video from the queue."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No video selected to remove.")
            return

        for item_id in selected_items:
            self.download_queue = [v for v in self.download_queue if v['item_id'] != item_id]
            self.tree.delete(item_id)
        self.log_message(f"Removed {len(selected_items)} item(s) from the queue.")
        self.update_reset_button_state()  # Update reset button after removal
        self.update_status_summary()  # Update status summary after removal
        self.save_settings()

    def clear_all(self):
        """Clears all items from the download queue."""
        if not self.download_queue:
            messagebox.showinfo("Info", "Download queue is already empty.")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all items from the queue?"):
            # Clear the treeview
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Clear the internal queue
            self.download_queue.clear()
            self.log_message("Cleared all items from the queue.")
            self.update_reset_button_state()  # Update reset button after clearing
            self.update_status_summary()  # Update status summary after clearing
            self.save_settings()

    def move_up(self):
        """Moves selected items up in the queue."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No video selected to move.")
            return

        # Get all items and their positions
        all_items = self.tree.get_children()
        
        # Check if any selected item is already at the top
        if selected_items[0] == all_items[0]:
            return  # Can't move up further
        
        # Move each selected item up
        moved_items = []
        for item_id in selected_items:
            current_index = all_items.index(item_id)
            if current_index > 0:
                # Move in treeview
                self.tree.move(item_id, '', current_index - 1)
                
                # Move in internal queue
                video_to_move = None
                for i, video in enumerate(self.download_queue):
                    if video['item_id'] == item_id:
                        video_to_move = self.download_queue.pop(i)
                        self.download_queue.insert(max(0, i - 1), video_to_move)
                        break
                
                moved_items.append(item_id)
        
        # Restore selection
        self.tree.selection_set(moved_items)
        self.log_message(f"Moved {len(moved_items)} item(s) up in the queue.")
        self.save_settings()

    def move_down(self):
        """Moves selected items down in the queue."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No video selected to move.")
            return

        # Get all items and their positions
        all_items = self.tree.get_children()
        
        # Check if any selected item is already at the bottom
        if selected_items[-1] == all_items[-1]:
            return  # Can't move down further
        
        # Move each selected item down (process in reverse order)
        moved_items = []
        for item_id in reversed(selected_items):
            current_index = all_items.index(item_id)
            if current_index < len(all_items) - 1:
                # Move in treeview
                self.tree.move(item_id, '', current_index + 1)
                
                # Move in internal queue
                video_to_move = None
                for i, video in enumerate(self.download_queue):
                    if video['item_id'] == item_id:
                        video_to_move = self.download_queue.pop(i)
                        self.download_queue.insert(min(len(self.download_queue), i + 1), video_to_move)
                        break
                
                moved_items.append(item_id)
        
        # Restore selection
        self.tree.selection_set(moved_items)
        self.log_message(f"Moved {len(moved_items)} item(s) down in the queue.")
        self.save_settings()

    def sort_treeview(self, column):
        """Sorts the treeview by the specified column."""
        # Determine sort order
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        # Update column headings to show sort indicators
        self.update_column_headings()

        # Get all items with their values
        items = []
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, 'values')
            items.append((item_id, values))

        # Sort items based on the selected column
        column_index = {'Name': 0, 'ID': 1, 'Quality': 2, 'Duration': 3, 'Status': 4}[column]
        
        if column == 'Duration':
            # Special sorting for duration (convert to seconds for comparison)
            items.sort(key=lambda x: self.duration_to_seconds(x[1][column_index]), reverse=self.sort_reverse)
        else:
            # Regular string sorting
            items.sort(key=lambda x: x[1][column_index].lower(), reverse=self.sort_reverse)

        # Reorder items in treeview
        for index, (item_id, values) in enumerate(items):
            self.tree.move(item_id, '', index)

        # Reorder internal queue to match
        new_queue = []
        for item_id, values in items:
            for video in self.download_queue:
                if video['item_id'] == item_id:
                    new_queue.append(video)
                    break
        
        self.download_queue = new_queue
        self.log_message(f"Sorted by {column} ({'descending' if self.sort_reverse else 'ascending'})")
        self.save_settings()

    def update_column_headings(self):
        """Updates column headings to show sort indicators."""
        columns = {'Name': 'Video Title', 'ID': 'Video ID', 'Quality': 'Format', 'Duration': 'Duration', 'Status': 'Status'}
        
        for col, title in columns.items():
            if col == self.sort_column:
                indicator = ' ↓' if self.sort_reverse else ' ↑'
                self.tree.heading(col, text=title + indicator)
            else:
                self.tree.heading(col, text=title)

    def duration_to_seconds(self, duration_str):
        """Converts duration string to seconds for sorting."""
        if duration_str == 'N/A':
            return 0
        
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return 0
        except (ValueError, IndexError):
            return 0

    def start_download(self):
        """Starts the download process."""
        if not self.download_queue:
            messagebox.showinfo("Info", "Download queue is empty.")
            return
        
        # Check if there are any pending videos to download
        pending_videos = [v for v in self.download_queue if v.get('status', 'Pending') == 'Pending']
        if not pending_videos:
            messagebox.showinfo("Info", "No pending videos to download. All videos are either completed, failed, or skipped.")
            return
            
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress.")
            return
        
        self.is_downloading = True
        self.stop_event.clear()
        self.update_button_states()

        self.download_thread = threading.Thread(target=self.download_worker, daemon=True)
        self.download_thread.start()
        self.log_message(f"--- Download process started for {len(pending_videos)} pending video(s) ---")

    def stop_download(self):
        """Signals the download thread to stop."""
        if self.is_downloading:
            self.stop_event.set()
            self.log_message("--- Stop signal sent. Stopping after current file... ---", "WARNING")
            self.log_message("Note: Current download will complete before stopping.", "INFO")
            
            # Update button states immediately to show stop is in progress
            self.stop_button.config(text="Stopping...", state=tk.DISABLED)
            
            # If there's an active yt-dlp process, we can't force stop it
            # but we can prevent new downloads from starting
            if self.ydl_process:
                self.log_message("Waiting for current download to finish...", "INFO")

    def download_worker(self):
        """The main worker function that downloads videos one by one."""
        download_path = self.download_path.get()
        if not os.path.isdir(download_path):
             self.log_message(f"Error: Download path '{download_path}' does not exist. Please select a valid folder.", "ERROR")
             self.is_downloading = False
             self.root.after(0, self.update_button_states)
             return

        current_index = 0
        current_downloading_video = None  # Track currently downloading video
        
        while current_index < len(self.download_queue) and not self.stop_event.is_set():
            video_entry = self.download_queue[current_index]
            self.ydl_process = None
            
            # Skip videos that are already completed, failed, or skipped
            if video_entry.get('status') in ['Done', 'Failed', 'Skipped']:
                self.log_message(f"Skipping {video_entry.get('status', 'completed').lower()} video: {video_entry['title']}")
                current_index += 1
                continue
            
            # File existence check is now handled by yt-dlp's download archive
            
            try:
                # Set status to downloading and track this video
                current_downloading_video = video_entry
                self.root.after(0, self.update_video_status, video_entry['item_id'], 'Downloading')
                self.log_message(f"Starting download: {video_entry['title']}")
                
                # # Auto-adjust quality if needed (for videos that weren't checked during URL processing)
                # if not video_entry['quality'].startswith('Audio-') and 'info' not in video_entry:
                #     original_quality = video_entry['quality']
                #     adjusted_quality = self.check_quality_before_download(video_entry)
                #     if adjusted_quality != original_quality:
                #         video_entry['quality'] = adjusted_quality
                #         # Update the GUI to show the adjusted quality
                #         self.root.after(0, self.update_video_quality_in_gui, video_entry['item_id'], adjusted_quality)
                
                self.last_progress_time = 0  # Reset progress timer for new download
                self.stop_message_logged = False  # Reset stop message flag for new download
                
                # Setup yt-dlp options with download archive
                ydl_opts = {
                    'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'), 
                    'progress_hooks': [self.progress_hook], 
                    'nocheckcertificate': True,
                    'download_archive': os.path.join(download_path, 'download-archive.txt'),  # Prevent re-downloads
                    'ignoreerrors': True
                }
                
                if video_entry['quality'].startswith('Audio-'):
                    audio_format = video_entry['quality'].split('-')[1]  # 'default', 'best' or 'mp3'
                    if audio_format == 'default':
                        # Use default audio format (most compatible, fallback-friendly)
                        ydl_opts['format'] = 'ba/b'
                        ydl_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'best',
                            'preferredquality': '0'
                        }]
                    elif audio_format == 'best':
                        # Use native audio format (no transcoding)
                        ydl_opts['format'] = 'ba[acodec^=aac]/ba[acodec^=mp4a.40.]/ba/b'
                        ydl_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'aac',
                            'preferredquality': '0',
                            'nopostoverwrites': False
                        }]
                        ydl_opts['final_ext'] = 'aac'  # Save as aac
                    else:
                        # Use mp3 format (with transcoding)
                        ydl_opts['format'] = 'ba[acodec^=mp3]/ba/b'
                        ydl_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio', 
                            'preferredcodec': 'mp3', 
                            'preferredquality': '192',
                            'nopostoverwrites': False
                        }]
                        ydl_opts['final_ext'] = 'mp3'  # Save as mp3
                else:
                    ydl_opts['format_sort'] = ['ext']  # Prefer mp4
                    quality = video_entry['quality']
                    if quality != 'Best':
                        resolution = quality[:-1]  # Remove 'p' from '1080p'
                        ydl_opts['format_sort'] += [f'res:{resolution}']
                    ydl_opts['merge_output_format'] = 'mp4'  # Ensure output is mp4
                    ydl_opts['final_ext'] = 'mp4'  # Save as mp4
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Store reference for potential termination
                    self.ydl_process = ydl
                    
                    # Check for stop before starting download
                    if self.stop_event.is_set():
                        self.log_message("Download stopped before starting this video.", "WARNING")
                        # Reset status back to pending since we didn't actually start
                        self.root.after(0, self.update_video_status, video_entry['item_id'], 'Pending')
                        current_downloading_video = None
                        break
                    
                    ydl.process_ie_result(video_entry['info'])

                if self.stop_event.is_set():
                    self.log_message("Download stopped by user after completing current video.", "WARNING")
                    # Don't reset status here since the download completed successfully
                    current_downloading_video = None
                    break
                
                # Set status to done and move to next video
                self.root.after(0, self.update_video_status, video_entry['item_id'], 'Done')
                self.log_message(f"Successfully downloaded: {video_entry['title']}", "INFO")
                current_downloading_video = None
                current_index += 1
                
            except Exception as e:
                if self.stop_event.is_set():
                    self.log_message("Download stopped by user.", "WARNING")
                    # Reset the currently downloading video back to pending
                    if current_downloading_video:
                        self.root.after(0, self.update_video_status, current_downloading_video['item_id'], 'Pending')
                        current_downloading_video = None
                    break
                
                # Classify the error and set appropriate status
                error_str = str(e)
                status = self.classify_download_error(error_str, video_entry)
                
                self.root.after(0, self.update_video_status, video_entry['item_id'], status)
                self.log_message(f"Error downloading {video_entry['title']}: {e}", "ERROR")
                
                # Provide troubleshooting suggestions for common errors
                self.suggest_troubleshooting(error_str)
                current_downloading_video = None
                current_index += 1
                continue
            finally:
                self.ydl_process = None
        
        # If we exited the loop due to stop event and there's still a downloading video, reset it
        if self.stop_event.is_set() and current_downloading_video:
            self.root.after(0, self.update_video_status, current_downloading_video['item_id'], 'Pending')
            self.log_message(f"Reset status to pending for interrupted download: {current_downloading_video['title']}", "INFO")

        # Check if we stopped due to user request
        was_stopped = self.stop_event.is_set()
        
        self.is_downloading = False
        self.stop_event.clear()
        
        # Count remaining pending videos
        remaining_pending = sum(1 for v in self.download_queue if v.get('status', 'Pending') == 'Pending')
        
        if was_stopped:
            self.log_message(f"--- Download process stopped. {remaining_pending} videos remain pending ---", "WARNING")
        else:
            self.log_message("--- Download process finished ---")
            if remaining_pending > 0:
                self.log_message(f"Note: {remaining_pending} videos remain pending (may have been skipped or failed)", "INFO")
        
        self.root.after(0, self.update_button_states)
        self.root.after(0, self.update_status_summary)



    def update_video_status(self, item_id, status):
        """Updates the status of a video in the treeview with appropriate colors."""
        if not self.tree.exists(item_id):
            return
            
        # Update internal data
        for video in self.download_queue:
            if video['item_id'] == item_id:
                video['status'] = status
                break
        
        # Update GUI with status text and colors
        current_values = list(self.tree.item(item_id, 'values'))
        if len(current_values) >= 5:
            # Set status display text and color tag
            if status == 'Pending':
                current_values[4] = 'Pending'
                self.tree.item(item_id, values=current_values, tags=('pending',))
            elif status == 'Downloading':
                current_values[4] = '↓ Downloading'
                self.tree.item(item_id, values=current_values, tags=('downloading',))
            elif status == 'Done':
                current_values[4] = 'Done'
                self.tree.item(item_id, values=current_values, tags=('done',))
            elif status == 'Failed':
                current_values[4] = 'Failed'
                self.tree.item(item_id, values=current_values, tags=('failed',))
            elif status == 'Skipped':
                current_values[4] = 'Skipped'
                self.tree.item(item_id, values=current_values, tags=('skipped',))
            elif status == 'QualityBlocked':
                current_values[4] = 'QualityBlocked'
                self.tree.item(item_id, values=current_values, tags=('qualityblocked',))
            elif status == 'AgeRestricted':
                current_values[4] = 'AgeRestricted'
                self.tree.item(item_id, values=current_values, tags=('agerestricted',))
        
        # Update reset button state and status summary
        self.update_reset_button_state()
        self.update_status_summary()



    def reset_selected(self):
        """Reset selected videos by deleting files and setting status to Pending."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No videos selected to reset.")
            return
        
        # Check if any selected items can be reset
        resetable_items = []
        for item_id in selected_items:
            current_values = self.tree.item(item_id, 'values')
            if len(current_values) >= 5:
                status = current_values[4]
                if status in ['Done', 'Failed', 'Skipped', 'QualityBlocked', 'AgeRestricted']:
                    resetable_items.append(item_id)
        
        if not resetable_items:
            messagebox.showinfo("Info", "No resetable videos selected. Only Done, Failed, Skipped, QualityBlocked, or AgeRestricted videos can be reset.")
            return
        
        if messagebox.askyesno("Confirm Reset", f"Are you sure you want to reset {len(resetable_items)} video(s)? This will delete existing files and restart the download."):
            download_path = self.download_path.get()
            
            for item_id in resetable_items:
                # Find video info
                video_entry = None
                for video in self.download_queue:
                    if video['item_id'] == item_id:
                        video_entry = video
                        break
                
                if video_entry:
                    # Try to delete existing file and remove from download archive
                    try:
                        # Remove from download archive if it exists
                        archive_path = os.path.join(download_path, 'download-archive.txt')
                        if os.path.exists(archive_path) and video_entry.get('id'):
                            with open(archive_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                            
                            # Filter out the video ID from archive
                            new_lines = [line for line in lines if not line.strip().endswith(video_entry['id'])]
                            
                            if len(new_lines) != len(lines):
                                with open(archive_path, 'w', encoding='utf-8') as f:
                                    f.writelines(new_lines)
                                self.log_message(f"Removed {video_entry['title']} from download archive")
                        
                        # Try to find and delete the actual file (best effort)
                        # This is less reliable but still useful for cleanup
                        if video_entry['quality'].startswith('Audio-'):
                            audio_format = video_entry['quality'].split('-')[1]
                            if audio_format == 'default':
                                # Default format - could be various audio formats
                                possible_extensions = ['.webm', '.m4a', '.aac', '.mp3', '.ogg', '.opus']
                            elif audio_format == 'best':
                                # Could be m4a, aac, or other formats
                                possible_extensions = ['.m4a', '.aac', '.webm', '.mp4']
                            else:
                                possible_extensions = ['.mp3']
                        else:
                            possible_extensions = ['.mp4', '.mkv', '.webm']
                        
                        # Try to find files with the video title
                        title_safe = re.sub(r'[<>:"/\\|?*]', '_', video_entry['title'])
                        for ext in possible_extensions:
                            potential_file = os.path.join(download_path, f"{title_safe}{ext}")
                            if os.path.exists(potential_file):
                                os.remove(potential_file)
                                self.log_message(f"Deleted existing file: {os.path.basename(potential_file)}")
                                break
                                
                    except Exception as e:
                        self.log_message(f"Error during reset for {video_entry['title']}: {e}", "WARNING")
                    
                    # Reset status to Pending
                    self.update_video_status(item_id, 'Pending')
            
            self.log_message(f"Reset {len(resetable_items)} video(s) to Pending status.")
            self.update_status_summary()  # Update status summary after reset

    def update_reset_button_state(self):
        """Enable/disable reset button based on selection."""
        selected_items = self.tree.selection()
        resetable_count = 0
        
        for item_id in selected_items:
            current_values = self.tree.item(item_id, 'values')
            if len(current_values) >= 5:
                status = current_values[4]
                if status in ['Done', 'Failed', 'Skipped', 'QualityBlocked', 'AgeRestricted']:
                    resetable_count += 1
        
        if resetable_count > 0:
            self.reset_button.config(state=tk.NORMAL)
        else:
            self.reset_button.config(state=tk.DISABLED)

    def update_status_summary(self):
        """Update the status summary display with counts and colors."""
        if not hasattr(self, 'total_label'):
            return
            
        # Count statuses
        total = len(self.download_queue)
        done = sum(1 for v in self.download_queue if v.get('status') == 'Done')
        pending = sum(1 for v in self.download_queue if v.get('status', 'Pending') == 'Pending')
        failed = sum(1 for v in self.download_queue if v.get('status') == 'Failed')
        skipped = sum(1 for v in self.download_queue if v.get('status') == 'Skipped')
        quality_blocked = sum(1 for v in self.download_queue if v.get('status') == 'QualityBlocked')
        age_restricted = sum(1 for v in self.download_queue if v.get('status') == 'AgeRestricted')
        downloading = sum(1 for v in self.download_queue if v.get('status') == 'Downloading')
        
        # Update individual colored labels
        self.total_label.config(text=f"Total: {total}")
        self.done_label.config(text=f"Done: {done}")
        self.pending_label.config(text=f"Pending: {pending}")
        self.failed_label.config(text=f"Failed: {failed}")
        self.skipped_label.config(text=f"Skipped: {skipped}")
        self.quality_blocked_label.config(text=f"QualityBlocked: {quality_blocked}")
        self.age_restricted_label.config(text=f"AgeRestricted: {age_restricted}")
        
        # Show/hide downloading label based on whether there are downloading items
        if downloading > 0:
            self.downloading_label.config(text=f"Downloading: {downloading}")
            self.downloading_label.pack(side=tk.LEFT, padx=(0, 10))
        else:
            self.downloading_label.pack_forget()

    def classify_download_error(self, error_message, video_entry):
        """Classify download errors and return appropriate status."""
        error_lower = error_message.lower()
        
        # Check for HTTP 403 Forbidden errors
        if "http error 403" in error_lower or "403: forbidden" in error_lower:
            self.log_message(f"HTTP 403 Forbidden detected for {video_entry['title']} - Quality may be blocked", "WARNING")
            
            # Try to auto-retry with a different quality
            if self.auto_retry_with_different_quality(video_entry):
                return 'Pending'  # Reset to pending for retry
            else:
                return 'QualityBlocked'
        
        # Check for age restriction errors
        if any(phrase in error_lower for phrase in [
            "age restricted", "age-restricted", "sign in to confirm your age",
            "this video may be inappropriate", "content warning",
            "requires age verification", "age gate"
        ]):
            self.log_message(f"Age restriction detected for {video_entry['title']}", "WARNING")
            return 'AgeRestricted'
        
        # Check for other specific error patterns
        if "unavailable" in error_lower and "private" in error_lower:
            return 'Failed'
        
        if "region" in error_lower and ("blocked" in error_lower or "restricted" in error_lower):
            return 'Failed'
        
        # Default to Failed for other errors
        return 'Failed'

    def auto_retry_with_different_quality(self, video_entry):
        """Automatically retry with a different quality when 403 error occurs."""
        current_quality = video_entry['quality']
        
        # Handle audio format fallbacks
        if current_quality.startswith('Audio-'):
            audio_format = current_quality.split('-')[1]
            # Audio format fallback hierarchy: best → default (no more fallbacks after default)
            audio_fallback = {
                'best': 'default'
            }
            
            fallback_format = audio_fallback.get(audio_format)
            if fallback_format:
                fallback_quality = f'Audio-{fallback_format}'
                self.log_message(f"Auto-retrying {video_entry['title']} with audio format: {current_quality} → {fallback_quality}", "INFO")
                video_entry['quality'] = fallback_quality
                
                # Update GUI to show the new quality
                self.root.after(0, self.update_video_quality_in_gui, video_entry['item_id'], fallback_quality)
                return True
            
            return False  # No more audio fallbacks available
        
        # Video quality fallback hierarchy
        quality_fallback = {
            'Best': '1080p',
            '1080p': '720p', 
            '720p': '480p',
            '480p': '360p',
            '360p': 'Audio-default'  # Final fallback to default audio
        }
        
        fallback_quality = quality_fallback.get(current_quality)
        if fallback_quality:
            self.log_message(f"Auto-retrying {video_entry['title']} with quality: {current_quality} → {fallback_quality}", "INFO")
            video_entry['quality'] = fallback_quality
            
            # Update GUI to show the new quality
            self.root.after(0, self.update_video_quality_in_gui, video_entry['item_id'], fallback_quality)
            return True
        
        return False

    def suggest_troubleshooting(self, error_message):
        """Provide troubleshooting suggestions for common download errors."""
        error_lower = error_message.lower()
        
        if "postprocessing" in error_lower and "invalid data found when processing input" in error_lower:
            self.log_message("TROUBLESHOOTING: Postprocessing error detected. This usually happens when:", "WARNING")
            self.log_message("1. The video stream is corrupted or incomplete", "INFO")
            self.log_message("2. FFmpeg cannot merge the video and audio streams", "INFO")
            self.log_message("3. The video format is not compatible with the selected quality", "INFO")
            self.log_message("4. FFmpeg version is outdated or incompatible", "INFO")
            self.log_message("SOLUTIONS:", "WARNING")
            self.log_message("• Update FFmpeg to the latest version (see: https://github.com/yt-dlp/yt-dlp/issues/7541)", "INFO")
            self.log_message("• Try downloading as Audio Only (mp3) instead", "INFO")
            self.log_message("• Select a lower quality (720p or 480p)", "INFO")
            self.log_message("• Check if FFmpeg is properly installed and updated", "INFO")
            self.log_message("• The video might be region-restricted or have DRM protection", "INFO")
            self.log_message("• Try again later - the issue might be temporary", "INFO")
            
        elif "unavailable" in error_lower or "private" in error_lower:
            self.log_message("TROUBLESHOOTING: Video unavailable. Possible causes:", "WARNING")
            self.log_message("• Video is private, deleted, or region-restricted", "INFO")
            self.log_message("• Video requires age verification", "INFO")
            self.log_message("• Temporary YouTube server issues", "INFO")
            
        elif "format" in error_lower and "not available" in error_lower:
            self.log_message("TROUBLESHOOTING: Format not available. Try:", "WARNING")
            self.log_message("• Selecting a different quality option", "INFO")
            self.log_message("• Using Audio Only mode", "INFO")
            self.log_message("• The video might not have the requested quality", "INFO")
            
        elif "network" in error_lower or "connection" in error_lower or "timeout" in error_lower:
            self.log_message("TROUBLESHOOTING: Network issue detected. Try:", "WARNING")
            self.log_message("• Check your internet connection", "INFO")
            self.log_message("• Retry the download", "INFO")
            self.log_message("• Use a VPN if the content is region-blocked", "INFO")
            
        elif "ffmpeg" in error_lower:
            self.log_message("TROUBLESHOOTING: FFmpeg error. Solutions:", "WARNING")
            self.log_message("• Ensure FFmpeg is installed and in your PATH", "INFO")
            self.log_message("• Update FFmpeg to the latest version", "INFO")
            
        elif "http error 403" in error_lower or "403: forbidden" in error_lower:
            self.log_message("TROUBLESHOOTING: HTTP 403 Forbidden - Quality may be blocked. Try:", "WARNING")
            self.log_message("• Select a different quality (try 'Best' or lower quality)", "INFO")
            self.log_message("• Use Audio Only mode instead", "INFO")
            self.log_message("• The specific quality/format may be restricted for this video", "INFO")
            self.log_message("• Try again later - YouTube may have temporary restrictions", "INFO")
            self.log_message("• Some videos have quality-specific access restrictions", "INFO")
            
        elif any(phrase in error_lower for phrase in [
            "age restricted", "age-restricted", "sign in to confirm your age",
            "this video may be inappropriate", "content warning",
            "requires age verification", "age gate"
        ]):
            self.log_message("TROUBLESHOOTING: Age Restricted content detected:", "WARNING")
            self.log_message("• This video requires age verification on YouTube", "INFO")
            self.log_message("• Age-restricted videos cannot be downloaded without authentication", "INFO")
            self.log_message("• YouTube's age verification system blocks automated downloads", "INFO")
            self.log_message("• Consider using a different video or check if it's available elsewhere", "INFO")
            self.log_message("• Try downloading as Audio Only to bypass video processing", "INFO")

    def progress_hook(self, d):
        # Check if stop was requested during download
        if self.stop_event.is_set():
            # We can't actually stop yt-dlp mid-download, but we can log it once
            if d['status'] == 'downloading' and not self.stop_message_logged:
                self.progress_queue.put({'status': 'stop_requested'})
                self.stop_message_logged = True
        self.progress_queue.put(d)

    def process_progress_queue(self):
        """Processes progress updates from the queue and displays them in the console."""
        try:
            while not self.progress_queue.empty():
                d = self.progress_queue.get_nowait()
                if d['status'] == 'stop_requested':
                    self.log_message("Stop requested - waiting for current download to complete...", "WARNING")
                elif d['status'] == 'downloading':
                    current_time = time.time()
                    # Only update progress every 30 seconds
                    if current_time - self.last_progress_time >= 30:
                        percent_str = self.clean_ansi_codes(d.get('_percent_str', '0.0%').strip())
                        speed_str = self.clean_ansi_codes(d.get('_speed_str', 'N/A').strip())
                        eta_str = self.clean_ansi_codes(d.get('_eta_str', 'N/A').strip())
                        message = f"Downloading... {percent_str} | Speed: {speed_str} | ETA: {eta_str}"
                        self.log_message(message, overwrite=True)
                        self.last_progress_time = current_time
                elif d['status'] == 'finished':
                    # Add a final "100%" message before finalizing
                    self.log_message("Downloading... 100.0%", overwrite=True)
                    self.log_message("Finalizing download...", overwrite=False)
                    self.last_progress_time = 0  # Reset for next download
        except Exception: 
            pass # Ignore if queue is empty
        finally: 
            self.root.after(200, self.process_progress_queue) # Poll every 200ms

    def clean_ansi_codes(self, text):
        """Remove ANSI color codes from text."""
        # Remove ANSI escape sequences like [0;94m, [0m, etc.
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[[0-9;]*m')
        return ansi_escape.sub('', text)

    def log_message(self, msg, level='INFO', overwrite=False):
        """Logs a message to the console widget with log level filtering."""
        # Define log level hierarchy
        log_levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        current_level = log_levels.get(self.log_level_var.get(), 1)
        message_level = log_levels.get(level.upper(), 1)
        
        # Only show messages at or above the current log level
        if message_level < current_level:
            return
            
        self.console.config(state=tk.NORMAL)

        # Add level prefix to message
        if level.upper() != 'INFO':
            formatted_msg = f"[{level.upper()}] {msg}"
        else:
            formatted_msg = msg

        if overwrite:
            # Check if the last line is a progress line. If so, delete it.
            current_last_line = self.console.get("end-1l linestart", "end-1c")
            if current_last_line.startswith("Downloading...") or current_last_line.startswith("[INFO] Downloading..."):
                self.console.delete("end-1l", "end")

            self.console.insert("end", formatted_msg)
        else:
            # For a normal message, check if the previous line was a progress update.
            current_last_line = self.console.get("end-1l linestart", "end-1c")
            if current_last_line.startswith("Downloading...") or current_last_line.startswith("[INFO] Downloading..."):
                self.console.delete("end-1l", "end")

            self.console.insert("end", formatted_msg + "\n")

        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)


    def update_button_states(self):
        """Enables/disables buttons based on the application's state."""
        state = tk.DISABLED if self.is_downloading else tk.NORMAL
        self.start_button.config(state=state)
        self.remove_button.config(state=state)
        self.clear_all_button.config(state=state)
        self.move_up_button.config(state=state)
        self.move_down_button.config(state=state)
        self.add_button.config(state=state)
        self.change_path_button.config(state=state)
        if self.is_downloading:
            self.stop_button.config(state=tk.NORMAL, text="Stop")
        else:
            self.stop_button.config(state=tk.DISABLED, text="Stop")
        
        # Reset button is handled separately by update_reset_button_state
        if not self.is_downloading:
            self.update_reset_button_state()
            self.update_status_summary()

    def save_settings(self):
        """Saves download path, log level, and queue to the settings file."""
        try:
            settings = {
                'download_path': self.download_path.get(),
                'log_level': self.log_level_var.get(),
                'audio_format': self.audio_format_var.get(),
                'queue': [{k: v for k, v in video.items() if k not in ['item_id', 'info']} for video in self.download_queue]  # Exclude 'info' from saving
            }
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        """Loads settings from the settings file on startup."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                
                path = settings.get('download_path', DEFAULT_DOWNLOAD_PATH)
                self.download_path.set(path)

                # Load log level setting
                log_level = settings.get('log_level', 'INFO')
                self.log_level_var.set(log_level)
                
                # Load audio format setting
                audio_format = settings.get('audio_format', 'default (YouTube)')
                self.audio_format_var.set(audio_format)

                loaded_queue = settings.get('queue', [])
                if loaded_queue:
                    # Ensure duration and status fields exist for backward compatibility
                    for video in loaded_queue:
                        if 'duration' not in video:
                            video['duration'] = 'N/A'
                        if 'status' not in video:
                            video['status'] = 'Pending'
                    self.add_videos_to_gui(loaded_queue)
                    self.log_message(f"Loaded {len(loaded_queue)} items and settings from previous session.")
                else:
                    # Initialize status summary even with empty queue
                    self.update_status_summary()
            except Exception as e:
                self.log_message(f"Could not load settings: {e}", "ERROR")
                self.update_status_summary()  # Initialize status summary on error
        else:
            # Initialize status summary for first run
            self.update_status_summary()

    def on_closing(self):
        """Handles the window closing event."""
        if self.is_downloading:
            if messagebox.askyesno("Exit", "A download is in progress. Are you sure you want to exit?"):
                self.stop_event.set()
                self.save_settings()
                self.root.destroy()
        else:
            self.save_settings()
            self.root.destroy()



def main():
    """Main function to run the application."""
    try:

        
        # Create and run the app
        root = tk.Tk()
        app = YouTubeDownloaderApp(root)
        root.mainloop()
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    main()
