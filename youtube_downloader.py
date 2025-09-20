import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import json
import os
import sys
from queue import Queue
import yt_dlp

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

        # --- GUI Variables ---
        self.download_path = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)

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
        quality_options = ['1080p', '720p', '480p', '360p']
        self.quality_menu = ttk.OptionMenu(options_frame, self.quality_var, quality_options[0], *quality_options)
        self.quality_menu.pack(side=tk.LEFT, padx=(0, 20))
        
        self.audio_only_var = tk.BooleanVar()
        self.audio_only_check = ttk.Checkbutton(options_frame, text="Audio Only (mp3)", variable=self.audio_only_var, command=self.on_setting_change)
        self.audio_only_check.pack(side=tk.LEFT)
        
        self.quality_var.trace_add('write', self.on_setting_change)

        # --- Download Path Frame ---
        path_frame = ttk.Frame(top_frame)
        path_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=5)
        ttk.Label(path_frame, text="Download Folder:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.download_path, state='readonly')
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.change_path_button = ttk.Button(path_frame, text="Change...", command=self.change_download_path)
        self.change_path_button.pack(side=tk.LEFT, padx=5)


        # --- List Frame: Download Queue ---
        self.tree = ttk.Treeview(list_frame, columns=('Name', 'ID', 'Quality'), show='headings')
        self.tree.heading('Name', text='Video Title')
        self.tree.heading('ID', text='Video ID')
        self.tree.heading('Quality', text='Format')
        self.tree.column('Name', width=400)
        self.tree.column('ID', width=120)
        self.tree.column('Quality', width=100, anchor='center')
        self.tree.bind('<<TreeviewSelect>>', self.on_video_select)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- List Control Buttons ---
        list_button_frame = ttk.Frame(list_frame)
        list_button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        self.remove_button = ttk.Button(list_button_frame, text="Remove", command=self.remove_selected)
        self.remove_button.pack(pady=5, fill=tk.X)

        self.start_button = ttk.Button(list_button_frame, text="Start", command=self.start_download)
        self.start_button.pack(pady=5, fill=tk.X)

        self.stop_button = ttk.Button(list_button_frame, text="Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(pady=5, fill=tk.X)

        # --- Console Frame: Progress Output ---
        ttk.Label(console_frame, text="Progress Log:").pack(anchor='w')
        self.console = scrolledtext.ScrolledText(console_frame, height=8, state=tk.DISABLED, bg='black', fg='white', font=("Courier", 9))
        self.console.pack(fill=tk.X, expand=True)

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
        
        video_info = None
        for v in self.download_queue:
            if v['item_id'] == item_id:
                video_info = v
                break

        if video_info:
            self.is_updating_from_selection = True # Set flag to prevent trace callback
            
            quality = video_info['quality']
            if quality == 'Audio':
                self.audio_only_var.set(True)
                self.quality_menu.config(state=tk.DISABLED)
            else:
                self.audio_only_var.set(False)
                self.quality_var.set(quality)
                self.quality_menu.config(state=tk.NORMAL)
            
            self.is_updating_from_selection = False # Unset flag

    def on_setting_change(self, *args):
        """Updates a selected video's settings when controls are changed."""
        if self.is_updating_from_selection: # Do nothing if change was triggered by selection
            return
            
        selected_items = self.tree.selection()
        if not selected_items:
            return

        new_quality = 'Audio' if self.audio_only_var.get() else self.quality_var.get()

        for item_id in selected_items:
            # Update internal data
            for video in self.download_queue:
                if video['item_id'] == item_id:
                    video['quality'] = new_quality
                    break
            
            # Update GUI
            current_values = self.tree.item(item_id, 'values')
            self.tree.item(item_id, values=(current_values[0], current_values[1], new_quality))
        
        self.quality_menu.config(state=tk.DISABLED if self.audio_only_var.get() else tk.NORMAL)
        self.log_message(f"Updated settings for {len(selected_items)} selected item(s).")
        self.save_settings()

    def add_url(self):
        """Handles adding a URL to the download queue."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "URL field cannot be empty.")
            return

        quality = 'Audio' if self.audio_only_var.get() else self.quality_var.get()
        self.url_entry.delete(0, tk.END)
        self.log_message("Processing URL... (This may take a moment for playlists)")
        threading.Thread(target=self._process_url, args=(url, quality), daemon=True).start()

    def _process_url(self, url, quality):
        """Worker function to fetch video info without blocking the GUI."""
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist', 'skip_download': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            videos_to_add = []
            if 'entries' in info: # Playlist
                for entry in info['entries']:
                    if entry:
                        videos_to_add.append({'title': entry.get('title', 'N/A'), 'id': entry.get('id', 'N/A'), 'url': f"https://www.youtube.com/watch?v={entry.get('id')}", 'quality': quality})
                self.log_message(f"Added {len(videos_to_add)} videos from playlist.")
            else: # Single video
                videos_to_add.append({'title': info.get('title', 'N/A'), 'id': info.get('id', 'N/A'), 'url': info.get('webpage_url'), 'quality': quality})
                self.log_message(f"Added video: {info.get('title')}")
            
            self.root.after(0, self.add_videos_to_gui, videos_to_add)
        except Exception as e:
            self.log_message(f"Error fetching video info: {e}", "error")

    def add_videos_to_gui(self, videos):
        """Adds video information to the Treeview and internal queue."""
        for video in videos:
            item_id = self.tree.insert('', tk.END, values=(video['title'], video['id'], video['quality']))
            video['item_id'] = item_id
            self.download_queue.append(video)
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
        self.save_settings()

    def start_download(self):
        """Starts the download process."""
        if not self.download_queue:
            messagebox.showinfo("Info", "Download queue is empty.")
            return
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress.")
            return
        
        self.is_downloading = True
        self.stop_event.clear()
        self.update_button_states()

        self.download_thread = threading.Thread(target=self.download_worker, daemon=True)
        self.download_thread.start()
        self.log_message("--- Download process started ---")

    def stop_download(self):
        """Signals the download thread to stop."""
        if self.is_downloading:
            self.stop_event.set()
            self.log_message("--- Stop signal sent. Finishing current file... ---", "warning")

    def download_worker(self):
        """The main worker function that downloads videos one by one."""
        download_path = self.download_path.get()
        if not os.path.isdir(download_path):
             self.log_message(f"Error: Download path '{download_path}' does not exist. Please select a valid folder.", "error")
             self.is_downloading = False
             self.root.after(0, self.update_button_states)
             return

        while self.download_queue and not self.stop_event.is_set():
            video_info = self.download_queue[0]
            try:
                self.log_message(f"Starting download: {video_info['title']}")
                if video_info['quality'] == 'Audio':
                    ydl_opts = {'format': 'bestaudio/best', 'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'progress_hooks': [self.progress_hook], 'nocheckcertificate': True}
                else:
                    quality = video_info['quality']
                    ydl_opts = {'format': f'bestvideo[height<=?{quality[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'), 'progress_hooks': [self.progress_hook], 'nocheckcertificate': True}
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_info['url']])

                if self.stop_event.is_set():
                    self.log_message("Download stopped by user.", "warning")
                    break
                
                self.log_message(f"Successfully downloaded: {video_info['title']}", "success")
                self.root.after(0, self.remove_completed_item, video_info['item_id'])
            except Exception as e:
                self.log_message(f"Error downloading {video_info['title']}: {e}", "error")
                self.root.after(0, self.remove_completed_item, video_info['item_id'])
                continue

        self.is_downloading = False
        self.stop_event.clear()
        self.log_message("--- Download process finished ---")
        self.root.after(0, self.update_button_states)

    def remove_completed_item(self, item_id):
        """Removes an item from the queue and GUI after completion or error."""
        try:
            if self.tree.exists(item_id):
                self.tree.delete(item_id)
            self.download_queue.pop(0)
            self.save_settings()
        except IndexError:
            # This can happen if the queue was cleared while a download finished
            pass

    def progress_hook(self, d):
        self.progress_queue.put(d)

    def process_progress_queue(self):
        """Processes progress updates from the queue and displays them in the console."""
        try:
            while not self.progress_queue.empty():
                d = self.progress_queue.get_nowait()
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0.0%').strip()
                    speed_str = d.get('_speed_str', 'N/A').strip()
                    eta_str = d.get('_eta_str', 'N/A').strip()
                    message = f"Downloading... {percent_str} | Speed: {speed_str} | ETA: {eta_str}"
                    self.log_message(message, overwrite=True)
                elif d['status'] == 'finished':
                    # Add a final "100%" message before finalizing
                    self.log_message("Downloading... 100.0%", overwrite=True)
                    self.log_message("Finalizing download...", overwrite=False)
        except Exception: 
            pass # Ignore if queue is empty
        finally: 
            self.root.after(200, self.process_progress_queue) # Poll every 200ms

    def log_message(self, msg, level='info', overwrite=False):
        """Logs a message to the console widget, handling single-line overwrites."""
        self.console.config(state=tk.NORMAL)

        if overwrite:
            # Check if the last line is a progress line. If so, delete it.
            # This check prevents deleting a non-progress line if two 'overwrite' messages arrive back-to-back.
            current_last_line = self.console.get("end-1l linestart", "end-1c")
            if current_last_line.startswith("Downloading..."):
                self.console.delete("end-1l", "end")

            # Insert the new message. We add a newline temporarily and then delete it.
            # This ensures the view scrolls down correctly if needed.
            self.console.insert("end", msg)
        else:
            # For a normal message, check if the previous line was a progress update.
            # If so, we want to replace it by first deleting it.
            current_last_line = self.console.get("end-1l linestart", "end-1c")
            if current_last_line.startswith("Downloading..."):
                self.console.delete("end-1l", "end")

            # Insert the new message, followed by a newline.
            self.console.insert("end", msg + "\n")

        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)


    def update_button_states(self):
        """Enables/disables buttons based on the application's state."""
        state = tk.DISABLED if self.is_downloading else tk.NORMAL
        self.start_button.config(state=state)
        self.remove_button.config(state=state)
        self.add_button.config(state=state)
        self.change_path_button.config(state=state)
        self.stop_button.config(state=tk.NORMAL if self.is_downloading else tk.DISABLED)

    def save_settings(self):
        """Saves download path and queue to the settings file."""
        try:
            settings = {
                'download_path': self.download_path.get(),
                'queue': [{k: v for k, v in video.items() if k != 'item_id'} for video in self.download_queue]
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

                loaded_queue = settings.get('queue', [])
                if loaded_queue:
                    self.add_videos_to_gui(loaded_queue)
                    self.log_message(f"Loaded {len(loaded_queue)} items and settings from previous session.")
            except Exception as e:
                self.log_message(f"Could not load settings: {e}", "error")

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

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
