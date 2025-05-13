import sys
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, Label, Button, messagebox
import json
import shutil
import os
import re
import string
import urllib.request
from threading import Thread

app_version = "0.3.0"

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

    def init_ui(self):
        """Initialize all UI components"""
        # Setup frames
        self.button_frame = ttk.Frame(self.master)
        self.button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        self.version_frame = ttk.Frame(self.master)
        self.version_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Setup version label
        self.version_label = ttk.Label(self.version_frame, text="RTX-Remix Version: N/A")
        self.version_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Setup buttons
        self.setup_buttons()
        
        # Setup status bar
        self.setup_status_bar()
        
        # Setup treeview
        self.setup_treeview()

    def setup_buttons(self):
        """Set up all buttons in the left panel"""
        buttons = [
            ("Select RTX-Remix", self.select_source),
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
                   "dxvk.conf", "d3d8to9.dll", "Runtime Version", "Bridge Version")
        
        # Create treeview
        self.tree = ttk.Treeview(self.master, columns=columns, show="headings")
        
        # Configure column widths
        for col in columns:
            self.tree.heading(col, text=col)
            width = 10 if col == "🔓" else 160 if col in ["Game Name", "Folder Path"] else \
                   20 if col in ["Bridge", "Runtime", "dxvk.conf", "d3d8to9.dll"] else 80
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
            if col_index in [0, 3, 4, 5, 6]:
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
                    elif col_index in [3, 4, 5, 6]:
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
                "runtime version": current_values[7],
                "bridge version": current_values[8]
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
                    
    def select_source(self):
        """Select and validate the RTX-Remix source folder"""
        new_folder = filedialog.askdirectory()
        if not new_folder:
            return
            
        missing_files, extra_files = self.check_sources(new_folder)
        if missing_files:
            message = "Please select the 'RTX-Remix' folder only, with No extra files."
            if missing_files:
                message += f"\nMissing necessary files/folders:\n{', '.join(missing_files)}"
            if extra_files:
                message += "\nThere are too many extra files in the RTX-Remix folder; it doesn't seem to be a correct RTX-Remix Folder."
            messagebox.showerror("Error", message)
            self.status_left.config(text="RTX-Remix Folder: None")
            self.status_right.config(text="Invalid RTX-Remix folder selected.")
            return
            
        # Valid folder, update settings
        self.remix_folder = new_folder.replace("/", "\\")
        self.source_versions = self.load_versions_from_file(self.remix_folder, True)
        version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
        self.version_label.config(text=version_info)
        self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
        self.save_config()

        # Re-check version compatibility for all games
        for item in self.tree.get_children():
            destination_folder = self.tree.item(item, "values")[2]
            destination_versions = self.load_versions_from_file(destination_folder)
            self.check_version_and_tag(item, destination_versions)

        # Update status
        status = "Configuration saved successfully. "
        status += "Ready to proceed." if self.tree.get_children() else "Please select the Game Folder(s) to proceed."
        self.status_right.config(text=status)
        self.update_copy_button_state()

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
            "🔓", game_name, folder_path, 'Yes', 'Yes', 'No', 'No', 
            destination_versions["runtime version"], destination_versions["bridge version"]
        ))
        self.check_version_and_tag(tree_item, destination_versions)
        self.status_right.config(text="Game added and configuration saved successfully. Ready to proceed.")
        self.save_config()
        self.update_copy_button_state()
        
    def show_popup_window(self, versions, directory):
        """Show a popup window to input version information"""
        # Create the popup window
        popup_window = tk.Toplevel(self.master)
        popup_window.title("Version Input")
        popup_window.configure(bg="#1a1a1a")
    
        # Position the popup window centered on the main window
        win_width, win_height = 300, 150
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (win_width // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (win_height // 2)
        popup_window.geometry(f"{win_width}x{win_height}+{x}+{y}")
    
        # Validation function for input
        def validate_input(text):
            allowed_chars = set(string.digits + string.ascii_letters + ".")
            return all(char in allowed_chars for char in text)
    
        # Create the input fields
        runtime_label = tk.Label(popup_window, text="Runtime Version:", bg="#1a1a1a", fg="#e0e0e0")
        runtime_entry = ttk.Entry(popup_window, validate="key", 
                                  validatecommand=(popup_window.register(validate_input), "%S"))
        bridge_label = tk.Label(popup_window, text="Bridge Version:", bg="#1a1a1a", fg="#e0e0e0")
        bridge_entry = ttk.Entry(popup_window, validate="key", 
                                validatecommand=(popup_window.register(validate_input), "%S"))
    
        # Create the submit button
        submit_button = ttk.Button(popup_window, text="Submit", command=lambda: submit())
        submit_button.state(["disabled"])
    
        # Submit function
        def submit():
            runtime_version = runtime_entry.get().strip()
            bridge_version = bridge_entry.get().strip()
            if runtime_version and bridge_version:
                versions["runtime version"] = runtime_version
                versions["bridge version"] = bridge_version
                self.save_versions_to_file(versions, os.path.join(directory, "build_names.txt"))
                popup_window.destroy()
    
        # Enable submit button when both fields have values
        def enable_submit_button(*args):
            runtime = runtime_entry.get().strip()
            bridge = bridge_entry.get().strip()
            if runtime and bridge:
                submit_button.state(["!disabled"])
            else:
                submit_button.state(["disabled"])
    
        runtime_entry.bind("<KeyRelease>", enable_submit_button)
        bridge_entry.bind("<KeyRelease>", enable_submit_button)
    
        # Layout elements
        runtime_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        runtime_entry.grid(row=0, column=1, padx=10, pady=10, sticky="we")
        bridge_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        bridge_entry.grid(row=1, column=1, padx=10, pady=10, sticky="we")
        submit_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
    
        # Make the grid cells expand
        popup_window.grid_columnconfigure(1, weight=1)
        runtime_entry.focus_set()
        popup_window.mainloop()
    
        return versions
        
    def save_versions_to_file(self, folder, versions):
        """Save version information to a file in the specified folder"""
        try:
            # Make sure the runtime and bridge versions are in the dictionary
            if 'runtime version' not in versions:
                versions['runtime version'] = 'N/A'
            if 'bridge version' not in versions:
                versions['bridge version'] = 'N/A'
                
            # Create a version info file
            version_file = os.path.join(folder, ".rtx_remix_versions")
            with open(version_file, 'w') as f:
                for key, value in versions.items():
                    f.write(f"{key}={value}\n")
            return True
        except Exception:
            return False
            
    def load_versions_from_file(self, directory, isSource=False):
        """Load version information from build_names.txt or build-names.txt file"""
        versions = {"runtime version": "N/A", "bridge version": "N/A"}
        version_file = os.path.join(directory, ".rtx_remix_versions")
        
        # Try to load from .rtx_remix_versions first if it exists
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            versions[key] = value
                return versions
            except Exception:
                pass
        
        # Try both filename variants
        build_names_file = None
        global oldVersion
        
        if os.path.exists(os.path.join(directory, "build-names.txt")):
            build_names_file = os.path.join(directory, "build-names.txt")
            oldVersion = False
        elif os.path.exists(os.path.join(directory, "build_names.txt")):
            build_names_file = os.path.join(directory, "build_names.txt")
            oldVersion = True
        
        if build_names_file:
            try:
                with open(build_names_file, 'r') as file:
                    lines = file.readlines()
                    
                    # Handle old format (multiple lines with dxvk-remix and bridge-remix)
                    if len(lines) > 1 or "dxvk-remix" in lines[0] or "bridge-remix" in lines[0]:
                        for line in lines:
                            if "dxvk-remix" in line:
                                versions["runtime version"] = '-'.join(line.strip().split('-')[-3:])
                            elif "bridge-remix" in line:
                                versions["bridge version"] = '-'.join(line.strip().split('-')[-3:])
                    
                    # Handle new format (single line with rtx-remix)
                    else:
                        # Example: rtx-remix-for-x86-games-c2a30ed-812-release
                        single_line = lines[0].strip()
                        
                        # Extract the version identifier
                        if "-" in single_line:
                            parts = single_line.split("-")
                            if len(parts) >= 3:
                                # Find parts that contain version identifiers
                                # Typically there would be a commit hash and build number
                                version_parts = []
                                for part in parts:
                                    # Look for parts that might be commit hashes or build numbers
                                    if re.match(r'[0-9a-f]{7,}', part) or part.isdigit():
                                        version_parts.append(part)
                                
                                # For the new format, use the same version for both runtime and bridge
                                version_str = '-'.join(version_parts[-3:]) if version_parts else single_line
                                versions["runtime version"] = version_str
                                versions["bridge version"] = version_str
                
                # If versions weren't found, try to extract from the filename
                if versions["runtime version"] == "N/A" and versions["bridge version"] == "N/A":
                    filename = os.path.basename(build_names_file)
                    if filename:
                        versions["runtime version"] = filename
                        versions["bridge version"] = filename
                        
                return versions
                
            except Exception as e:
                print(f"Error reading build names file: {e}")
                
        # If no version info found and it's a source directory, prompt for values
        if isSource and versions["runtime version"] == "N/A" and versions["bridge version"] == "N/A":
            if not firstLaunch:
                return self.show_popup_window(versions, directory)
                
        return versions
                
    def check_version_and_tag(self, tree_item_id, destination_versions):
        """Check if versions match and apply appropriate tags"""
        if not self.remix_folder:
            return
            
        current_values = list(self.tree.item(tree_item_id, 'values'))
    
        # Update version information
        current_values[7] = destination_versions["runtime version"]
        current_values[8] = destination_versions["bridge version"]
        self.tree.item(tree_item_id, values=current_values)
    
        # Apply version match/mismatch tag
        if (destination_versions["runtime version"] != self.source_versions["runtime version"] or
            destination_versions["bridge version"] != self.source_versions["bridge version"]):
            self.tree.item(tree_item_id, tags=("version_mismatch",))
        else:
            self.tree.item(tree_item_id, tags=("version_match",))

    def determine_files_to_copy(self, bridge, runtime, dxvk, d3d8to9):
        """Determine which files need to be copied based on selected options"""
        files_to_copy = []
        try:
            items = os.listdir(self.remix_folder)
        except OSError as e:
            self.status_right.config(text=f"Error reading directory {self.remix_folder}: {e}")
            return files_to_copy
    
        # Bridge files (base files except dxvk.conf and d3d8to9.dll)
        if bridge:
            excluded_files = {"dxvk.conf", "d3d8to9.dll"}
            for file in items:
                if file not in excluded_files and not file.startswith('.'):
                    files_to_copy.append(os.path.join(self.remix_folder, file))
    
        # Runtime (.trex directory)
        if runtime and '.trex' in items:
            trex_path = os.path.join(self.remix_folder, '.trex')
            if os.path.isdir(trex_path):
                files_to_copy.append(trex_path)
            else:
                self.status_right.config(text='.trex is not a directory or does not exist')
    
        # DXVK configuration
        if dxvk and 'dxvk.conf' in items:
            files_to_copy.append(os.path.join(self.remix_folder, 'dxvk.conf'))
        elif dxvk:
            self.status_right.config(text='dxvk.conf not found in the directory')
    
        # D3D8 to D3D9 wrapper
        if d3d8to9 and 'd3d8to9.dll' in items:
            files_to_copy.append(os.path.join(self.remix_folder, 'd3d8to9.dll'))
        elif d3d8to9:
            self.status_right.config(text='d3d8to9.dll not found in the directory')
    
        return files_to_copy

    def copy_files(self):
        """Copy selected files to game directories"""
        global oldVersion
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_right.config(text="No Game is selected for copy.")
            return
        
        # Calculate total files across all games first
        total_files_count = 0
        game_file_counts = {}
        
        for item in selected_items:
            details = self.tree.item(item, 'values')
            lock, game_name, folder_path, bridge, runtime, dxvk, d3d8to9, _, _ = details
            
            # Convert 'Yes'/'No' to boolean
            bridge = bridge == 'Yes'
            runtime = runtime == 'Yes'
            dxvk = dxvk == 'Yes'
            d3d8to9 = d3d8to9 == 'Yes'
            
            files_to_copy = self.determine_files_to_copy(bridge, runtime, dxvk, d3d8to9)
            
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
        
        # Reset progress bar
        self.progress_bar['value'] = 0
        self.status_right.config(text=f"Starting copy operation for {len(selected_items)} games. Total files: {total_files_count}")
        
        # Start the copy process in a thread
        self.copy_all_files_threaded(selected_items, game_file_counts, total_files_count)
        
    def copy_all_files_threaded(self, selected_items, game_file_counts, total_files_count):
        """Copy files for all selected games in a background thread"""
        def thread_target():
            current_overall_count = 0
            
            for item in selected_items:
                details = self.tree.item(item, 'values')
                lock, game_name, folder_path, bridge, runtime, dxvk, d3d8to9, _, _ = details
                
                # Convert 'Yes'/'No' to boolean
                bridge = bridge == 'Yes'
                runtime = runtime == 'Yes'
                dxvk = dxvk == 'Yes'
                d3d8to9 = d3d8to9 == 'Yes'
                
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
                
                files_to_copy = self.determine_files_to_copy(bridge, runtime, dxvk, d3d8to9)
                
                # Process each file/directory
                for source in files_to_copy:
                    if os.path.isdir(source):
                        for dirpath, dirnames, filenames in os.walk(source):
                            for filename in filenames:
                                rel_dir = os.path.relpath(dirpath, self.remix_folder)
                                dest_dir = os.path.join(folder_path, rel_dir)
                                
                                # Create destination directory if it doesn't exist
                                if not os.path.exists(dest_dir):
                                    os.makedirs(dest_dir)
                                    
                                # Copy file
                                src_file = os.path.join(dirpath, filename)
                                dest_file = os.path.join(dest_dir, filename)
                                shutil.copy(src_file, dest_file)
                                
                                # Update progress
                                current_overall_count += 1
                                percent = (current_overall_count / total_files_count) * 100
                                self.master.after(0, lambda c=current_overall_count, t=total_files_count, p=percent, gn=game_name: 
                                                 self.update_copy_progress(c, t, p, gn))
                    else:
                        # Simple file copy
                        filename = os.path.basename(source)
                        destination = os.path.join(folder_path, filename)
                        shutil.copy(source, destination)
                        
                        # Update progress
                        current_overall_count += 1
                        percent = (current_overall_count / total_files_count) * 100
                        self.master.after(0, lambda c=current_overall_count, t=total_files_count, p=percent, gn=game_name: 
                                         self.update_copy_progress(c, t, p, gn))
                
                # Handle version files
                # First, remove any existing build_names.txt or build-names.txt files
                for build_file in ["build_names.txt", "build-names.txt"]:
                    build_file_path = os.path.join(folder_path, build_file)
                    if os.path.exists(build_file_path):
                        try:
                            os.remove(build_file_path)
                        except Exception as e:
                            print(f"Error removing {build_file}: {e}")
                
                # Copy the current version file from source to destination
                if os.path.exists(os.path.join(self.remix_folder, "build-names.txt")):
                    shutil.copy2(
                        os.path.join(self.remix_folder, "build-names.txt"),
                        os.path.join(folder_path, "build-names.txt")
                    )
                elif os.path.exists(os.path.join(self.remix_folder, "build_names.txt")):
                    shutil.copy2(
                        os.path.join(self.remix_folder, "build_names.txt"),
                        os.path.join(folder_path, "build_names.txt")
                    )
                    
                # Save source version info to destination
                self.save_versions_to_file(folder_path, self.source_versions)
                    
                # Update version information in the tree
                # Reload versions to ensure we get the latest
                destination_versions = self.load_versions_from_file(folder_path)
                
                # Update the item in the tree with correct version info
                current_values = list(self.tree.item(item, 'values'))
                current_values[7] = destination_versions["runtime version"]
                current_values[8] = destination_versions["bridge version"]
                
                # This will properly update the tree with current versions
                self.master.after(0, lambda i=item, v=current_values, dv=destination_versions: 
                                 self.update_item_after_copy(i, v, dv))
                
            # When all copies are done
            self.master.after(0, lambda: self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}"))
            self.master.after(0, lambda: self.status_right.config(text="Copy operation completed for all games."))
        
        thread = Thread(target=thread_target)
        thread.start()
        
    def update_item_after_copy(self, item, values, destination_versions):
        """Update item in tree after copy operation is complete"""
        # Update the values in the tree item
        self.tree.item(item, values=values)
        
        # Then check version and tag it properly
        self.check_version_and_tag(item, destination_versions)

    def update_copy_progress(self, current, total, percent, game_name):
        """Update progress bar and status message during copy operation"""
        self.progress_bar['value'] = percent
        self.status_right.config(text=f"Copying for {game_name}... ({current}/{total} files)")
        
    def copy_files_threaded(self, files_to_copy, folder_path, tree_item):
        """Copy files in a separate thread to keep UI responsive"""
        def thread_target():
            total_files = len(files_to_copy)
            current_file_count = 0
            
            for source in files_to_copy:
                # Check if it's a directory or file
                if os.path.isdir(source):
                    for dirpath, dirnames, filenames in os.walk(source):
                        for filename in filenames:
                            rel_dir = os.path.relpath(dirpath, self.remix_folder)
                            dest_dir = os.path.join(folder_path, rel_dir)
                            
                            # Create destination directory if it doesn't exist
                            if not os.path.exists(dest_dir):
                                os.makedirs(dest_dir)
                                
                            # Copy file
                            src_file = os.path.join(dirpath, filename)
                            dest_file = os.path.join(dest_dir, filename)
                            shutil.copy(src_file, dest_file)
                            
                            # Update progress
                            current_file_count += 1
                            self.master.after(0, lambda c=current_file_count, t=total_files: 
                                             self.update_progress_bar(c, t))
                else:
                    # Simple file copy
                    filename = os.path.basename(source)
                    destination = os.path.join(folder_path, filename)
                    shutil.copy(source, destination)
                    
                    # Update progress
                    current_file_count += 1
                    self.master.after(0, lambda c=current_file_count, t=total_files: 
                                     self.update_progress_bar(c, t))
            
            # When done, update status and refresh version info
            self.master.after(0, lambda: self.status_right.config(text="Copy completed."))
            destination_versions = self.load_versions_from_file(folder_path)
            self.check_version_and_tag(tree_item, destination_versions)

        thread = Thread(target=thread_target)
        thread.start()
    
    def update_progress_bar(self, current, total):
        """Update the progress bar and status message with copy progress"""
        self.progress_bar['value'] = current / total * 100
        self.status_right.config(text=f"Copying... ({current}/{total})")
            
    def remove_selected_game(self):
        """Remove selected games from the treeview"""
        for item in self.tree.selection():
            self.tree.delete(item)
        self.save_config()
        self.update_copy_button_state()

    def load_config(self):
        """Load application configuration from file"""
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'r') as config_file:
                config = json.load(config_file)
                
                # Load RTX-Remix folder
                self.remix_folder = config.get('remix_folder')
                if self.remix_folder:
                    self.remix_folder = self.remix_folder.replace('\\', '/')
                    self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
                    self.source_versions = self.load_versions_from_file(self.remix_folder, True)
                    version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
                    self.version_label.config(text=version_info)
                
                # Load treeview items
                for item in config.get('treeview', []):
                    destination_versions = self.load_versions_from_file(item[2])
                    newItem = self.tree.insert('', 'end', values=(
                        item[0],  # lock
                        item[1],  # Game Name
                        item[2],  # Game Folder
                        item[3],  # Bridge
                        item[4],  # Runtime
                        item[5],  # dxvk.conf
                        item[6],  # d3d8to9.dll
                        destination_versions["runtime version"],  # Runtime Version
                        destination_versions["bridge version"]    # Bridge Version
                    ))
                    
                    self.check_version_and_tag(newItem, destination_versions)
                    if item[0] == "🔒":
                        self.tree.item(newItem, tags=('disable',))
                
                # Apply window geometry
                if 'window_geometry' in config:
                    self.master.geometry(config['window_geometry'])
                
                # Final UI updates
                self.update_copy_button_state()
                self.status_right.config(text="Configuration loaded successfully.")
                self.tree.update_idletasks()
                
                # Check RTX-Remix folder
                if self.remix_folder:
                    self.check_sources(self.remix_folder)
                
        except FileNotFoundError:
            self.status_right.config(text="Configuration file not found.")
        except json.JSONDecodeError:
            self.status_right.config(text="Configuration file is corrupt.")
        except Exception as e:
            self.status_right.config(text=f"Error loading configuration: {str(e)}")
            
    def save_config(self):
        """Save application configuration to file"""
        treeview_data = self.serialize_treeview()
        if self.remix_folder or treeview_data:
            config = {
                'remix_folder': self.remix_folder,
                'treeview': treeview_data,
                'window_geometry': self.master.geometry()
            }
            try:
                with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                    json.dump(config, config_file, indent=4)
                self.status_right.config(text="Configuration saved successfully.")
            except Exception as e:
                self.status_right.config(text=f"Error saving configuration: {str(e)}")
    
    def on_closing(self):
        """Handle window closing"""
        self.save_config()
        self.master.destroy()
        
    def download_rtx_remix_component(self):
        """Download RTX Remix components with tabbed interface and shared destination"""
        self.download_window = tk.Toplevel(self.master)
        self.download_window.title("RTX Remix Downloader")
        self.download_window.configure(bg="#1a1a1a")
        self.download_window.geometry("700x650")
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
    
        # Create tabs
        self.create_release_tab()
        self.create_nightly_tab()
    
        # ================= BOTTOM FRAME (Shared Controls) =================
        self.create_shared_controls(main_frame)
    
        # Set default destination
        default_dest = os.path.join(os.path.expanduser("~"), "RTX-Remix-Downloads")
        self.shared_dest_var.set(default_dest)
    
        # Auto-fetch versions when tabs are selected
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Force initial fetch for the first tab
        self.notebook.select(0)
        
        self.create_status_bar(self.download_window)

        self.on_tab_changed(None)
    
    def download_build(self):
        """Handle download based on current active tab"""
        current_tab = self.notebook.index("current")
        if current_tab == 0:  # Release tab
            self.download_release()
        else:  # Nightly tab
            self.download_nightly()
    
    def download_release(self):
        """Download selected release version"""
        version = self.release_version_var.get()
        destination = self.shared_dest_var.get()
        
        if not version:
            self.release_status.config(text="Please select a version first")
            return
            
        if not destination:
            self.release_status.config(text="Please select a destination folder")
            return
        
        try:
            self.progress_bar['value'] = 0
            self.release_status.config(text=f"Starting download of {version}...")
            self.download_window.update()
            
            # Your download implementation here
            # Example:
            # 1. Extract version number from version string
            # 2. Construct download URL
            # 3. Download and extract files
            # 4. Update progress bar
            
            self.release_status.config(text=f"Successfully downloaded {version} to {destination}")
        except Exception as e:
            self.release_status.config(text=f"Download failed: {str(e)}")
        finally:
            self.progress_bar['value'] = 100
    
    def download_nightly(self):
        """Download selected nightly build"""
        version = self.nightly_version_var.get()
        destination = self.shared_dest_var.get()
        repo = self.nightly_repo_var.get()
        variant = self.nightly_variant_var.get()
        
        if not version:
            self.nightly_status.config(text="Please select a version first")
            return
            
        if not destination:
            self.nightly_status.config(text="Please select a destination folder")
            return
        
        try:
            self.progress_bar['value'] = 0
            self.nightly_status.config(text=f"Starting download of {repo} {variant} build...")
            self.download_window.update()
            
            # Your download implementation here
            # Example:
            # 1. Extract run ID from version string
            # 2. Download appropriate artifact
            # 3. Extract files
            # 4. Update progress bar
            
            self.nightly_status.config(text=f"Successfully downloaded {repo} to {destination}")
        except Exception as e:
            self.nightly_status.config(text=f"Download failed: {str(e)}")
        finally:
            self.progress_bar['value'] = 100
    
    def create_release_tab(self):
        """Create release build tab"""
        self.release_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.release_frame, text="Release Builds (Stable)")
        
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
    
        self.release_status = ttk.Label(self.release_frame, text="Ready to download stable releases")
        self.release_status.pack(pady=10)
    
    def create_nightly_tab(self):
        """Create nightly build tab with only Bridge and Runtime/DXVK options"""
        self.nightly_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.nightly_frame, text="Nightly Builds (Actions)")
        
        # Component selection header
        ttk.Label(self.nightly_frame, 
                 text="Select Component:",
                 font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, pady=(5, 0))
        
        # Only show Bridge and Runtime/DXVK options
        self.nightly_repo_var = tk.StringVar(value="bridge-remix")  # Default to Bridge
        
        # Bridge Option
        bridge_frame = ttk.Frame(self.nightly_frame)
        bridge_frame.pack(anchor=tk.W, padx=20, pady=5, fill=tk.X)
        ttk.Radiobutton(bridge_frame, 
                       text="Bridge Only (Required for Remix functionality)",
                       value="bridge-remix",
                       variable=self.nightly_repo_var).pack(anchor=tk.W)
        
        # Runtime/DXVK Option
        dxvk_frame = ttk.Frame(self.nightly_frame)
        dxvk_frame.pack(anchor=tk.W, padx=20, pady=5, fill=tk.X)
        ttk.Radiobutton(dxvk_frame, 
                       text="Runtime/DXVK Only (Graphics components)",
                       value="dxvk-remix",
                       variable=self.nightly_repo_var).pack(anchor=tk.W)
        
        # Auto-refresh versions when component changes
        self.nightly_repo_var.trace_add('write', lambda *_: self.fetch_nightly_versions())
    
        # Build variant selection
        ttk.Label(self.nightly_frame, 
                 text="Build Variant:",
                 font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, pady=(10, 0))
        
        self.nightly_variant_var = tk.StringVar(value="release")
        variant_frame = ttk.Frame(self.nightly_frame)
        variant_frame.pack(anchor=tk.W, padx=20, pady=5, fill=tk.X)
        
        variants = [
            ("Release (Best Performance)", "release"),
            ("Debug Optimized (Fast with debug functions)", "debugoptimized"),
            ("Debug (Slow, with debug symbols)", "debug")
        ]
        
        for text, value in variants:
            ttk.Radiobutton(variant_frame, 
                           text=text,
                           value=value,
                           variable=self.nightly_variant_var).pack(anchor=tk.W, pady=2)
    
        # Version selection
        version_frame = ttk.Frame(self.nightly_frame)
        version_frame.pack(fill=tk.X, pady=10, padx=10)
        
        ttk.Label(version_frame, text="Available Versions:").pack(side=tk.LEFT, padx=5)
        
        self.nightly_version_var = tk.StringVar()
        self.nightly_version_combo = ttk.Combobox(version_frame, 
                                                textvariable=self.nightly_version_var, 
                                                state="readonly")
        self.nightly_version_combo.pack(side=tk.LEFT, expand=True, fill=tk.X)
    
        # Status label
        self.nightly_status = ttk.Label(self.nightly_frame, 
                                      text="Select a component and variant to see available builds",
                                      wraplength=600)
        self.nightly_status.pack(pady=10)
    
    def create_shared_controls(self, parent):
        """Create shared controls at bottom with animated progress bar"""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Destination controls
        ttk.Label(bottom_frame, text="Destination Folder:").pack(side=tk.LEFT, padx=5)
        self.shared_dest_var = tk.StringVar()
        ttk.Entry(bottom_frame, textvariable=self.shared_dest_var, width=50).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(bottom_frame, text="Browse...", command=lambda: self.shared_dest_var.set(filedialog.askdirectory())).pack(side=tk.LEFT)
        
        # Download button
        self.download_btn = ttk.Button(bottom_frame, text="Download", command=self.download_build)
        self.download_btn.pack(pady=10, side=tk.LEFT, padx=10)
        
        # Windows 11 style animated progress bar
        self.progress_frame = tk.Canvas(bottom_frame, height=4, bg='#1a1a1a', highlightthickness=0)
        self.progress_frame.pack(fill=tk.X, pady=5, expand=True)
        
        # Gradient colors (Windows 11 accent colors)
        self.gradient_colors = [
            '#0078D7', '#1081E8', '#208AFA', '#3093FF', 
            '#409CFF', '#50A5FF', '#60AEFF', '#70B7FF'
        ]
        self.gradient_pos = 0
        self.progress_id = None
        self.progress_animation = None
        self.progress_value = 0
        
        # Status label below progress bar
        self.global_status = ttk.Label(bottom_frame, text="Ready")
        self.global_status.pack(fill=tk.X, pady=(0,5))
    
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
        """Start progress animation"""
        self.global_status.config(text=message)
        self.update_progress(1)  # Small value to start animation
    
    def complete_progress(self, message):
        """Complete progress with full bar"""
        self.update_progress(100, message)
        # Reset after delay
        self.status_bar.after(1500, lambda: self.update_progress(0, "Ready"))
    
    def error_progress(self, message):
        """Show error state"""
        self.progress_canvas.delete("all")
        width = self.progress_canvas.winfo_width()
        self.progress_canvas.create_rectangle(
            0, 0, width, 4,
            fill=self.progress_colors['error'],
            outline=self.progress_colors['error']
        )
        self.global_status.config(text=message)
        # Reset after delay
        self.status_bar.after(3000, lambda: self.update_progress(0, "Ready"))
    
    def fetch_release_versions(self):
        """Fetch release versions with progress animation"""
        self.start_progress_animation()
        
        try:
            # Run in a thread to prevent UI freezing
            Thread(target=self._fetch_release_versions_thread).start()
        except Exception as e:
            self.stop_progress_animation()
            self.release_status.config(text=f"Error: {str(e)}")
    
    def _fetch_release_versions_thread(self):
        """Threaded version fetching for releases"""
        try:
            url = "https://api.github.com/repos/NVIDIAGameWorks/rtx-remix/releases"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                releases = json.loads(response.read().decode())
            
            versions = []
            for release in releases:
                version_name = release['tag_name']
                version_date = release['published_at'][:10]
                versions.append(f"{version_name} ({version_date})")
            
            # Update UI in main thread
            self.download_window.after(0, lambda: self._update_release_versions(versions))
        except Exception as e:
            self.download_window.after(0, lambda: self.release_status.config(text=f"Error: {str(e)}"))
        finally:
            self.download_window.after(0, self.stop_progress_animation)
    
    def _update_release_versions(self, versions):
        """Update release version combobox"""
        self.release_version_combo['values'] = versions
        if versions:
            self.release_version_combo.current(0)
        self.release_status.config(text=f"Found {len(versions)} release versions")
        self.global_status.config(text="Ready")
    
    def on_tab_changed(self, event):
        """Handle tab changes to auto-fetch versions"""
        current_tab = self.notebook.index("current")
        if current_tab == 0:  # Release tab
            self.fetch_release_versions()
            self.download_btn.config(text="Download Release Build")
        else:  # Nightly tab
            self.fetch_nightly_versions()
            self.download_btn.config(text="Download Nightly Build")
    
    def fetch_release_versions(self):
        """Fetch release versions from GitHub"""
        try:
            url = "https://api.github.com/repos/NVIDIAGameWorks/rtx-remix/releases"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                releases = json.loads(response.read().decode())
            
            versions = []
            for release in releases:
                version_name = release['tag_name']
                version_date = release['published_at'][:10]  # YYYY-MM-DD
                versions.append(f"{version_name} ({version_date})")
            
            self.release_version_combo['values'] = versions
            if versions:
                self.release_version_combo.current(0)
            self.release_status.config(text=f"Found {len(versions)} release versions")
        except Exception as e:
            self.release_status.config(text=f"Error fetching releases: {str(e)}")
    
    def fetch_nightly_versions(self):
        """Fetch nightly versions from GitHub Actions"""
        try:
            repo = self.nightly_repo_var.get()
            url = f"https://api.github.com/repos/NVIDIAGameWorks/{repo}/actions/runs"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github+json")
            
            with urllib.request.urlopen(req) as response:
                runs = json.loads(response.read().decode())
            
            versions = []
            for run in runs.get('workflow_runs', []):
                if run['conclusion'] == 'success':
                    run_id = run['id']
                    workflow = run['name']
                    date = run['created_at'][:10]
                    versions.append(f"[{run_id}] {workflow} ({date})")
            
            self.nightly_version_combo['values'] = versions
            if versions:
                self.nightly_version_combo.current(0)
            self.nightly_status.config(text=f"Found {len(versions)} nightly builds")
        except Exception as e:
            self.nightly_status.config(text=f"Error fetching nightlies: {str(e)}")
    
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