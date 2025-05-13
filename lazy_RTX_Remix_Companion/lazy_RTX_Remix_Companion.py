import sys
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, Label, Button, messagebox
import json
import shutil
import os
import re
import string
import urllib.request
import math
import zipfile
from threading import Thread
import datetime
import requests
import time

app_version = "1.0.0.reborn"

class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

# Global variables
firstLaunch = True
oldVersion = False

class CustomGameNameDialog(simpledialog.Dialog):
    def __init__(self, parent, title, folder_path):
        self.folder_path = folder_path
        self.exclude_keywords = {
            'steam', 'steamlibrary', 'steamapps', 'common', 'game', 'games', 'gamedata',
            'data', 'system', 'systemdata', 'bin', 'x64', 'x86', 'ea games', 'ea sports',
            'ubisoft', 'ubisoft games', 'program files', 'program files (x86)'
        }
        super().__init__(parent, title=title)

    def body(self, frame):
        Label(frame, text="Select or enter the game name:").pack(pady=5)
        options = self.generate_options()
        self.game_name_var = ttk.Combobox(frame, values=options)
        self.game_name_var.pack(pady=10, fill='x', expand=True)
        self.game_name_var.set(self.generate_default_name(options))
        return self.game_name_var  # initial focus

    def generate_options(self):
        path_elements = filter(None, re.split(r'[/\\]', self.folder_path.replace('_', ' ')))
        options = set()
        for pe in path_elements:
            if ':' not in pe and not any(keyword in pe.lower() for keyword in self.exclude_keywords):
                formatted_name = self.format_camel_case_and_numbers(pe.replace('_', ' '))
                options.add(formatted_name)
                shortened_names = self.generate_shortened_name(formatted_name)
                options.update(shortened_names)
        return list(options) if options else ["New Game"]

    def format_camel_case_and_numbers(self, name):
        name_with_spaces = re.sub(r'(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[0-9][^0-9])', ' ', name)
        name_with_spaces = re.sub(r'(?<=[0-9])(?=[A-Z])', ' ', name_with_spaces)
        return name_with_spaces
        
    def roman_to_arabic(self, roman):
        roman_numerals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
        result = 0
        prev_value = 0
        for char in reversed(roman):
            value = roman_numerals.get(char, 0)
            if value >= prev_value:
                result += value
            else:
                result -= value
            prev_value = value
        return result
        
    def generate_shortened_name(self, name):
        if re.fullmatch(r'[A-Z]+[0-9]{0,4}', name) or len(name) <= 4:
            return {name}
    
        words = re.split(r'\s+', name.strip())
        base_abbr = ''
        shortened_names = set()
    
        for word in words:
            if len(word) == 4 and (word.startswith("19") or word.startswith("20")):
                year_abbr = "1K" if word.startswith("19") else "2K"
                year_part_full = word[2:]  # Last two digits with leading zero
                year_part_short = str(int(year_part_full))  # Convert to integer to remove leading zero
                shortened_names.add(f"{base_abbr}{year_abbr}{year_part_full}")
                shortened_names.add(f"{base_abbr}{year_abbr}{year_part_short}")
            elif word.isdigit():
                base_abbr += word
            elif re.fullmatch(r'IV|IX|V?I{0,3}', word):  # Regex to identify common Roman numerals
                arabic = self.roman_to_arabic(word)
                base_abbr += str(arabic)
            else:
                base_abbr += word[0].upper()
    
        if not shortened_names and len(base_abbr) >= 2:
            shortened_names.add(base_abbr)
    
        return shortened_names
    
    def generate_default_name(self, options):
        return max(options, key=len) if options else "New Game"

    def apply(self):
        self.result = self.game_name_var.get()

