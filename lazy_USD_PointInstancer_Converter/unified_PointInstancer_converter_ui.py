#!/usr/bin/env python3
"""
Unified USD PointInstancer Converter UI - Professional Clean Design
Beautiful single-page layout with proper proportions and clean styling
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import threading
import subprocess
from unified_PointInstancer_converter import CleanUnifiedConverter

class UnifiedConverterUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔧 lazy_USD_PointInstancer_Converter")
        self.root.geometry("900x1000")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(True, True)
        
        # Settings file path
        self.settings_file = os.path.join(os.path.dirname(__file__), 'converter_settings.json')
        
        # Variables for both modes
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.folder_input_dir = tk.StringVar()
        self.folder_output_dir = tk.StringVar()
        # Remember last directories for single file mode
        self.last_input_dir = ""
        self.last_output_dir = ""
        self.use_external = tk.BooleanVar(value=True)
        self.export_usd_binary = tk.BooleanVar(value=False)
        self.quiet_mode = tk.BooleanVar(value=True)
        self.convert_textures = tk.BooleanVar(value=True)
        self.interpolation_mode = tk.StringVar(value="none")  # Default to none
        self.processing = False
        
        # Check NVIDIA Texture Tools availability
        self.nvtt_available = self.check_nvtt_availability()
        
        # Load saved settings
        self.load_settings()
        
        self.create_widgets()
        self.center_window()
        
        # Auto-load folder contents on startup if folder exists
        self.root.after(100, self.auto_load_folder_if_exists)
    
    def normalize_path_display(self, path):
        """Normalize path to use forward slashes for consistent display"""
        return path.replace('\\', '/') if path else path
    
    def center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        pos_x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        pos_y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.folder_input_dir.set(settings.get('folder_input_dir', ''))
                    self.folder_output_dir.set(settings.get('folder_output_dir', ''))
                    # Load last single file directories
                    self.last_input_dir = settings.get('last_input_dir', '')
                    self.last_output_dir = settings.get('last_output_dir', '')
                    self.use_external.set(settings.get('use_external', True))
                    self.export_usd_binary.set(settings.get('export_usd_binary', False))
                    self.quiet_mode.set(settings.get('quiet_mode', True))
                    # Only enable texture conversion if NVTT is available
                    if self.nvtt_available:
                        self.convert_textures.set(settings.get('convert_textures', False))
                    else:
                        self.convert_textures.set(False)
                    self.interpolation_mode.set(settings.get('interpolation_mode', 'faceVarying'))
        except Exception as e:
            print(f"Could not load settings: {e}")
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            settings = {
                'folder_input_dir': self.folder_input_dir.get(),
                'folder_output_dir': self.folder_output_dir.get(),
                'last_input_dir': self.last_input_dir,
                'last_output_dir': self.last_output_dir,
                'use_external': self.use_external.get(),
                'export_usd_binary': self.export_usd_binary.get(),
                'quiet_mode': self.quiet_mode.get(),
                'convert_textures': self.convert_textures.get(),
                'interpolation_mode': self.interpolation_mode.get()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Could not save settings: {e}")
    
    def create_widgets(self):
        """Create the main UI elements with professional styling"""
        # Header
        header_frame = tk.Frame(self.root, bg='#1a1a1a')
        header_frame.pack(fill='x', padx=10, pady=(10, 0))
        
        title_label = tk.Label(header_frame, text="lazy_USD_PointInstancer_Converter", 
                             bg='#1a1a1a', fg='#76b900',
                             font=('Segoe UI', 16, 'bold'))
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame, text="Automatically detects input format and applies appropriate conversion", 
                                bg='#1a1a1a', fg='#b0b0b0',
                                font=('Segoe UI', 9))
        subtitle_label.pack(pady=(2, 0))
        
        # Feature description
        features_text = ("• Forward: Instanceable References → PointInstancer (for files with instanceable prims)\n"
                        "• Reverse: Individual Objects → PointInstancer (for files with duplicate blender.data_name)\n"
                        "• Existing: Export external references from PointInstancers (blender.4.5+ support)\n"
                        "• External prototypes: always saved as .usd binary format for optimal performance")
        
        features_label = tk.Label(header_frame, text=features_text, 
                                bg='#1a1a1a', fg='#909090',
                                font=('Segoe UI', 8), justify='left')
        features_label.pack(pady=(5, 10))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        
        # Configure notebook style for dark theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#1a1a1a', borderwidth=0, relief='flat')
        style.configure('TNotebook.Tab', background='#2a2a2a', foreground='white', 
                       padding=[12, 3], font=('Segoe UI', 9))
        style.map('TNotebook.Tab', background=[('selected', '#76b900'), ('active', '#3a3a3a')],
                 foreground=[('selected', 'black'), ('active', 'white')])
        
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Bind tab change event to auto-load folder contents
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Create tabs
        self.create_single_file_tab()
        self.create_folder_mode_tab()
        self.create_common_options()
        self.create_log_section()
    
    def create_single_file_tab(self):
        """Create single file conversion tab"""
        tab = tk.Frame(self.notebook, bg='#1a1a1a')
        self.notebook.add(tab, text='Single File Mode')
        
        # Input USD File section
        input_frame = tk.LabelFrame(tab, text="Input USD File:", 
                                  bg='#1a1a1a', fg='#76b900',
                                  font=('Segoe UI', 10, 'bold'))
        input_frame.pack(fill='x', padx=12, pady=(3, 2))
        
        input_path_frame = tk.Frame(input_frame, bg='#1a1a1a')
        input_path_frame.pack(fill='x', padx=8, pady=2)
        
        self.input_entry = tk.Entry(input_path_frame, textvariable=self.input_file,
                                  bg='#0a0a0a', fg='white', insertbackground='white',
                                  font=('Segoe UI', 9), relief='flat', bd=0)
        self.input_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=6)
        
        # Bind input file changes to auto-update output suggestion
        self.input_file.trace('w', self.on_input_file_changed)
        
        tk.Button(input_path_frame, text="Browse", command=self.browse_input,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=12, pady=4,
                font=('Segoe UI', 8)).pack(side='right')
        
        # Output USD File section
        output_frame = tk.LabelFrame(tab, text="Output USD File:", 
                                   bg='#1a1a1a', fg='#76b900',
                                   font=('Segoe UI', 10, 'bold'))
        output_frame.pack(fill='x', padx=12, pady=(0, 2))
        
        output_path_frame = tk.Frame(output_frame, bg='#1a1a1a')
        output_path_frame.pack(fill='x', padx=8, pady=2)
        
        self.output_entry = tk.Entry(output_path_frame, textvariable=self.output_file,
                                   bg='#0a0a0a', fg='white', insertbackground='white',
                                   font=('Segoe UI', 9), relief='flat', bd=0)
        self.output_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=6)
        
        tk.Button(output_path_frame, text="Browse", command=self.browse_output,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=12, pady=4,
                font=('Segoe UI', 8)).pack(side='right')
        
        # Convert button
        self.single_convert_button = tk.Button(tab, text="Convert File", 
                                      command=self.convert_file,
                                      bg='#76b900', fg='black', 
                                      activebackground='#8bc924',
                                      relief='flat', bd=0, padx=16, pady=6,
                                      font=('Segoe UI', 9, 'bold'))
        self.single_convert_button.pack(pady=2)
    
    def create_folder_mode_tab(self):
        """Create folder batch conversion tab"""
        tab = tk.Frame(self.notebook, bg='#1a1a1a')
        self.notebook.add(tab, text='Folder Mode')
        
        # Source folder section
        source_frame = tk.LabelFrame(tab, text="Source Folder (USD Files):", 
                                   bg='#1a1a1a', fg='#76b900',
                                   font=('Segoe UI', 10, 'bold'))
        source_frame.pack(fill='x', padx=12, pady=(3, 2))
        
        source_path_frame = tk.Frame(source_frame, bg='#1a1a1a')
        source_path_frame.pack(fill='x', padx=8, pady=2)
        
        self.folder_input_entry = tk.Entry(source_path_frame, textvariable=self.folder_input_dir,
                                         bg='#0a0a0a', fg='white', insertbackground='white',
                                         font=('Segoe UI', 9), relief='flat', bd=0)
        self.folder_input_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=6)
        
        tk.Button(source_path_frame, text="Browse", command=self.browse_folder_input,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=12, pady=4,
                font=('Segoe UI', 8)).pack(side='right')
        
        # Destination folder section
        dest_frame = tk.LabelFrame(tab, text="Destination Folder:", 
                                 bg='#1a1a1a', fg='#76b900',
                                 font=('Segoe UI', 10, 'bold'))
        dest_frame.pack(fill='x', padx=12, pady=(0, 2))
        
        dest_path_frame = tk.Frame(dest_frame, bg='#1a1a1a')
        dest_path_frame.pack(fill='x', padx=8, pady=2)
        
        self.folder_output_entry = tk.Entry(dest_path_frame, textvariable=self.folder_output_dir,
                                          bg='#0a0a0a', fg='white', insertbackground='white',
                                          font=('Segoe UI', 9), relief='flat', bd=0)
        self.folder_output_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=6)
        
        tk.Button(dest_path_frame, text="Browse", command=self.browse_folder_output,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=12, pady=4,
                font=('Segoe UI', 8)).pack(side='right')
        
        # File list section
        file_list_frame = tk.LabelFrame(tab, text="USD Files in Source Folder:", 
                                      bg='#1a1a1a', fg='#76b900',
                                      font=('Segoe UI', 10, 'bold'))
        file_list_frame.pack(fill='both', expand=True, padx=12, pady=(0, 2))
        
        # Control buttons frame
        control_frame = tk.Frame(file_list_frame, bg='#1a1a1a')
        control_frame.pack(fill='x', padx=8, pady=(2, 1))
        
        # File count display
        self.file_count_label = tk.Label(control_frame, text="No folder selected", 
                                       bg='#1a1a1a', fg='#909090',
                                       font=('Segoe UI', 9))
        self.file_count_label.pack(side='left')
        
        # Selection buttons
        tk.Button(control_frame, text="Select All", command=self.select_all_files,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=8, pady=2,
                font=('Segoe UI', 8)).pack(side='right', padx=(4, 0))
        
        tk.Button(control_frame, text="Select None", command=self.select_no_files,
                bg='#4a4a4a', fg='white', activebackground='#5a5a5a',
                relief='flat', bd=0, padx=8, pady=2,
                font=('Segoe UI', 8)).pack(side='right', padx=(4, 0))
        
        # File list with scrollbar and checkboxes
        list_container = tk.Frame(file_list_frame, bg='#1a1a1a')
        list_container.pack(fill='both', expand=True, padx=8, pady=(0, 2))
        
        # Scrollable frame for file checkboxes
        self.file_canvas = tk.Canvas(list_container, bg='#0a0a0a', highlightthickness=0)
        self.file_scrollbar = tk.Scrollbar(list_container, orient="vertical", command=self.file_canvas.yview,
                                         bg='#4a4a4a', troughcolor='#1a1a1a')
        self.file_scrollable_frame = tk.Frame(self.file_canvas, bg='#0a0a0a')
        
        self.file_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.file_canvas.configure(scrollregion=self.file_canvas.bbox("all"))
        )
        
        self.file_canvas.create_window((0, 0), window=self.file_scrollable_frame, anchor="nw")
        self.file_canvas.configure(yscrollcommand=self.file_scrollbar.set)
        
        self.file_canvas.pack(side="left", fill="both", expand=True)
        self.file_scrollbar.pack(side="right", fill="y")
        
        # Store file checkboxes and variables
        self.file_checkboxes = {}
        self.file_vars = {}
        
        # Bind folder input change to update file list
        self.folder_input_dir.trace('w', self.update_file_list)
        
        # Convert buttons frame
        button_frame = tk.Frame(tab, bg='#1a1a1a')
        button_frame.pack(fill='x', padx=12, pady=2)
        
        # Convert selected button
        self.convert_selected_button = tk.Button(button_frame, text="Convert Selected Files", 
                                               command=self.convert_selected_files,
                                               bg='#76b900', fg='black', 
                                               activebackground='#8bc924',
                                               relief='flat', bd=0, padx=16, pady=6,
                                               font=('Segoe UI', 9, 'bold'))
        self.convert_selected_button.pack(side='left', padx=(0, 8))
        
        # Convert all button
        self.folder_convert_button = tk.Button(button_frame, text="Convert All Files", 
                                             command=self.convert_folder,
                                             bg='#ff6b35', fg='white', 
                                             activebackground='#ff8a65',
                                             relief='flat', bd=0, padx=16, pady=6,
                                             font=('Segoe UI', 9, 'bold'))
        self.folder_convert_button.pack(side='left')
    
    def create_common_options(self):
        """Create common options section below tabs"""
        # Conversion Options section
        options_frame = tk.LabelFrame(self.root, text="Conversion Options", 
                                    bg='#1a1a1a', fg='#76b900',
                                    font=('Segoe UI', 10, 'bold'))
        options_frame.pack(fill='x', padx=10, pady=(0, 8))
        
        options_inner = tk.Frame(options_frame, bg='#1a1a1a')
        options_inner.pack(fill='x', padx=8, pady=8)
        
        # Checkboxes with clean professional styling
        self.external_checkbox = tk.Checkbutton(options_inner, 
                                              text="Use External References (Instance_Objs folder) - always saved as .usd binary format",
                                              variable=self.use_external,
                                              bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                                              activebackground='#1a1a1a',
                                              font=('Segoe UI', 9))
        self.external_checkbox.pack(anchor='w', pady=2)
        
        self.binary_checkbox = tk.Checkbutton(options_inner, 
                                            text="Export main file as USD Binary (.usd) - default is ASCII (.usda)",
                                            variable=self.export_usd_binary,
                                            bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                                            activebackground='#1a1a1a',
                                            font=('Segoe UI', 9))
        self.binary_checkbox.pack(anchor='w', pady=2)
        
        self.quiet_checkbox = tk.Checkbutton(options_inner, 
                                           text="Quiet mode (reduce log verbosity for large files)",
                                           variable=self.quiet_mode,
                                           bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                                           activebackground='#1a1a1a',
                                           font=('Segoe UI', 9))
        self.quiet_checkbox.pack(anchor='w', pady=2)
        
        # NVIDIA Texture Tools checkbox with status indicator
        texture_frame = tk.Frame(options_inner, bg='#1a1a1a')
        texture_frame.pack(fill='x', pady=2)
        
        # Status indicator and checkbox text based on NVTT availability
        if self.nvtt_available:
            status_icon = "✅"
            status_color = "#76b900"  # NVIDIA green
            checkbox_text = "Convert textures to DDS using NVIDIA Texture Tools"
            checkbox_state = "normal"
            checkbox_fg = "white"
        else:
            status_icon = "❌"
            status_color = "#ff4444"  # Red for unavailable
            checkbox_text = "Convert textures to DDS using NVIDIA Texture Tools"
            checkbox_state = "disabled"
            checkbox_fg = "#666666"
            # Disable the option if NVTT is not available
            self.convert_textures.set(False)
        
        # Create checkbox without status icon
        self.texture_checkbox = tk.Checkbutton(texture_frame, 
                                             text=checkbox_text,
                                             variable=self.convert_textures,
                                             state=checkbox_state,
                                             bg='#1a1a1a', fg=checkbox_fg, selectcolor='#0a0a0a',
                                             activebackground='#1a1a1a', disabledforeground='#666666',
                                             font=('Segoe UI', 9))
        self.texture_checkbox.pack(side='left')
        
        # Add status indicator after the checkbox text
        status_label = tk.Label(texture_frame, 
                               text=f" {status_icon}",
                               bg='#1a1a1a', fg=status_color,
                               font=('Segoe UI', 11))
        status_label.pack(side='left')
        
        # Interpolation mode section
        interp_frame = tk.Frame(options_inner, bg='#1a1a1a')
        interp_frame.pack(fill='x', pady=6)
        
        interp_label = tk.Label(interp_frame, 
                               text="Interpolation Conversion for normals and texCoords:",
                               bg='#1a1a1a', fg='#c0c0c0',
                               font=('Segoe UI', 9))
        interp_label.pack(side='left')
        
        # Radio buttons for interpolation mode
        interp_radio_frame = tk.Frame(interp_frame, bg='#1a1a1a')
        interp_radio_frame.pack(side='right', padx=(10, 0))
        
        tk.Radiobutton(interp_radio_frame, text="vertex → faceVarying", 
                      variable=self.interpolation_mode, value="faceVarying",
                      bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                      activebackground='#1a1a1a', font=('Segoe UI', 8)).pack(side='left')
        
        tk.Radiobutton(interp_radio_frame, text="faceVarying → vertex", 
                      variable=self.interpolation_mode, value="vertex",
                      bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                      activebackground='#1a1a1a', font=('Segoe UI', 8)).pack(side='left', padx=(8, 0))
        
        tk.Radiobutton(interp_radio_frame, text="No conversion", 
                      variable=self.interpolation_mode, value="none",
                      bg='#1a1a1a', fg='white', selectcolor='#0a0a0a',
                      activebackground='#1a1a1a', font=('Segoe UI', 8)).pack(side='left', padx=(8, 0))
        
        # Material Conversion info section
        material_frame = tk.LabelFrame(self.root, text="Material Conversion (Enabled by Default)", 
                                     bg='#1a1a1a', fg='#76b900',
                                     font=('Segoe UI', 10, 'bold'))
        material_frame.pack(fill='x', padx=10, pady=(0, 8))
        
        material_text = ("Material conversion is enabled by default using the unified method:\n"
                        "• PrincipledBSDF → Remix Opacity Material\n"
                        "• OmniPBR → Remix Opacity Material\n"
                        "• All materials use the same unified Remix structure")
        
        tk.Label(material_frame, text=material_text, 
               bg='#1a1a1a', fg='#c0c0c0',
               font=('Segoe UI', 8), justify='left').pack(anchor='w', padx=8, pady=6)
    
    def create_log_section(self):
        """Create log section at bottom"""
        # Processing Log section
        log_frame = tk.LabelFrame(self.root, text="Processing Log", 
                                bg='#1a1a1a', fg='#76b900',
                                font=('Segoe UI', 10, 'bold'))
        log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg='#0a0a0a', fg='white',
                                                insertbackground='white',
                                                font=('Consolas', 8), relief='flat', bd=0,
                                                wrap=tk.WORD, height=6)
        self.log_text.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Initial log message
        self.log_message("Unified USD PointInstancer converter initialized")
        self.log_message("Select input and output files, then click Convert to start")
        self.log_message("Supports Forward (Instanceable References → PointInstancer) and Reverse (Individual Objects → PointInstancer)")
    
    def on_tab_changed(self, event):
        """Handle tab change events"""
        selected_tab = event.widget.tab('current')['text']
        if selected_tab == 'Folder Mode':
            # Auto-load folder contents when switching to folder mode
            self.auto_load_folder_if_exists()
    
    def auto_load_folder_if_exists(self):
        """Auto-load folder contents if remembered folder exists"""
        folder = self.folder_input_dir.get()
        if folder and os.path.exists(folder):
            # Force update the file list since folder already exists
            self.update_file_list()
            self.log_message(f"Auto-loaded folder: {folder}")
        elif folder:
            # Folder path exists but directory doesn't exist anymore
            self.file_count_label.config(text=f"Remembered folder no longer exists: {os.path.basename(folder)}")
            self.log_message(f"Warning: Remembered folder no longer exists: {folder}")
    
    def check_nvtt_availability(self):
        """Check if NVIDIA Texture Tools is available on the system"""
        # Check for nvtt_export.exe - the actual NVIDIA Texture Tools executable
        default_install = r"C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools"
        candidates = [
            os.path.join(default_install, "nvtt_export.exe"),
            "nvtt_export.exe"  # Check if it's in PATH
        ]
        
        # Try each candidate
        for candidate in candidates:
            try:
                result = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return True
            except:
                continue
        
        return False
    
    def on_input_file_changed(self, *args):
        """Handle input file changes to auto-suggest output filename"""
        input_path = self.input_file.get().strip()
        if input_path and os.path.exists(input_path):
            # Only auto-update if output is empty or was previously auto-generated
            current_output = self.output_file.get().strip()
            if not current_output or "_converted" in current_output:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                
                # Use last output directory if available, otherwise use input file's directory
                if self.last_output_dir and os.path.exists(self.last_output_dir):
                    suggested_output = os.path.join(self.last_output_dir, f"{base_name}_converted.usda")
                else:
                    suggested_output = f"{os.path.splitext(input_path)[0]}_converted.usda"
                
                # Normalize path display to use forward slashes
                self.output_file.set(self.normalize_path_display(suggested_output))
    
    def browse_input(self):
        """Browse for input USD file"""
        # Use last input directory or folder input directory as initial directory
        initial_dir = self.last_input_dir or self.folder_input_dir.get() or os.getcwd()
        if not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
            
        filename = filedialog.askopenfilename(
            title="Select Input USD File",
            initialdir=initial_dir,
            filetypes=[("USD files", "*.usd *.usda *.usdc"), ("All files", "*.*")]
        )
        if filename:
            # Normalize path display to use forward slashes
            self.input_file.set(self.normalize_path_display(filename))
            # Remember the directory for next time
            self.last_input_dir = os.path.dirname(filename)
            self.save_settings()  # Auto-save directory selection
            # Auto-suggest output filename only if output is empty or was auto-generated
            current_output = self.output_file.get().strip()
            if not current_output or "_converted" in current_output:
                base_name = os.path.splitext(os.path.basename(filename))[0]
                
                # Use last output directory if available, otherwise use input file's directory
                if self.last_output_dir and os.path.exists(self.last_output_dir):
                    suggested_output = os.path.join(self.last_output_dir, f"{base_name}_converted.usda")
                else:
                    suggested_output = f"{os.path.splitext(filename)[0]}_converted.usda"
                
                # Normalize path display to use forward slashes
                self.output_file.set(self.normalize_path_display(suggested_output))
                self.log_message(f"Auto-suggested output: {os.path.basename(suggested_output)}")
    
    def browse_output(self):
        """Browse for output USD file"""
        # Get suggested filename based on input file
        suggested_filename = ""
        # Prioritize last output directory first, then input file directory, then folder output directory
        initial_dir = self.last_output_dir or self.folder_output_dir.get() or os.getcwd()
        
        input_path = self.input_file.get().strip()
        if input_path and os.path.exists(input_path):
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            suggested_filename = f"{base_name}_converted.usda"
            # Only use input directory if we don't have a remembered output directory
            if not self.last_output_dir:
                input_dir = os.path.dirname(input_path)
                if os.path.exists(input_dir):
                    initial_dir = input_dir
        
        # Fallback to current directory if initial_dir doesn't exist
        if not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        filename = filedialog.asksaveasfilename(
            title="Save Converted USD File As",
            initialdir=initial_dir,
            initialfile=suggested_filename,  # Auto-suggest filename
            defaultextension=".usda",
            filetypes=[("USD ASCII", "*.usda"), ("USD Binary", "*.usd"), ("All files", "*.*")]
        )
        if filename:
            # Normalize path display to use forward slashes
            self.output_file.set(self.normalize_path_display(filename))
            # Remember the directory for next time
            self.last_output_dir = os.path.dirname(filename)
            self.save_settings()  # Auto-save directory selection
    
    def browse_folder_input(self):
        """Browse for input folder"""
        folder = filedialog.askdirectory(title="Select Source Folder with USD Files")
        if folder:
            self.folder_input_dir.set(folder)
            self.save_settings()  # Auto-save folder selection
            # Force immediate update of file list
            self.update_file_list()
            self.log_message(f"Selected source folder: {folder}")
    
    def browse_folder_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(title="Select Destination Folder")
        if folder:
            self.folder_output_dir.set(folder)
            self.save_settings()  # Auto-save folder selection
            self.log_message(f"Selected destination folder: {folder}")
    
    def update_file_count(self, *args):
        """Update file count when folder selection changes"""
        folder = self.folder_input_dir.get()
        if folder and os.path.exists(folder):
            usd_files = [f for f in os.listdir(folder) 
                        if f.lower().endswith(('.usd', '.usda', '.usdc'))]
            count = len(usd_files)
            if count > 0:
                self.file_count_label.config(text=f"Found {count} USD file{'s' if count != 1 else ''}")
            else:
                self.file_count_label.config(text="No USD files found in folder")
        else:
            self.file_count_label.config(text="No folder selected")
    
    def update_file_list(self, *args):
        """Update file list with checkboxes when folder selection changes"""
        # Clear existing checkboxes
        for widget in self.file_scrollable_frame.winfo_children():
            widget.destroy()
        self.file_checkboxes.clear()
        self.file_vars.clear()
        
        folder = self.folder_input_dir.get()
        if folder and os.path.exists(folder):
            try:
                usd_files = [f for f in os.listdir(folder) 
                            if f.lower().endswith(('.usd', '.usda', '.usdc'))]
                usd_files.sort()  # Sort alphabetically
                
                count = len(usd_files)
                if count > 0:
                    self.file_count_label.config(text=f"Found {count} USD file{'s' if count != 1 else ''} (.usd, .usda, .usdc)")
                    
                    # Create checkboxes for each file
                    for filename in usd_files:
                        var = tk.BooleanVar(value=True)  # Default to selected
                        self.file_vars[filename] = var
                        
                        checkbox = tk.Checkbutton(self.file_scrollable_frame, 
                                                text=filename,
                                                variable=var,
                                                bg='#0a0a0a', fg='white', 
                                                selectcolor='#1a1a1a',
                                                activebackground='#0a0a0a',
                                                font=('Segoe UI', 9),
                                                anchor='w')
                        checkbox.pack(fill='x', padx=4, pady=1)
                        self.file_checkboxes[filename] = checkbox
                else:
                    self.file_count_label.config(text="No USD files found in folder (.usd, .usda, .usdc)")
            except Exception as e:
                self.file_count_label.config(text=f"Error reading folder: {str(e)}")
        else:
            self.file_count_label.config(text="No folder selected")
    
    def select_all_files(self):
        """Select all files in the list"""
        for var in self.file_vars.values():
            var.set(True)
    
    def select_no_files(self):
        """Deselect all files in the list"""
        for var in self.file_vars.values():
            var.set(False)
    
    def get_selected_files(self):
        """Get list of selected files"""
        return [filename for filename, var in self.file_vars.items() if var.get()]
    
    def convert_selected_files(self):
        """Convert only selected files"""
        if self.processing:
            return
        
        input_dir = self.folder_input_dir.get().strip()
        output_dir = self.folder_output_dir.get().strip()
        
        if not input_dir or not output_dir:
            messagebox.showerror("Error", "Please select both source and destination folders")
            return
        
        if not os.path.exists(input_dir):
            messagebox.showerror("Error", f"Source folder does not exist: {input_dir}")
            return
        
        selected_files = self.get_selected_files()
        if not selected_files:
            messagebox.showerror("Error", "No files selected for conversion")
            return
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create destination folder: {str(e)}")
                return
        
        # Save settings before conversion
        self.save_settings()
        
        # Start conversion in thread
        self.processing = True
        self.convert_selected_button.config(state='disabled', text="Converting...")
        self.folder_convert_button.config(state='disabled')
        
        thread = threading.Thread(target=self._convert_folder_thread, 
                                 args=(input_dir, output_dir, selected_files))
        thread.daemon = True
        thread.start()
    
    def convert_folder(self):
        """Convert all USD files in folder"""
        if self.processing:
            return
        
        input_dir = self.folder_input_dir.get().strip()
        output_dir = self.folder_output_dir.get().strip()
        
        if not input_dir or not output_dir:
            messagebox.showerror("Error", "Please select both source and destination folders")
            return
        
        if not os.path.exists(input_dir):
            messagebox.showerror("Error", f"Source folder does not exist: {input_dir}")
            return
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create destination folder: {str(e)}")
                return
        
        # Get USD files - include .usdc support
        usd_files = [f for f in os.listdir(input_dir) 
                    if f.lower().endswith(('.usd', '.usda', '.usdc'))]
        
        if not usd_files:
            messagebox.showerror("Error", "No USD files found in source folder")
            return
        
        # Save settings before conversion
        self.save_settings()
        
        # Start conversion in thread
        self.processing = True
        self.folder_convert_button.config(state='disabled', text="Converting...")
        self.convert_selected_button.config(state='disabled')
        
        thread = threading.Thread(target=self._convert_folder_thread, 
                                 args=(input_dir, output_dir, usd_files))
        thread.daemon = True
        thread.start()
    
    def _convert_folder_thread(self, input_dir, output_dir, usd_files):
        """Convert folder in separate thread"""
        try:
            total_files = len(usd_files)
            converted = 0
            failed = 0
            
            self.root.after(0, self.log_message, f"Starting batch conversion of {total_files} files")
            self.root.after(0, self.log_message, f"Source: {input_dir}")
            self.root.after(0, self.log_message, f"Destination: {output_dir}")
            
            for i, filename in enumerate(usd_files, 1):
                input_path = os.path.join(input_dir, filename)
                base_name = os.path.splitext(filename)[0]
                output_filename = f"{base_name}_converted.usda"
                output_path = os.path.join(output_dir, output_filename)
                
                try:
                    self.root.after(0, self.log_message, f"[{i}/{total_files}] Converting: {filename}")
                    
                    converter = CleanUnifiedConverter(input_path, export_binary=self.export_usd_binary.get())
                    result = converter.convert(
                        output_path,
                        use_external_references=self.use_external.get(),
                        export_binary=self.export_usd_binary.get(),
                        convert_textures=self.convert_textures.get(),
                        interpolation_mode=self.interpolation_mode.get()
                    )
                    
                    if result:
                        converted += 1
                        self.root.after(0, self.log_message, f"✅ Completed: {output_filename}")
                    else:
                        failed += 1
                        self.root.after(0, self.log_message, f"❌ Failed: {filename}")
                        
                except Exception as e:
                    failed += 1
                    self.root.after(0, self.log_message, f"❌ Error converting {filename}: {str(e)}")
            
            # Summary
            self.root.after(0, self.log_message, f"Batch conversion completed: {converted} successful, {failed} failed")
            
            if failed == 0:
                self.root.after(0, messagebox.showinfo, "Success", 
                              f"All {converted} files converted successfully!")
            else:
                self.root.after(0, messagebox.showwarning, "Partial Success", 
                              f"Converted {converted} files successfully, {failed} failed. Check log for details.")
                
        except Exception as e:
            error_msg = f"❌ Batch conversion failed: {str(e)}"
            self.root.after(0, self.log_message, error_msg)
            self.root.after(0, messagebox.showerror, "Error", f"Batch conversion failed:\n{str(e)}")
        
        finally:
            self.processing = False
            self.root.after(0, lambda: self.folder_convert_button.config(state='normal', text="Convert All Files"))
            self.root.after(0, lambda: self.convert_selected_button.config(state='normal', text="Convert Selected Files"))
    
    def log_message(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def convert_file(self):
        """Convert the USD file"""
        if self.processing:
            return
        
        input_path = self.input_file.get().strip()
        output_path = self.output_file.get().strip()
        
        if not input_path or not output_path:
            messagebox.showerror("Error", "Please select both input and output files")
            return
        
        if not os.path.exists(input_path):
            messagebox.showerror("Error", f"Input file does not exist: {input_path}")
            return
        
        # Save settings before conversion
        self.save_settings()
        
        # Start conversion in thread
        self.processing = True
        self.single_convert_button.config(state='disabled', text="Converting...")
        
        thread = threading.Thread(target=self._convert_thread, args=(input_path, output_path))
        thread.daemon = True
        thread.start()
    
    def _convert_thread(self, input_path, output_path):
        """Convert file in separate thread"""
        try:
            converter = CleanUnifiedConverter(
                input_path, 
                export_binary=self.export_usd_binary.get()
            )
            
            self.log_message(f"Starting conversion: {os.path.basename(input_path)}")
            self.log_message(f"Output: {os.path.basename(output_path)}")
            
            # Perform conversion
            result = converter.convert(
                output_path, 
                use_external_references=self.use_external.get(),
                export_binary=self.export_usd_binary.get(),
                convert_textures=self.convert_textures.get(),
                interpolation_mode=self.interpolation_mode.get()
            )
            
            if result:
                self.root.after(0, self.log_message, "✅ Conversion completed successfully!")
                self.root.after(0, messagebox.showinfo, "Success", "Conversion completed successfully!")
            else:
                self.root.after(0, self.log_message, "❌ Conversion failed - check input file")
                self.root.after(0, messagebox.showerror, "Error", "Conversion failed - check input file")
            
        except Exception as e:
            error_msg = f"❌ Conversion failed: {str(e)}"
            self.root.after(0, self.log_message, error_msg)
            self.root.after(0, messagebox.showerror, "Error", f"Conversion failed:\n{str(e)}")
        
        finally:
            self.processing = False
            self.root.after(0, lambda: self.single_convert_button.config(state='normal', text="Convert File"))

def main():
    root = tk.Tk()
    app = UnifiedConverterUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()