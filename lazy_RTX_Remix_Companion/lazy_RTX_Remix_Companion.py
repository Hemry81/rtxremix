import sys
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, Label, Button, messagebox
import json
import shutil
import os
import re
import string
from threading import Thread
        
class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

global firstLaunch
global oldVersion

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
        super().__init__(parent, title=title)  # Corrected the super() call

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
        # Split only if the number appears to be a year or is clearly separate
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
                # Add both versions: with and without leading zero
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
        self.master.title("lazy_RTX-Remix Companion")
    
        # Setting up the main frame for buttons and label
        self.button_frame = ttk.Frame(master)
        self.button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Version display frame
        self.version_frame = ttk.Frame(master)
        self.version_frame.pack(fill=tk.X, padx=10, pady=5)
        self.version_label = ttk.Label(self.version_frame, text="RTX-Remix Version: N/A")
        self.version_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Initialize tipwindow
        self.tipwindow = None  
        self.text = None
        
        # Setting up the buttons
        self.setup_buttons()
        
        # Setup the status bar
        self.setup_status_bar()
        
        # Initialize as None
        self.remix_folder = None
    
        # Setting up the Treeview
        self.setup_treeview()
        self.load_config()

    def setup_buttons(self):
        # Button for selecting RTX-Remix folder
        ttk.Button(self.button_frame, text="Select RTX-Remix", command=self.select_source).pack(anchor=tk.W)
        # Button for selecting destination folder
        ttk.Button(self.button_frame, text="Add Game Folder", command=self.select_destination).pack(anchor=tk.W)
        # Button for delete selected folder
        ttk.Button(self.button_frame, text="Remove Game", command=self.remove_selected_game).pack(anchor=tk.W)
        # Button for copying files
        self.copy_button = ttk.Button(self.button_frame, text="Copy Files", command=self.copy_files)
        self.copy_button.pack(anchor=tk.W)  # Pack the button after assigning it to self.copy_button
        self.copy_button.configure(state='disabled')  # Now correctly configure the button
        
    def setup_treeview(self):
        """Setup the Treeview with columns, headings, and interaction bindings."""
        # Treeview setup
        self.tree = ttk.Treeview(self.master, columns=("🔓", "Game Name", "Folder Path", "Bridge", "Runtime", "dxvk.conf", "d3d8to9.dll", "Runtime Version", "Bridge Version"), show="headings")
        headings = ["🔓", "Game Name", "Folder Path", "Bridge", "Runtime", "dxvk.conf", "d3d8to9.dll", "Runtime Version", "Bridge Version"]
        for heading in headings:
            self.tree.heading(heading, text=heading)
            if heading in ["🔓"]:
                iwidth = 10
            elif heading in ["Game Name", "Folder Path"]:
                iwidth = 160
            elif heading in ["Bridge", "Runtime", "dxvk.conf", "d3d8to9.dll"]:
                iwidth = 20
            else:
                iwidth = 80
            self.tree.column(heading, anchor="center", width=iwidth)
        
        # Vertical scrollbar
        v_scroll = ttk.Scrollbar(self.master, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side='right', fill='y')
        
        # Horizontal scrollbar
        h_scroll = ttk.Scrollbar(self.master, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(side='bottom', fill='x')
        
        # Define tags for version match and mismatch
        self.tree.tag_configure("version_mismatch", foreground="red")
        self.tree.tag_configure("version_match", foreground="green")
        self.tree.tag_configure('disable', background='grey', foreground='white')
    
        self.tree.pack(expand=True, fill='both')
        self.tree_tooltip = Tooltip(self.tree)
        
        # Bind events for selection, clicking, hovering, and tooltip management
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)
        self.tree.bind("<Button-1>", self.handle_click)
        self.tree.bind("<Motion>", self.handle_motion)
        
        # Bind Ctrl+A to select all non-disabled items
        self.tree.bind('<Control-a>', self.select_all_except_disabled)  # For letter 'a' if Caps Lock is off
        self.tree.bind('<Control-A>', self.select_all_except_disabled)  # For letter 'A' if Caps Lock is on
        self.tree.bind('<Control-d>', self.deselect_all)                # For letter 'd' if Caps Lock is off
        self.tree.bind('<Control-D>', self.deselect_all)                # For letter 'D' if Caps Lock is on
        
    def select_all_except_disabled(self, event):
        # Clear existing selection
        self.tree.selection_remove(self.tree.selection())

        # Iterate through all tree items
        for item in self.tree.get_children():
            tags = self.tree.item(item, 'tags')
            if 'disable' not in tags:
                self.tree.selection_add(item)
    
    def deselect_all(self, event):
        self.tree.selection_remove(self.tree.selection())
                
    def show_tooltip(self, text, x, y):
        if self.tipwindow or not text:
            return
        self.text = text
        self.tipwindow = tw = tk.Toplevel(self.master)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x+20}+{y+20}")  # Position tooltip
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                        background="lightyellow", relief=tk.SOLID, borderwidth=1,
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
    
        # Check if the cursor is over an item and the column is identified.
        if row_id and column_id and region == "cell":
            col_index = int(column_id.strip('#')) - 1
            # Change cursor for specific columns
            if col_index in [0, 3, 4, 5, 6]:
                widget.configure(cursor="hand2")
            else:
                widget.configure(cursor="arrow")
        else:
            # Reset cursor to default if not over an item or in a specific region
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
                        if current_values[col_index] == "🔓":
                            new_value = "🔒"
                            new_tag = "disable"
                            current_values[col_index] = new_value
                            widget.item(row_id, values=current_values, tags=(new_tag, ))
                        else:
                            new_value = "🔓"
                            destination_versions = {
                                "runtime version": current_values[7],
                                "bridge version": current_values[8]
                            }
                            self.check_version_and_tag(row_id, destination_versions)
                            current_values[col_index] = new_value
                            widget.item(row_id, values=current_values)
                        self.save_config()
    
                    elif col_index in [3, 4, 5, 6]:
                        current_value = current_values[col_index]
                        new_value = "No" if current_value == "Yes" else "Yes"
                        current_values[col_index] = new_value
                        widget.item(row_id, values=current_values)
                        self.save_config()
    
        self.update_copy_button_state()
        self.tree.update_idletasks()
        
    def on_tree_selection(self, event):
        # Get the Treeview widget
        treeview = event.widget
        selection = treeview.selection()
        
        for item in selection:
            # Check if the item has the 'disable' tag
            if 'disable' in treeview.item(item, 'tags'):
                # This item should not be selectable, remove from selection
                # This method clears all selections and reselects items without the 'disable' tag
                treeview.selection_remove(item)
        self.update_copy_button_state()
        self.tree.update_idletasks()

    def change_cursor_on_hover(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column_id = self.tree.identify_column(event.x)
            col_number = int(column_id.strip('#')) - 1
            if col_number in [2, 3, 4, 5]:  # Specific columns
                self.tree.configure(cursor="hand2")
            else:
                self.tree.configure(cursor="")
        else:
            self.tree.configure(cursor="")
        
    def serialize_treeview(self):
        tree_items = []
        for child in self.tree.get_children():
            tree_items.append(self.tree.item(child, 'values'))
        return tree_items

    def update_copy_button_state(self):
        try:
            # Check required conditions for enabling the button
            if self.remix_folder and self.tree.selection():
                self.copy_button.configure(state='Normal')  # Enable the button
                self.status_right.config(text="Ready to copy files.")  # Update status message
            else:
                self.copy_button.configure(state='disabled')  # Disable the button
                if not self.remix_folder:
                    self.status_right.config(text="Select an RTX-Remix folder to enable copying.")  # Specific feedback
                elif not self.tree.selection():
                    self.status_right.config(text="Select one or more items in the list to copy.")  # Specific feedback
        except AttributeError as e:
            # Log the error and update the status bar for user feedback
            self.status_right.config(text=f"Error: {e}")
            # Optionally, add a logging statement if logging is configured
            # import logging
            # logging.error(f"Failed to update button state: {e}")
            
    def check_sources(self, folder):
        required_files_v1 = {
            "build-names.txt", "d3d8_off.dll", "d3d8to9.dll", "d3d9.dll", "dxvk.conf", "dxwrapper.dll", "dxwrapper.ini",
            "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
            "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", "ThirdPartyLicenses-dxwrapper.txt", ".trex"
        }
        required_files_v2 = {
            "build_names.txt", "d3d8to9.dll", "d3d9.dll", "dxvk.conf", "LICENSE.txt", "NvRemixLauncher32.exe",
            "ThirdPartyLicenses-bridge.txt", "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
        }
        required_files_v3 = {
            "build_names.txt", "d3d8to9.dll", "d3d9.dll", "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
            "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
        }
        required_files_v4 = {
            "d3d8to9.dll", "d3d9.dll", "LICENSE.txt", "NvRemixLauncher32.exe", "ThirdPartyLicenses-bridge.txt",
            "ThirdPartyLicenses-d3d8to9.txt", "ThirdPartyLicenses-dxvk.txt", ".trex"
        }
        global oldVersion
        oldVersion = False # Reset the oldVersion flag
        actual_files = set(os.listdir(folder))
        extra_files = actual_files - required_files_v1
        if extra_files:
            oldVersion = True
            extra_files = actual_files - required_files_v2
            if extra_files:
                extra_files = actual_files - required_files_v3
                if extra_files:
                    extra_files = actual_files - required_files_v4
                
        missing_files = required_files_v1 - actual_files
        if missing_files:
            oldVersion = True
            missing_files = required_files_v2 - actual_files
            if missing_files:
                missing_files = required_files_v3 - actual_files
                if missing_files:
                    missing_files = required_files_v4 - actual_files
                    
        return missing_files, extra_files
                    
    def select_source(self):
        new_folder = filedialog.askdirectory()
        if new_folder:
            missing_files, extra_files = self.check_sources(new_folder)  # Check version compatibility
            if extra_files or missing_files:
                message = "Please select the 'RTX-Remix' folder only, with No extra files."
                if missing_files:
                    message += f"\nMissing necessary files/folders:\n{', '.join(missing_files)}"
                if extra_files:
                    message += "\nThere are too many extra files in the RTX-Remix folder; it doesn't seem to be a correct RTX-Remix Folder."
                messagebox.showerror("Error", message)
                self.status_left.config(text="RTX-Remix Folder: None")
                self.status_right.config(text="Invalid RTX-Remix folder selected.")
            else:
                self.remix_folder = new_folder.replace("/", "\\")  # Update the global source folder path, Replace forward slashes with double forward slashes
                self.source_versions = self.load_versions_from_file(self.remix_folder, True)
                version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
                self.version_label.config(text=version_info)
                self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
                self.save_config()
    
                # Re-check the version compatibility for each game in the tree
                for item in self.tree.get_children():
                    destination_folder = self.tree.item(item, "values")[2]  # Assuming folder path is the third value
                    destination_versions = self.load_versions_from_file(destination_folder)
                    self.check_version_and_tag(item, destination_versions)
    
                # Update status text based on whether there are items in the tree
                if self.tree.get_children():
                    self.status_right.config(text="Configuration saved successfully. Ready to proceed.")
                else:
                    self.status_right.config(text="Configuration saved successfully. Please select the Game Folder(s) to proceed.")
                    
                self.update_copy_button_state()

    def select_destination(self):
        folder_path = filedialog.askdirectory(title="Select Game Folder")
        if folder_path:
            # Check for .exe files in the selected folder (only in the first level)
            exe_files = [f for f in os.listdir(folder_path) if f.endswith('.exe')]
            if not exe_files:
                messagebox.showinfo("No Executable Found", "No executable game file found in the selected folder.")
                return  # Optionally return if you don't want to proceed
    
            dialog = CustomGameNameDialog(self.master, "Game Name", folder_path)  # Pass self.master if in a class context
            game_name = dialog.result  # Access result after dialog has been handled
            if game_name:
                destination_versions = self.load_versions_from_file(folder_path)
                tree_item = self.tree.insert("", 'end', values=("🔓", game_name, folder_path, 'Yes', 'Yes', 'No', 'No', destination_versions["runtime version"], destination_versions["bridge version"]))
                self.check_version_and_tag(tree_item, destination_versions)
                self.status_right.config(text="Game added and configuration saved successfully. Ready to proceed.")
                self.save_config()
            else:
                self.status_right.config(text="Game name entry was cancelled.")
        else:
            self.status_right.config(text="Folder selection was cancelled.")
    
        self.update_copy_button_state()
        
    import string

    def show_popup_window(self, versions, directory):
        # Create the popup window
        popup_window = tk.Toplevel(self.master)
        popup_window.title("Version Input")
    
        # Get the width and height of the main window
        main_window_width = self.master.winfo_width()
        main_window_height = self.master.winfo_height()
    
        # Calculate the position of the popup window
        popup_window_width = 300
        popup_window_height = 150
        popup_window_x = self.master.winfo_x() + (main_window_width // 2) - (popup_window_width // 2)
        popup_window_y = self.master.winfo_y() + (main_window_height // 2) - (popup_window_height // 2)
    
        # Set the position of the popup window
        popup_window.geometry(f"{popup_window_width}x{popup_window_height}+{popup_window_x}+{popup_window_y}")
    
        # Define the validation function
        def validate_input(text):
            allowed_chars = set(string.digits + string.ascii_letters + ".")
            return all(char in allowed_chars for char in text)
    
        # Create the input fields
        runtime_version_label = tk.Label(popup_window, text="Runtime Version:")
        runtime_version_entry = ttk.Entry(popup_window, validate="key", validatecommand=(popup_window.register(validate_input), "%S"))
        bridge_version_label = tk.Label(popup_window, text="Bridge Version:")
        bridge_version_entry = ttk.Entry(popup_window, validate="key", validatecommand=(popup_window.register(validate_input), "%S"))
    
        # Create the submit button
        submit_button = tk.Button(popup_window, text="Submit", command=lambda: submit())
        submit_button.config(state="disabled")  # Disable the submit button initially
    
        # Define the submit function
        def submit():
            # Update the versions dictionary with user input
            runtime_version = runtime_version_entry.get().strip()
            bridge_version = bridge_version_entry.get().strip()
            if runtime_version and bridge_version:
                versions["runtime version"] = runtime_version
                versions["bridge version"] = bridge_version
    
                # Save the versions to the "build_names.txt" file
                self.save_versions_to_file(versions, os.path.join(directory, "build_names.txt"))
    
                popup_window.destroy()
            else:
                # Display an error message or do nothing
                pass
    
        # Enable the submit button when both fields have a value
        def enable_submit_button(*args):
            runtime_version = runtime_version_entry.get().strip()
            bridge_version = bridge_version_entry.get().strip()
            if runtime_version and bridge_version:
                submit_button.config(state="normal")
            else:
                submit_button.config(state="disabled")
    
        runtime_version_entry.bind("<KeyRelease>", enable_submit_button)
        bridge_version_entry.bind("<KeyRelease>", enable_submit_button)
    
        # Layout the elements
        runtime_version_label.grid(row=0, column=0, padx=10, pady=10)
        runtime_version_entry.grid(row=0, column=1, padx=10, pady=10)
        bridge_version_label.grid(row=1, column=0, padx=10, pady=10)
        bridge_version_entry.grid(row=1, column=1, padx=10, pady=10)
        submit_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
    
        # Set focus on the first entry field
        runtime_version_entry.focus_set()
    
        # Run the main loop
        popup_window.mainloop()
    
        return versions
        
    def save_versions_to_file(self, versions, filepath):
        runtime_version = versions["runtime version"]
        bridge_version = versions["bridge version"]
    
        # Construct the lines to write to the file
        lines = [
            f"dxvk-remix-{runtime_version}",
            f"bridge-remix-{bridge_version}"
        ]
    
        # Write the lines to the file
        with open(filepath, 'w') as file:
            file.writelines('\n'.join(lines))
            
    def load_versions_from_file(self, directory, isSource=False):
        versions = {"runtime version": "N/A", "bridge version": "N/A"}
        if os.path.exists(os.path.join(directory, "build-names.txt")):
            filepath = os.path.join(directory, "build-names.txt")
        else:
            filepath = os.path.join(directory, "build_names.txt")
        try:
            with open(filepath, 'r') as file:
                lines = file.readlines()
                for line in lines:
                    if "dxvk-remix" in line:
                        versions["runtime version"] = '-'.join(line.strip().split('-')[-3:])
                    elif "bridge-remix" in line:
                        versions["bridge version"] = '-'.join(line.strip().split('-')[-3:])
            return versions
        except:
            if not firstLaunch:
                if isSource:
                    return self.show_popup_window(versions, directory)
                else:
                    return versions
                
    def check_version_and_tag(self, tree_item_id, destination_versions):
        if self.remix_folder:
            current_values = list(self.tree.item(tree_item_id, 'values'))
    
            # Update 'Runtime Version' and 'Bridge Version'
            current_values[7] = destination_versions["runtime version"]
            current_values[8] = destination_versions["bridge version"]
            self.tree.item(tree_item_id, values=current_values)
    
            # Check version mismatch and apply tags
            if (destination_versions["runtime version"] != self.source_versions["runtime version"] or
                destination_versions["bridge version"] != self.source_versions["bridge version"]):
                self.tree.item(tree_item_id, tags=("version_mismatch",))
            else:
                self.tree.item(tree_item_id, tags=("version_match",))
    
            # Update UI
            self.tree.update_idletasks()

    def determine_files_to_copy(self, bridge, runtime, dxvk, d3d8to9):
        files_to_copy = []
        try:
            items = os.listdir(self.remix_folder)
        except OSError as e:
            self.status_right.config(text=f"Error reading directory {self.remix_folder}: {e}")
            return files_to_copy  # Return empty list if directory reading fails
    
        if bridge:
            # Exclude specific files unless other conditions include them later
            excluded_files = {"dxvk.conf", "d3d8to9.dll"}
            for file in items:
                os.path.join(self.remix_folder, file)
                if file not in excluded_files and not file.startswith('.'):
                    files_to_copy.append(os.path.join(self.remix_folder, file))
    
        if runtime and '.trex' in items:
            trex_path = os.path.join(self.remix_folder, '.trex')
            if os.path.isdir(trex_path):
                files_to_copy.append(trex_path)
            else:
                self.status_right.config(text='.trex is not a directory or does not exist')
    
        if dxvk and 'dxvk.conf' in items:
            files_to_copy.append(os.path.join(self.remix_folder, 'dxvk.conf'))
        elif dxvk:
            self.status_right.config(text='dxvk.conf not found in the directory')
    
        if d3d8to9 and 'd3d8to9.dll' in items:
            files_to_copy.append(os.path.join(self.remix_folder, 'd3d8to9.dll'))
        elif d3d8to9:
            self.status_right.config(text='d3d8to9.dll not found in the directory')
    
        return files_to_copy

    def copy_files(self):
        global oldVersion
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_right.config(text="No Game is selected for copy.")
            return
    
        self.status_right.config(text=f"Selected items: {selected_items}")
        for item in selected_items:
            self.status_right.config(text=f"Selected items: {item}")
            details = self.tree.item(item, 'values')
            lock, game_name, folder_path, bridge, runtime, dxvk, d3d8to9, _, _ = details
            # Convert 'Yes'/'No' to boolean
            bridge = bridge == 'Yes'
            runtime = runtime == 'Yes'
            dxvk = dxvk == 'Yes'
            d3d8to9 = d3d8to9 == 'Yes'

            self.status_left.config(text=f"Starting copy for {game_name}...")
            files_to_copy = self.determine_files_to_copy(bridge, runtime, dxvk, d3d8to9)
            self.copy_files_threaded(files_to_copy, folder_path, item)
        if oldVersion:
            if os.path.exists(os.path.join(folder_path, "build-names.txt")):
                os.remove(os.path.join(folder_path, "build-names.txt"))
        elif os.path.exists(os.path.join(folder_path, "build_names.txt")):
                os.remove(os.path.join(folder_path, "build_names.txt"))
            
    def setup_status_bar(self):
        self.status_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_left = ttk.Label(self.status_frame, text="RTX-Remix Folder: None", anchor=tk.W)
        self.status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_right = ttk.Label(self.status_frame, text="Please Select the RTX-Remix folder and Game Folder(s) to proceed.", anchor=tk.W)
        self.status_right.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(self.status_frame, orient="horizontal", mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X)
    
    def copy_files_threaded(self, files_to_copy, folder_path, tree_item):
        def thread_target():
            total_files = len(files_to_copy)
            current_file_count = 0
            for source in files_to_copy:
                full_source_path = os.path.join(self.remix_folder, source)
                if os.path.isdir(full_source_path):
                    for dirpath, dirnames, filenames in os.walk(full_source_path):
                        for filename in filenames:
                            rel_dir = os.path.relpath(dirpath, self.remix_folder)
                            dest_dir = os.path.join(folder_path, rel_dir)
                            if not os.path.exists(dest_dir):
                                os.makedirs(dest_dir)
                            src_file = os.path.join(dirpath, filename)
                            dest_file = os.path.join(dest_dir, filename)
                            shutil.copy(src_file, dest_file)
                            current_file_count += 1
                            self.master.after(0, lambda c=current_file_count, t=total_files: self.update_progress_bar(c, t))
                else:
                    destination = os.path.join(folder_path, os.path.basename(full_source_path))
                    shutil.copy(full_source_path, destination)
                    current_file_count += 1
                    self.master.after(0, lambda c=current_file_count, t=total_files: self.update_progress_bar(c, t))
            
            self.master.after(0, lambda: self.status_right.config(text="Copy completed."))
            destination_versions = self.load_versions_from_file(folder_path)
            self.check_version_and_tag(tree_item, destination_versions)

        thread = Thread(target=thread_target)
        thread.start()
    
    def update_progress_bar(self, current, total):
        self.progress_bar['value'] = current / total * 100
        self.status_right.config(text=f"Copying... ({current}/{total})")

    def update_progress(self, src_file, dst_dir):
        self.progress_label.config(text=f"Copying: {os.path.basename(src_file)}")
        self.progress_bar['value'] += os.path.getsize(src_file)
        self.progress_bar.update_idletasks()

    def list_files(self, folder):
        return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            
    def remove_selected_game(self):
        selected_items = self.tree.selection()
        for item in selected_items:
            try:
                self.tree.delete(item)
            except Exception as e:
                self.status_right.config(text=f"Error deleting item {item}: {str(e)}")

    def load_config(self):
        """Loads the configuration from a JSON file and updates the UI accordingly."""
        
        # Attempt to load configuration from a file
        try:
            with open('lazy_RTX_Remix_Companion.conf', 'r') as config_file:
                config = json.load(config_file)
    
                # Update UI with Remix Folder Info
                self.update_remix_folder_info(config)
    
                # Populate Treeview with items from the config
                self.populate_treeview_with_items(config)
    
                # Load and apply window geometry
                self.apply_window_geometry(config)
    
                # Final UI updates and status message
                self.finalize_ui_loading()
                
                self.check_sources(self.remix_folder)
    
        # Handle FileNotFoundError
        except FileNotFoundError:
            self.status_right.config(text="Error: Configuration file not found.")
        
        # Handle JSONDecodeError
        except json.JSONDecodeError:
            self.status_right.config(text="Error: Configuration file is corrupt or unreadable.")
        
        # Handle any other exceptions
        except Exception as e:
            self.status_right.config(text=f"Error: {str(e)}")
    
    def update_remix_folder_info(self, config):
        """Updates the remix folder information on the UI."""
        self.remix_folder = config.get('remix_folder', 'None')
        if self.remix_folder:
            self.remix_folder = self.remix_folder.replace('\\', '/')
            self.status_left.config(text=f"RTX-Remix Folder: {self.remix_folder}")
            self.source_versions = self.load_versions_from_file(self.remix_folder, True)
            version_info = f"RTX-Remix Version: Runtime {self.source_versions['runtime version']}, Bridge {self.source_versions['bridge version']}"
            self.version_label.config(text=version_info)
        else:
            self.status_left.config(text="RTX-Remix Folder: None")
    
    def populate_treeview_with_items(self, config):
        """Populates the Treeview widget with items from the configuration data."""
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
            # Apply tags based on the lock status
            if item[0] == "🔒":
                self.tree.item(newItem, tags=('disable',))
    
    def apply_window_geometry(self, config):
        """Applies saved window geometry from configuration."""
        if 'window_geometry' in config:
            self.master.geometry(config['window_geometry'])
    
    def finalize_ui_loading(self):
        """Final updates to UI post configuration loading."""
        self.update_copy_button_state()
        self.status_right.config(text="Configuration loaded successfully.")
        self.tree.update_idletasks()
            
    def save_config(self):
        treeview_data = self.serialize_treeview()
        if self.remix_folder or treeview_data:
            config = {
                'remix_folder': self.remix_folder,
                'treeview': treeview_data,
                'window_geometry': self.master.geometry()  # Save window size and position
            }
            try:
                with open('lazy_RTX_Remix_Companion.conf', 'w') as config_file:
                    json.dump(config, config_file, indent=4)
                self.status_right.config(text="Configuration saved successfully.")
            except Exception as e:
                self.status_right.config(text=f"Error saving configuration: {str(e)}")
    
    def on_closing(self):
        self.save_config()  # Save the current configuration
        self.master.destroy()  # Close the window
    
def check_python_version():
    # Create a root window but keep it hidden
    root = tk.Tk()
    root.withdraw()
    
    # Check if the current Python version is less than 3.8
    if sys.version_info < (3, 8):
        messagebox.showerror(
            "Version Error",
            "Your Python version is too old. Please download Python 3.8 or newer."
        )
        root.destroy()  # Destroy the hidden root window after displaying the message
        return False
    root.destroy()  # Make sure to clean up the root in case of valid version
    return True

if __name__ == "__main__":
    if not check_python_version():
        sys.exit(1)
    # Main window setup
    root = tk.Tk()
    app = lazy_rtx_remix_companion(root)
    firstLaunch = False
    root.mainloop()