class lazy_rtx_remix_companion:
    def __init__(self, master):
        self.master = master
        self.master.geometry(('1280x720+100+100'))
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.title(f"lazy_RTX-Remix Companion %s" % app_version)
        
        # Windows 11 progress colors
        self.progress_colors = {
            'bg': '#f0f0f0',
            'fill_start': '#0078D7',
            'fill_end': '#4CC2FF',
            'text': '#ffffff',
            'error': '#d83b3b'
        }
        
        # Initialize config dictionary 
        self.config = {}
        
        # Apply Nvidia dark theme
        self.apply_nvidia_theme(master)
        
        # Initialize UI components
        self.init_ui()
        
        # Initialize as None
        self.remix_folder = None
        self.tipwindow = None
        self.text = None
        
        # Load configuration
        self.load_config()
        
    def init_ui(self):
        """Initialize all UI components"""
        # Setup frames
        self.button_frame = ttk.Frame(self.master)
        self.button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Setup buttons
        self.setup_buttons()
        
        # Setup status bar
        self.setup_status_bar()
        
        # Setup treeview
        self.setup_treeview()
        
        # Flag to track if first launch tutorial has been shown
        self.first_launch_shown = False
        
        # Create context menu for the main window
        self.create_context_menu()

    def apply_nvidia_theme(self, root):
        """Apply NVIDIA-themed dark style to the application"""
        # NVIDIA-inspired color scheme
        dark_bg = "#1a1a1a"  # Very dark gray/almost black
        darker_bg = "#141414"  # Even darker for contrast
        nvidia_green = "#76B900"  # NVIDIA's signature green
        darker_green = "#5a8c00"  # Darker green for buttons
        highlight_color = "#2a2a2a"  # Slightly lighter gray for highlights
        text_color = "#e0e0e0"  # Light gray for text
        entry_bg = "#242424"  # Dark gray for entry fields
        
        # Configure ttk styles
        style = ttk.Style()
        style.theme_use('clam')  # Use clam as base theme
        
        # Configure colors for various widget types
        style.configure('TFrame', background=dark_bg)
        style.configure('TLabel', background=dark_bg, foreground=text_color)
        
        # Button styling
        style.configure('TButton', 
                       background=darker_green, 
                       foreground=text_color, 
                       borderwidth=1,
                       focusthickness=3,
                       focuscolor=nvidia_green)
        style.map('TButton', 
                  background=[('active', nvidia_green), ('pressed', darker_green)],
                  foreground=[('active', 'black'), ('pressed', text_color)])
        
        # Entry field styling
        style.configure('TEntry', 
                       fieldbackground=entry_bg, 
                       foreground=text_color, 
                       bordercolor=darker_green,
                       lightcolor=darker_green,
                       darkcolor=darker_green)
        style.map('TEntry', 
                  fieldbackground=[('focus', entry_bg)], 
                  bordercolor=[('focus', nvidia_green)])
        
        # Checkbutton and Radiobutton styling
        style.configure('TCheckbutton', 
                       background=dark_bg, 
                       foreground=text_color)
        style.map('TCheckbutton', 
                  background=[('active', dark_bg)],
                  foreground=[('active', nvidia_green)])
        
        style.configure('TRadiobutton', 
                       background=dark_bg, 
                       foreground=text_color)
        style.map('TRadiobutton',
                  background=[('active', dark_bg)],
                  foreground=[('active', nvidia_green)])
        
        # Notebook (tabs) styling
        style.configure('TNotebook', 
                       background=darker_bg, 
                       borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background=highlight_color, 
                       foreground=text_color, 
                       padding=[10, 2])
        style.map('TNotebook.Tab',
                  background=[('selected', nvidia_green)],
                  foreground=[('selected', 'black')])
        
        # Labelframe styling
        style.configure('TLabelframe', 
                       background=dark_bg, 
                       foreground=nvidia_green, 
                       bordercolor=darker_green)
        style.configure('TLabelframe.Label', 
                       background=dark_bg, 
                       foreground=nvidia_green)
        
        # Scrollbar styling
        style.configure('TScrollbar', 
                       background=highlight_color, 
                       bordercolor=highlight_color, 
                       arrowcolor=text_color, 
                       troughcolor=darker_bg)
        style.map('TScrollbar', 
                  background=[('active', nvidia_green), ('pressed', darker_green)],
                  arrowcolor=[('active', 'black'), ('pressed', 'black')])
                  
        style.configure('Status.TLabel', 
                       background='#1a1a1a',
                       foreground='#e0e0e0',
                       font=('Segoe UI', 9))
        
        # PanedWindow styling
        style.configure('TPanedwindow', background=dark_bg)
        
        # Configure Text widget and Canvas (these are not ttk widgets)
        root.option_add('*Text.background', entry_bg)
        root.option_add('*Text.foreground', text_color)
        root.option_add('*Text.borderwidth', 1)
        root.option_add('*Text.relief', 'solid')
        root.option_add('*Canvas.background', 'black')
        root.option_add('*Canvas.borderwidth', 1)
        root.option_add('*Canvas.relief', 'solid')
        
        # Treeview styling
        style.configure("Treeview",
                        background=dark_bg,
                        foreground=text_color,
                        fieldbackground=dark_bg)
        style.map("Treeview",
                  background=[('selected', nvidia_green)],
                  foreground=[('selected', 'black')])
        style.configure("Treeview.Heading",
                        background=darker_bg,
                        foreground=nvidia_green)
        
        # Progressbar styling
        style.configure("Horizontal.TProgressbar",
                        background=nvidia_green,
                        troughcolor=darker_bg)
        
        # Set the main window background
        root.configure(background=darker_bg)

    def __init__(self, master):
        self.master = master
        self.master.geometry(('1280x720+100+100'))
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.title(f"lazy_RTX-Remix Companion %s" % app_version)
        
        # Windows 11 progress colors
        self.progress_colors = {
            'bg': '#f0f0f0',
            'fill_start': '#0078D7',
            'fill_end': '#4CC2FF',
            'text': '#ffffff',
            'error': '#d83b3b'
        }
        
        # Initialize config dictionary 
        self.config = {}
        
        # Initialize source_versions with default values
        self.source_versions = {"runtime version": "N/A", "bridge version": "N/A"}
        
        # Apply Nvidia dark theme
        self.apply_nvidia_theme(master)
        
        # Initialize UI components
        self.init_ui()
        
        # Initialize as None
        self.remix_folder = None
        self.tipwindow = None
        self.text = None
        
        # Load configuration
        self.load_config()
    
    def create_context_menu(self):
        """Create a context menu for the main window"""
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Reset Configuration (Keep Games)", command=self.reset_config_keep_games)
        
        # Bind right-click to show the context menu
        self.master.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show the context menu on right-click"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def setup_buttons(self):
        """Set up all buttons in the left panel"""
        buttons = [
            ("Download RTX-Remix", self.download_rtx_remix_component),
            ("Add Game Folder", self.select_destination),
            ("Remove Game", self.remove_selected_game),
            ("Copy Files", self.copy_files)
        ]
        
        for text, command in buttons:
            button = ttk.Button(self.button_frame, text=text, command=command)
            button.pack(anchor=tk.W, pady=5, padx=5, fill=tk.X)
            
            # Store copy button reference to enable/disable it
            if text == "Copy Files":
                self.copy_button = button
                self.copy_button.configure(state='disabled')
        
        # Add a settings/options section
        settings_frame = ttk.LabelFrame(self.button_frame, text="Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=10, anchor=tk.W)
        
        # Reset config button
        reset_button = ttk.Button(
            settings_frame, 
            text="Reset Configuration", 
            command=self.reset_config_keep_games
        )
        reset_button.pack(pady=5, padx=5, fill=tk.X)

    def setup_status_bar(self):
        """Set up the status bar at the bottom of the window"""
        self.status_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_left = ttk.Label(self.status_frame, text="RTX-Remix Folder: None", anchor=tk.W)
        self.status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_right = ttk.Label(self.status_frame, 
                                      text="Please Select the RTX-Remix folder and Game Folder(s) to proceed.", 
                                      anchor=tk.W)
        self.status_right.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(self.status_frame, orient="horizontal", mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X)

    def setup_treeview(self):
        """Setup the Treeview with columns, headings, and interaction bindings"""
        # Define columns
        columns = ("🔓", "Game Name", "Folder Path", "Bridge", "Runtime", 
                  "Runtime Version", "Bridge Version")
        
        # Create treeview
        self.tree = ttk.Treeview(self.master, columns=columns, show="headings")
        
        # Configure column widths
        for col in columns:
            self.tree.heading(col, text=col)
            width = 10 if col == "🔓" else 160 if col in ["Game Name", "Folder Path"] else \
                  20 if col in ["Bridge", "Runtime"] else 80
            self.tree.column(col, anchor="center", width=width)
        
        # Add scrollbars
        v_scroll = ttk.Scrollbar(self.master, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side='right', fill='y')
        
        h_scroll = ttk.Scrollbar(self.master, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(side='bottom', fill='x')
        
        # Configure tags for visual indicators
        self.tree.tag_configure("version_mismatch", foreground="#FF5555")
        self.tree.tag_configure("version_match", foreground="#76B900")
        self.tree.tag_configure('disable', background='#444444', foreground='#BBBBBB')
        
        # Pack the tree
        self.tree.pack(expand=True, fill='both')
        
        # Setup tooltip and bindings
        self.tree_tooltip = Tooltip(self.tree)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)
        self.tree.bind("<Button-1>", self.handle_click)
        self.tree.bind("<Motion>", self.handle_motion)
        
        # Keyboard shortcuts
        self.tree.bind('<Control-a>', self.select_all_except_disabled)
        self.tree.bind('<Control-A>', self.select_all_except_disabled)
        self.tree.bind('<Control-d>', self.deselect_all)
        self.tree.bind('<Control-D>', self.deselect_all)

    def select_all_except_disabled(self, event):
        self.tree.selection_remove(self.tree.selection())
        for item in self.tree.get_children():
            if 'disable' not in self.tree.item(item, 'tags'):
                self.tree.selection_add(item)
    
    def deselect_all(self, event):
        self.tree.selection_remove(self.tree.selection())
                
    def show_tooltip(self, text, x, y):
        if self.tipwindow or not text:
            return
        self.text = text
        self.tipwindow = tw = tk.Toplevel(self.master)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x+20}+{y+20}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                        background="#242424", foreground="#e0e0e0", 
                        relief=tk.SOLID, borderwidth=1,
                        font=("tahoma", "8", "Normal"))
        label.pack(ipadx=1)
        
    def hide_tooltip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
        
    def handle_motion(self, event):
        x, y, widget = event.x, event.y, event.widget
        region = widget.identify_region(x, y)
        column_id = widget.identify_column(x)
        row_id = widget.identify_row(y)
    
        if row_id and column_id and region == "cell":
            col_index = int(column_id.strip('#')) - 1
            if col_index in [0, 3, 4]:  # Modified to only include lock, Bridge, and Runtime
                widget.configure(cursor="hand2")
            else:
                widget.configure(cursor="arrow")
        else:
            widget.configure(cursor="arrow")

    def handle_click(self, event):
        x, y, widget = event.x, event.y, event.widget
        column_id = widget.identify_column(x)
        row_id = widget.identify_row(y)
    
        if not row_id:
            self.deselect_all(event)
            return
    
        if column_id and row_id:
            col_index = int(column_id.strip('#')) - 1
            if widget.exists(row_id):
                current_values = list(widget.item(row_id, 'values'))
    
                if 0 <= col_index < len(current_values):
                    if col_index == 0:
                        self.toggle_lock_status(row_id, current_values)
                    elif col_index in [3, 4]:  # Modified to only include Bridge and Runtime
                        self.toggle_yes_no(row_id, current_values, col_index)
    
        self.update_copy_button_state()

    def toggle_lock_status(self, row_id, current_values):
        """Toggle between locked and unlocked state for a row"""
        if current_values[0] == "🔓":
            current_values[0] = "🔒"
            self.tree.item(row_id, values=current_values, tags=("disable",))
        else:
            current_values[0] = "🔓"
            destination_versions = {
                "runtime version": current_values[5],
                "bridge version": current_values[6]
            }
            self.check_version_and_tag(row_id, destination_versions)
            self.tree.item(row_id, values=current_values)
        self.save_config()

    def toggle_yes_no(self, row_id, current_values, col_index):
        """Toggle between Yes and No for a specific column"""
        current_values[col_index] = "No" if current_values[col_index] == "Yes" else "Yes"
        self.tree.item(row_id, values=current_values)
        self.save_config()
        
    def on_tree_selection(self, event):
        treeview = event.widget
        selection = treeview.selection()
        
        for item in selection:
            if 'disable' in treeview.item(item, 'tags'):
                treeview.selection_remove(item)
        self.update_copy_button_state()
        
    def serialize_treeview(self):
        """Get all treeview items as a serializable list"""
        return [self.tree.item(child, 'values') for child in self.tree.get_children()]

    def update_copy_button_state(self):
        """Enable or disable the copy button based on current selection and settings"""
        try:
            if self.remix_folder and self.tree.selection():
                self.copy_button.configure(state='normal')
                self.status_right.config(text="Ready to copy files.")
            else:
                self.copy_button.configure(state='disabled')
                if not self.remix_folder:
                    self.status_right.config(text="Select an RTX-Remix folder to enable copying.")
                elif not self.tree.selection():
                    self.status_right.config(text="Select one or more items in the list to copy.")
        except Exception as e:
            self.status_right.config(text=f"Error: {e}")
            
    def check_sources(self, folder):
        """Verify if the selected folder is a valid RTX-Remix folder"""
        if not folder or not os.path.exists(folder):
            return {"Non-existent directory"}, set()
            
        required_files_versions = [
            # Version 1
            {
                "build-names.txt", "d3d8_off.dll", "d3d9.dll", "dxvk.conf", "dxwrapper.dll", "dxwrapper.ini",
                "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
                "ThirdPartyLicenses-dxvk.txt", "ThirdPartyLicenses-dxwrapper.txt", ".trex"
            },
            # Version 2
            {
                "build_names.txt", "d3d8to9.dll", "d3d9.dll", "dxvk.conf", "LICENSE.txt", "NvRemixLauncher32.exe",
                "ThirdPartyLicenses-bridge.txt", "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
            },
            # Version 3
            {
                "build_names.txt", "d3d8to9.dll", "d3d9.dll", "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
                "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
            },
            # Version 4
            {
                "d3d8to9.dll", "d3d9.dll", "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
                "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
            }
        ]
        
        global oldVersion
        oldVersion = False
        
        try:
            actual_files = set(os.listdir(folder))
            
            # Check against each version of required files
            for version_files in required_files_versions:
                missing = version_files - actual_files
                extra = actual_files - version_files
                
                # If we find a match (minimal missing/extra files), we're good
                if not missing:
                    return set(), extra
            
            # If no match found, return details from first version (most comprehensive)
            return required_files_versions[0] - actual_files, actual_files - required_files_versions[0]
        except FileNotFoundError:
            return {"Non-existent directory"}, set()
        except PermissionError:
            return {"Permission denied"}, set()
        except Exception as e:
            return {f"Error: {str(e)}"}, set()
                
    def create_progress_dialog(self, title, message):
        """Create a standardized progress dialog"""
        progress_window = tk.Toplevel(self.master)
        progress_window.title(title)
        progress_window.configure(bg="#1a1a1a")
        progress_window.geometry("400x150")
        progress_window.transient(self.master)
        progress_window.grab_set()
        
        # Center the window
        window_width = 400
        window_height = 150
        screen_width = progress_window.winfo_screenwidth()
        screen_height = progress_window.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        progress_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Progress message
        message_label = tk.Label(
            progress_window,
            text=message,
            font=("Segoe UI", 10),
            fg="#e0e0e0",
            bg="#1a1a1a",
            justify=tk.LEFT
        )
        message_label.pack(pady=(15, 10), padx=20)
        
        # Progress bar
        progress_bar = ttk.Progressbar(
            progress_window, 
            orient="horizontal", 
            mode="determinate",
            length=360
        )
        progress_bar.pack(pady=10, padx=20)
        progress_bar.name = "progress"  # For easier reference later
        
        # Status label
        status_label = tk.Label(
            progress_window,
            text="Working...",
            font=("Segoe UI", 9),
            fg="#e0e0e0",
            bg="#1a1a1a"
        )
        status_label.pack(pady=5)
        status_label.name = "status"  # For easier reference later
        
        progress_window.update()
        return progress_window
        
    def update_all_version_tags(self, force=False):
        """Update version tags for all games based on current source_versions"""
        # Skip redundant updates unless forced
        current_time = time.time()
        if not force and hasattr(self, '_last_update_time') and current_time - self._last_update_time < 1.0:
            print(f"Skipping redundant version tag update (last update was {current_time - self._last_update_time:.2f}s ago)")
            return
        
        # Set the last update time
        self._last_update_time = current_time
        
        # Check if we have source_versions
        if not hasattr(self, 'source_versions') or not self.source_versions:
            print("Cannot update version tags: no source_versions available")
            return
                
        print(f"Updating version tags for all games using source versions: runtime='{self.source_versions['runtime version']}', bridge='{self.source_versions['bridge version']}'")
        
        for item in self.tree.get_children():
            # Skip locked items
            if 'disable' in self.tree.item(item, 'tags'):
                continue
                
            # Get current values and destination versions
            current_values = self.tree.item(item, 'values')
            folder_path = current_values[2]
            game_name = current_values[1]
            
            # Load current versions from the game folder
            destination_versions = self.load_versions_from_file(folder_path)
            
            # Compare with source versions
            matched = True
            if destination_versions["runtime version"] != self.source_versions["runtime version"]:
                matched = False
                runtime_display = self.simplify_version_display(destination_versions["runtime version"])
                source_display = self.simplify_version_display(self.source_versions["runtime version"])
                print(f"Runtime version mismatch for {game_name}: '{runtime_display}' vs source '{source_display}'")
            
            if destination_versions["bridge version"] != self.source_versions["bridge version"]:
                matched = False
                bridge_display = self.simplify_version_display(destination_versions["bridge version"])
                source_display = self.simplify_version_display(self.source_versions["bridge version"])
                print(f"Bridge version mismatch for {game_name}: '{bridge_display}' vs source '{source_display}'")
            
            # Update the tree item with simplified display but maintain correct tags
            self.check_version_and_tag(item, destination_versions)
    
    def set_active_build(self, build_path):
        """Set the specified build as the active RTX-Remix build for copying to games"""
        # Keep the main folder unchanged, but set the specific build as active
        self.active_build_path = build_path.replace("/", "\\") 
        
        # Load version information from the active build
        old_versions = None
        if hasattr(self, 'source_versions'):
            old_versions = self.source_versions.copy()
            
        self.source_versions = self.load_versions_from_file(build_path, True)
        print(f"Loaded source_versions: runtime={self.source_versions['runtime version']}, bridge={self.source_versions['bridge version']}")
        
        # Update status to show version info
        runtime_ver = self.source_versions['runtime version']
        bridge_ver = self.source_versions['bridge version']
        self.status_right.config(text=f"Active build: {os.path.basename(build_path)} | Runtime: {runtime_ver} | Bridge: {bridge_ver}")
        
        # Check if versions changed
        versions_changed = not old_versions or old_versions['runtime version'] != self.source_versions['runtime version'] or old_versions['bridge version'] != self.source_versions['bridge version']
        
        # Always force an update when the active build changes
        self.update_all_version_tags(force=True)
        
        # Update copy button state
        self.update_copy_button_state()
        
        # Update config
        self.current_build = os.path.basename(build_path)
        self.save_config()
    
    def show_build_name_dialog(self, folder_path, versions):
        """Show a styled dialog for naming a build that matches show_popup_window style"""
        # Create the popup window
        popup_window = tk.Toplevel(self.master)
        popup_window.title("Name This Build")
        popup_window.configure(bg="#1a1a1a")
        popup_window.transient(self.master)
        popup_window.grab_set()
    
        # Position the popup window centered on the main window
        win_width, win_height = 400, 200
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (win_width // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (win_height // 2)
        popup_window.geometry(f"{win_width}x{win_height}+{x}+{y}")
    
        # Title
        title_label = tk.Label(
            popup_window,
            text="Name This RTX-Remix Build",
            font=("Segoe UI", 12, "bold"),
            bg="#1a1a1a",
            fg="#76B900",
            justify="center"
        )
        title_label.pack(pady=(15, 10))
    
        # Description
        description = tk.Label(
            popup_window,
            text="Enter a name for this RTX-Remix build folder:",
            bg="#1a1a1a",
            fg="#e0e0e0",
            justify="center",
            wraplength=350
        )
        description.pack(pady=(0, 10))
    
        # Version info
        runtime_version = versions["runtime version"]
        bridge_version = versions["bridge version"]
        version_info = tk.Label(
            popup_window,
            text=f"Runtime: {runtime_version}\nBridge: {bridge_version}",
            bg="#1a1a1a",
            fg="#76B900",
            font=("Consolas", 9),
            justify=tk.LEFT
        )
        version_info.pack(pady=(0, 10))
    
        # Default name based on folder
        default_name = os.path.basename(folder_path)
        if not default_name or default_name.strip() == "":
            default_name = "rtx_remix_build"
        
        # Try to create a better default name based on version information
        if runtime_version != "N/A" and runtime_version.startswith("dxvk-remix-"):
            # Extract the version part from runtime_version
            version_part = runtime_version.replace("dxvk-remix-", "")
            # If it contains a build type (release, debug, etc.), extract that too
            if "-" in version_part:
                version_num, build_type = version_part.split("-", 1)
                default_name = f"remix_{version_num}"
        
        # Name input
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(popup_window, textvariable=name_var, width=40)
        name_entry.pack(pady=10, padx=20)
        name_entry.select_range(0, tk.END)
        name_entry.focus_set()
    
        # Buttons
        button_frame = ttk.Frame(popup_window)
        button_frame.pack(pady=15)
    
        result = [None]
    
        def on_cancel():
            result[0] = None
            popup_window.destroy()
    
        def on_submit():
            result[0] = name_var.get()
            popup_window.destroy()
    
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=on_cancel
        )
        cancel_button.grid(row=0, column=0, padx=10, pady=10)
    
        submit_button = ttk.Button(
            button_frame,
            text="OK",
            command=on_submit
        )
        submit_button.grid(row=0, column=1, padx=10, pady=10)
    
        # Make the dialog modal
        popup_window.wait_window()
    
        return result[0]
        
    def reorganize_builds_folder_structure(self):
        """
        Reorganize the RTX-Remix folder structure to a more organized layout on application load:
        
        RTX-Remix/
            release/
                release/
                    [builds]
                debug/
                    [builds]
                debugoptimized/
                    [builds]
            nightly/
                bridge/
                    x86/
                        release/
                            [builds]
                        debug/
                            [builds]
                        debugoptimized/
                            [builds]
                    x64/
                        release/
                            [builds]
                        debug/
                            [builds]
                        debugoptimized/
                            [builds]
                dxvk/
                    x86/
                        release/
                            [builds]
                        debug/
                            [builds]
                        debugoptimized/
                            [builds]
                    x64/
                        release/
                            [builds]
                        debug/
                            [builds]
                        debugoptimized/
                            [builds]
        """
        if not hasattr(self, 'remix_folder') or not self.remix_folder or not os.path.exists(self.remix_folder):
            return
        
        try:
            # Create all necessary folders
            build_types = ["release", "debug", "debugoptimized"]
            architectures = ["x86", "x64"]
            
            # Create the release folder structure
            release_folder = os.path.join(self.remix_folder, "release")
            os.makedirs(release_folder, exist_ok=True)
            
            # Create build type folders under release folder
            for build_type in build_types:
                os.makedirs(os.path.join(release_folder, build_type), exist_ok=True)
            
            # Create nightly structure with architecture subfolders
            nightly_folder = os.path.join(self.remix_folder, "nightly")
            os.makedirs(nightly_folder, exist_ok=True)
            
            # Create bridge and dxvk folders with architecture and build type subfolders
            for component in ["bridge", "dxvk"]:
                component_folder = os.path.join(nightly_folder, component)
                os.makedirs(component_folder, exist_ok=True)
                
                for arch in architectures:
                    arch_folder = os.path.join(component_folder, arch)
                    os.makedirs(arch_folder, exist_ok=True)
                    
                    for build_type in build_types:
                        os.makedirs(os.path.join(arch_folder, build_type), exist_ok=True)
            
            # Scan all items in the main folder for relocation
            relocated_count = 0
            for item_name in os.listdir(self.remix_folder):
                item_path = os.path.join(self.remix_folder, item_name)
                
                # Skip if it's already one of our structure folders
                if item_name in ["release", "nightly"]:
                    continue
                    
                # Also skip if it's one of the old build type folders at the root level
                if item_name in build_types:
                    # Process the builds in these folders separately
                    continue
                    
                # Only consider directories that could be RTX-Remix builds
                if not os.path.isdir(item_path) or not self.is_rtx_remix_folder(item_path):
                    continue
                
                # Determine where this build should go
                build_type = None
                is_nightly = False
                component = None
                arch = "x64"  # Default to x64 if not specified
                
                # Check if it's a nightly build and which component
                if "bridge-remix-" in item_name.lower() or "bridge_remix" in item_name.lower():
                    is_nightly = True
                    component = "bridge"
                elif "dxvk-remix-" in item_name.lower() or "dxvk_remix" in item_name.lower() or "rtx-remix-for-" in item_name.lower():
                    is_nightly = True
                    component = "dxvk"
                    
                    # Determine architecture for dxvk/runtime
                    if "x86" in item_name.lower() or "for-x86-games" in item_name.lower():
                        arch = "x86"
                    elif "x64" in item_name.lower() or "for-x64-games" in item_name.lower():
                        arch = "x64"
                
                # Determine build type
                if "release" in item_name.lower():
                    build_type = "release"
                elif "debugoptimized" in item_name.lower() or "debugopt" in item_name.lower():
                    build_type = "debugoptimized"
                elif "debug" in item_name.lower():
                    build_type = "debug"
                else:
                    # Default to release if not specified
                    build_type = "release"
                
                # Determine destination path
                if is_nightly and component:
                    # For nightly builds
                    destination_folder = os.path.join(nightly_folder, component, arch, build_type)
                else:
                    # For release builds, place under release/build_type/
                    destination_folder = os.path.join(release_folder, build_type)
                
                # Create a new name that avoids conflicts
                base_name = item_name
                destination_path = os.path.join(destination_folder, base_name)
                
                # If destination already exists, add a unique identifier
                counter = 1
                while os.path.exists(destination_path):
                    new_name = f"{base_name}_{counter}"
                    destination_path = os.path.join(destination_folder, new_name)
                    counter += 1
                
                # Move the folder to its new location
                try:
                    shutil.move(item_path, destination_path)
                    print(f"Moved {item_path} to {destination_path}")
                    relocated_count += 1
                except Exception as e:
                    print(f"Error moving {item_path}: {e}")
            
            # Process builds in old root-level build type folders (release, debug, debugoptimized)
            for build_type in build_types:
                old_build_type_path = os.path.join(self.remix_folder, build_type)
                if os.path.exists(old_build_type_path) and os.path.isdir(old_build_type_path):
                    # Get all builds in this folder
                    for build_name in os.listdir(old_build_type_path):
                        build_path = os.path.join(old_build_type_path, build_name)
                        if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                            # Move to the new location under release/build_type/
                            new_dest = os.path.join(release_folder, build_type, build_name)
                            
                            # Create a unique name if needed
                            counter = 1
                            while os.path.exists(new_dest):
                                new_name = f"{build_name}_{counter}"
                                new_dest = os.path.join(release_folder, build_type, new_name)
                                counter += 1
                            
                            # Move the build
                            try:
                                shutil.move(build_path, new_dest)
                                print(f"Moved {build_path} to {new_dest}")
                                relocated_count += 1
                            except Exception as e:
                                print(f"Error moving {build_path}: {e}")
                    
                    # Try to remove the now empty build_type folder at root level
                    if not os.listdir(old_build_type_path):
                        try:
                            os.rmdir(old_build_type_path)
                            print(f"Removed empty directory: {old_build_type_path}")
                        except Exception as e:
                            print(f"Could not remove directory {old_build_type_path}: {e}")
            
            # Also check for builds in the old nightly structure (without architecture folders)
            # and move them to the new structure
            old_structure_relocated = 0
            try:
                for component in ["bridge", "dxvk"]:
                    old_component_path = os.path.join(nightly_folder, component)
                    if os.path.exists(old_component_path):
                        for item_name in os.listdir(old_component_path):
                            item_path = os.path.join(old_component_path, item_name)
                            
                            # Skip if it's already one of our architecture folders
                            if item_name in architectures:
                                continue
                            
                            # Skip if it's a build type folder without builds inside
                            if item_name in build_types:
                                build_type_path = os.path.join(old_component_path, item_name)
                                # Iterate through this folder and move each build to the new structure
                                if os.path.isdir(build_type_path):
                                    for build_name in os.listdir(build_type_path):
                                        build_path = os.path.join(build_type_path, build_name)
                                        if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                                            # Determine architecture (default to x64)
                                            build_arch = "x64"
                                            if "x86" in build_name.lower() or "for-x86-games" in build_name.lower():
                                                build_arch = "x86"
                                                
                                            # Create destination path in new structure
                                            new_dest = os.path.join(nightly_folder, component, build_arch, item_name, build_name)
                                            
                                            # Create a unique name if needed
                                            counter = 1
                                            while os.path.exists(new_dest):
                                                new_name = f"{build_name}_{counter}"
                                                new_dest = os.path.join(nightly_folder, component, build_arch, item_name, new_name)
                                                counter += 1
                                            
                                            # Move the build
                                            try:
                                                shutil.move(build_path, new_dest)
                                                print(f"Moved {build_path} to {new_dest}")
                                                old_structure_relocated += 1
                                            except Exception as e:
                                                print(f"Error moving {build_path}: {e}")
                                continue
                            
                            # Only consider directories that could be RTX-Remix builds
                            if not os.path.isdir(item_path) or not self.is_rtx_remix_folder(item_path):
                                continue
                            
                            # Determine build type and architecture
                            build_type = "release"  # Default
                            arch = "x64"  # Default
                            
                            if "release" in item_name.lower():
                                build_type = "release"
                            elif "debugoptimized" in item_name.lower() or "debugopt" in item_name.lower():
                                build_type = "debugoptimized"
                            elif "debug" in item_name.lower():
                                build_type = "debug"
                            
                            if "x86" in item_name.lower() or "for-x86-games" in item_name.lower():
                                arch = "x86"
                            
                            # Create destination path in new structure
                            destination_folder = os.path.join(nightly_folder, component, arch, build_type)
                            destination_path = os.path.join(destination_folder, item_name)
                            
                            # Create a unique name if needed
                            counter = 1
                            while os.path.exists(destination_path):
                                new_name = f"{item_name}_{counter}"
                                destination_path = os.path.join(destination_folder, new_name)
                                counter += 1
                            
                            # Move the folder
                            try:
                                shutil.move(item_path, destination_path)
                                print(f"Moved {item_path} to {destination_path}")
                                old_structure_relocated += 1
                            except Exception as e:
                                print(f"Error moving {item_path}: {e}")
            except Exception as e:
                print(f"Error processing old nightly structure: {e}")
            
            # Clean up empty old-structure folders if possible
            for component in ["bridge", "dxvk"]:
                for build_type in build_types:
                    old_path = os.path.join(nightly_folder, component, build_type)
                    if os.path.exists(old_path) and os.path.isdir(old_path) and not os.listdir(old_path):
                        try:
                            os.rmdir(old_path)
                            print(f"Removed empty directory: {old_path}")
                        except:
                            pass
            
            total_relocated = relocated_count + old_structure_relocated
            if total_relocated > 0:
                self.status_right.config(text=f"Reorganized {total_relocated} RTX-Remix builds into a structured folder hierarchy.")
                
        except Exception as e:
            print(f"Error reorganizing builds: {e}")
    
    def update_build_selection_options(self):
        """Update the build selection options with available RTX-Remix builds"""
        # Create UI elements if they don't exist yet
        self.create_remix_selection_ui_if_needed()
        
        # Lists to store available builds
        release_builds = []
        nightly_bridge_builds = []
        nightly_runtime_builds = []
        
        # Check if main RTX-Remix folder exists
        if not hasattr(self, 'remix_folder') or not self.remix_folder or not os.path.exists(self.remix_folder):
            print("Warning: Main RTX-Remix folder not set or doesn't exist")
            return
        
        # Print debug info
        print(f"Scanning for builds in {self.remix_folder}...")
        
        try:
            # Scan for release builds in the new structure:
            # RTX-Remix/release/[build_type]/[build_name]/
            release_path = os.path.join(self.remix_folder, "release")
            if os.path.exists(release_path) and os.path.isdir(release_path):
                print(f"Scanning release folder: {release_path}")
                
                for build_type in ["release", "debug", "debugoptimized"]:
                    build_type_path = os.path.join(release_path, build_type)
                    if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                        print(f"Found build type folder: {build_type_path}")
                        
                        # Scan all builds in this build type folder
                        for build_name in os.listdir(build_type_path):
                            build_path = os.path.join(build_type_path, build_name)
                            if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                                versions = self.load_versions_from_file(build_path, False)
                                print(f"Found release build: {build_name} ({build_type}) at {build_path}")
                                release_builds.append({
                                    "name": f"{build_name} ({build_type})",
                                    "folder": build_name,
                                    "path": build_path,
                                    "runtime_version": versions["runtime version"],
                                    "bridge_version": versions["bridge version"],
                                    "build_type": build_type
                                })
            else:
                print(f"Release folder not found at {release_path}")
                
            # Scan for nightly builds in the new structure:
            # RTX-Remix/nightly/[component]/[architecture]/[build_type]/[build_name]
            nightly_path = os.path.join(self.remix_folder, "nightly")
            if os.path.exists(nightly_path) and os.path.isdir(nightly_path):
                print(f"Scanning nightly folder: {nightly_path}")
                
                # Scan bridge builds
                bridge_path = os.path.join(nightly_path, "bridge")
                if os.path.exists(bridge_path) and os.path.isdir(bridge_path):
                    print(f"Found bridge folder: {bridge_path}")
                    
                    # Scan each architecture folder
                    for arch in ["x86", "x64"]:
                        arch_path = os.path.join(bridge_path, arch)
                        if os.path.exists(arch_path) and os.path.isdir(arch_path):
                            print(f"Found architecture folder: {arch_path}")
                            
                            # Scan each build type folder
                            for build_type in ["release", "debug", "debugoptimized"]:
                                build_type_path = os.path.join(arch_path, build_type)
                                if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                                    print(f"Found build type folder: {build_type_path}")
                                    
                                    # Scan all builds in this build type folder
                                    for build_name in os.listdir(build_type_path):
                                        build_path = os.path.join(build_type_path, build_name)
                                        if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                                            versions = self.load_versions_from_file(build_path, False)
                                            timestamp = os.path.getmtime(build_path)
                                            print(f"Found bridge build: {build_name} in {arch}/{build_type}")
                                            nightly_bridge_builds.append({
                                                "name": f"bridge-remix-{build_name} ({arch}, {build_type})",
                                                "folder": build_name,
                                                "path": build_path,
                                                "version": versions["bridge version"],
                                                "timestamp": timestamp,
                                                "build_type": build_type,
                                                "architecture": arch
                                            })
                
                # Scan dxvk/runtime builds
                dxvk_path = os.path.join(nightly_path, "dxvk")
                if os.path.exists(dxvk_path) and os.path.isdir(dxvk_path):
                    print(f"Found dxvk folder: {dxvk_path}")
                    
                    # Scan each architecture folder
                    for arch in ["x86", "x64"]:
                        arch_path = os.path.join(dxvk_path, arch)
                        if os.path.exists(arch_path) and os.path.isdir(arch_path):
                            print(f"Found architecture folder: {arch_path}")
                            
                            # Scan each build type folder
                            for build_type in ["release", "debug", "debugoptimized"]:
                                build_type_path = os.path.join(arch_path, build_type)
                                if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                                    print(f"Found build type folder: {build_type_path}")
                                    
                                    # Scan all builds in this build type folder
                                    for build_name in os.listdir(build_type_path):
                                        build_path = os.path.join(build_type_path, build_name)
                                        if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                                            versions = self.load_versions_from_file(build_path, False)
                                            timestamp = os.path.getmtime(build_path)
                                            print(f"Found dxvk build: {build_name} in {arch}/{build_type}")
                                            nightly_runtime_builds.append({
                                                "name": f"dxvk-remix-{build_name} ({arch}, {build_type})",
                                                "folder": build_name,
                                                "path": build_path,
                                                "version": versions["runtime version"],
                                                "timestamp": timestamp,
                                                "build_type": build_type,
                                                "architecture": arch
                                            })
                                            
            # Also check legacy locations for backward compatibility
            # Old structure: RTX-Remix/[build_type]/[build_name]
            for build_type in ["release", "debug", "debugoptimized"]:
                build_type_path = os.path.join(self.remix_folder, build_type)
                if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                    for build_name in os.listdir(build_type_path):
                        build_path = os.path.join(build_type_path, build_name)
                        if os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                            versions = self.load_versions_from_file(build_path, False)
                            print(f"Found legacy build: {build_name} ({build_type})")
                            release_builds.append({
                                "name": f"{build_name} ({build_type}) [Legacy]",
                                "folder": build_name,
                                "path": build_path,
                                "runtime_version": versions["runtime version"],
                                "bridge_version": versions["bridge version"],
                                "build_type": build_type
                            })
            
            # Also check for standalone builds at the root level that haven't been organized yet
            for item in os.listdir(self.remix_folder):
                item_path = os.path.join(self.remix_folder, item)
                if (item not in ["release", "nightly"] and 
                    os.path.isdir(item_path) and 
                    self.is_rtx_remix_folder(item_path)):
                    
                    # Determine if it's a release, bridge or dxvk build
                    versions = self.load_versions_from_file(item_path, False)
                    is_bridge = "bridge" in item.lower()
                    is_dxvk = "dxvk" in item.lower() or "rtx-remix" in item.lower()
                    
                    # Default to release build if can't determine
                    if not (is_bridge or is_dxvk):
                        release_builds.append({
                            "name": f"{item} (standalone)",
                            "folder": item,
                            "path": item_path,
                            "runtime_version": versions["runtime version"],
                            "bridge_version": versions["bridge version"],
                            "build_type": "unknown"
                        })
                        print(f"Found standalone build: {item}")
                        
            # Trigger version update after dropdown is populated
            self.master.after(100, self.trigger_version_update)
                        
        except Exception as e:
            print(f"Error scanning build folders: {e}")
            import traceback
            traceback.print_exc()
        
        # Store builds for later reference
        self.available_release_builds = release_builds
        self.available_nightly_bridge_builds = nightly_bridge_builds
        self.available_nightly_runtime_builds = nightly_runtime_builds
        
        # Print counts for debugging
        print(f"Found {len(release_builds)} release builds, {len(nightly_bridge_builds)} nightly bridge builds, {len(nightly_runtime_builds)} nightly runtime builds")
        
        # Update the UI dropdowns
        self.update_rtx_remix_dropdowns()
        
    def extract_version_number(self, version_string):
        """Extract a clean version number from a version string"""
        if version_string == "N/A":
            return "N/A"
        
        # Try to extract version information
        # First, remove common prefixes
        version = version_string
        for prefix in ["dxvk-remix-", "bridge-remix-", "rtx-remix-for-x86-games-", "rtx-remix-for-x64-games-"]:
            if version.startswith(prefix):
                version = version.replace(prefix, "")
        
        # Remove build type suffixes
        for suffix in ["-release", "-debug", "-debugoptimized"]:
            if version.endswith(suffix):
                version = version.replace(suffix, "")
        
        return version
    
    def create_remix_selection_ui_if_needed(self):
        """Create the RTX Remix selection UI elements if they don't exist yet"""
        # Check if we already have the frame
        if not hasattr(self, 'rtx_remix_frame'):
            # Create a new frame for RTX Remix selection
            self.rtx_remix_frame = ttk.LabelFrame(self.button_frame, text="RTX Remix Version")
            self.rtx_remix_frame.pack(fill=tk.X, padx=5, pady=10, after=self.button_frame.winfo_children()[1])
            
            # Create the type selector
            self.remix_type_var = tk.StringVar(value="Release")
            
            ttk.Label(self.rtx_remix_frame, text="Type:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            self.remix_type_dropdown = ttk.OptionMenu(
                self.rtx_remix_frame,
                self.remix_type_var,
                "Release",
                "Release", "Nightly"
            )
            self.remix_type_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
            
            # Architecture selection for nightly builds
            self.remix_arch_frame = ttk.Frame(self.rtx_remix_frame)
            self.remix_arch_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
            
            self.remix_arch_var = tk.StringVar(value="x64")
            ttk.Label(self.remix_arch_frame, text="Architecture:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            
            arch_options = ttk.Frame(self.remix_arch_frame)
            arch_options.grid(row=0, column=1, sticky="w", padx=5, pady=5)
            
            ttk.Radiobutton(
                arch_options, 
                text="x64 (64-bit games)",
                variable=self.remix_arch_var,
                value="x64",
                command=self.update_nightly_version_dropdown
            ).pack(side=tk.LEFT, padx=(0, 15))
            
            ttk.Radiobutton(
                arch_options, 
                text="x86 (32-bit games)",
                variable=self.remix_arch_var,
                value="x86",
                command=self.update_nightly_version_dropdown
            ).pack(side=tk.LEFT)
            
            # Hide architecture selection initially (only shown for nightly builds)
            self.remix_arch_frame.grid_remove()
            
            # Create the version selector (used by both release and nightly)
            ttk.Label(self.rtx_remix_frame, text="Version:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
            self.remix_version_var = tk.StringVar()
            self.remix_version_dropdown = ttk.Combobox(
                self.rtx_remix_frame, 
                textvariable=self.remix_version_var,
                state="readonly"
            )
            self.remix_version_dropdown.bind("<<ComboboxSelected>>", self.on_version_selected)
            self.remix_version_dropdown.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
            
            # Configure column weights
            self.rtx_remix_frame.columnconfigure(1, weight=1)
            
            # Connect the type change handler to toggle visibility
            self.remix_type_var.trace_add("write", lambda *args: self.on_remix_type_changed(self.remix_type_var.get()))
    
    def on_version_selected(self, event):
        """Handle version selection and automatically set as active"""
        # Skip if events are blocked
        if hasattr(self, 'block_events') and self.block_events:
            print("Skipping version selection event - events are blocked")
            return
            
        selected_display = self.remix_version_var.get()
        
        if not selected_display or "No builds found" in selected_display:
            return
        
        print(f"Selected build from dropdown: '{selected_display}'")
        
        # Check if we're in release or nightly mode
        if self.remix_type_var.get() == "Release":
            # Find the release build
            found = False
            for item in self.available_release_displays:
                if item["display"] == selected_display:
                    found = True
                    build = item["build"]
                    selected_path = build["path"]
                    
                    # Check if version info exists
                    runtime_ver = build.get("runtime_version", "N/A")
                    bridge_ver = build.get("bridge_version", "N/A")
                    if runtime_ver == "N/A" or bridge_ver == "N/A":
                        # Prompt for version info
                        versions = {"runtime version": runtime_ver, "bridge version": bridge_ver}
                        if messagebox.askyesno("Version Information Needed", 
                                             "This build is missing complete version information.\n"
                                             "Would you like to add it now?"):
                            versions = self.show_popup_window(versions, selected_path)
                            self.save_versions_to_file(selected_path, versions)
                    
                    # Set this as the active build - this will also update version tags if needed
                    print(f"Setting active build to: {selected_path}")
                    
                    # Store current path to compare if it actually changed
                    old_path = None
                    if hasattr(self, 'active_build_path'):
                        old_path = self.active_build_path
                    
                    # Only set active build and update if it changed
                    if old_path != selected_path:
                        self.set_active_build(selected_path)
                        self.status_right.config(text=f"Active RTX-Remix build: {selected_display}")
                    else:
                        print(f"Build path unchanged, skipping update: {selected_path}")
                    
                    break
                    
            if not found:
                print(f"WARNING: Could not find selected build '{selected_display}' in available_release_displays")
        else:  # Nightly
            # Find the nightly build
            found = False
            for item in self.available_nightly_displays:
                if item["display"] == selected_display:
                    found = True
                    build = item["build"]
                    selected_path = build["path"]
                    
                    # Check if version info exists
                    runtime_ver = build.get("version", "N/A")
                    if runtime_ver == "N/A":
                        # Prompt for version info
                        versions = {"runtime version": "N/A", "bridge version": "N/A"}
                        if messagebox.askyesno("Version Information Needed", 
                                             "This build is missing version information.\n"
                                             "Would you like to add it now?"):
                            versions = self.show_popup_window(versions, selected_path)
                            self.save_versions_to_file(selected_path, versions)
                    
                    # Store current path to compare if it actually changed
                    old_path = None
                    if hasattr(self, 'active_build_path'):
                        old_path = self.active_build_path
                    
                    # Only set active build and update if it changed
                    if old_path != selected_path:
                        # Set this as the active build
                        print(f"Setting active build to: {selected_path}")
                        self.set_active_build(selected_path)
                        self.status_right.config(text=f"Active RTX-Remix build: {selected_display}")
                    else:
                        print(f"Build path unchanged, skipping update: {selected_path}")
                    
                    break
                    
            if not found:
                print(f"WARNING: Could not find selected build '{selected_display}' in available_nightly_displays")
    
    def on_nightly_selection_changed(self, event):
        """Handle nightly build selection and automatically create/set composite build if needed"""
        # Only proceed if both Bridge and Runtime are selected
        selected_bridge_display = self.nightly_bridge_var.get()
        selected_runtime_display = self.nightly_runtime_var.get()
        
        if selected_bridge_display == "No builds found" or selected_runtime_display == "No builds found":
            return
        
        # Find the bridge and runtime builds
        bridge_path = None
        runtime_path = None
        bridge_folder = None
        runtime_folder = None
        
        for item in self.available_bridge_displays:
            if item["display"] == selected_bridge_display:
                bridge_build = item["build"]
                bridge_path = bridge_build["path"]
                bridge_folder = bridge_build.get("folder", os.path.basename(bridge_path))
                break
                
        for item in self.available_runtime_displays:
            if item["display"] == selected_runtime_display:
                runtime_build = item["build"]
                runtime_path = runtime_build["path"]
                runtime_folder = runtime_build.get("folder", os.path.basename(runtime_path))
                break
        
        if not bridge_path or not runtime_path:
            return
        
        # Check if they're the same build or if we need a composite
        if bridge_path == runtime_path:
            # Same build, no need for composite
            selected_path = bridge_path
            self.set_active_build(selected_path)
            self.status_right.config(text=f"Active RTX-Remix build: {selected_bridge_display}")
        else:
            # Need to create a composite build
            composite_name = f"composite_{bridge_folder}_{runtime_folder}"
            display_name = f"Composite: {selected_bridge_display} + {selected_runtime_display}"
            composite_path = os.path.join(self.remix_folder, composite_name)
            
            # Check if this composite already exists
            if os.path.exists(composite_path):
                # Use existing composite
                self.set_active_build(composite_path)
                self.status_right.config(text=f"Active RTX-Remix build: {display_name}")
            else:
                # Create a new composite
                self.status_right.config(text=f"Creating composite build...")
                selected_path = self.create_composite_build(bridge_path, runtime_path, bridge_folder, runtime_folder)
                if selected_path:
                    self.set_active_build(selected_path)
                    self.status_right.config(text=f"Active RTX-Remix build: {display_name}")
            
    def extract_version_from_folder_name(self, folder_name):
        """Extract version number from a folder name like 'remix 1.0.0'"""
        # Try to find a version pattern like X.Y.Z or X.Y
        version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', folder_name)
        if version_match:
            return version_match.group(1)
        
        # Try more aggressively to find just numbers that might be a version
        number_match = re.search(r'(\d+(?:\.\d+)+)', folder_name)
        if number_match:
            return number_match.group(1)
        
        # If no version found, return None
        return None
            
    def set_selected_build_as_active(self):
        """Set the selected build from the dropdown as the active RTX Remix build"""
        remix_type = self.remix_type_var.get()
        
        if remix_type == "Release":
            # For release builds, just get the selected version
            selected_version = self.remix_version_var.get()
            
            if selected_version == "No builds found":
                messagebox.showerror("No Build Available", "No release builds found to select.")
                return
                
            # Find the build by its display name
            for build in self.available_release_builds:
                if build["name"] == selected_version:
                    selected_path = build["path"]
                    # Check if version info exists
                    runtime_ver = build.get("runtime_version", "N/A")
                    bridge_ver = build.get("bridge_version", "N/A")
                    if runtime_ver == "N/A" or bridge_ver == "N/A":
                        # Prompt for version info
                        versions = {"runtime version": runtime_ver, "bridge version": bridge_ver}
                        if messagebox.askyesno("Version Information Needed", 
                                             "This build is missing complete version information.\n"
                                             "Would you like to add it now?"):
                            versions = self.show_popup_window(versions, selected_path)
                            self.save_versions_to_file(selected_path, versions)
                    break
            else:
                messagebox.showerror("Build Not Found", "Selected RTX Remix release build not found")
                return
        else:
            # For nightly builds, check if we need to create a composite build
            selected_bridge = self.nightly_bridge_var.get()
            selected_runtime = self.nightly_runtime_var.get()
            
            if selected_bridge == "No builds found" or selected_runtime == "No builds found":
                messagebox.showerror("No Build Available", "One or both required nightly builds not found.")
                return
            
            # Find the bridge and runtime builds
            bridge_path = None
            runtime_path = None
            
            for build in self.available_nightly_bridge_builds:
                if build["name"] == selected_bridge:
                    bridge_path = build["path"]
                    bridge_folder = build.get("folder", os.path.basename(build["path"]))
                    bridge_version = build.get("version", "N/A")
                    if bridge_version == "N/A":
                        # Prompt for version info
                        versions = {"runtime version": "N/A", "bridge version": "N/A"}
                        if messagebox.askyesno("Bridge Version Information Needed", 
                                             f"The bridge component '{bridge_folder}' is missing version information.\n"
                                             f"Would you like to add it now?"):
                            versions = self.show_popup_window(versions, bridge_path)
                            self.save_versions_to_file(bridge_path, versions)
                            bridge_version = versions["bridge version"]
                    break
                    
            for build in self.available_nightly_runtime_builds:
                if build["name"] == selected_runtime:
                    runtime_path = build["path"]
                    runtime_folder = build.get("folder", os.path.basename(build["path"]))
                    runtime_version = build.get("version", "N/A")
                    if runtime_version == "N/A":
                        # Prompt for version info
                        versions = {"runtime version": "N/A", "bridge version": "N/A"}
                        if messagebox.askyesno("Runtime Version Information Needed", 
                                             f"The runtime component '{runtime_folder}' is missing version information.\n"
                                             f"Would you like to add it now?"):
                            versions = self.show_popup_window(versions, runtime_path)
                            self.save_versions_to_file(runtime_path, versions)
                            runtime_version = versions["runtime version"]
                    break
            
            if not bridge_path or not runtime_path:
                messagebox.showerror("Build Not Found", "Could not locate one or both of the selected builds")
                return
            
            # Check if they're the same build or if we need a composite
            if bridge_path == runtime_path:
                # Same build, no need for composite
                selected_path = bridge_path
            else:
                # Need to create a composite build
                composite_name = f"composite_{bridge_folder}_{runtime_folder}"
                composite_path = os.path.join(self.remix_folder, composite_name)
                
                # Check if this composite already exists
                if os.path.exists(composite_path):
                    # Ask if user wants to use existing or recreate
                    if messagebox.askyesno("Composite Exists", 
                                         f"A composite build of these components already exists.\n\n"
                                         f"Do you want to use the existing composite?"):
                        selected_path = composite_path
                    else:
                        # Recreate the composite
                        selected_path = self.create_composite_build(bridge_path, runtime_path, 
                                                                  bridge_folder, runtime_folder)
                else:
                    # Create a new composite
                    selected_path = self.create_composite_build(bridge_path, runtime_path, 
                                                              bridge_folder, runtime_folder)
        
        # Set the selected build as active
        if selected_path:
            # Update the active RTX-Remix build (not the main folder)
            self.set_active_build(selected_path)
            
            # Notify the user
            messagebox.showinfo("Build Activated", 
                              f"Set {os.path.basename(selected_path)} as the active RTX-Remix build.")
                              
    def create_composite_build(self, bridge_path, runtime_path, bridge_folder, runtime_folder):
        """Create a composite build from separate bridge and runtime components"""
        # Create a composite name
        composite_name = f"composite_{bridge_folder}_{runtime_folder}"
        composite_path = os.path.join(self.remix_folder, composite_name)
        
        try:
            # Create the directory
            os.makedirs(composite_path, exist_ok=True)
            
            # Create progress dialog
            progress_window = self.create_progress_dialog(
                "Creating Composite Build",
                f"Creating composite build from {bridge_folder} and {runtime_folder}..."
            )
            progress_bar = progress_window.nametowidget("progress")
            status_label = progress_window.nametowidget("status")
            
            # List of all operations to perform
            operations = []
            
            # First, add files from bridge folder
            for item in os.listdir(bridge_path):
                if item != '.trex':  # Don't copy runtime folder from bridge
                    src = os.path.join(bridge_path, item)
                    dst = os.path.join(composite_path, item)
                    operations.append((src, dst, os.path.isdir(src)))
            
            # Then add .trex folder from runtime
            trex_src = os.path.join(runtime_path, '.trex')
            if os.path.exists(trex_src) and os.path.isdir(trex_src):
                trex_dst = os.path.join(composite_path, '.trex')
                operations.append((trex_src, trex_dst, True))
            
            # Configure progress
            progress_bar["maximum"] = len(operations)
            progress_bar["value"] = 0
            
            # Perform operations
            for i, (src, dst, is_dir) in enumerate(operations):
                progress_bar["value"] = i
                status_label.config(text=f"Copying {os.path.basename(src)}... ({i+1}/{len(operations)})")
                progress_window.update()
                
                if is_dir:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            
            # Create a buildname file for this composite build
            with open(os.path.join(composite_path, "build_names.txt"), "w") as f:
                # Load version information from the source folders
                bridge_versions = self.load_versions_from_file(bridge_path, False)
                runtime_versions = self.load_versions_from_file(runtime_path, False)
                
                # Use the version information if available, otherwise use folder names
                runtime_version = runtime_versions.get("runtime version", runtime_folder)
                bridge_version = bridge_versions.get("bridge version", bridge_folder)
                
                f.write(f"{runtime_version}\n")
                f.write(f"{bridge_version}\n")
                
            # Complete progress
            progress_bar["value"] = len(operations)
            status_label.config(text="Composite build created successfully!")
            progress_window.update()
            
            # Close progress window after delay
            progress_window.after(1500, progress_window.destroy)
            
            return composite_path
            
        except Exception as e:
            if 'progress_window' in locals():
                progress_window.destroy()
            messagebox.showerror("Error Creating Composite Build", f"Error: {str(e)}")
            return None
    
    def update_rtx_remix_dropdowns(self):
        """Update the dropdown menus with available builds"""
        # Only if we have the UI elements
        if not hasattr(self, 'remix_type_var') or not hasattr(self, 'remix_version_dropdown'):
            return
            
        # Get the current selection mode
        current_mode = self.remix_type_var.get()
        
        # Update based on mode
        if current_mode == "Release":
            # Update with release builds
            if hasattr(self, 'available_release_builds') and self.available_release_builds:
                # Format display names for release builds
                display_values = []
                for build in self.available_release_builds:
                    display_name = build["name"]
                    display_values.append({"display": display_name, "build": build})
                
                # Sort version numbers (higher versions first)
                display_values.sort(key=lambda x: self.sort_version_key(x["display"]), reverse=True)
                
                # Update dropdown with display values
                self.remix_version_dropdown['values'] = [item["display"] for item in display_values]
                self.available_release_displays = display_values  # Store for reference in selection handler
                
                if display_values:
                    self.remix_version_dropdown.current(0)
                    print(f"Updated release dropdown with: {len(display_values)} builds")
                else:
                    self.remix_version_dropdown['values'] = ["No builds found"]
                    self.remix_version_dropdown.current(0)
                    print("No release builds found for dropdown")
        else:  # "Nightly"
            # Update nightly builds dropdown based on selected architecture
            self.update_nightly_version_dropdown()
    
    def sort_version_key(self, version_string):
        """Create a key for sorting version strings"""
        # Extract the version number from the display string (format: "0.4.1 (release)")
        try:
            version_part = version_string.split(" (")[0]
        except:
            # If we can't split, just return a low priority for sorting
            return [0]
        
        # Split into components
        parts = version_part.split(".")
        
        # Ensure we have consistent return types - always return a list of integers
        # If a part is not a number, we'll use -1 to represent it (sorts before numbers)
        result = []
        for part in parts:
            try:
                # Try to convert to integer
                result.append(int(part))
            except ValueError:
                # If conversion fails, use a very low number to sort non-numeric parts first
                result.append(-1)
        
        # If the result is empty, return a default value
        if not result:
            return [0]
        
        return result
    
    def detect_rtx_remix_subfolders(self, main_folder):
        """Scan the main folder to find potential RTX-Remix installations in subfolders"""
        rtx_subfolders = []
        
        try:
            for subfolder_name in os.listdir(main_folder):
                subfolder_path = os.path.join(main_folder, subfolder_name)
                if os.path.isdir(subfolder_path):
                    # Check if this subfolder could be an RTX-Remix folder
                    key_files = ['d3d9.dll', 'NvRemixLauncher32.exe']
                    has_key_files = any(os.path.exists(os.path.join(subfolder_path, file)) for file in key_files)
                    has_trex_folder = os.path.exists(os.path.join(subfolder_path, '.trex'))
                    
                    if has_key_files or has_trex_folder:
                        # This subfolder is potentially an RTX-Remix installation
                        rtx_subfolders.append({
                            'name': subfolder_name,
                            'path': subfolder_path,
                            'versions': self.load_versions_from_file(subfolder_path, False)
                        })
        except Exception as e:
            print(f"Error scanning for RTX-Remix subfolders: {e}")
        
        return rtx_subfolders
    
    def configure_existing_rtx_subfolders(self, rtx_subfolders):
        """Configure existing RTX-Remix subfolders found in the main directory"""
        if not rtx_subfolders:
            return
        
        # Create a dialog to show the detected subfolders
        config_window = tk.Toplevel(self.master)
        config_window.title("Configure RTX-Remix Installations")
        config_window.configure(bg="#1a1a1a")
        config_window.grab_set()
        config_window.transient(self.master)
        
        # Center and size the window
        win_width, win_height = 700, 500
        screen_width = config_window.winfo_screenwidth()
        screen_height = config_window.winfo_screenheight()
        x = int((screen_width / 2) - (win_width / 2))
        y = int((screen_height / 2) - (win_height / 2))
        config_window.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
        # Title
        title_label = tk.Label(
            config_window,
            text="Configure RTX-Remix Installations",
            font=("Segoe UI", 16, "bold"),
            bg="#1a1a1a",
            fg="#76B900"
        )
        title_label.pack(pady=(15, 10))
        
        # Description
        desc_label = tk.Label(
            config_window,
            text="The following RTX-Remix installations were found.\nPlease configure any missing version information.",
            bg="#1a1a1a",
            fg="#e0e0e0",
            wraplength=650,
            justify=tk.CENTER
        )
        desc_label.pack(pady=(0, 15))
        
        # Create a scrollable frame for the subfolders
        frame_container = ttk.Frame(config_window)
        frame_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        canvas = tk.Canvas(frame_container, bg="#1a1a1a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_container, orient="vertical", command=canvas.yview)
        
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Keep track of which subfolders need configuration
        subfolders_to_configure = []
        
        # Add each subfolder as a section in the scrollable frame
        for i, subfolder in enumerate(rtx_subfolders):
            folder_frame = ttk.LabelFrame(
                scrollable_frame, 
                text=f"Installation {i+1}: {subfolder['name']}"
            )
            folder_frame.pack(fill=tk.X, pady=10, padx=5)
            
            # Show current path
            path_label = ttk.Label(
                folder_frame,
                text=f"Path: {subfolder['path']}",
                wraplength=600,
                style="Status.TLabel"
            )
            path_label.pack(pady=(5, 0), padx=10, anchor="w")
            
            # Show current version info
            versions = subfolder['versions']
            runtime_version = versions["runtime version"]
            bridge_version = versions["bridge version"]
            
            version_label = ttk.Label(
                folder_frame,
                text=f"Runtime: {runtime_version}\nBridge: {bridge_version}",
                wraplength=600,
                style="Status.TLabel"
            )
            version_label.pack(pady=5, padx=10, anchor="w")
            
            # Determine if configuration is needed
            needs_config = (runtime_version == "N/A" or bridge_version == "N/A")
            
            # Add to the list of subfolders that need configuration
            if needs_config:
                subfolders_to_configure.append(subfolder)
                
                status_frame = ttk.Frame(folder_frame)
                status_frame.pack(fill=tk.X, pady=5, padx=10)
                
                status_label = ttk.Label(
                    status_frame,
                    text="Status: ⚠️ Missing version information",
                    foreground="#FF9900"
                )
                status_label.pack(side=tk.LEFT)
                
                configure_button = ttk.Button(
                    status_frame,
                    text="Configure Now",
                    command=lambda sf=subfolder: self.configure_subfolder(sf, config_window)
                )
                configure_button.pack(side=tk.RIGHT)
            else:
                status_frame = ttk.Frame(folder_frame)
                status_frame.pack(fill=tk.X, pady=5, padx=10)
                
                status_label = ttk.Label(
                    status_frame,
                    text="Status: ✓ Version information complete",
                    foreground="#76B900"
                )
                status_label.pack(side=tk.LEFT)
                
                set_current_button = ttk.Button(
                    status_frame,
                    text="Set as Current",
                    command=lambda sf=subfolder: self.set_current_build(sf, config_window)
                )
                set_current_button.pack(side=tk.RIGHT)
        
        # Add buttons at the bottom
        button_frame = ttk.Frame(config_window)
        button_frame.pack(fill=tk.X, pady=15, padx=20)
        
        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=config_window.destroy
        )
        close_button.pack(side=tk.RIGHT)
        
        # Wait for the window
        config_window.wait_window()
    
    def configure_subfolder(self, subfolder, parent_window):
        """Configure a subfolder's version information"""
        # Hide parent window temporarily
        parent_window.withdraw()
        
        # Show the popup window to configure build information
        folder_path = subfolder['path']
        versions = self.show_popup_window(subfolder['versions'], folder_path)
        
        # Update the subfolder dictionary
        subfolder['versions'] = versions
        
        # Update the UI in the parent window
        parent_window.deiconify()
        
        # Refresh the dialog (simplest is to close and reopen)
        parent_window.destroy()
        rtx_subfolders = self.detect_rtx_remix_subfolders(self.remix_folder)
        self.configure_existing_rtx_subfolders(rtx_subfolders)
    
    def set_current_build(self, subfolder, parent_window):
        """Set the selected build as the current RTX-Remix folder"""
        folder_path = subfolder['path']
        
        # Set as current folder
        self.remix_folder = folder_path.replace("/", "\\")
        self.source_versions = subfolder['versions']
        version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
        self.version_label.config(text=version_info)
        self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
        
        # Re-check version compatibility for all games
        for item in self.tree.get_children():
            destination_folder = self.tree.item(item, "values")[2]
            destination_versions = self.load_versions_from_file(destination_folder)
            self.check_version_and_tag(item, destination_versions)
        
        # Save the configuration
        self.save_config()
        self.update_copy_button_state()
        
        # Close parent window
        parent_window.destroy()
        
        # Success message
        messagebox.showinfo("Success", 
                          f"Set '{subfolder['name']}' as the active RTX-Remix folder.\n\n"
                          f"You can now add games and apply RTX-Remix to them.")

    def select_destination(self):
        """Select a game folder to add to the list"""
        folder_path = filedialog.askdirectory(title="Select Game Folder")
        if not folder_path:
            self.status_right.config(text="Folder selection was cancelled.")
            return
            
        # Check for .exe files
        exe_files = [f for f in os.listdir(folder_path) if f.endswith('.exe')]
        if not exe_files:
            messagebox.showinfo("No Executable Found", "No executable game file found in the selected folder.")
            return
    
        # Get game name from dialog
        dialog = CustomGameNameDialog(self.master, "Game Name", folder_path)
        game_name = dialog.result
        if not game_name:
            self.status_right.config(text="Game name entry was cancelled.")
            return
            
        # Add to treeview
        destination_versions = self.load_versions_from_file(folder_path)
        tree_item = self.tree.insert("", 'end', values=(
            "🔓", game_name, folder_path, 'Yes', 'Yes',  
            destination_versions["runtime version"], destination_versions["bridge version"]
        ))
        self.check_version_and_tag(tree_item, destination_versions)
        self.status_right.config(text="Game added and configuration saved successfully. Ready to proceed.")
        self.save_config()
        self.update_copy_button_state()
        
    def show_popup_window(self, versions, directory):
        """Show a popup window to input version information with advanced options"""
        # Create the popup window
        popup_window = tk.Toplevel(self.master)
        popup_window.title("RTX Remix Version Input")
        popup_window.configure(bg="#1a1a1a")
    
        # Position the popup window centered on the main window
        win_width, win_height = 500, 550  # Increased height
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (win_width // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (win_height // 2)
        popup_window.geometry(f"{win_width}x{win_height}+{x}+{y}")
    
        # Validation function for input
        def validate_input(text):
            allowed_chars = set(string.digits + string.ascii_letters + ".-_")
            return all(char in allowed_chars for char in text)
    
        # Title and description
        title_label = tk.Label(
            popup_window, 
            text="RTX Remix Build Configuration",
            bg="#1a1a1a", 
            fg="#76B900",
            font=("Segoe UI", 12, "bold"),
            justify="center"
        )
        title_label.grid(row=0, column=0, columnspan=3, padx=10, pady=(15,5))
        
        # Extract the directory name for better context
        folder_name = os.path.basename(directory)
        
        description = tk.Label(
            popup_window, 
            text=f"Configure version information for: {folder_name}",
            bg="#1a1a1a", 
            fg="#e0e0e0", 
            justify="center",
            wraplength=400
        )
        description.grid(row=1, column=0, columnspan=3, padx=10, pady=(0,15))
    
        # Format selection
        format_label = tk.Label(
            popup_window,
            text="Build Format:",
            bg="#1a1a1a",
            fg="#e0e0e0"
        )
        format_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        # Set default format based on detected version strings
        default_format = "old"
        if versions["runtime version"] != "N/A" and ("rtx-remix-for-" in versions["runtime version"]):
            default_format = "new"
        
        format_var = tk.StringVar(value=default_format)
        old_format_rb = ttk.Radiobutton(
            popup_window,
            text="Separate Builds (Pre-1.0)",
            variable=format_var,
            value="old"
        )
        new_format_rb = ttk.Radiobutton(
            popup_window,
            text="Merged Build (1.0+)",
            variable=format_var,
            value="new"
        )
        old_format_rb.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        new_format_rb.grid(row=2, column=2, padx=10, pady=10, sticky="w")
    
        # Version number inputs
        version_frame = ttk.LabelFrame(popup_window, text="Version Information", padding=(10, 5))
        version_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        popup_window.grid_columnconfigure(0, weight=1)
        
        # Old format frame
        old_format_frame = ttk.Frame(version_frame)
        old_format_frame.grid(row=0, column=0, sticky="ew")
        old_format_frame.grid_columnconfigure(1, weight=1)
        
        # Extract version from folder name if possible
        folder_version = self.extract_version_from_folder_name(folder_name) or ""
        
        # For old format, separate entry fields for runtime and bridge
        # Runtime version (old format)
        runtime_label_old = tk.Label(old_format_frame, text="Runtime Version:", bg="#1a1a1a", fg="#e0e0e0")
        runtime_entry_old = ttk.Entry(old_format_frame, validate="key", 
                                  validatecommand=(popup_window.register(validate_input), "%S"))
        runtime_label_old.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        runtime_entry_old.grid(row=0, column=1, padx=10, pady=5, sticky="we")
        
        # Set default runtime version if available
        if versions["runtime version"] != "N/A":
            # Use existing value if it exists
            runtime_entry_old.insert(0, versions["runtime version"].replace("dxvk-remix-", ""))
        elif folder_version:
            # Otherwise use the extracted folder version if available
            runtime_entry_old.insert(0, folder_version)
        
        # Runtime hint
        runtime_hint = tk.Label(
            old_format_frame,
            text=f"Example: {folder_version or '0.5.4'}",
            bg="#1a1a1a",
            fg="#a0a0a0",
            font=("Segoe UI", 8)
        )
        runtime_hint.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        
        # Bridge version (old format)
        bridge_label_old = tk.Label(old_format_frame, text="Bridge Version:", bg="#1a1a1a", fg="#e0e0e0")
        bridge_entry_old = ttk.Entry(old_format_frame, validate="key", 
                                validatecommand=(popup_window.register(validate_input), "%S"))
        bridge_label_old.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        bridge_entry_old.grid(row=1, column=1, padx=10, pady=5, sticky="we")
        
        # Set default bridge version if available
        if versions["bridge version"] != "N/A":
            # Use existing value if it exists
            bridge_entry_old.insert(0, versions["bridge version"].replace("bridge-remix-", ""))
        elif folder_version:
            # Otherwise use the extracted folder version if available
            bridge_entry_old.insert(0, folder_version)
        
        # Bridge hint
        bridge_hint = tk.Label(
            old_format_frame,
            text=f"Example: {folder_version or '0.5.4'}",
            bg="#1a1a1a",
            fg="#a0a0a0",
            font=("Segoe UI", 8)
        )
        bridge_hint.grid(row=1, column=2, padx=10, pady=5, sticky="w")
        
        # New format frame
        new_format_frame = ttk.Frame(version_frame)
        new_format_frame.grid(row=1, column=0, sticky="ew")
        new_format_frame.grid_columnconfigure(1, weight=1)
        
        # Version identifier (new format)
        version_label = tk.Label(new_format_frame, text="Version ID:", bg="#1a1a1a", fg="#e0e0e0")
        version_entry = ttk.Entry(new_format_frame, validate="key", 
                              validatecommand=(popup_window.register(validate_input), "%S"))
        version_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        version_entry.grid(row=0, column=1, padx=10, pady=5, sticky="we")
        
        # Set default version ID if available
        if versions["runtime version"] != "N/A" and "rtx-remix-for-" in versions["runtime version"]:
            # Extract version ID from existing value
            version_match = re.search(r'rtx-remix-for-\w+-games-(.+)', versions["runtime version"])
            if version_match:
                version_entry.insert(0, version_match.group(1))
        elif folder_version:
            # Otherwise use the extracted folder version if available
            version_entry.insert(0, folder_version)
        
        # Version hint
        version_hint = tk.Label(
            new_format_frame,
            text=f"Use {folder_version or '1.0.0'} or commit hash (a123b456)",
            bg="#1a1a1a",
            fg="#a0a0a0",
            font=("Segoe UI", 8)
        )
        version_hint.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        
        version_frame.grid_columnconfigure(0, weight=1)
    
        # Architecture selection (for new format only)
        arch_frame = ttk.LabelFrame(popup_window, text="Architecture (1.0+ only)", padding=(10, 5))
        
        arch_var = tk.StringVar(value="x86")
        x86_rb = ttk.Radiobutton(
            arch_frame,
            text="x86 (32-bit games)",
            variable=arch_var,
            value="x86"
        )
        x64_rb = ttk.Radiobutton(
            arch_frame,
            text="x64 (64-bit games)",
            variable=arch_var,
            value="x64"
        )
        x86_rb.grid(row=0, column=0, padx=20, pady=5, sticky="w")
        x64_rb.grid(row=0, column=1, padx=20, pady=5, sticky="w")
    
        # Build type selection
        build_frame = ttk.LabelFrame(popup_window, text="Build Type", padding=(10, 5))
        build_frame.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        
        # Set default build type based on folder name or existing values
        default_build_type = "release"
        if "debug" in folder_name.lower():
            default_build_type = "debug"
        elif "debugopt" in folder_name.lower():
            default_build_type = "debugoptimized"
        
        build_var = tk.StringVar(value=default_build_type)
        release_rb = ttk.Radiobutton(
            build_frame,
            text="Release",
            variable=build_var,
            value="release"
        )
        debugopt_rb = ttk.Radiobutton(
            build_frame,
            text="Debug Optimized",
            variable=build_var,
            value="debugoptimized"
        )
        debug_rb = ttk.Radiobutton(
            build_frame,
            text="Debug",
            variable=build_var,
            value="debug"
        )
        release_rb.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        debugopt_rb.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        debug_rb.grid(row=0, column=2, padx=10, pady=5, sticky="w")
    
        # Example output
        example_frame = ttk.LabelFrame(popup_window, text="Build Name Preview", padding=(10, 5))
        example_frame.grid(row=6, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        
        example_output = tk.Label(
            example_frame,
            text="dxvk-remix-[version]-release\nbridge-remix-[version]-release",
            bg="#1a1a1a",
            fg="#76B900",
            font=("Consolas", 9),
            wraplength=470,
            justify="left",
            height=3  # Fixed height to accommodate both formats
        )
        example_output.pack(padx=5, pady=5, anchor="w")
    
        # Buttons
        button_frame = ttk.Frame(popup_window)
        button_frame.grid(row=7, column=0, columnspan=3, padx=10, pady=10)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=popup_window.destroy)
        submit_button = ttk.Button(button_frame, text="Submit", command=lambda: submit())
        
        cancel_button.grid(row=0, column=0, padx=10, pady=10)
        submit_button.grid(row=0, column=1, padx=10, pady=10)
    
        # Update UI based on format selection
        def update_ui(*args):
            is_old_format = format_var.get() == "old"
            global oldVersion
            oldVersion = is_old_format
            
            # Show/hide appropriate frames
            if is_old_format:
                old_format_frame.grid(row=0, column=0, sticky="ew")
                new_format_frame.grid_forget()
                
                # Hide architecture frame for old format
                arch_frame.grid_forget()
            else:
                old_format_frame.grid_forget()
                new_format_frame.grid(row=0, column=0, sticky="ew")
                
                # Show architecture frame for new format
                arch_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
            
            update_example()
            check_submit_button()
    
        # Update example text
        def update_example(*args):
            build_type = build_var.get()
            
            if format_var.get() == "old":
                # For old format, show both runtime and bridge
                runtime_text = runtime_entry_old.get().strip() or "[version]"
                bridge_text = bridge_entry_old.get().strip() or "[version]"
                
                # If the version doesn't include the build type, add it
                if "-" not in runtime_text:
                    runtime_with_build = f"{runtime_text}-{build_type}"
                else:
                    runtime_with_build = runtime_text
                    
                if "-" not in bridge_text:
                    bridge_with_build = f"{bridge_text}-{build_type}"
                else:
                    bridge_with_build = bridge_text
                    
                example = f"dxvk-remix-{runtime_with_build}\nbridge-remix-{bridge_with_build}"
            else:
                # For new format, show version ID
                arch = arch_var.get()
                version_id = version_entry.get().strip() or "[version]"
                
                example = f"rtx-remix-for-{arch}-games-{version_id}-{build_type}"
                
            example_output.config(text=example)
    
        # Enable/disable submit button
        def check_submit_button(*args):
            if format_var.get() == "old":
                runtime = runtime_entry_old.get().strip()
                bridge = bridge_entry_old.get().strip()
                
                if runtime and bridge:
                    submit_button.state(["!disabled"])
                else:
                    submit_button.state(["disabled"])
            else:
                version_id = version_entry.get().strip()
                
                if version_id:
                    submit_button.state(["!disabled"])
                else:
                    submit_button.state(["disabled"])
    
        # Submit function
        def submit():
            build_type = build_var.get()
            
            if format_var.get() == "old":
                # For old format, use the version entries
                runtime_version = runtime_entry_old.get().strip()
                bridge_version = bridge_entry_old.get().strip()
                
                # Add build type if not present
                if "-" not in runtime_version:
                    runtime_version = f"{runtime_version}-{build_type}"
                if "-" not in bridge_version:
                    bridge_version = f"{bridge_version}-{build_type}"
                    
                # Store the version identifiers
                versions["runtime version"] = runtime_version
                versions["bridge version"] = bridge_version
            else:
                # For new format, use version ID
                version_id = version_entry.get().strip()
                
                # Create the version string in the exact format requested
                version_string = f"{version_id}-{build_type}"
                
                # Store both versions as the same value for consistency
                versions["runtime version"] = version_string
                versions["bridge version"] = version_string
                versions["architecture"] = arch_var.get()
            
            # Set the global format flag
            global oldVersion
            oldVersion = (format_var.get() == "old")
            
            # Create the appropriate build file
            self.save_versions_to_file(directory, versions)
            popup_window.destroy()
    
        # Connect all events
        format_var.trace_add("write", update_ui)
        runtime_entry_old.bind("<KeyRelease>", lambda e: (update_example(), check_submit_button()))
        bridge_entry_old.bind("<KeyRelease>", lambda e: (update_example(), check_submit_button()))
        version_entry.bind("<KeyRelease>", lambda e: (update_example(), check_submit_button()))
        build_var.trace_add("write", update_example)
        arch_var.trace_add("write", update_example)
        
        # Initialize UI state
        update_ui()
        check_submit_button()
        
        # Make the dialog modal
        popup_window.grab_set()
        popup_window.wait_window()
    
        return versions
            
    def load_versions_from_file(self, directory, isSource=False):
        """Load version information from any of the version file formats"""
        versions = {"runtime version": "N/A", "bridge version": "N/A"}
        
        # First check for detailed buildname.txt (preferred)
        buildname_file = os.path.join(directory, "buildname.txt")
        if os.path.exists(buildname_file):
            try:
                with open(buildname_file, 'r') as file:
                    content = file.read()
                    
                    # Extract commit hash directly - this is the most important information
                    commit_hash_match = re.search(r'Commit Hash:\s*([0-9a-f]+)', content)
                    if commit_hash_match:
                        commit_hash = commit_hash_match.group(1).strip()
                        # Use the commit hash for both runtime and bridge versions
                        versions["runtime version"] = commit_hash
                        versions["bridge version"] = commit_hash
                        return versions
                    
                    # If no commit hash found, extract versions from the detailed format
                    if "Repository: rtx-remix" in content or "Repository: dxvk-remix" in content:
                        # Extract version information from detailed buildname.txt
                        release_version_match = re.search(r'Release Version:\s*(.+)', content)
                        build_type_match = re.search(r'Build Type:\s*(.+)', content)
                        full_version_match = re.search(r'Full Version:\s*(.+)', content)
                        
                        # If we have "Full Version" line, use that directly
                        if full_version_match:
                            version_str = full_version_match.group(1).strip()
                            versions["runtime version"] = version_str
                            versions["bridge version"] = version_str
                            return versions
                        
                        # Otherwise, build from components if available
                        if release_version_match and build_type_match:
                            version = release_version_match.group(1).strip()
                            build_type = build_type_match.group(1).strip()
                            version_str = f"{version}-{build_type}"
                            
                            # Set both versions to the same value
                            versions["runtime version"] = version_str
                            versions["bridge version"] = version_str
                            return versions
                    
                    # Fallback for other formats in buildname.txt
                    lines = content.strip().split('\n')
                    if lines:
                        if len(lines) >= 2:
                            versions["runtime version"] = lines[0].strip()
                            versions["bridge version"] = lines[1].strip()
                        else:
                            # Single line, use for both
                            versions["runtime version"] = lines[0].strip()
                            versions["bridge version"] = lines[0].strip()
                        return versions
            except Exception as e:
                print(f"Error reading buildname.txt: {e}")
        
        # Then try traditional build_names.txt or build-names.txt
        global oldVersion
        
        # Check build-names.txt (dash format)
        build_names_dash = os.path.join(directory, "build-names.txt")
        if os.path.exists(build_names_dash):
            oldVersion = False
            try:
                with open(build_names_dash, 'r') as file:
                    lines = file.readlines()
                    
                    # Make sure we have at least one line
                    if lines:
                        # If we have at least two lines, it's likely the old format with separate entries
                        if len(lines) >= 2:
                            runtime_line = lines[0].strip()
                            bridge_line = lines[1].strip()
                            
                            # Store the complete lines
                            versions["runtime version"] = runtime_line
                            versions["bridge version"] = bridge_line
                        # If we have only one line, check if it's an old or new format
                        elif "dxvk-remix" in lines[0] or "bridge-remix" in lines[0]:
                            # Old format with only one component specified
                            line = lines[0].strip()
                            if "dxvk-remix" in line:
                                versions["runtime version"] = line
                                versions["bridge version"] = line  # Use same for both if only one specified
                            elif "bridge-remix" in line:
                                versions["bridge version"] = line
                                versions["runtime version"] = line  # Use same for both if only one specified
                        # Otherwise assume it's the new format (rtx-remix-for-x86-games)
                        else:
                            single_line = lines[0].strip()
                            versions["runtime version"] = single_line
                            versions["bridge version"] = single_line
                        
                        return versions
            except Exception as e:
                print(f"Error reading build-names.txt: {e}")
        
        # Check build_names.txt (underscore format)
        build_names_under = os.path.join(directory, "build_names.txt")
        if os.path.exists(build_names_under):
            oldVersion = True
            try:
                with open(build_names_under, 'r') as file:
                    lines = file.readlines()
                    
                    # Make sure we have at least one line
                    if lines:
                        # If we have at least two lines, it's likely the old format with separate entries
                        if len(lines) >= 2:
                            runtime_line = lines[0].strip()
                            bridge_line = lines[1].strip()
                            
                            # Store the complete lines
                            versions["runtime version"] = runtime_line
                            versions["bridge version"] = bridge_line
                        # If we have only one line, check if it's an old or new format
                        elif "dxvk-remix" in lines[0] or "bridge-remix" in lines[0]:
                            # Old format with only one component specified
                            line = lines[0].strip()
                            if "dxvk-remix" in line:
                                versions["runtime version"] = line
                                versions["bridge version"] = line  # Use same for both if only one specified
                            elif "bridge-remix" in line:
                                versions["bridge version"] = line
                                versions["runtime version"] = line  # Use same for both if only one specified
                        # Otherwise assume it's the new format (rtx-remix-for-x86-games)
                        else:
                            single_line = lines[0].strip()
                            versions["runtime version"] = single_line
                            versions["bridge version"] = single_line
                        
                        return versions
            except Exception as e:
                print(f"Error reading build_names.txt: {e}")
                        
        # If no version info found and it's a source directory, prompt for values
        if isSource and versions["runtime version"] == "N/A" and versions["bridge version"] == "N/A":
            if not firstLaunch:
                return self.show_popup_window(versions, directory)
                        
        return versions
    
    def save_versions_to_file(self, directory, versions):
        """Save version information to build file in the specified directory"""
        try:
            # Create or update the appropriate build file
            global oldVersion
            build_file = "build_names.txt" if oldVersion else "build-names.txt"
            build_file_path = os.path.join(directory, build_file)
            
            with open(build_file_path, 'w') as f:
                runtime_version = versions['runtime version']
                bridge_version = versions['bridge version']
                
                if oldVersion:
                    # Old format with separate lines and full component names
                    f.write(f"dxvk-remix-{runtime_version}\n")
                    f.write(f"bridge-remix-{bridge_version}\n")
                else:
                    # New format with single line
                    architecture = versions.get('architecture', 'x86')
                    f.write(f"rtx-remix-for-{architecture}-games-{runtime_version}\n")
            
            return True
        except Exception as e:
            print(f"Error saving version file: {e}")
            return False
                
    def check_version_and_tag(self, tree_item_id, destination_versions):
        """Check if versions match with active build and apply appropriate tags"""
        # Make sure we have source versions to compare against
        if not hasattr(self, 'source_versions'):
            # We need source versions to compare against
            if hasattr(self, 'active_build_path'):
                # If we have an active build path but no source_versions, load them
                self.source_versions = self.load_versions_from_file(self.active_build_path, True)
            else:
                # Without active_build_path, we can't do a comparison
                return
        
        # Get current values from tree
        current_values = list(self.tree.item(tree_item_id, 'values'))
        
        # Make sure the lock status is preserved
        is_locked = current_values[0] == "🔒"
        
        # Extract commit hash from version strings for cleaner display
        runtime_version = destination_versions["runtime version"]
        bridge_version = destination_versions["bridge version"]
        
        # Update with simplified display (just the commit hash) for the tree view
        runtime_display = self.simplify_version_display(runtime_version)
        bridge_display = self.simplify_version_display(bridge_version)
        
        # Update version information with simplified display - adjusted for new column structure
        current_values[5] = runtime_display  # Now at index 5 instead of 7
        current_values[6] = bridge_display   # Now at index 6 instead of 8
        
        # Update the tree item values
        self.tree.item(tree_item_id, values=current_values)
        
        # Handle locked entries
        if is_locked:
            self.tree.item(tree_item_id, tags=("disable",))
            return
        
        # Apply version match/mismatch tag - use FULL versions for comparison
        try:
            # For comparison, use the full version strings, not the simplified display
            if (destination_versions["runtime version"] != self.source_versions["runtime version"] or 
                destination_versions["bridge version"] != self.source_versions["bridge version"]):
                # Version mismatch
                self.tree.item(tree_item_id, tags=("version_mismatch",))
            else:
                # Version match
                self.tree.item(tree_item_id, tags=("version_match",))
        except Exception as e:
            print(f"Error comparing versions: {e}")
            # Remove any tags if there's an error in comparison
            self.tree.item(tree_item_id, tags=())
                
    def simplify_version_display(self, version_string):
        """Extract a clean commit hash or simple version identifier from a version string"""
        if version_string == "N/A":
            return "N/A"
        
        # Check for commit hash pattern (7+ hex characters)
        commit_hash_match = re.search(r'([0-9a-f]{7,40})', version_string)
        if commit_hash_match:
            return commit_hash_match.group(1)[:8]  # Just show first 8 chars of commit hash
        
        # Check for version number pattern (e.g., 1.0.0)
        version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_string)
        if version_match:
            return version_match.group(1)  # Show clean version number
        
        # If all else fails, get the last part of any dashed string
        if '-' in version_string:
            parts = version_string.split('-')
            return parts[-1]  # Return the last part
        
        # Otherwise return the original but truncated if too long
        if len(version_string) > 10:
            return version_string[:10] + "..."
        return version_string

    def determine_files_to_copy(self, bridge, runtime, source_folder):
        """Determine which files need to be copied based on selected options"""
        files_to_copy = []
        
        # Debug information
        print(f"Scanning source folder for files: {source_folder}")
        
        try:
            items = os.listdir(source_folder)
        except OSError as e:
            self.status_right.config(text=f"Error reading directory {source_folder}: {e}")
            return files_to_copy
    
        # Bridge files (base files except .trex)
        if bridge:
            for file in items:
                if file != '.trex' and not file.startswith('.'):
                    files_to_copy.append(os.path.join(source_folder, file))
    
        # Runtime (.trex directory)
        if runtime and '.trex' in items:
            trex_path = os.path.join(source_folder, '.trex')
            if os.path.isdir(trex_path):
                files_to_copy.append(trex_path)
            else:
                self.status_right.config(text='.trex is not a directory or does not exist')
    
        return files_to_copy

    def copy_files(self):
        """Copy selected files to game directories"""
        global oldVersion
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_right.config(text="No Game is selected for copy.")
            return
        
        # Explicitly get the active build path from the dropdown selection
        if hasattr(self, 'remix_version_var') and self.remix_version_var.get():
            # Try to get the build path from the current dropdown selection
            selected_display = self.remix_version_var.get()
            
            # Skip if it's a "No builds found" message
            if "No builds found" not in selected_display:
                if self.remix_type_var.get() == "Release" and hasattr(self, 'available_release_displays'):
                    for item in self.available_release_displays:
                        if item["display"] == selected_display:
                            self.active_build_path = item["build"]["path"]
                            self.source_versions = self.load_versions_from_file(self.active_build_path, True)
                            print(f"Updated active_build_path from release dropdown: {self.active_build_path}")
                            break
                elif self.remix_type_var.get() == "Nightly" and hasattr(self, 'available_nightly_displays'):
                    for item in self.available_nightly_displays:
                        if item["display"] == selected_display:
                            self.active_build_path = item["build"]["path"]
                            self.source_versions = self.load_versions_from_file(self.active_build_path, True)
                            print(f"Updated active_build_path from nightly dropdown: {self.active_build_path}")
                            break
        
        # Verify we have a valid active_build_path
        if not hasattr(self, 'active_build_path') or not self.active_build_path or not os.path.exists(self.active_build_path):
            messagebox.showerror(
                "No RTX-Remix Build Selected",
                "Please select an RTX-Remix build first.\n\n"
                "You can:\n"
                "• Download RTX-Remix using the 'Download RTX-Remix' button\n"
                "• Select a build from the dropdown if you already have builds available"
            )
            self.status_right.config(text="Copy operation cancelled: No RTX-Remix build selected.")
            return
        
        # Check if the selected build is a valid RTX-Remix build
        if not self.is_rtx_remix_folder(self.active_build_path):
            messagebox.showerror(
                "Invalid RTX-Remix Build",
                f"The selected build does not appear to be a valid RTX-Remix installation:\n\n"
                f"{self.active_build_path}\n\n"
                "Please select a different build."
            )
            self.status_right.config(text="Copy operation cancelled: Invalid RTX-Remix build.")
            return
        
        # Use the validated active_build_path as source folder
        source_folder = self.active_build_path
        print(f"Using source folder for copy: {source_folder}")
        
        # Calculate total files across all games first
        total_files_count = 0
        game_file_counts = {}
        
        for item in selected_items:
            details = self.tree.item(item, 'values')
            # Updated unpacking to match the new column structure
            lock, game_name, folder_path, bridge, runtime, _, _ = details
            
            # Convert 'Yes'/'No' to boolean
            bridge = bridge == 'Yes'
            runtime = runtime == 'Yes'
            
            # Determine files to copy using the source_folder we identified
            files_to_copy = []
            
            try:
                items = os.listdir(source_folder)
                
                # Bridge files (excluding .trex folder)
                if bridge:
                    for file in items:
                        if file != '.trex' and not file.startswith('.'):
                            files_to_copy.append(os.path.join(source_folder, file))
                
                # Runtime (.trex directory)
                if runtime and '.trex' in items:
                    trex_path = os.path.join(source_folder, '.trex')
                    if os.path.isdir(trex_path):
                        files_to_copy.append(trex_path)
                    else:
                        self.status_right.config(text='.trex is not a directory or does not exist')
                
            except OSError as e:
                self.status_right.config(text=f"Error reading directory {source_folder}: {e}")
                return
            
            # Count files including those in directories
            file_count = 0
            for source in files_to_copy:
                if os.path.isdir(source):
                    for _, _, filenames in os.walk(source):
                        file_count += len(filenames)
                else:
                    file_count += 1
            
            game_file_counts[item] = file_count
            total_files_count += file_count
        
        # Check if we have any files to copy
        if total_files_count == 0:
            messagebox.showwarning(
                "No Files to Copy",
                "No files were found to copy based on your selections.\n\n"
                "Make sure you have selected the correct RTX-Remix build and have enabled the components you want to copy."
            )
            self.status_right.config(text="Copy operation cancelled: No files to copy.")
            return
        
        # Confirm the operation with the user
        if not messagebox.askyesno(
            "Confirm Copy Operation",
            f"This will copy RTX-Remix files to {len(selected_items)} selected game(s).\n\n"
            f"Source: {os.path.basename(source_folder)}\n"
            f"Total files: {total_files_count}\n\n"
            "Proceed with copy operation?"
        ):
            self.status_right.config(text="Copy operation cancelled by user.")
            return
        
        # Start the copy process in a thread
        def copy_thread():
            current_overall_count = 0
            
            for item in selected_items:
                details = self.tree.item(item, 'values')
                # Updated unpacking
                lock, game_name, folder_path, bridge, runtime, _, _ = details
                
                # Convert 'Yes'/'No' to boolean
                bridge = bridge == 'Yes'
                runtime = runtime == 'Yes'
                
                # Update status for current game
                self.master.after(0, lambda gn=game_name: 
                                  self.status_left.config(text=f"Copying files for: {gn}"))
                
                # Delete any existing dxvk-cache files in the game folder to avoid weird behavior
                try:
                    for file in os.listdir(folder_path):
                        if file.endswith('.dxvk-cache'):
                            cache_file_path = os.path.join(folder_path, file)
                            try:
                                os.remove(cache_file_path)
                                print(f"Deleted cache file: {cache_file_path}")
                            except Exception as e:
                                print(f"Error deleting cache file {cache_file_path}: {e}")
                except Exception as e:
                    print(f"Error scanning for cache files in {folder_path}: {e}")
                
                # Remove any existing version files in the main folder
                for build_file in ["build_names.txt", "build-names.txt", "buildname.txt"]:
                    build_file_path = os.path.join(folder_path, build_file)
                    if os.path.exists(build_file_path):
                        try:
                            os.remove(build_file_path)
                            print(f"Removed existing version file: {build_file_path}")
                        except Exception as e:
                            print(f"Error removing {build_file_path}: {e}")
                
                # Check for and remove any version files within the .trex folder
                trex_path = os.path.join(folder_path, ".trex")
                if os.path.exists(trex_path) and os.path.isdir(trex_path):
                    for build_file in ["build_names.txt", "build-names.txt", "buildname.txt"]:
                        trex_build_file = os.path.join(trex_path, build_file)
                        if os.path.exists(trex_build_file):
                            try:
                                os.remove(trex_build_file)
                                print(f"Removed version file from .trex folder: {trex_build_file}")
                            except Exception as e:
                                print(f"Error removing version file from .trex folder: {e}")
                
                # Re-determine files to copy using the source_folder we identified
                files_to_copy = []
                
                try:
                    items = os.listdir(source_folder)
                    
                    # Bridge files (excluding .trex folder)
                    if bridge:
                        for file in items:
                            if file != '.trex' and not file.startswith('.'):
                                files_to_copy.append(os.path.join(source_folder, file))
                    
                    # Runtime (.trex directory)
                    if runtime and '.trex' in items:
                        trex_path = os.path.join(source_folder, '.trex')
                        if os.path.isdir(trex_path):
                            files_to_copy.append(trex_path)
                    
                except OSError as e:
                    print(f"Error in thread reading directory {source_folder}: {e}")
                    continue
                
                # Process each file/directory
                for source in files_to_copy:
                    if os.path.isdir(source):
                        for dirpath, dirnames, filenames in os.walk(source):
                            for filename in filenames:
                                # Calculate relative path from source_folder, not self.remix_folder
                                rel_dir = os.path.relpath(dirpath, source_folder)
                                dest_dir = os.path.join(folder_path, rel_dir)
                                
                                # Create destination directory if it doesn't exist
                                if not os.path.exists(dest_dir):
                                    os.makedirs(dest_dir)
                                    
                                # Copy file
                                src_file = os.path.join(dirpath, filename)
                                dest_file = os.path.join(dest_dir, filename)
                                shutil.copy2(src_file, dest_file)
                                print(f"Copied directory file: {src_file} -> {dest_file}")
                                
                                # Update progress
                                current_overall_count += 1
                                percent = (current_overall_count / total_files_count) * 100
                                self.master.after(0, lambda c=current_overall_count, t=total_files_count, p=percent, gn=game_name: 
                                                 self.update_copy_progress(c, t, p, gn))
                    else:
                        # Simple file copy
                        filename = os.path.basename(source)
                        destination = os.path.join(folder_path, filename)
                        shutil.copy2(source, destination)
                        print(f"Copied file: {source} -> {destination}")
                        
                        # Update progress
                        current_overall_count += 1
                        percent = (current_overall_count / total_files_count) * 100
                        self.master.after(0, lambda c=current_overall_count, t=total_files_count, p=percent, gn=game_name: 
                                         self.update_copy_progress(c, t, p, gn))
                
                # Copy version files from source to destination
                version_file_copied = False
                for build_file in ["build-names.txt", "build_names.txt", "buildname.txt"]:
                    source_build_file = os.path.join(source_folder, build_file)
                    if os.path.exists(source_build_file):
                        # Use the same filename format when copying
                        dest_file = os.path.join(folder_path, build_file)
                        shutil.copy2(source_build_file, dest_file)
                        print(f"Copied version file: {source_build_file} -> {dest_file}")
                        version_file_copied = True
                        break
                
                # If no version file was found, create one using source_versions
                if not version_file_copied and hasattr(self, 'source_versions'):
                    # Determine which filename to use based on oldVersion
                    build_file = "build_names.txt" if oldVersion else "build-names.txt"
                    dest_file = os.path.join(folder_path, build_file)
                    
                    try:
                        with open(dest_file, 'w') as f:
                            runtime_version = self.source_versions.get('runtime version', 'N/A')
                            bridge_version = self.source_versions.get('bridge version', 'N/A')
                            
                            if oldVersion:
                                # Old format with separate lines
                                f.write(f"{runtime_version}\n")
                                f.write(f"{bridge_version}\n")
                            else:
                                # New format with single line
                                f.write(f"{runtime_version}\n")
                        
                        print(f"Created version file: {dest_file}")
                    except Exception as e:
                        print(f"Error creating version file: {e}")
                    
                # Update version information in the tree
                destination_versions = self.load_versions_from_file(folder_path)
                
                # Update the item in the tree with correct version info
                current_values = list(self.tree.item(item, 'values'))
                current_values[5] = destination_versions["runtime version"]
                current_values[6] = destination_versions["bridge version"]
                
                # This will properly update the tree with current versions
                self.master.after(0, lambda i=item, v=current_values, dv=destination_versions: 
                                self.update_item_after_copy(i, v, dv))
            
            # When all copies are done
            self.master.after(0, lambda: self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}"))
            self.master.after(0, lambda: self.status_right.config(text="Copy operation completed for all games."))
            self.master.after(0, self.clean_up_after_copy)
        
        # Start the copy thread
        copy_thread = Thread(target=copy_thread)
        copy_thread.start()
    
    def update_item_after_copy(self, item, values, destination_versions):
        """Update item in tree after copy operation is complete"""
        # Update the values in the tree item
        self.tree.item(item, values=values)
        
        # Then check version and tag it properly
        self.check_version_and_tag(item, destination_versions)

    def update_copy_progress(self, current, total, percent, game_name):
        """Update progress bar and status message during copy operation"""
        # Get the status bar progress bar - using the bottom status bar 
        # (not the download window progress bar)
        # Update status text
        self.status_right.config(text=f"Copying for {game_name}... ({current}/{total} files)")
        
        # Create a temporary progress indicator if needed
        if not hasattr(self, 'progress_indicator'):
            # Add a temporary progress bar to the status bar
            self.progress_indicator = ttk.Progressbar(
                self.status_frame, 
                orient="horizontal", 
                length=200, 
                mode="determinate"
            )
            self.progress_indicator.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)
        
        # Update the temporary progress bar
        self.progress_indicator['value'] = percent
        
    def clean_up_after_copy(self):
        """Clean up temporary UI elements after copy operation"""
        if hasattr(self, 'progress_indicator'):
            self.progress_indicator.destroy()
            delattr(self, 'progress_indicator')
    
    def update_progress(self, value, message=None):
        """Update progress bar with animation"""
        self.progress_value = max(0, min(100, value))
        
        if message:
            self.global_status.config(text=message)
        
        # Clear previous gradient
        for segment in self.gradient_segments:
            self.progress_canvas.delete(segment)
        self.gradient_segments = []
        
        # Calculate dimensions
        width = self.progress_canvas.winfo_width()
        progress_width = (width * self.progress_value) / 100
        
        # Create animated gradient effect
        if 0 < self.progress_value < 100 and width > 0:  # Ensure width is greater than 0
            segment_width = max(1, width // 6)  # Ensure segment_width is at least 1
            for i in range(7):
                x0 = i * segment_width - self.gradient_pos
                x1 = (i+1) * segment_width - self.gradient_pos
                x0 = max(0, min(x0, progress_width))
                x1 = max(0, min(x1, progress_width))
                
                if x1 > x0:  # Only draw visible segments
                    # Color interpolation
                    ratio = i / 6
                    r = int(0x00 + (0x4C - 0x00) * ratio)
                    g = int(0x78 + (0xC2 - 0x78) * ratio)
                    b = int(0xD7 + (0xFF - 0xD7) * ratio)
                    color = f'#{r:02x}{g:02x}{b:02x}'
                    
                    segment = self.progress_canvas.create_rectangle(
                        x0, 0, x1, 4,
                        fill=color,
                        outline=color
                    )
                    self.gradient_segments.append(segment)
            
            # Animate gradient - prevent division by zero
            if segment_width > 0:  # Add this check to prevent division by zero
                self.gradient_pos = (self.gradient_pos + 2) % segment_width
                self.animation_id = self.progress_canvas.after(50, lambda: self.update_progress(self.progress_value))
        else:
            # Solid color for 0% or 100%
            color = self.progress_colors['fill_start'] if self.progress_value <= 0 else self.progress_colors['fill_end']
            if width > 0:  # Ensure we have a valid width
                self.progress_canvas.create_rectangle(
                    0, 0, progress_width, 4,
                    fill=color,
                    outline=color
                )
            
            if self.animation_id:
                self.progress_canvas.after_cancel(self.animation_id)
                self.animation_id = None
            
    def remove_selected_game(self):
        """Remove selected games from the treeview"""
        for item in self.tree.selection():
            self.tree.delete(item)
        self.save_config()
        self.update_copy_button_state()
            
    def show_main_folder_setup(self):
        """Show the initial setup dialog for the main RTX-Remix folder"""
        setup_window = tk.Toplevel(self.master)
        setup_window.title("RTX-Remix Main Folder Setup")
        setup_window.configure(bg="#1a1a1a")
        setup_window.geometry("600x600")
        setup_window.transient(self.master)
        setup_window.grab_set()
        setup_window.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent closing with X button
        
        # Center the window
        window_width = 600
        window_height = 600
        screen_width = setup_window.winfo_screenwidth()
        screen_height = setup_window.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        setup_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Title
        title_label = tk.Label(
            setup_window,
            text="Welcome to lazy_RTX-Remix Companion!",
            font=("Segoe UI", 16, "bold"),
            fg="#76B900",
            bg="#1a1a1a"
        )
        title_label.pack(pady=(20, 5))
        
        subtitle_label = tk.Label(
            setup_window,
            text="First-Time Setup",
            font=("Segoe UI", 12),
            fg="#e0e0e0",
            bg="#1a1a1a"
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Explanation
        explanation = tk.Label(
            setup_window,
            text=(
                "Before we begin, you need to set up your main RTX-Remix folder.\n\n"
                "This will be the central location where all your RTX-Remix builds are stored.\n"
                "You can download or add RTX-Remix builds to this folder later."
            ),
            font=("Segoe UI", 11),
            fg="#e0e0e0",
            bg="#1a1a1a",
            wraplength=500,
            justify=tk.LEFT
        )
        explanation.pack(padx=30, pady=10, fill=tk.X)
        
        # Folder selection section
        folder_frame = ttk.LabelFrame(setup_window, text="Select Main RTX-Remix Folder")
        folder_frame.pack(fill=tk.X, padx=30, pady=10)
        
        folder_instructions = ttk.Label(
            folder_frame,
            text=(
                "Please select or create a folder for your RTX-Remix installations.\n"
                "This should be an empty folder or a folder that already contains RTX-Remix."
            ),
            wraplength=500,
            justify=tk.LEFT
        )
        folder_instructions.pack(padx=10, pady=10, anchor="w")
        
        # Folder selection controls
        folder_select_frame = ttk.Frame(folder_frame)
        folder_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        folder_var = tk.StringVar()
        
        # Try to suggest a default location
        try:
            # Check if we have the documents folder
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
                docs_path = winreg.QueryValueEx(key, 'Personal')[0]
                default_folder = os.path.join(docs_path, "RTX-Remix")
        except:
            # Fall back to a simple path
            default_folder = os.path.join(os.path.expanduser("~"), "RTX-Remix")
                
        folder_var.set(default_folder)
        
        folder_entry = ttk.Entry(folder_select_frame, textvariable=folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        def browse_folder():
            folder = filedialog.askdirectory(title="Select or Create Main RTX-Remix Folder", 
                                             initialdir=folder_var.get())
            if folder:
                folder_var.set(folder)
        
        browse_button = ttk.Button(folder_select_frame, text="Browse...", command=browse_folder)
        browse_button.pack(side=tk.RIGHT)
        
        # Next steps section
        next_steps_frame = ttk.LabelFrame(setup_window, text="Next Steps After Setup")
        next_steps_frame.pack(fill=tk.X, padx=30, pady=10)
        
        next_steps_text = ttk.Label(
            next_steps_frame,
            text=(
                "After setting up your main folder, you'll need to:\n\n"
                "1. Get RTX-Remix - either by downloading a release version or adding an existing folder\n"
                "2. Add your games to the application\n"
                "3. Apply RTX-Remix to your games\n\n"
                "Don't worry! We'll guide you through each step."
            ),
            wraplength=500,
            justify=tk.LEFT
        )
        next_steps_text.pack(padx=10, pady=10, fill=tk.X)
        
        # Action buttons
        button_frame = ttk.Frame(setup_window)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=20)
        
        def validate_and_continue():
            selected_folder = folder_var.get().strip()
            
            # Check if the folder path is empty
            if not selected_folder:
                messagebox.showerror("Error", "Please enter or select a folder path.")
                return
            
            # Create the folder if it doesn't exist
            try:
                os.makedirs(selected_folder, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder: {str(e)}")
                return
            
            # Set the folder as our main RTX-Remix folder
            self.remix_folder = selected_folder.replace("/", "\\")
            self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
            self.save_config()
            
            # Close the setup window
            setup_window.destroy()
            
            # Scan and load builds immediately
            self.status_right.config(text="Scanning for RTX-Remix builds...")
            self.master.update()  # Force UI update to show the status change
            
            # Load all builds first
            self.update_build_selection_options()
            
            # Show what to do next
            self.show_next_steps_dialog()
        
        # Continue button
        continue_btn = ttk.Button(
            button_frame,
            text="Continue",
            command=validate_and_continue
        )
        continue_btn.pack(side=tk.RIGHT, padx=30)
        
        # Exit application button (in case user doesn't want to proceed)
        exit_btn = ttk.Button(
            button_frame,
            text="Exit Application",
            command=self.master.destroy
        )
        exit_btn.pack(side=tk.LEFT, padx=30)
    
    def synchronize_source_versions_with_ui(self):
        """Ensures source versions match the currently selected build in the UI"""
        try:
            # Get the current dropdown mode and selected value
            current_mode = self.remix_type_var.get() if hasattr(self, 'remix_type_var') else "Release"
            selected_display = self.remix_version_var.get() if hasattr(self, 'remix_version_var') else None
            
            if not selected_display or "No builds found" in selected_display:
                print("No build selected in UI, cannot synchronize")
                return
                
            print(f"Synchronizing source versions with UI selection: {current_mode} - {selected_display}")
            
            # Find the build path based on the UI selection
            selected_path = None
            if current_mode == "Release" and hasattr(self, 'available_release_displays'):
                for item in self.available_release_displays:
                    if item["display"] == selected_display:
                        selected_path = item["build"]["path"]
                        break
            elif current_mode == "Nightly" and hasattr(self, 'available_nightly_displays'):
                for item in self.available_nightly_displays:
                    if item["display"] == selected_display:
                        selected_path = item["build"]["path"]
                        break
            
            if selected_path and selected_path != self.active_build_path:
                print(f"UI selection path ({selected_path}) differs from active path ({self.active_build_path})")
                print(f"Updating active_build_path to match UI selection")
                self.active_build_path = selected_path
                
                # Reload source versions from the correct path
                self.source_versions = self.load_versions_from_file(selected_path, True)
                print(f"Updated source_versions to match UI: runtime={self.source_versions['runtime version']}, bridge={self.source_versions['bridge version']}")
                
                # Update status
                runtime_ver = self.source_versions['runtime version']
                bridge_ver = self.source_versions['bridge version']
                self.status_right.config(text=f"Active build: {os.path.basename(selected_path)} | Runtime: {runtime_ver} | Bridge: {bridge_ver}")
                
                # Save to config
                self.current_build = os.path.basename(selected_path)
                self.save_config()
        except Exception as e:
            print(f"Error synchronizing source versions with UI: {str(e)}")
    
    def load_config(self):
        """Load application configuration from file"""
        needs_main_folder_setup = True  # Default to needing setup
        
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'r') as config_file:
                config = json.load(config_file)
                
                # Load RTX-Remix folder
                self.remix_folder = config.get('remix_folder')
                if self.remix_folder and os.path.exists(self.remix_folder):
                    # We have a valid main folder
                    self.remix_folder = self.remix_folder.replace('\\', '/')
                    self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
                    
                    # Reorganize the folder structure first
                    self.reorganize_builds_folder_structure()
                    
                    # Then scan for RTX-Remix builds in the reorganized structure
                    self.status_right.config(text="Scanning for RTX-Remix builds...")
                    self.master.update()  # Force UI update to show the status change
                    
                    # Immediately scan for builds
                    self.update_build_selection_options()
                    
                    # Check if there's a current build set
                    current_build = config.get('current_build')
                    if current_build:
                        # First try with the direct path
                        current_build_path = os.path.join(self.remix_folder, current_build)
                        
                        if os.path.exists(current_build_path) and self.is_rtx_remix_folder(current_build_path):
                            # Direct path exists and is a valid RTX-Remix folder
                            self.active_build_path = current_build_path
                            self.source_versions = self.load_versions_from_file(current_build_path, True)
                            print(f"Set active_build_path directly to: {self.active_build_path}")
                        else:
                            # If the direct path doesn't exist or isn't valid, search for the build
                            found = False
                            
                            # Look in release folder structure
                            release_path = os.path.join(self.remix_folder, "release")
                            if os.path.exists(release_path):
                                for build_type in ["release", "debug", "debugoptimized"]:
                                    build_type_path = os.path.join(release_path, build_type)
                                    if os.path.exists(build_type_path):
                                        # Try exact match first
                                        possible_path = os.path.join(build_type_path, current_build)
                                        if os.path.exists(possible_path) and self.is_rtx_remix_folder(possible_path):
                                            self.active_build_path = possible_path
                                            self.source_versions = self.load_versions_from_file(possible_path, True)
                                            found = True
                                            print(f"Found build in release/{build_type}: {self.active_build_path}")
                                            break
                                        
                                        # Then try partial match
                                        if not found:
                                            for folder in os.listdir(build_type_path):
                                                if current_build in folder:  # partial match
                                                    possible_path = os.path.join(build_type_path, folder)
                                                    if os.path.exists(possible_path) and self.is_rtx_remix_folder(possible_path):
                                                        self.active_build_path = possible_path
                                                        self.source_versions = self.load_versions_from_file(possible_path, True)
                                                        found = True
                                                        print(f"Found build by partial match in release/{build_type}: {self.active_build_path}")
                                                        break
                            
                            # If not found in release, look in nightly structure
                            if not found:
                                nightly_path = os.path.join(self.remix_folder, "nightly")
                                if os.path.exists(nightly_path):
                                    for component in ["dxvk", "bridge"]:
                                        component_path = os.path.join(nightly_path, component)
                                        if os.path.exists(component_path):
                                            for arch in ["x86", "x64"]:
                                                arch_path = os.path.join(component_path, arch)
                                                if os.path.exists(arch_path):
                                                    for build_type in ["release", "debug", "debugoptimized"]:
                                                        build_type_path = os.path.join(arch_path, build_type)
                                                        if os.path.exists(build_type_path):
                                                            for subfolder in os.listdir(build_type_path):
                                                                if current_build in subfolder:  # partial match
                                                                    possible_path = os.path.join(build_type_path, subfolder)
                                                                    if os.path.exists(possible_path) and self.is_rtx_remix_folder(possible_path):
                                                                        self.active_build_path = possible_path
                                                                        self.source_versions = self.load_versions_from_file(possible_path, True)
                                                                        found = True
                                                                        print(f"Found build in nightly/{component}/{arch}/{build_type}: {self.active_build_path}")
                                                                        break
                                                        if found:
                                                            break
                                                if found:
                                                    break
                                        if found:
                                            break
                            
                            # If still not found, look directly in the main folder
                            if not found:
                                for item in os.listdir(self.remix_folder):
                                    if current_build in item and item != current_build:  # partial match but not the name itself
                                        possible_path = os.path.join(self.remix_folder, item)
                                        if os.path.isdir(possible_path) and self.is_rtx_remix_folder(possible_path):
                                            self.active_build_path = possible_path
                                            self.source_versions = self.load_versions_from_file(possible_path, True)
                                            found = True
                                            print(f"Found build in main folder: {self.active_build_path}")
                                            break
                            
                            # If all else fails, use the main folder
                            if not found:
                                print(f"Could not find saved build: {current_build}, using main folder")
                                self.active_build_path = self.remix_folder
                                self.source_versions = self.load_versions_from_file(self.remix_folder, True)
                    else:
                        # No current build, use main folder
                        self.active_build_path = self.remix_folder
                        self.source_versions = self.load_versions_from_file(self.remix_folder, True)
                    
                    # Update status to show we've loaded the versions
                    runtime_ver = self.source_versions.get('runtime version', 'N/A')
                    bridge_ver = self.source_versions.get('bridge version', 'N/A')
                    self.status_right.config(text=f"Active build: {os.path.basename(self.active_build_path)} | Runtime: {runtime_ver} | Bridge: {bridge_ver}")
                    
                    # We don't need to set up the main folder
                    needs_main_folder_setup = False
                else:
                    # Path doesn't exist or is None, we need to set up the main folder
                    if self.remix_folder:
                        self.status_right.config(text=f"Warning: Saved RTX-Remix folder not found: {self.remix_folder}")
                    self.remix_folder = None
                    needs_main_folder_setup = True
                    
                # Load download destination
                self.download_destination = config.get('download_destination')
                if self.download_destination and not os.path.exists(self.download_destination):
                    self.status_right.config(text=f"Warning: Download destination not found: {self.download_destination}")
                
                # Load treeview items
                try:
                    migrated_data = []
                    for item in config.get('treeview', []):
                        # Check if the game folder exists
                        game_folder = item[2]
                        if not os.path.exists(game_folder):
                            self.status_right.config(text=f"Warning: Game folder not found: {game_folder}")
                            continue
                            
                        # Handle different column structure between versions
                        if len(item) >= 9:  # Old format with dxvk.conf and d3d8to9.dll columns
                            # Extract only the columns we need for the new format
                            lock = item[0]
                            game_name = item[1]
                            folder_path = item[2]
                            bridge = item[3]
                            runtime = item[4]
                            # Skip dxvk.conf and d3d8to9.dll
                            
                            # Load destination versions for the game
                            destination_versions = self.load_versions_from_file(folder_path)
                            
                            # Add to treeview with new format
                            newItem = self.tree.insert('', 'end', values=(
                                lock, game_name, folder_path, bridge, runtime,
                                destination_versions["runtime version"], destination_versions["bridge version"]
                            ))
                            
                            # Save for migration
                            migrated_data.append([
                                lock, game_name, folder_path, bridge, runtime,
                                destination_versions["runtime version"], destination_versions["bridge version"]
                            ])
                        else:  # New format (already compatible)
                            # Load destination versions for the game
                            destination_versions = self.load_versions_from_file(item[2])
                            
                            newItem = self.tree.insert('', 'end', values=(
                                item[0],  # lock
                                item[1],  # Game Name
                                item[2],  # Game Folder
                                item[3],  # Bridge
                                item[4],  # Runtime
                                destination_versions["runtime version"],  # Runtime Version
                                destination_versions["bridge version"]    # Bridge Version
                            ))
                        
                        # Apply tags
                        if item[0] == "🔒":
                            self.tree.item(newItem, tags=('disable',))
                        
                        # Check and apply version tags immediately for each item
                        self.check_version_and_tag(newItem, destination_versions)
                    
                    # If we migrated data, save the config to avoid future migrations
                    if migrated_data and any(len(item) >= 9 for item in config.get('treeview', [])):
                        config['treeview'] = migrated_data
                        with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                            json.dump(config, config_file, indent=4)
                        print("Config file migrated to new column structure")
                        
                except IndexError as e:
                    print(f"IndexError during config loading, likely due to column structure change: {e}")
                    # Reset silently without prompting
                    self.reset_config_keep_games_silent()
                    return
                    
                # Apply window geometry
                if 'window_geometry' in config:
                    self.master.geometry(config['window_geometry'])
                
                # Final UI updates
                self.update_copy_button_state()
                if not needs_main_folder_setup:
                    self.status_right.config(text="Configuration loaded successfully.")
                else:
                    self.status_right.config(text="RTX-Remix folder not configured. Please set up your main folder.")
                self.tree.update_idletasks()
                
                # Check RTX-Remix folder if it exists
                if not needs_main_folder_setup:
                    self.check_sources(self.remix_folder)
                    
                # Use a multi-stage approach to finalize UI updates
                if hasattr(self, 'active_build_path') and os.path.exists(self.active_build_path):
                    # Stage 1: Basic UI setup (100ms)
                    self.master.after(100, lambda: self.select_active_build_in_dropdown())
                    
                    # Stage 2: Ensure source versions are loaded (250ms)
                    def ensure_source_versions():
                        if not hasattr(self, 'source_versions') or not self.source_versions:
                            print("Loading source versions for startup...")
                            self.source_versions = self.load_versions_from_file(self.active_build_path, True)
                            print(f"Loaded source versions: runtime={self.source_versions.get('runtime version', 'N/A')}, bridge={self.source_versions.get('bridge version', 'N/A')}")
                        # Then proceed to final updates
                        self.master.after(250, lambda: self.finalize_ui_updates(force=True))
                    
                    # Schedule the second stage
                    self.master.after(250, ensure_source_versions)
                    
                    # Stage 3: Final version check (1500ms)
                    def final_version_check():
                        print("Performing final version check...")
                        
                        # First, ensure source versions match the UI selection
                        self.synchronize_source_versions_with_ui()
                        
                        # Force update all version tags one last time
                        self.update_all_version_tags(force=True)
                        
                        # Update status with final version info
                        if hasattr(self, 'source_versions') and self.source_versions:
                            runtime_ver = self.source_versions.get('runtime version', 'N/A')
                            bridge_ver = self.source_versions.get('bridge version', 'N/A')
                            self.status_right.config(text=f"Active build: {os.path.basename(self.active_build_path)} | Runtime: {runtime_ver} | Bridge: {bridge_ver}")
                    
                    # Schedule the final stage after a longer delay
                    self.master.after(1500, final_version_check)
            
        except FileNotFoundError:
            self.status_right.config(text="First time setup: Please configure your RTX-Remix folder.")
            needs_main_folder_setup = True
        except json.JSONDecodeError:
            self.status_right.config(text="Configuration file is corrupt.")
            # Reset silently without prompting
            self.reset_config_keep_games_silent()
            return
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
            self.status_right.config(text=f"Error loading configuration: {str(e)}")
            # Reset silently without prompting
            self.reset_config_keep_games_silent()
            return
        
        # If we need to set up the main folder, show the setup dialog
        if needs_main_folder_setup:
            self.master.after(500, self.show_main_folder_setup)
        else:
            # Show welcome tutorial only if we already have a main folder set up and it's first launch
            if hasattr(self, 'remix_folder') and self.remix_folder and not hasattr(self, 'first_launch_shown'):
                self.master.after(2000, self.show_welcome_tutorial)  # Show tutorial after everything else is loaded
                self.first_launch_shown = True
    
    def finalize_ui_updates(self, force=True):
        """Centralized function to finalize UI updates after loading config"""
        # Cancel any pending timer
        if hasattr(self, '_finalize_timer_id') and self._finalize_timer_id:
            self.master.after_cancel(self._finalize_timer_id)
            self._finalize_timer_id = None
        
        # First, ensure dropdown selection is correct
        self.block_events = True
        self.select_active_build_in_dropdown()
        
        # Synchronize source versions with the UI selection
        if hasattr(self, 'remix_version_var') and hasattr(self, 'remix_type_var'):
            self.synchronize_source_versions_with_ui()
        
        # Perform immediate version update with force if needed
        print("Finalizing UI updates with version tag update...")
        
        # Verify source versions are loaded
        if not hasattr(self, 'source_versions') or not self.source_versions:
            # Try to reload source versions if missing
            if hasattr(self, 'active_build_path') and os.path.exists(self.active_build_path):
                print(f"Reloading source versions from: {self.active_build_path}")
                self.source_versions = self.load_versions_from_file(self.active_build_path, True)
        
        # Force update all version tags
        self.update_all_version_tags(force=force)
        
        # Update status display
        if hasattr(self, 'source_versions') and self.source_versions:
            runtime_ver = self.source_versions.get('runtime version', 'N/A')
            bridge_ver = self.source_versions.get('bridge version', 'N/A')
            self.status_right.config(text=f"Active build: {os.path.basename(self.active_build_path)} | Runtime: {runtime_ver} | Bridge: {bridge_ver}")
        
        # Ensure UI is updated
        self.master.update_idletasks()
        
        # Unblock events with a slight delay
        self.master.after(100, self.unblock_events)
    
    def update_dropdown_selection_from_active_build(self):
        """Update the RTX Remix dropdown selection to match the active build"""
        # Only proceed if we have the UI elements and an active build path
        if not hasattr(self, 'remix_type_var') or not hasattr(self, 'remix_version_dropdown'):
            return
                
        if not hasattr(self, 'active_build_path') or not self.active_build_path:
            return
                
        print(f"Attempting to update dropdown selection to match active build: {self.active_build_path}")
        
        # Get build path normalized for comparisons
        active_build_path = self.active_build_path.replace('\\', '/')
        active_build_name = os.path.basename(active_build_path)
        
        # Make sure source_versions are loaded
        if not hasattr(self, 'source_versions') or not self.source_versions:
            self.source_versions = self.load_versions_from_file(active_build_path, True)
            print(f"Loaded source_versions in update_dropdown: {self.source_versions}")
        
        # Update all version tags first
        self.update_all_version_tags()
        
        # Check if it's in a nightly or release folder structure
        is_nightly = "nightly" in active_build_path.lower()
        
        if is_nightly:
            # Set dropdown to Nightly
            self.remix_type_var.set("Nightly")
            self.on_remix_type_changed("Nightly")  # Show architecture selection and load nightly builds
            
            # Determine architecture from path
            if "x86" in active_build_path.lower():
                self.remix_arch_var.set("x86")
            else:
                self.remix_arch_var.set("x64")
                
            # Update the nightly dropdown based on selected architecture
            self.update_nightly_version_dropdown()
            
            # Look for a matching build in the dropdown values
            if hasattr(self, 'available_nightly_displays'):
                for i, item in enumerate(self.available_nightly_displays):
                    build = item["build"]
                    build_path = build["path"].replace('\\', '/')
                    
                    if build_path == active_build_path:
                        # Found an exact match
                        self.remix_version_dropdown.current(i)
                        print(f"Selected matching nightly build in dropdown: {item['display']}")
                        # Update source_versions and version tags
                        self.source_versions = self.load_versions_from_file(active_build_path, True)
                        self.update_all_version_tags()
                        return
                    
                # If no exact match found but we have values, select the first one
                if self.remix_version_dropdown['values'] and len(self.remix_version_dropdown['values']) > 0:
                    self.remix_version_dropdown.current(0)
                    print(f"No exact match found, selected first nightly build")
                    # Force version_selected handler to run
                    self.on_version_selected(None)
        else:
            # Set dropdown to Release
            self.remix_type_var.set("Release")
            self.on_remix_type_changed("Release")  # Load release builds
            
            # Look for the matching build in the release dropdown
            if hasattr(self, 'available_release_displays'):
                for i, item in enumerate(self.available_release_displays):
                    build = item["build"]
                    build_path = build["path"].replace('\\', '/')
                    
                    if build_path == active_build_path:
                        # Found an exact match
                        self.remix_version_dropdown.current(i)
                        print(f"Selected matching release build in dropdown: {item['display']}")
                        # Update source_versions and version tags
                        self.source_versions = self.load_versions_from_file(active_build_path, True)
                        self.update_all_version_tags()
                        return
                
                # If no exact match but we have values, select the first one
                if self.remix_version_dropdown['values'] and len(self.remix_version_dropdown['values']) > 0:
                    self.remix_version_dropdown.current(0)
                    print(f"No exact match found, selected first release build")
                    # Force version_selected handler to run
                    self.on_version_selected(None)
    
    def show_next_steps_dialog(self):
        """Show a dialog with next steps after setting up the main folder"""
        next_window = tk.Toplevel(self.master)
        next_window.title("Next Steps")
        next_window.configure(bg="#1a1a1a")
        next_window.geometry("500x400")
        next_window.transient(self.master)
        next_window.grab_set()
        
        # Center the window
        window_width = 500
        window_height = 400
        screen_width = next_window.winfo_screenwidth()
        screen_height = next_window.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        next_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Question label
        tk.Label(
            next_window,
            text="What would you like to do next?",
            font=("Segoe UI", 14, "bold"),
            fg="#76B900",
            bg="#1a1a1a"
        ).pack(pady=(20, 30))
        
        # Next options with descriptions
        next_options = [
            ("Download RTX-Remix", "Download the latest stable or development version of RTX-Remix", 
             lambda: [next_window.destroy(), self.download_rtx_remix_component()]),
            
            ("Add Games", "Add game folders to apply RTX-Remix to them later", 
             lambda: [next_window.destroy(), self.select_destination()]),
            
            ("Show Full Tutorial", "View a comprehensive tutorial about using this application", 
             lambda: [next_window.destroy(), self.show_welcome_tutorial()])
        ]
        
        # Create buttons for each option
        for option, description, command in next_options:
            option_frame = ttk.Frame(next_window)
            option_frame.pack(fill=tk.X, padx=30, pady=5)
            
            ttk.Button(
                option_frame,
                text=option,
                command=command,
                width=25
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Label(
                option_frame,
                text=description,
                wraplength=250
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Skip option
        skip_frame = ttk.Frame(next_window)
        skip_frame.pack(fill=tk.X, pady=(20, 10))
        
        ttk.Button(
            skip_frame,
            text="Skip (I'll continue on my own)",
            command=next_window.destroy
        ).pack()
        
    def reset_config_keep_games(self):
        """Reset configuration but keep game directory data"""
        # Confirm with user
        if not messagebox.askyesno("Reset Configuration", 
                                 "This will reset all configuration settings except your game directories.\n\n"
                                 "Continue?"):
            return
        
        # Store existing game data
        treeview_data = self.serialize_treeview()
        
        # Reset main variables
        self.remix_folder = None
        if hasattr(self, 'active_build_path'):
            del self.active_build_path
        if hasattr(self, 'current_build'):
            del self.current_build
        if hasattr(self, 'download_destination'):
            del self.download_destination
        if hasattr(self, 'source_versions'):
            del self.source_versions
        
        # Reset UI elements
        self.status_left.config(text="RTX-Remix Folder: None")
        self.status_right.config(text="Configuration reset. Please set up your RTX-Remix folder.")
        
        # Remove build selection UI if it exists
        if hasattr(self, 'rtx_remix_frame'):
            self.rtx_remix_frame.destroy()
            del self.rtx_remix_frame
            # Remove related variables
            for attr in ['remix_type_var', 'remix_version_dropdown', 'remix_version_var', 
                        'nightly_frame', 'bridge_dropdown', 'runtime_dropdown',
                        'nightly_bridge_var', 'nightly_runtime_var']:
                if hasattr(self, attr):
                    delattr(self, attr)
        
        # Save minimal config with just game data
        config = {
            'remix_folder': None,
            'treeview': treeview_data,
            'window_geometry': self.master.geometry()
        }
        
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                json.dump(config, config_file, indent=4)
            self.status_right.config(text="Configuration reset while preserving game data.")
        except Exception as e:
            self.status_right.config(text=f"Error saving configuration: {str(e)}")
        
        # Prompt to set up RTX-Remix folder again
        self.master.after(500, self.show_main_folder_setup)
    
    def reset_config_keep_games_silent(self):
        """Reset configuration but keep game directory data without prompting"""
        # Store existing game data before clearing the tree
        game_data = []
        for item in self.tree.get_children():
            current_values = self.tree.item(item, 'values')
            # Only need lock status, game name, and path - we'll rebuild the rest
            game_data.append([current_values[0], current_values[1], current_values[2]])
        
        # Clear the tree
        self.tree.delete(*self.tree.get_children())
        
        # Reset main variables
        self.remix_folder = None
        if hasattr(self, 'active_build_path'):
            del self.active_build_path
        if hasattr(self, 'current_build'):
            del self.current_build
        if hasattr(self, 'download_destination'):
            del self.download_destination
        if hasattr(self, 'source_versions'):
            del self.source_versions
        
        # Reset UI elements
        self.status_left.config(text="RTX-Remix Folder: None")
        self.status_right.config(text="Configuration reset due to compatibility issue. Please set up your RTX-Remix folder.")
        
        # Remove build selection UI if it exists
        if hasattr(self, 'rtx_remix_frame'):
            self.rtx_remix_frame.destroy()
            del self.rtx_remix_frame
            # Remove related variables
            for attr in ['remix_type_var', 'remix_version_dropdown', 'remix_version_var', 
                        'nightly_frame', 'bridge_dropdown', 'runtime_dropdown',
                        'nightly_bridge_var', 'nightly_runtime_var']:
                if hasattr(self, attr):
                    delattr(self, attr)
        
        # Restore game data with default settings
        for game_item in game_data:
            lock_status = game_item[0]
            game_name = game_item[1]
            folder_path = game_item[2]
            
            # Check if the folder still exists
            if not os.path.exists(folder_path):
                continue
                
            # Add to treeview with default values for new format
            destination_versions = self.load_versions_from_file(folder_path)
            tree_item = self.tree.insert("", 'end', values=(
                lock_status, game_name, folder_path, 'Yes', 'Yes',
                destination_versions["runtime version"], destination_versions["bridge version"]
            ))
            
            # Apply appropriate tags
            if lock_status == "🔒":
                self.tree.item(tree_item, tags=('disable',))
        
        # Save the new config
        treeview_data = self.serialize_treeview()
        config = {
            'remix_folder': None,
            'treeview': treeview_data,
            'window_geometry': self.master.geometry()
        }
        
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                json.dump(config, config_file, indent=4)
        except Exception as e:
            self.status_right.config(text=f"Error saving configuration: {str(e)}")
        
        # Show a notification about the reset
        messagebox.showinfo(
            "Configuration Reset",
            "The application configuration has been reset due to compatibility issues with a new version.\n\n"
            "Your game list has been preserved, but you may need to reconfigure some settings."
        )
        
        # Prompt to set up RTX-Remix folder again
        self.master.after(500, self.show_main_folder_setup)
    
    def show_welcome_tutorial(self):
        """Show welcome message and introduction for first-time users"""
        welcome_window = tk.Toplevel(self.master)
        welcome_window.title("Welcome to lazy_RTX-Remix Companion")
        welcome_window.configure(bg="#1a1a1a")
        welcome_window.geometry("600x450")
        welcome_window.transient(self.master)
        welcome_window.grab_set()
        
        # Center the window on the screen
        window_width = 600
        window_height = 450
        screen_width = welcome_window.winfo_screenwidth()
        screen_height = welcome_window.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        welcome_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Welcome message
        title_label = tk.Label(
            welcome_window,
            text="Welcome to lazy_RTX-Remix Companion!",
            font=("Segoe UI", 16, "bold"),
            fg="#76B900",
            bg="#1a1a1a"
        )
        title_label.pack(pady=(20, 10))
        
        subtitle_label = tk.Label(
            welcome_window,
            text="The easiest way to manage your RTX Remix games",
            font=("Segoe UI", 12),
            fg="#e0e0e0",
            bg="#1a1a1a"
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Description
        description = tk.Label(
            welcome_window,
            text=(
                "This tool helps you manage RTX Remix for multiple games.\n\n"
                "To get started, you'll need an RTX Remix installation.\n"
                "You can download it using the Download RTX-Remix button."
            ),
            justify=tk.LEFT,
            wraplength=500,
            font=("Segoe UI", 11),
            fg="#e0e0e0",
            bg="#1a1a1a"
        )
        description.pack(pady=10, padx=30, anchor="w")
        
        # What you can do section
        features_label = tk.Label(
            welcome_window,
            text="With this tool, you can:",
            font=("Segoe UI", 11, "bold"),
            fg="#76B900",
            bg="#1a1a1a",
            justify=tk.LEFT
        )
        features_label.pack(pady=(10, 5), padx=30, anchor="w")
        
        # Feature list
        features = [
            "● Download official RTX Remix releases",
            "● Download nightly builds with latest features",
            "● Manage multiple games with RTX Remix",
            "● Copy RTX Remix files to your game folders",
            "● Track different versions across your games"
        ]
        
        for feature in features:
            feature_item = tk.Label(
                welcome_window,
                text=feature,
                font=("Segoe UI", 10),
                fg="#e0e0e0",
                bg="#1a1a1a",
                justify=tk.LEFT
            )
            feature_item.pack(pady=2, padx=50, anchor="w")
        
        # Action buttons
        button_frame = ttk.Frame(welcome_window)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=20)
        
        # Download button
        download_btn = ttk.Button(
            button_frame, 
            text="Download RTX Remix",
            command=lambda: [welcome_window.destroy(), self.download_rtx_remix_component()]
        )
        download_btn.pack(side=tk.LEFT, padx=(50, 10))
        
        # Close button
        close_btn = ttk.Button(
            button_frame, 
            text="Close",
            command=welcome_window.destroy
        )
        close_btn.pack(side=tk.RIGHT, padx=50)
        
    def show_first_launch_tutorial(self):
        """Show a step-by-step tutorial for first-time users"""
        if hasattr(self, 'remix_folder') and self.remix_folder:
            # Already have an RTX-Remix folder, no need for tutorial
            return
            
        tutorial_window = tk.Toplevel(self.master)
        tutorial_window.title("Getting Started with RTX Remix")
        tutorial_window.configure(bg="#1a1a1a")
        tutorial_window.geometry("700x500")
        tutorial_window.transient(self.master)
        tutorial_window.grab_set()
        
        # Center the window
        window_width = 700
        window_height = 500
        screen_width = tutorial_window.winfo_screenwidth()
        screen_height = tutorial_window.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        tutorial_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Title
        title_label = tk.Label(
            tutorial_window,
            text="Getting Started with RTX Remix",
            font=("Segoe UI", 16, "bold"),
            fg="#76B900",
            bg="#1a1a1a"
        )
        title_label.pack(pady=(20, 10))
        
        # Create tabs for multi-step tutorial
        notebook = ttk.Notebook(tutorial_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create the tabs
        step1_frame = ttk.Frame(notebook)
        step2_frame = ttk.Frame(notebook)
        step3_frame = ttk.Frame(notebook)
        
        notebook.add(step1_frame, text="Step 1: Get RTX Remix")
        notebook.add(step2_frame, text="Step 2: Add Games")
        notebook.add(step3_frame, text="Step 3: Apply RTX Remix")
        
        # ===== Step 1: Get RTX Remix =====
        step1_content = ttk.Frame(step1_frame)
        step1_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        ttk.Label(
            step1_content, 
            text="First, you need to get RTX Remix:",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        # Option 1: Download
        option1_frame = ttk.LabelFrame(step1_content, text="Download RTX Remix")
        option1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            option1_frame,
            text=(
                "1. Click on \"Download RTX-Remix\" button in the left panel\n"
                "2. Choose between Release (stable) or Nightly (latest features) builds\n"
                "3. Select a version and build type\n"
                "4. Click Download and wait for the process to complete"
            ),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor="w")
        
        ttk.Button(
            option1_frame,
            text="Download RTX Remix",
            command=lambda: [tutorial_window.destroy(), self.download_rtx_remix_component()]
        ).pack(padx=10, pady=(0, 10))
        
        # ===== Step 2: Add Games =====
        step2_content = ttk.Frame(step2_frame)
        step2_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        ttk.Label(
            step2_content, 
            text="Next, add games you want to enhance with RTX Remix:",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        game_add_frame = ttk.Frame(step2_content)
        game_add_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            game_add_frame,
            text=(
                "1. Click on \"Add Game Folder\" button in the left panel\n"
                "2. Browse to and select the game's main folder (must contain game .exe file)\n"
                "3. Enter or select a name for the game\n"
                "4. The game will appear in the list with default settings\n"
                "5. You can add multiple games by repeating these steps"
            ),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor="w")
        
        ttk.Label(
            game_add_frame,
            text=(
                "Game Compatibility Notes:\n"
                "• RTX Remix works with DirectX 8 and DirectX 9 games\n"
                "• Games should be 32-bit (x86) for best compatibility\n"
                "• Some games may require specific settings or tweaks"
            ),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor="w")
        
        ttk.Button(
            game_add_frame,
            text="Add Game Folder",
            command=lambda: [tutorial_window.destroy(), self.select_destination()]
        ).pack(padx=10, pady=(0, 10))
        
        # ===== Step 3: Apply RTX Remix =====
        step3_content = ttk.Frame(step3_frame)
        step3_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        ttk.Label(
            step3_content, 
            text="Finally, apply RTX Remix to your games:",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        apply_frame = ttk.Frame(step3_content)
        apply_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            apply_frame,
            text=(
                "1. In the main list, select one or more games to modify\n"
                "2. Click the column cells to customize what components to copy:\n"
                "   • Bridge: Core RTX Remix functionality (usually needed)\n"
                "   • Runtime: The .trex folder with shaders (usually needed)\n"
                "3. Click \"Copy Files\" to apply RTX Remix to selected games"
            ),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor="w")
        
        ttk.Label(
            apply_frame,
            text=(
                "Tips:\n"
                "• The 🔓/🔒 icon lets you lock games from being modified\n"
                "• Version differences are highlighted in red\n"
                "• You can select multiple games with Ctrl+click\n"
                "• Select all unlocked games with Ctrl+A"
            ),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor="w")
        
        # Bottom buttons
        button_frame = ttk.Frame(tutorial_window)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        
        ttk.Button(
            button_frame, 
            text="Close Tutorial",
            command=tutorial_window.destroy
        ).pack(side=tk.RIGHT, padx=20)
        
        # Create "Don't show again" checkbox
        show_tutorial_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            button_frame,
            text="Show this tutorial at startup",
            variable=show_tutorial_var,
            onvalue=True,
            offvalue=False,
            command=lambda: setattr(self, 'show_tutorial_at_startup', show_tutorial_var.get())
        ).pack(side=tk.LEFT, padx=20)
        
        # Set default
        self.show_tutorial_at_startup = True
            
    def save_config(self):
        """Save application configuration to file"""
        treeview_data = self.serialize_treeview()
        config = {
            'remix_folder': self.remix_folder,
            'treeview': treeview_data,
            'window_geometry': self.master.geometry()
        }
        
        # Save download destination if it's set
        if hasattr(self, 'download_destination') and self.download_destination:
            config['download_destination'] = self.download_destination
        
        # Save current build if it's set
        if hasattr(self, 'current_build') and self.current_build:
            config['current_build'] = self.current_build
        
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                json.dump(config, config_file, indent=4)
            self.status_right.config(text="Configuration saved successfully.")
        except Exception as e:
            self.status_right.config(text=f"Error saving configuration: {str(e)}")
            
    def download_rtx_remix_component(self):
        """Download RTX Remix components with tabbed interface"""
        # Check if a download window is already open and destroy it
        if hasattr(self, 'download_window') and self.download_window.winfo_exists():
            self.download_window.destroy()
        
        # Check if RTX-Remix folder is set first
        if not hasattr(self, 'remix_folder') or not self.remix_folder or not os.path.exists(self.remix_folder):
            # Ask the user to set up the RTX-Remix folder first
            if messagebox.askyesno(
                "RTX-Remix Working Folder Required",
                "You need to set up your RTX-Remix working folder before downloading.\n\n"
                "Would you like to set it up now?"
            ):
                # Let the user select a folder
                folder = filedialog.askdirectory(
                    title="Select or Create RTX-Remix Working Folder"
                )
                
                if not folder:
                    messagebox.showinfo(
                        "Cancelled",
                        "Working folder selection was cancelled.\n"
                        "You need to set a working folder before downloading."
                    )
                    return
                
                # Create the folder if it doesn't exist
                try:
                    os.makedirs(folder, exist_ok=True)
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Could not create folder: {str(e)}"
                    )
                    return
                
                # Set as the RTX-Remix folder
                self.remix_folder = folder.replace("/", "\\")
                self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
                self.save_config()
            else:
                return  # User chose not to set up a folder, so abort download
        
        # Create the lookup table of locally downloaded builds
        self.create_local_builds_lookup()
        
        # Create the download window with specific position
        self.download_window = tk.Toplevel(self.master)
        self.download_window.title("RTX Remix Downloader")
        self.download_window.configure(bg="#1a1a1a")
        
        # First set a default size
        self.download_window.geometry("700x650")
        
        # Calculate the position to center on parent
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        
        # Calculate center position
        x = parent_x + (parent_width - 700) // 2
        y = parent_y + (parent_height - 650) // 2
        
        # Make sure position is not negative
        x = max(x, 0)
        y = max(y, 0)
        
        # Set the position
        self.download_window.geometry(f"700x600+{x}+{y}")
        
        self.download_window.transient(self.master)
        self.download_window.grab_set()
        
        # Main container frame
        main_frame = ttk.Frame(self.download_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ================= TOP FRAME (Build Type Tabs) =================
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create tabbed interface
        self.notebook = ttk.Notebook(top_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs - ensure these functions set self.release_frame and self.nightly_frame
        self.create_release_tab()
        self.create_nightly_tab()
        
        # ================= BOTTOM FRAME (Shared Controls) =================
        self.create_shared_controls(main_frame)
        
        # Auto-fetch versions when tabs are selected
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Create status bar
        self.create_status_bar(self.download_window)
        
        # Force initial fetch for the first tab
        self.notebook.select(0)
        self.on_tab_changed(None)
        
        # Set up window close handling to clean up the references
        self.download_window.protocol("WM_DELETE_WINDOW", self.on_download_window_close)
        
    def create_local_builds_lookup(self):
        """Create a lookup table of locally downloaded builds using the correct folder structure"""
        self.local_builds = {
            "dxvk": {
                "release": set(),
                "debug": set(),
                "debugoptimized": set()
            },
            "bridge": {
                "release": set(),
                "debug": set(),
                "debugoptimized": set()
            }
        }
        
        # Check if the RTX-Remix folder exists
        if not hasattr(self, 'remix_folder') or not os.path.exists(self.remix_folder):
            return
        
        # Print for debugging
        print(f"Scanning for builds in: {self.remix_folder}")
        
        # ==== Check builds in the release folder structure ====
        release_path = os.path.join(self.remix_folder, "release")
        if os.path.exists(release_path):
            print(f"Found release folder: {release_path}")
            # Check each build type folder
            for build_type in ["release", "debug", "debugoptimized"]:
                build_type_path = os.path.join(release_path, build_type)
                if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                    print(f"Found build type folder: {build_type_path}")
                    # Process release builds: add to both dxvk and bridge since they're combined
                    for release_name in os.listdir(build_type_path):
                        release_folder = os.path.join(build_type_path, release_name)
                        if os.path.isdir(release_folder) and self.is_rtx_remix_folder(release_folder):
                            # Add to both component types since release builds contain both
                            for component in ["dxvk", "bridge"]:
                                if component not in self.local_builds:
                                    self.local_builds[component] = {}
                                if build_type not in self.local_builds[component]:
                                    self.local_builds[component][build_type] = set()
                                self.local_builds[component][build_type].add(release_name)
                                print(f"Added release build: {release_name} to {component}/{build_type}")
        
        # ==== Check builds in the nightly folder structure ====
        nightly_path = os.path.join(self.remix_folder, "nightly")
        if os.path.exists(nightly_path):
            print(f"Found nightly folder: {nightly_path}")
            # Check each component type
            for component_type in ["dxvk", "bridge"]:
                component_path = os.path.join(nightly_path, component_type)
                if os.path.exists(component_path):
                    print(f"Found component folder: {component_path}")
                    # Check each architecture folder
                    for arch in ["x86", "x64"]:
                        arch_path = os.path.join(component_path, arch)
                        if os.path.exists(arch_path) and os.path.isdir(arch_path):
                            print(f"Found architecture folder: {arch_path}")
                            # Check each build type
                            for build_type in ["release", "debug", "debugoptimized"]:
                                build_type_path = os.path.join(arch_path, build_type)
                                if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                                    print(f"Found build type folder: {build_type_path}")
                                    # Add all commit hash folders
                                    for folder in os.listdir(build_type_path):
                                        folder_path = os.path.join(build_type_path, folder)
                                        if os.path.isdir(folder_path) and self.is_rtx_remix_folder(folder_path):
                                            if component_type not in self.local_builds:
                                                self.local_builds[component_type] = {}
                                            if build_type not in self.local_builds[component_type]:
                                                self.local_builds[component_type][build_type] = set()
                                            self.local_builds[component_type][build_type].add(folder)
                                            print(f"Added nightly build: {folder} to {component_type}/{build_type}")
        
        # ==== Also check the old structure in case there are still builds there ====
        # This is for backwards compatibility
        try:
            # Check direct under remix folder
            for component_type in ["dxvk", "bridge"]:
                component_path = os.path.join(self.remix_folder, component_type)
                if os.path.exists(component_path) and os.path.isdir(component_path):
                    for build_type in ["release", "debug", "debugoptimized"]:
                        build_type_path = os.path.join(component_path, build_type)
                        if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                            for folder in os.listdir(build_type_path):
                                folder_path = os.path.join(build_type_path, folder)
                                if os.path.isdir(folder_path) and self.is_rtx_remix_folder(folder_path):
                                    if component_type not in self.local_builds:
                                        self.local_builds[component_type] = {}
                                    if build_type not in self.local_builds[component_type]:
                                        self.local_builds[component_type][build_type] = set()
                                    self.local_builds[component_type][build_type].add(folder)
                                    print(f"Added legacy build: {folder} to {component_type}/{build_type}")
            
            # Also check in nightly folder without architecture
            for component_type in ["dxvk", "bridge"]:
                component_path = os.path.join(nightly_path, component_type)
                if os.path.exists(component_path) and os.path.isdir(component_path):
                    for build_type in ["release", "debug", "debugoptimized"]:
                        build_type_path = os.path.join(component_path, build_type)
                        if os.path.exists(build_type_path) and os.path.isdir(build_type_path):
                            for folder in os.listdir(build_type_path):
                                folder_path = os.path.join(build_type_path, folder)
                                if os.path.isdir(folder_path) and self.is_rtx_remix_folder(folder_path):
                                    if component_type not in self.local_builds:
                                        self.local_builds[component_type] = {}
                                    if build_type not in self.local_builds[component_type]:
                                        self.local_builds[component_type][build_type] = set()
                                    self.local_builds[component_type][build_type].add(folder)
                                    print(f"Added old nightly build: {folder} to {component_type}/{build_type}")
        except Exception as e:
            print(f"Error checking old folder structure: {e}")
        
        print(f"Local builds lookup created: {self.local_builds}")
    
    def on_closing(self):
        """Handle window closing"""
        self.save_config()
        self.master.destroy()
        
    def on_download_window_close(self):
        """Handle download window closing - clean up references"""
        # Clean up frame references to avoid errors
        if hasattr(self, 'release_frame'):
            delattr(self, 'release_frame')
        if hasattr(self, 'nightly_frame'):
            delattr(self, 'nightly_frame')
        if hasattr(self, 'notebook'):
            delattr(self, 'notebook')
        if hasattr(self, 'dxvk_status'):
            delattr(self, 'dxvk_status')
        if hasattr(self, 'bridge_status'):
            delattr(self, 'bridge_status')
        if hasattr(self, 'progress_bar'):
            delattr(self, 'progress_bar')
        if hasattr(self, 'global_status'):
            delattr(self, 'global_status')
        
        # Close the window
        self.download_window.destroy()
        delattr(self, 'download_window')
    
    def download_build(self):
        """Handle download based on current active tab"""
        current_tab = self.notebook.index("current")
        if current_tab == 0:  # Release tab
            self.download_release()
        else:  # Nightly tab
            self.download_nightly()
    
    def download_release(self):
        """Download selected release version to the main RTX-Remix folder"""
        version_str = self.release_version_var.get()
        
        # Check if RTX-Remix folder is set
        if not hasattr(self, 'remix_folder') or not self.remix_folder:
            messagebox.showerror(
                "No Working Folder",
                "You need to set an RTX-Remix working folder first.",
                parent=self.download_window
            )
            return
        
        if not version_str:
            self.release_status.config(text="Please select a version first")
            return
        
        # Extract tag name from version string (format: "tag_name (date) [DOWNLOADED]")
        tag_name = version_str.split(" (")[0]
        build_type = self.release_build_var.get()
        
        # Check if this version is already marked as downloaded
        is_already_downloaded = "[DOWNLOADED]" in version_str
        
        # Create the proper folder structure:
        # RTX-Remix/release/build_type/clean_tag/
        
        # Create the release folder if it doesn't exist
        release_folder = os.path.join(self.remix_folder, "release")
        os.makedirs(release_folder, exist_ok=True)
        
        # Create the build type folder if it doesn't exist
        build_type_folder = os.path.join(release_folder, build_type)
        os.makedirs(build_type_folder, exist_ok=True)
        
        # Create a subfolder for this specific release
        clean_tag = tag_name.replace("remix-", "")  # Remove "remix-" prefix for cleaner folder names
        destination = os.path.join(build_type_folder, f"{clean_tag}")
        
        # Check if destination already exists and has content
        if os.path.exists(destination) and os.listdir(destination):
            # Make the dialog appear as topmost window
            self.download_window.attributes('-topmost', True)
            
            # Use a more specific message when we know it's already downloaded
            if is_already_downloaded:
                message = (f"RTX Remix {tag_name} ({build_type}) is already downloaded.\n\n"
                          f"Do you want to download again and overwrite the existing content?")
            else:
                message = (f"The folder '{os.path.basename(destination)}' already exists in release/{build_type}/.\n\n"
                          "Do you want to download again and overwrite the existing content?")
            
            user_choice = messagebox.askyesno(
                "Folder Exists",
                message,
                parent=self.download_window
            )
            self.download_window.attributes('-topmost', False)
            
            if not user_choice:
                self.release_status.config(text="Download cancelled by user.")
                return
        
        try:
            # Update UI
            self.start_progress(f"Downloading {tag_name} ({build_type})...")
            self.progress_bar['value'] = 10
            self.download_window.update()
            
            # Create destination directory if it doesn't exist
            os.makedirs(destination, exist_ok=True)
            
            # Get release info to find assets
            release_url = f"https://api.github.com/repos/NVIDIAGameWorks/rtx-remix/releases/tags/{tag_name}"
            req = urllib.request.Request(release_url)
            
            with urllib.request.urlopen(req) as response:
                release_data = json.loads(response.read().decode())
                
            # Get commit hash from the release
            commit_hash = release_data.get('target_commitish', '')
            if len(commit_hash) > 7:
                commit_hash = commit_hash[:7]  # Use first 7 characters of commit hash
                
            # Find the ZIP asset that matches the build type and is NOT a symbols zip
            zip_asset = None
            for asset in release_data['assets']:
                # Check if it's a zip file
                if asset['name'].endswith('.zip'):
                    # Ensure it's not a symbols zip file
                    if "-symbols.zip" not in asset['name'].lower():
                        # Check if build type is in the asset name
                        if build_type in asset['name'].lower():
                            zip_asset = asset
                            break
            
            # If no specific build type asset found, look for any non-symbols ZIP
            if not zip_asset:
                for asset in release_data['assets']:
                    if asset['name'].endswith('.zip') and "-symbols.zip" not in asset['name'].lower():
                        zip_asset = asset
                        break
            
            if not zip_asset:
                self.error_progress("No suitable ZIP package found in this release")
                return
                
            # Download the ZIP file
            zip_url = zip_asset['browser_download_url']
            zip_size = zip_asset['size']
            
            # Set filename for downloaded zip
            zip_filename = os.path.join(destination, zip_asset['name'])
            
            # Progress updater for download
            def report_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, int(downloaded * 100 / zip_size))
                self.progress_bar['value'] = percent
                self.global_status.config(text=f"Downloading: {percent}% of {self.format_size(zip_size)}")
                self.download_window.update()
            
            # Download with progress reporting
            self.release_status.config(text=f"Downloading {zip_asset['name']}...")
            urllib.request.urlretrieve(zip_url, zip_filename, reporthook=report_progress)
            
            # Update progress for extraction
            self.progress_bar['value'] = 100
            self.global_status.config(text=f"Download complete. Extracting...")
            self.download_window.update()
            
            # Extract the ZIP file
            import zipfile
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(destination)
            
            # Create a detailed buildname.txt file similar to nightly builds
            buildname_path = os.path.join(destination, "buildname.txt")
            try:
                with open(buildname_path, 'w') as f:
                    # Use release version format for consistency with nightly builds
                    f.write(f"Repository: rtx-remix\n")
                    f.write(f"Release Version: {clean_tag}\n")
                    f.write(f"Commit Hash: {commit_hash}\n")
                    f.write(f"Build Type: {build_type}\n")
                    f.write(f"Architecture: x86\n")  # Most releases are x86
                    f.write(f"Downloaded On: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if zip_asset:
                        f.write(f"Asset Name: {zip_asset['name']}\n")
                    f.write(f"Full Version: {clean_tag}-{build_type}\n")
                print(f"SUCCESS: Created detailed {buildname_path}")
            except Exception as e:
                print(f"ERROR creating {buildname_path}: {e}")
            
            # For backward compatibility, also create the traditional build-names.txt
            build_names_path = os.path.join(destination, "build-names.txt")
            try:
                with open(build_names_path, 'w') as f:
                    # Keep the traditional format for backward compatibility
                    version_string = f"{clean_tag}-{build_type}"
                    f.write(f"rtx-remix-for-x86-games-{version_string}")
                print(f"SUCCESS: Created backward-compatible {build_names_path}")
            except Exception as e:
                print(f"ERROR creating {build_names_path}: {e}")
            
            # Now walk through all subdirectories and create the files in any folders 
            # containing RTX Remix components (d3d9.dll or .trex folder)
            for root, dirs, files in os.walk(destination):
                is_remix_folder = False
                
                # Check for .trex directory
                if '.trex' in dirs:
                    is_remix_folder = True
                    
                # Check for d3d9.dll
                if 'd3d9.dll' in files:
                    is_remix_folder = True
                
                # Create version files if this looks like an RTX Remix folder
                if is_remix_folder:
                    # Create detailed buildname.txt
                    subfolder_buildname_path = os.path.join(root, "buildname.txt")
                    try:
                        with open(subfolder_buildname_path, 'w') as f:
                            f.write(f"Repository: rtx-remix\n")
                            f.write(f"Release Version: {clean_tag}\n")
                            f.write(f"Commit Hash: {commit_hash}\n")
                            f.write(f"Build Type: {build_type}\n")
                            f.write(f"Architecture: x86\n")
                            f.write(f"Downloaded On: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            if zip_asset:
                                f.write(f"Asset Name: {zip_asset['name']}\n")
                            f.write(f"Full Version: {clean_tag}-{build_type}\n")
                        print(f"SUCCESS: Created detailed {subfolder_buildname_path}")
                    except Exception as e:
                        print(f"ERROR creating {subfolder_buildname_path}: {e}")
                    
                    # Create traditional build-names.txt for backward compatibility
                    subfolder_build_path = os.path.join(root, "build-names.txt")
                    try:
                        with open(subfolder_build_path, 'w') as f:
                            version_string = f"{clean_tag}-{build_type}"
                            f.write(f"rtx-remix-for-x86-games-{version_string}")
                        print(f"SUCCESS: Created backward-compatible {subfolder_build_path}")
                    except Exception as e:
                        print(f"ERROR creating {subfolder_build_path}: {e}")
            
            # Delete the ZIP file to save space
            try:
                os.remove(zip_filename)
                self.global_status.config(text=f"Deleted ZIP file to save disk space")
                self.download_window.update()
            except Exception as e:
                self.global_status.config(text=f"Note: Could not delete ZIP file: {str(e)}")
                self.download_window.update()
            
            # Success message
            self.complete_progress(f"Successfully downloaded and extracted {tag_name} ({build_type})")
            self.release_status.config(text=f"Successfully downloaded {tag_name} ({build_type})")
            
            # Update the dropdown to mark this version as downloaded if it wasn't already
            if not is_already_downloaded:
                # Get the current list of versions
                versions = list(self.release_version_combo['values'])
                # Find the current selection
                current_index = self.release_version_combo.current()
                # Update it to show as downloaded
                versions[current_index] = f"{versions[current_index]} [DOWNLOADED]".replace(" [DOWNLOADED] [DOWNLOADED]", " [DOWNLOADED]")
                # Update the dropdown
                self.release_version_combo['values'] = versions
                # Keep the same selection
                self.release_version_combo.current(current_index)
            
            # Refresh the build list to include the newly downloaded build
            self.update_build_selection_options()
            
            # Show a simple success message but don't close the window
            self.download_window.attributes('-topmost', True)
            messagebox.showinfo(
                "Download Complete",
                f"Successfully downloaded RTX Remix {tag_name} ({build_type}).\n\n"
                f"The build has been added to your release/{build_type}/ folder.",
                parent=self.download_window
            )
            self.download_window.attributes('-topmost', False)
            
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            print(error_msg)
            self.error_progress(f"Download failed: {str(e)}")
            self.release_status.config(text=f"Download failed: {str(e)}")
    
    def download_nightly(self, repo, version_var):
        """Download a nightly build from GitHub"""
        # Get selected version
        version_display = version_var.get()
        
        # Exit if no version is selected
        if not version_display or "No builds found" in version_display:
            self.global_status.config(text="No valid version selected")
            return
        
        # Get the artifact info based on the display string
        if repo == "dxvk-remix":
            artifact_map = self.dxvk_artifact_map
            status_widget = self.dxvk_status
            component_type = "dxvk"
        else:
            self.global_status.config(text="Error: Unsupported repository type")
            return
        
        info = artifact_map.get(version_display)
        if not info:
            self.global_status.config(text="Error: Could not find build information")
            return
        
        # Extract artifact details
        artifact = info["artifact"]
        commit_hash = info["commit_hash"]
        build_type = info["build_type"]  # Extracted from the artifact name
        architecture = info.get("architecture", "x64")  # Use the architecture from the mapping
        date_str = info.get("date_str", "")  # Get date string if available
        
        # Check if already downloaded
        if "[DOWNLOADED]" in version_display:
            if messagebox.askyesno(
                "Build Already Downloaded",
                f"This build is already downloaded to your system. Do you want to download it again?"
            ):
                pass  # Continue with download
            else:
                return  # Exit if user doesn't want to download again
        
        # Set up download destination using the correct folder structure:
        # /RTX-Remix/nightly/component_type/architecture/build_type/commit_hash
        destination_dir = os.path.join(self.remix_folder, "nightly", component_type, architecture, build_type, commit_hash)
        
        # Create destination directory if it doesn't exist
        os.makedirs(destination_dir, exist_ok=True)
        
        # Set up progress bar
        self.progress_bar['value'] = 0
        self.global_status.config(text=f"Downloading {version_display}...")
        status_widget.config(text="Preparing download...")
        self.download_window.update()
        
        # Create a temporary download location to avoid confusion
        temp_zip_filename = os.path.join(self.remix_folder, f"temp_{artifact['name']}.zip")
        
        print(f"Downloading {artifact['name']} to {temp_zip_filename}")
        status_widget.config(text="Starting download...")
        
        # Prepare artifact download URL
        download_url = f"https://nightly.link/NVIDIAGameWorks/{repo}/actions/artifacts/{artifact['id']}.zip"
        
        try:
            # Download the zip file with progress tracking
            with requests.get(download_url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(temp_zip_filename, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = int(100 * downloaded / total_size) if total_size > 0 else 0
                            self.progress_bar['value'] = progress
                            status_widget.config(text=f"Downloading... {progress}%")
                            self.download_window.update()
            
            status_widget.config(text="Extracting files...")
            self.download_window.update()
            
            # Extract the zip file
            with zipfile.ZipFile(temp_zip_filename, 'r') as zip_ref:
                zip_ref.extractall(destination_dir)
            
            # Create a buildname file with version information
            with open(os.path.join(destination_dir, "buildname.txt"), 'w') as f:
                f.write(f"Repository: {repo}\n")
                f.write(f"Commit Hash: {commit_hash}\n")
                f.write(f"Build Type: {build_type}\n")
                f.write(f"Architecture: {architecture}\n")
                f.write(f"Downloaded On: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Artifact ID: {artifact['id']}\n")
                f.write(f"Artifact Name: {artifact['name']}\n")
                if date_str:
                    f.write(f"Build Date: {date_str}\n")
            
            # Delete the temporary zip file
            os.remove(temp_zip_filename)
            
            # Show success message
            self.global_status.config(text=f"Successfully downloaded {artifact['name']}!")
            status_widget.config(text="Download complete!")
            self.progress_bar['value'] = 100
            
            # Update the dropdown entry to show this build is now downloaded
            new_display = version_display
            if "[DOWNLOADED]" not in version_display:
                new_display = f"{version_display} [DOWNLOADED]"
            
            # Update the dropdown values
            values = list(self.dxvk_combo['values'])
            if version_display in values:
                index = values.index(version_display)
                values[index] = new_display
                self.dxvk_combo['values'] = values
                
                # Update the current selection
                self.dxvk_version_var.set(new_display)
                
                # Update the artifact map
                info_copy = info.copy()
                self.dxvk_artifact_map[new_display] = info_copy
                if version_display in self.dxvk_artifact_map:
                    del self.dxvk_artifact_map[version_display]
            
            # Refresh the list of local builds
            self.create_local_builds_lookup()
            self.update_destination_preview()
            
            # Update the main build selection dropdown
            self.update_build_selection_options()
            
        except Exception as e:
            error_msg = f"Error downloading: {str(e)}"
            self.global_status.config(text=error_msg)
            status_widget.config(text="Download failed!")
            print(error_msg)
            
            # Try to clean up if there was an error
            if os.path.exists(temp_zip_filename):
                try:
                    os.remove(temp_zip_filename)
                except:
                    pass
    
    def on_remix_type_changed(self, value):
        """Handle changing between release and nightly builds in the dropdown"""
        # Only proceed if we have the necessary frames
        if not hasattr(self, 'rtx_remix_frame'):
            return
        
        print(f"Build type changed to: {value}")
        
        try:
            if value == "Release":
                # Hide architecture selection for release builds
                if hasattr(self, 'remix_arch_frame'):
                    self.remix_arch_frame.grid_remove()
                
                # Update the dropdown with release versions
                if hasattr(self, 'available_release_builds') and self.available_release_builds:
                    # Update with release builds
                    display_values = []
                    for build in self.available_release_builds:
                        display_values.append({"display": build["name"], "build": build})
                    
                    # Sort version numbers (higher versions first)
                    display_values.sort(key=lambda x: self.sort_version_key(x["display"]), reverse=True)
                    
                    # Update dropdown with display values
                    self.remix_version_dropdown['values'] = [item["display"] for item in display_values]
                    self.available_release_displays = display_values  # Store for reference in selection handler
                    
                    if display_values:
                        self.remix_version_dropdown.current(0)
                        # Now trigger on_version_selected to update the active build and version tags
                        self.on_version_selected(None)
                    else:
                        self.remix_version_dropdown['values'] = ["No builds found"]
                        self.remix_version_dropdown.current(0)
            else:  # "Nightly"
                # Show architecture selection for nightly builds
                if hasattr(self, 'remix_arch_frame'):
                    self.remix_arch_frame.grid()
                
                # Update the dropdown with nightly versions based on selected architecture
                self.update_nightly_version_dropdown()
                # This will trigger version update through selection event
        except Exception as e:
            print(f"Error in on_remix_type_changed: {e}")
            import traceback
            traceback.print_exc()
    
    def update_nightly_version_dropdown(self):
        """Update the version dropdown with nightly builds based on selected architecture"""
        if not hasattr(self, 'remix_version_dropdown'):
            return
            
        # Get the selected architecture
        selected_arch = self.remix_arch_var.get()
        print(f"Updating nightly version dropdown for architecture: {selected_arch}")
        
        # Filter nightly runtime builds by architecture
        if hasattr(self, 'available_nightly_runtime_builds'):
            filtered_builds = []
            for build in self.available_nightly_runtime_builds:
                # Check if this build matches the selected architecture
                build_arch = build.get("architecture", "x64")
                if build_arch == selected_arch:
                    # Get timestamp for sorting, or use 0 if not available
                    timestamp = build.get("timestamp", 0)
                    if not timestamp and hasattr(build["path"], "replace"):
                        # If no timestamp, try to get file creation time
                        try:
                            timestamp = os.path.getctime(build["path"])
                        except:
                            pass
                    
                    # Try to extract date information
                    date_str = ""
                    # First check if we can get it from the name
                    path = build["path"]
                    if hasattr(path, "replace"):  # Ensure it's a string path
                        # Check if there's a buildname.txt with date info
                        buildname_path = os.path.join(path, "buildname.txt")
                        if os.path.exists(buildname_path):
                            try:
                                with open(buildname_path, 'r') as f:
                                    content = f.read()
                                    # Try to find a date in the content
                                    date_match = re.search(r'Build Date:\s*(.+)', content)
                                    if date_match:
                                        date_str = date_match.group(1).strip()
                                    else:
                                        # Look for Downloaded On field
                                        date_match = re.search(r'Downloaded On:\s*(.+)', content)
                                        if date_match:
                                            date_str = date_match.group(1).strip()
                            except:
                                pass
                    
                    # If no date found, use folder modified time
                    if not date_str and hasattr(path, "replace") and os.path.exists(path):
                        try:
                            mod_time = os.path.getmtime(path)
                            date_str = datetime.datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    # Create a more readable display name
                    display_name = build["name"]
                    if date_str:
                        # Format: "2025-05-13 12:30 | dxvk-remix-abc123f | 64-bit release"
                        base_name = os.path.basename(path) if hasattr(path, "replace") else build.get("folder", "unknown")
                        build_type = build.get("build_type", "unknown")
                        display_name = f"{date_str} | {base_name} | {selected_arch}-bit {build_type}"
                    
                    # Add to filtered builds
                    filtered_builds.append({
                        "display": display_name,
                        "build": build,
                        "timestamp": timestamp
                    })
            
            # Sort by timestamp (newest first)
            filtered_builds.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Update dropdown
            self.remix_version_dropdown['values'] = [item["display"] for item in filtered_builds]
            self.available_nightly_displays = filtered_builds
            
            if filtered_builds:
                self.remix_version_dropdown.current(0)
                # Now trigger on_version_selected to update the active build and version tags
                self.on_version_selected(None)
            else:
                self.remix_version_dropdown['values'] = [f"No {selected_arch} builds found"]
                self.remix_version_dropdown.current(0)
    
    def set_current_rtx_remix(self):
        """Set the selected build as the current RTX Remix build"""
        remix_type = self.remix_type_var.get()
        
        if remix_type == "Release":
            # For release builds, just get the selected version's path
            selected_version = self.remix_version_var.get()
            
            if selected_version == "No builds found":
                messagebox.showerror("No Build Available", "No release builds found to select.")
                return
                
            for build in self.available_release_builds:
                if build["name"] == selected_version:
                    rtx_folder = build["path"]
                    break
            else:
                messagebox.showerror("Build Not Found", "Selected RTX Remix release build not found")
                return
        else:
            # For nightly builds, we need to create a composite folder that contains both bridge and runtime
            selected_bridge = self.nightly_bridge_var.get()
            selected_runtime = self.nightly_runtime_var.get()
            
            if selected_bridge == "No builds found" or selected_runtime == "No builds found":
                messagebox.showerror("No Build Available", "One or both required nightly builds not found.")
                return
            
            # Find the bridge and runtime paths
            bridge_path = None
            runtime_path = None
            
            for build in self.available_nightly_bridge_builds:
                if build["name"] == selected_bridge:
                    bridge_path = build["path"]
                    bridge_commit = build["commit"]
                    break
                    
            for build in self.available_nightly_runtime_builds:
                if build["name"] == selected_runtime:
                    runtime_path = build["path"]
                    runtime_commit = build["commit"]
                    break
            
            if not bridge_path or not runtime_path:
                messagebox.showerror("Build Not Found", "Could not locate one or both of the selected builds")
                return
                
            # Create a temporary composite folder
            temp_dir = os.path.join(self.download_destination, f"composite_nightly_{bridge_commit[:7]}_{runtime_commit[:7]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Copy bridge and runtime files to the composite folder
            try:
                # Copy bridge files (excluding any runtime files that might be there)
                for item in os.listdir(bridge_path):
                    if item != '.trex':  # Don't copy runtime folder from bridge
                        src = os.path.join(bridge_path, item)
                        dst = os.path.join(temp_dir, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src, dst)
                
                # Copy runtime folder
                trex_src = os.path.join(runtime_path, '.trex')
                if os.path.exists(trex_src) and os.path.isdir(trex_src):
                    trex_dst = os.path.join(temp_dir, '.trex')
                    shutil.copytree(trex_src, trex_dst, dirs_exist_ok=True)
                
                # Create a buildname file for this composite build
                with open(os.path.join(temp_dir, "build_names.txt"), "w") as f:
                    f.write(f"dxvk-remix-{runtime_commit}\n")
                    f.write(f"bridge-remix-{bridge_commit}\n")
                    
                rtx_folder = temp_dir
                
            except Exception as e:
                messagebox.showerror("Error Creating Composite Build", f"Error: {str(e)}")
                return
        
        # Set the selected folder as the current RTX Remix folder
        self.remix_folder = rtx_folder
        self.source_versions = self.load_versions_from_file(self.remix_folder, True)
        version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
        self.version_label.config(text=version_info)
        self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
        
        # Re-check version compatibility for all games
        for item in self.tree.get_children():
            destination_folder = self.tree.item(item, "values")[2]
            destination_versions = self.load_versions_from_file(destination_folder)
            self.check_version_and_tag(item, destination_versions)
        
        # Save the configuration
        self.save_config()
        
        messagebox.showinfo("Success", f"Set RTX-Remix folder to: {self.remix_folder}")
        self.update_copy_button_state()
    
    def load_build_selection_options(self):
        """Load build selection options when the application starts"""
        # Create UI elements and scan for available builds
        self.update_build_selection_options()
    
    def format_size(self, size_bytes):
        """Format bytes to human-readable size"""
        if size_bytes == 0:
            return "0B"
        size_names = ("B", "KB", "MB", "GB", "TB")
        i = int(math.log(size_bytes, 1024))
        p = math.pow(1024, i)
        size = round(size_bytes / p, 2)
        return f"{size} {size_names[i]}"
    
    def find_rtx_remix_folder(self, parent_dir):
        """Find RTX-Remix folder in extracted content"""
        # First, check if parent_dir itself is an RTX-Remix folder
        if self.is_rtx_remix_folder(parent_dir):
            return parent_dir
        
        # Walk through the directory structure to find the RTX-Remix folder
        for root, dirs, files in os.walk(parent_dir):
            # Check if current directory has the required files/folders for RTX-Remix
            if self.is_rtx_remix_folder(root):
                return root
                
            # Don't go too deep in the directory structure
            # Limit to 3 levels deep from the parent_dir
            if root.count(os.sep) > parent_dir.count(os.sep) + 3:
                continue
        
        # If not found, try a more lenient search
        for root, dirs, files in os.walk(parent_dir):
            # Look for key RTX-Remix files even if not all are present
            key_indicators = ['d3d9.dll', 'NvRemixLauncher32.exe']
            if any(f in files for f in key_indicators):
                return root
                
            # Limit depth
            if root.count(os.sep) > parent_dir.count(os.sep) + 3:
                continue
        
        # If still not found, just return the parent directory itself
        return parent_dir
        
    def is_rtx_remix_folder(self, folder_path):
        """Check if a folder contains RTX Remix files based on build type"""
        try:
            if not os.path.exists(folder_path):
                return False
                
            files = os.listdir(folder_path)
            
            # Check for x86 release builds or nightly x86 builds
            # These need d3d9.dll, NvRemixLauncher32.exe, and .trex folder
            if 'd3d9.dll' in files and 'NvRemixLauncher32.exe' in files and '.trex' in files:
                return True
                
            # Check for x64 nightly builds
            # These need d3d9.dll and NvRemixBridge.exe, .trex is not needed
            if 'd3d9.dll' in files and 'NvRemixBridge.exe' in files:
                return True
                
            # Also check for buildname.txt which indicates downloaded builds
            if 'buildname.txt' in files or 'build_names.txt' in files or 'build-names.txt' in files:
                # If we have the build name file and at least one of the key binaries,
                # consider it a valid Remix folder
                if 'd3d9.dll' in files or 'NvRemixLauncher32.exe' in files or 'NvRemixBridge.exe' in files:
                    return True
                    
            # Not a valid RTX Remix folder
            return False
            
        except Exception as e:
            print(f"Error checking RTX Remix folder: {e}")
            return False
    
    def create_release_tab(self):
        """Create the Release tab in the download window"""
        self.release_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.release_frame, text="Release Builds")
        
        # Version selection
        ttk.Label(self.release_frame, 
                 text="Complete RTX Remix (Recommended)\nBest performance, stable version",
                 justify=tk.CENTER).pack(pady=10)
        
        version_frame = ttk.Frame(self.release_frame)
        version_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(version_frame, text="Version:").pack(side=tk.LEFT, padx=5)
        
        self.release_version_var = tk.StringVar()
        self.release_version_combo = ttk.Combobox(version_frame, 
                                                textvariable=self.release_version_var, 
                                                state="readonly")
        self.release_version_combo.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        # Build type selection
        build_frame = ttk.LabelFrame(self.release_frame, text="Build Type")
        build_frame.pack(fill=tk.X, pady=10, padx=10)
        
        self.release_build_var = tk.StringVar(value="release")
        
        ttk.Radiobutton(build_frame, 
                       text="Release (Best Performance)",
                       value="release",
                       variable=self.release_build_var).pack(anchor=tk.W, pady=2)
                       
        ttk.Radiobutton(build_frame, 
                       text="Debug Optimized (Fast with debug functions)",
                       value="debugoptimized",
                       variable=self.release_build_var).pack(anchor=tk.W, pady=2)
                       
        ttk.Radiobutton(build_frame, 
                       text="Debug (Slow, with debug symbols)",
                       value="debug",
                       variable=self.release_build_var).pack(anchor=tk.W, pady=2)
    
        # Add download button
        download_button = ttk.Button(
            self.release_frame, 
            text="Download Selected Version", 
            command=self.download_release
        )
        download_button.pack(pady=15)
    
        self.release_status = ttk.Label(self.release_frame, text="Ready to download stable releases")
        self.release_status.pack(pady=10)
    
    def create_nightly_tab(self):
        """Create the Nightly tab in the download window with DXVK options only"""
        self.nightly_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.nightly_frame, text="Nightly Builds")
        
        # Create nightly tab content
        nightly_label = ttk.Label(
            self.nightly_frame, 
            text="Download the latest development builds from GitHub Actions",
            font=("Arial", 10)
        )
        nightly_label.grid(row=0, column=0, columnspan=3, pady=10, sticky="w")
        
        # Architecture selection (added for user to choose)
        arch_frame = ttk.LabelFrame(self.nightly_frame, text="Architecture")
        arch_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        self.nightly_arch_var = tk.StringVar(value="x64")
        ttk.Radiobutton(
            arch_frame, 
            text="x64 (64-bit games)",
            variable=self.nightly_arch_var,
            value="x64",
            command=lambda: self.fetch_nightly_versions_for_arch("dxvk-remix")
        ).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        ttk.Radiobutton(
            arch_frame, 
            text="x86 (32-bit games)",
            variable=self.nightly_arch_var,
            value="x86",
            command=lambda: self.fetch_nightly_versions_for_arch("dxvk-remix")
        ).grid(row=0, column=1, padx=10, pady=5, sticky="w")
        
        # DXVK (Runtime) section - Fixed height container
        dxvk_frame = ttk.LabelFrame(self.nightly_frame, text="RTX Remix Nightly Build")
        dxvk_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Set a minimum height for the frame to prevent resizing
        dxvk_inner_frame = ttk.Frame(dxvk_frame, height=150)  # Increased height for destination label
        dxvk_inner_frame.pack(fill=tk.X, expand=True)
        dxvk_inner_frame.pack_propagate(False)  # Prevent the frame from resizing to fit content
        
        # DXVK Build selection
        ttk.Label(dxvk_inner_frame, text="Select Version:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dxvk_version_var = tk.StringVar()
        self.dxvk_combo = ttk.Combobox(dxvk_inner_frame, textvariable=self.dxvk_version_var, width=50, state="readonly")
        self.dxvk_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Add binding to update the destination folder preview
        self.dxvk_combo.bind("<<ComboboxSelected>>", self.update_destination_preview)
        
        ttk.Button(dxvk_inner_frame, text="Refresh", command=lambda: self.fetch_nightly_versions("dxvk-remix")).grid(
            row=0, column=2, padx=5, pady=5
        )
        
        # Add destination folder preview
        ttk.Label(dxvk_inner_frame, text="Download Destination:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.destination_preview = ttk.Label(dxvk_inner_frame, text="Please select a build", font=("Consolas", 9))
        self.destination_preview.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        # DXVK Download button
        ttk.Button(
            dxvk_inner_frame, 
            text="Download Build", 
            command=lambda: self.download_nightly("dxvk-remix", self.dxvk_version_var)
        ).grid(row=2, column=0, columnspan=3, padx=5, pady=10)
        
        # DXVK Status - Fixed height with ellipsis
        status_frame = ttk.Frame(dxvk_inner_frame, height=20)
        status_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        status_frame.grid_propagate(False)  # Prevent frame from resizing
        
        self.dxvk_status = ttk.Label(status_frame, text="")
        self.dxvk_status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Notes section
        notes_frame = ttk.LabelFrame(self.nightly_frame, text="Notes")
        notes_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        notes_text = (
            "• Nightly builds are development builds and may contain bugs\n"
            "• x86 builds already include both DXVK and bridge components\n"
            "• x64 builds only contain DXVK (as bridge is not needed for 64-bit games)\n"
            "• GitHub Actions artifacts are automatically deleted after 90 days\n"
            "• Items marked with [DOWNLOADED] are already on your system"
        )
        ttk.Label(notes_frame, text=notes_text, wraplength=650).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        
    def update_destination_preview(self, event=None):
        """Update the destination folder preview when a build is selected"""
        version_display = self.dxvk_version_var.get()
        
        if not version_display or "No builds found" in version_display:
            self.destination_preview.config(text="Please select a build")
            return
        
        # Find the build info
        info = self.dxvk_artifact_map.get(version_display)
        if not info:
            self.destination_preview.config(text="Could not find build information")
            return
        
        # Extract details
        commit_hash = info["commit_hash"]
        build_type = info["build_type"]
        architecture = info.get("architecture", "x64")
        date_str = info.get("date_str", "")
        
        # Generate path
        destination = os.path.join(
            self.remix_folder, 
            "nightly", 
            "dxvk", 
            architecture, 
            build_type, 
            commit_hash
        )
        
        # Check if the build exists locally
        is_downloaded = False
        if os.path.exists(destination) and self.is_rtx_remix_folder(destination):
            is_downloaded = True
        
        # Create a more readable preview message
        display_str = f"nightly → dxvk → {architecture} → {build_type} → {commit_hash}"
        if date_str:
            display_str = f"{date_str} build → {display_str}"
        
        # Set the display text
        if is_downloaded:
            self.destination_preview.config(
                text=f"{display_str} [DOWNLOADED]",
                foreground="#76B900"  # Green for downloaded builds
            )
        else:
            self.destination_preview.config(
                text=display_str,
                foreground="#E0E0E0"  # Normal color for not downloaded
            )
    
    def fetch_nightly_versions_for_arch(self, repo):
        """Fetch nightly versions based on the currently selected architecture"""
        # This will be called when the architecture radio buttons are toggled
        selected_arch = self.nightly_arch_var.get()
        print(f"Fetching {repo} builds for architecture: {selected_arch}")
        
        # Clear and update the appropriate dropdown
        if repo == "dxvk-remix":
            self.dxvk_status.config(text=f"Fetching {selected_arch} builds...")
            self.dxvk_combo['values'] = []
            self.dxvk_version_var.set("")
            
            # Clear destination preview
            if hasattr(self, 'destination_preview'):
                self.destination_preview.config(text="Please select a build", foreground="#e0e0e0")
        
        # Fetch the versions for the selected architecture
        self.fetch_nightly_versions(repo)
    
    def on_dxvk_combo_select(self, event):
        """Handle selection from DXVK dropdown to highlight downloaded items"""
        # Get the selected text
        selected_text = self.dxvk_version_var.get()
        
        # If it contains [DOWNLOADED], change the foreground color to green
        if "[DOWNLOADED]" in selected_text:
            self.dxvk_combo.configure(foreground="green")
        else:
            self.dxvk_combo.configure(foreground="black")
    
    def on_bridge_combo_select(self, event):
        """Handle selection from Bridge dropdown to highlight downloaded items"""
        # Get the selected text
        selected_text = self.bridge_version_var.get()
        
        # If it contains [DOWNLOADED], change the foreground color to green
        if "[DOWNLOADED]" in selected_text:
            self.bridge_combo.configure(foreground="green")
        else:
            self.bridge_combo.configure(foreground="black")
    
    def create_shared_controls(self, parent_frame):
        """Create shared controls (just progress bar and status)"""
        bottom_frame = ttk.Frame(parent_frame)
        bottom_frame.pack(fill=tk.X, pady=5)
        
        # Status and progress bar only
        self.progress_bar = ttk.Progressbar(bottom_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # Global status bar (for download/extract progress)
        self.global_status = ttk.Label(bottom_frame, text="")
        self.global_status.pack(fill=tk.X, padx=10, pady=5)
        
    def setup_working_folder_from_download(self):
        """Set up the RTX-Remix working folder from the download window"""
        # Close the download window temporarily
        self.download_window.withdraw()
        
        # Show a message explaining what we're doing
        messagebox.showinfo(
            "Set RTX-Remix Working Folder",
            "Before downloading, you need to set up your RTX-Remix working folder.\n\n"
            "This is where all RTX-Remix builds will be stored and managed.\n\n"
            "In the next dialog, select or create a folder for this purpose."
        )
        
        # Ask for the folder
        folder = filedialog.askdirectory(
            title="Select or Create RTX-Remix Working Folder"
        )
        
        # Restore the download window
        self.download_window.deiconify()
        
        if not folder:
            messagebox.showinfo(
                "Cancelled",
                "Working folder selection was cancelled.\n"
                "You need to set a working folder before downloading.",
                parent=self.download_window
            )
            return
        
        # Create the folder if it doesn't exist
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Could not create folder: {str(e)}",
                parent=self.download_window
            )
            return
        
        # Set as the RTX-Remix folder
        self.remix_folder = folder.replace("/", "\\")
        self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
        self.save_config()
        
        # Update the download window destination label
        for widget in self.download_window.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Frame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ttk.Label) and grandchild.winfo_width() > 100:
                                grandchild.config(text=self.remix_folder)
                                break
        
        # Remove the setup button and enable the download button
        for widget in self.download_window.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget("text") == "Set Working Folder First":
                        child.destroy()
                        break
        
        # Enable the download button
        self.download_btn.configure(state="normal")
        
        # Update status
        self.global_status.config(text="Working folder set. Ready to download.")
        
        # Scan the folder for existing builds
        self.update_build_selection_options()
    
    def select_active_build_in_dropdown(self):
        """Select the active build in the dropdown and update version tags"""
        # Only proceed if we have the necessary UI elements and an active build path
        if not hasattr(self, 'remix_version_dropdown') or not hasattr(self, 'active_build_path'):
            return
                
        print(f"Selecting active build in dropdown: {self.active_build_path}")
        
        # Get the current dropdown mode
        current_mode = self.remix_type_var.get() if hasattr(self, 'remix_type_var') else "Release"
        
        # If build is a nightly but we're in Release mode, or vice versa, switch modes
        is_nightly = "nightly" in self.active_build_path.lower() or any(commit_hash in os.path.basename(self.active_build_path) for commit_hash in ["0f97438", "commit", "git"])
        
        if is_nightly and current_mode == "Release":
            print(f"Switching to Nightly mode for build: {self.active_build_path}")
            self.remix_type_var.set("Nightly")
            self.on_remix_type_changed()  # Refresh the dropdown options
            current_mode = "Nightly"
        elif not is_nightly and current_mode == "Nightly":
            print(f"Switching to Release mode for build: {self.active_build_path}")
            self.remix_type_var.set("Release")
            self.on_remix_type_changed()  # Refresh the dropdown options
            current_mode = "Release"
        
        # Find and select the matching build in the appropriate dropdown
        if current_mode == "Release" and hasattr(self, 'available_release_displays'):
            for i, item in enumerate(self.available_release_displays):
                build_path = item["build"]["path"].replace('\\', '/')
                if build_path == self.active_build_path.replace('\\', '/'):
                    self.remix_version_dropdown.current(i)
                    self.remix_version_var.set(item["display"])
                    print(f"Selected release build in dropdown: {item['display']}")
                    return
        elif current_mode == "Nightly" and hasattr(self, 'available_nightly_displays'):
            for i, item in enumerate(self.available_nightly_displays):
                build_path = item["build"]["path"].replace('\\', '/')
                if build_path == self.active_build_path.replace('\\', '/'):
                    self.remix_version_dropdown.current(i)
                    self.remix_version_var.set(item["display"])
                    print(f"Selected nightly build in dropdown: {item['display']}")
                    return
        
        print("No matching build found in dropdown")
    
    def unblock_events(self):
        """Unblock event handling after dropdown selection"""
        if hasattr(self, 'block_events'):
            self.block_events = False
    
    def trigger_version_update(self):
        """Trigger version update after UI is fully initialized"""
        print("Triggering version update...")
        
        # Make sure we have source_versions
        if not hasattr(self, 'source_versions') or not self.source_versions:
            if hasattr(self, 'active_build_path') and os.path.exists(self.active_build_path):
                self.source_versions = self.load_versions_from_file(self.active_build_path, True)
            else:
                print("No active build path found for version comparison")
                return
        
        # Now update all version tags
        self.update_all_version_tags()
        
        # Set the active build in the dropdown if needed
        if hasattr(self, 'remix_version_dropdown'):
            self.select_active_build_in_dropdown()
        else:
            print("No dropdown available for selection")
    
    def create_status_bar(self, parent):
        """Create Windows 11 style animated status bar"""
        self.status_bar = ttk.Frame(parent, style='TFrame')
        self.status_bar.pack(fill=tk.X, pady=(10,0), side=tk.BOTTOM)
        
        # Status text (left side)
        self.global_status = ttk.Label(
            self.status_bar, 
            text="Ready",
            style='Status.TLabel'
        )
        self.global_status.pack(side=tk.LEFT, padx=5)
        
        # Progress bar container
        self.progress_container = ttk.Frame(self.status_bar, width=200)
        self.progress_container.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        self.progress_container.pack_propagate(False)
        
        # Progress bar canvas
        self.progress_canvas = tk.Canvas(
            self.progress_container,
            height=4,
            bg=self.progress_colors['bg'],
            highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Progress variables
        self.progress_value = 0
        self.gradient_pos = 0
        self.animation_id = None
        self.gradient_segments = []
        
        # Initial empty progress
        self.update_progress(0)
    
    def update_progress(self, value, message=None):
        """Update progress bar with animation"""
        self.progress_value = max(0, min(100, value))
        
        if message:
            self.global_status.config(text=message)
        
        # Clear previous gradient
        for segment in self.gradient_segments:
            self.progress_canvas.delete(segment)
        self.gradient_segments = []
        
        # Calculate dimensions
        width = self.progress_canvas.winfo_width()
        progress_width = (width * self.progress_value) / 100
        
        # Create animated gradient effect
        if 0 < self.progress_value < 100:
            segment_width = width // 6
            for i in range(7):
                x0 = i * segment_width - self.gradient_pos
                x1 = (i+1) * segment_width - self.gradient_pos
                x0 = max(0, min(x0, progress_width))
                x1 = max(0, min(x1, progress_width))
                
                if x1 > x0:  # Only draw visible segments
                    # Color interpolation
                    ratio = i / 6
                    r = int(0x00 + (0x4C - 0x00) * ratio)
                    g = int(0x78 + (0xC2 - 0x78) * ratio)
                    b = int(0xD7 + (0xFF - 0xD7) * ratio)
                    color = f'#{r:02x}{g:02x}{b:02x}'
                    
                    segment = self.progress_canvas.create_rectangle(
                        x0, 0, x1, 4,
                        fill=color,
                        outline=color
                    )
                    self.gradient_segments.append(segment)
            
            # Animate gradient
            self.gradient_pos = (self.gradient_pos + 2) % segment_width
            self.animation_id = self.progress_canvas.after(50, lambda: self.update_progress(self.progress_value))
        else:
            # Solid color for 0% or 100%
            color = self.progress_colors['fill_start'] if self.progress_value <= 0 else self.progress_colors['fill_end']
            self.progress_canvas.create_rectangle(
                0, 0, progress_width, 4,
                fill=color,
                outline=color
            )
            
            if self.animation_id:
                self.progress_canvas.after_cancel(self.animation_id)
                self.animation_id = None
    
    def start_progress(self, message):
        """Start progress animation with simple approach to avoid errors"""
        self.global_status.config(text=message)
        self.progress_bar['value'] = 1  # Set a small initial value
        self.download_window.update()
    
    def complete_progress(self, message):
        """Complete progress with full bar"""
        self.global_status.config(text=message)
        self.progress_bar['value'] = 100
        self.download_window.update()
        # Reset after delay
        self.download_window.after(1500, lambda: self.reset_progress("Ready"))
    
    def reset_progress(self, message="Ready"):
        """Reset progress bar to 0"""
        self.progress_bar['value'] = 0
        self.global_status.config(text=message)
        self.download_window.update()
    
    def error_progress(self, message):
        """Show error state with simple approach"""
        self.global_status.config(text=message)
        self.progress_bar['value'] = 0  # Reset progress
        self.download_window.update()
    
    def fetch_release_versions(self):
        """Fetch release versions from GitHub"""
        try:
            # Show status
            self.global_status.config(text="Fetching available release builds...")
            
            url = "https://api.github.com/repos/NVIDIAGameWorks/rtx-remix/releases"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                releases = json.loads(response.read().decode())
            
            versions = []
            for release in releases:
                version_name = release['tag_name']
                version_date = release['published_at'][:10]  # YYYY-MM-DD
                
                # Check if this release build is already downloaded for any build type
                is_downloaded = False
                clean_tag = version_name.replace("remix-", "")
                
                # Check each build type folder
                for build_type in ["release", "debug", "debugoptimized"]:
                    build_path = os.path.join(self.remix_folder, "release", build_type, clean_tag)
                    if os.path.exists(build_path) and os.path.isdir(build_path) and self.is_rtx_remix_folder(build_path):
                        is_downloaded = True
                        break
                
                # Mark downloaded versions
                if is_downloaded:
                    versions.append(f"{version_name} ({version_date}) [DOWNLOADED]")
                else:
                    versions.append(f"{version_name} ({version_date})")
            
            self.release_version_combo['values'] = versions
            if versions:
                self.release_version_combo.current(0)
            self.release_status.config(text=f"Found {len(versions)} release versions")
            
            # Update global status
            self.global_status.config(text="Ready")
        except Exception as e:
            self.release_status.config(text=f"Error fetching releases: {str(e)}")
            self.global_status.config(text=f"Error: {str(e)}")
    
    def _update_release_versions(self, versions):
        """Update release version combobox"""
        self.release_version_combo['values'] = versions
        if versions:
            self.release_version_combo.current(0)
        self.release_status.config(text=f"Found {len(versions)} release versions")
        self.global_status.config(text="Ready")
    
    def on_tab_changed(self, event):
        """Handle tab selection in the download window"""
        tab_id = self.notebook.index(self.notebook.select())
        
        # Clear status
        self.global_status.config(text="")
        
        if tab_id == 0:  # Release tab
            # Fetch releases if we haven't yet
            if not self.release_version_combo.get():
                self.fetch_release_versions()
        else:  # Nightly tab
            # Fetch DXVK nightly builds if we haven't yet
            if not self.dxvk_combo.get():
                self.fetch_nightly_versions("dxvk-remix")
        
    def fetch_nightly_versions(self, repo):
        """Fetch available nightly versions from GitHub Actions"""
        self.global_status.config(text=f"Fetching available builds...")
        
        # Get the selected architecture
        selected_arch = self.nightly_arch_var.get() if hasattr(self, 'nightly_arch_var') else "x64"
        
        # Determine which dropdown to update based on repo type
        combo = self.dxvk_combo
        status_widget = self.dxvk_status
        component_type = "dxvk"
        
        # Clear previous values
        combo['values'] = []
        status_widget.config(text=f"Fetching {selected_arch} builds...")
        
        try:
            # Get builds from GitHub Actions
            url = f"https://api.github.com/repos/NVIDIAGameWorks/{repo}/actions/artifacts"
            
            # Try to fetch with stored token if available
            headers = {}
            if hasattr(self, 'github_token') and self.github_token:
                headers['Authorization'] = f"token {self.github_token}"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 401 or response.status_code == 403:
                # Token might be invalid or expired, clear it and retry without token
                self.github_token = None
                headers = {}
                response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"API error: HTTP {response.status_code} - {response.text}")
            
            data = response.json()
            # Limit to first 100 builds to avoid overwhelming the UI
            artifacts = data.get('artifacts', [])[:100]
            
            # Process artifacts and mark if they're already downloaded
            formatted_versions = []
            for artifact in artifacts:
                # Only show successful builds
                if artifact['expired']:
                    continue
                    
                name = artifact['name']
                
                # Filter by architecture for DXVK builds
                if selected_arch == "x64" and not ("x64" in name.lower() or "for-x64-games" in name.lower()):
                    continue
                if selected_arch == "x86" and not ("x86" in name.lower() or "for-x86-games" in name.lower()):
                    continue
                
                # Also ensure it's an RTX Remix build
                if not (name.startswith("rtx-remix-for-x64-games") or name.startswith("rtx-remix-for-x86-games")):
                    continue
                
                # Extract the build info (commit hash, build ID, etc.)
                build_info = ""
                commit_hash = ""
                build_type = "release"  # Default build type
                
                try:
                    # Split the name into parts
                    parts = name.split('-')
                    
                    # More robust method to find commit hash - look for a part that is 
                    # likely to be a git commit hash (typically 7+ hexadecimal chars)
                    for part in parts:
                        if len(part) >= 7 and all(c in '0123456789abcdef' for c in part[:7]):
                            commit_hash = part
                            break
                    
                    # Find build type - look for "release", "debugoptimized", or "debug"
                    for part in parts:
                        if part in ["release", "debugoptimized", "debug"]:
                            build_type = part
                            break
                    
                    # If we couldn't find a commit hash, generate one based on the artifact ID
                    if not commit_hash:
                        commit_hash = f"a{artifact['id']}"
                    
                    # Get the creation date
                    created_at = datetime.datetime.strptime(
                        artifact['created_at'], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    date_str = created_at.strftime("%Y-%m-%d %H:%M")
                    timestamp = created_at.timestamp()
                    
                    # Check if this build exists locally in the proper folder structure
                    is_downloaded = False
                    
                    # Full path to check: nightly/{component}/{arch}/{build_type}/{commit_hash}
                    expected_path = os.path.join(
                        self.remix_folder, 
                        "nightly", 
                        component_type, 
                        selected_arch, 
                        build_type, 
                        commit_hash
                    )
                    
                    if os.path.exists(expected_path) and os.path.isdir(expected_path):
                        # Check if it looks like an RTX Remix folder
                        is_downloaded = self.is_rtx_remix_folder(expected_path)
                        print(f"Checking {expected_path}: {is_downloaded}")
                    
                    # Format the build info - NEW FORMAT: Date first for better readability
                    arch_str = f"{selected_arch}"
                    # Format: "2025-05-13 12:30 | 64-bit | release | abc123f"
                    build_info = f"{date_str} | {arch_str}-bit | {build_type} | {commit_hash[:7]}"
                    
                    # Add [DOWNLOADED] mark if the build exists locally
                    if is_downloaded:
                        build_info += " [DOWNLOADED]"
                
                except Exception as e:
                    print(f"Error parsing artifact name: {e}")
                    # Fallback if parsing fails
                    build_info = name
                
                # Store the original artifact, commit hash, and build type for download
                formatted_versions.append({
                    "display": build_info,
                    "artifact": artifact,
                    "commit_hash": commit_hash,
                    "build_type": build_type,
                    "architecture": selected_arch,
                    "timestamp": timestamp,  # Store for sorting
                    "date_str": date_str     # Store for display
                })
            
            # Update the dropdown
            if formatted_versions:
                # Sort by creation date (newest first)
                formatted_versions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                
                # Extract display strings and set as dropdown values
                display_values = [item["display"] for item in formatted_versions]
                combo['values'] = display_values
                
                # Select the first (newest) option
                combo.current(0)
                status_widget.config(text=f"Found {len(formatted_versions)} {selected_arch} builds")
                
                # Store the mapping of display strings to artifact data for later use
                self.dxvk_artifact_map = {item["display"]: item for item in formatted_versions}
                    
                # Update the destination preview for the selected item
                self.update_destination_preview()
            else:
                status_widget.config(text=f"No {selected_arch} builds found")
                
        except Exception as e:
            error_msg = f"Error fetching builds: {str(e)}"
            print(error_msg)
            status_widget.config(text=error_msg)
        
        self.global_status.config(text="Ready")
        """Fetch available nightly versions from GitHub Actions"""
        self.global_status.config(text=f"Fetching available builds...")
        
        # Get the selected architecture
        selected_arch = self.nightly_arch_var.get() if hasattr(self, 'nightly_arch_var') else "x64"
        
        # Determine which dropdown to update based on repo type
        combo = self.dxvk_combo
        status_widget = self.dxvk_status
        component_type = "dxvk"
        
        # Clear previous values
        combo['values'] = []
        status_widget.config(text=f"Fetching {selected_arch} builds...")
        
        try:
            # Get builds from GitHub Actions
            url = f"https://api.github.com/repos/NVIDIAGameWorks/{repo}/actions/artifacts"
            
            # Try to fetch with stored token if available
            headers = {}
            if hasattr(self, 'github_token') and self.github_token:
                headers['Authorization'] = f"token {self.github_token}"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 401 or response.status_code == 403:
                # Token might be invalid or expired, clear it and retry without token
                self.github_token = None
                headers = {}
                response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"API error: HTTP {response.status_code} - {response.text}")
            
            data = response.json()
            # Limit to first 100 builds to avoid overwhelming the UI
            artifacts = data.get('artifacts', [])[:100]
            
            # Process artifacts and mark if they're already downloaded
            formatted_versions = []
            for artifact in artifacts:
                # Only show successful builds
                if artifact['expired']:
                    continue
                    
                name = artifact['name']
                
                # Filter by architecture for DXVK builds
                if selected_arch == "x64" and not ("x64" in name.lower() or "for-x64-games" in name.lower()):
                    continue
                if selected_arch == "x86" and not ("x86" in name.lower() or "for-x86-games" in name.lower()):
                    continue
                
                # Also ensure it's an RTX Remix build
                if not (name.startswith("rtx-remix-for-x64-games") or name.startswith("rtx-remix-for-x86-games")):
                    continue
                
                # Extract the build info (commit hash, build ID, etc.)
                build_info = ""
                commit_hash = ""
                build_type = "release"  # Default build type
                
                try:
                    # Split the name into parts
                    parts = name.split('-')
                    
                    # More robust method to find commit hash - look for a part that is 
                    # likely to be a git commit hash (typically 7+ hexadecimal chars)
                    for part in parts:
                        if len(part) >= 7 and all(c in '0123456789abcdef' for c in part[:7]):
                            commit_hash = part
                            break
                    
                    # Find build type - look for "release", "debugoptimized", or "debug"
                    for part in parts:
                        if part in ["release", "debugoptimized", "debug"]:
                            build_type = part
                            break
                    
                    # If we couldn't find a commit hash, generate one based on the artifact ID
                    if not commit_hash:
                        commit_hash = f"a{artifact['id']}"
                    
                    # Get the creation date
                    created_at = datetime.datetime.strptime(
                        artifact['created_at'], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    date_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Check if this build exists locally in the proper folder structure
                    is_downloaded = False
                    
                    # Full path to check: nightly/{component}/{arch}/{build_type}/{commit_hash}
                    expected_path = os.path.join(
                        self.remix_folder, 
                        "nightly", 
                        component_type, 
                        selected_arch, 
                        build_type, 
                        commit_hash
                    )
                    
                    if os.path.exists(expected_path) and os.path.isdir(expected_path):
                        # Check if it looks like an RTX Remix folder
                        is_downloaded = self.is_rtx_remix_folder(expected_path)
                        print(f"Checking {expected_path}: {is_downloaded}")
                    
                    # Format the build info 
                    arch_str = f"({selected_arch})"
                    build_info = f"{commit_hash} {arch_str} Build ({date_str}) - {build_type}"
                    
                    # Add [DOWNLOADED] mark if the build exists locally
                    if is_downloaded:
                        build_info += " [DOWNLOADED]"
                
                except Exception as e:
                    print(f"Error parsing artifact name: {e}")
                    # Fallback if parsing fails
                    build_info = name
                
                # Store the original artifact, commit hash, and build type for download
                formatted_versions.append({
                    "display": build_info,
                    "artifact": artifact,
                    "commit_hash": commit_hash,
                    "build_type": build_type,
                    "architecture": selected_arch
                })
            
            # Update the dropdown
            if formatted_versions:
                # Sort by creation date (newest first)
                formatted_versions.sort(key=lambda x: x["artifact"]["created_at"], reverse=True)
                
                # Extract display strings and set as dropdown values
                display_values = [item["display"] for item in formatted_versions]
                combo['values'] = display_values
                
                # Select the first (newest) option
                combo.current(0)
                status_widget.config(text=f"Found {len(formatted_versions)} {selected_arch} builds")
                
                # Store the mapping of display strings to artifact data for later use
                self.dxvk_artifact_map = {item["display"]: item for item in formatted_versions}
                    
                # Update the destination preview for the selected item
                self.update_destination_preview()
            else:
                status_widget.config(text=f"No {selected_arch} builds found")
                
        except Exception as e:
            error_msg = f"Error fetching builds: {str(e)}"
            print(error_msg)
            status_widget.config(text=error_msg)
        
        self.global_status.config(text="Ready")

def check_python_version():
    """Check if Python version is adequate"""
    root = tk.Tk()
    root.withdraw()
    
    if sys.version_info < (3, 8):
        messagebox.showerror(
            "Version Error",
            "Your Python version is too old. Please download Python 3.8 or newer."
        )
        root.destroy()
        return False
    root.destroy()
    return True
    


if __name__ == "__main__":
    if not check_python_version():
        sys.exit(1)
        
    # Main window setup
    root = tk.Tk()
    
    # Set window icon (optional)
    try:
        root.iconbitmap('nvidia.ico')
    except:
        pass
        
    app = lazy_rtx_remix_companion(root)
    firstLaunch = False
    root.mainloop()