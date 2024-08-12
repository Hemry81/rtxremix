# Lazy RTX Remix Companion

**Lazy RTX Remix Companion** is a Python script designed to facilitate the easy transfer of RTX-Remix Runtime/Bridge files from the [RTX Remix Downloader](https://github.com/Kim2091/RTX-Remix-Downloader/releases/latest/download/RTX.Remix.Downloader.exe) to multiple game folders.
This tool automates the process of updating game directories with the latest RTX-Remix files, ensuring that users can maintain up-to-date enhancements with minimal effort.

## Features

- **Easy Selection**: Choose your RTX-Remix folder and game directories through a user-friendly interface.
- **Automatic Naming**: Automatically generates game names based on selected folders or allows for custom input.
- **File Selection**: Toggle which specific files (Bridge, Runtimes, dxvk.conf, d3d8to9.dll) to copy to the game folders.
- **Version Checking**: Color-coded text displays whether the game’s RTX-Remix files are up-to-date.
- **Selective Copying**: Temporarily disable copying to specific game folders, useful for avoiding compatibility issues with new versions.
- **Bulk Actions**: Support for selecting all or deselecting all games for actions, with shortcuts for ease.

## How to Use

1. **Download Files**: Use the [RTX Remix Downloader](https://github.com/Kim2091/RTX-Remix-Downloader/releases/latest/download/RTX.Remix.Downloader.exe) to download all necessary files first.
2. **Select RTX-Remix Folder**: Click the "Select RTX-Remix" button to choose the downloaded RTX-Remix files (default folder is named "remix").
3. **Add Game Folder**: Click "Add Game Folder" to add a game directory to the list.
4, **Configure Names**: Upon folder selection, the script auto-generates or allows you to input the game name.
5. **File Preferences**: Choose which specific files you want to copy by toggling them in the interface.
6. **Manage Game List**: Lock game folders to exclude them from copying, or remove them permanently from the list.
7. **Copy Files**: Once satisfied with settings, press "Copy Files" to initiate the transfer of files to selected game folders.

## Installation
1. **Download the Script**: Clone or download this script to a local directory without admin permissions.
2. **Install Python**: Ensure Python 3.8 or higher is installed, available from [Python.org](https://www.python.org/downloads/).
3. **Run the Script**: Execute the script using Python from your command line or terminal.

## Frequently Asked Questions
**Q: Can I use the script standalone without "RTX Remix Downloader"?**  
**A**: *No, the script depends on the RTX Remix Downloader for file downloads and version validation.*

**Q: What are the advantages of this script compared to community scripts?**  
**A**: *This script offers version validation and allows selective file copying with options to temporarily disable copying for compatibility purposes.*

**Q: What features are planned for future updates?**  
**A**: *Planned enhancements include auto-renaming of d3d8to9.dll to d3d8.dll and the ability to rename d3d9.dll to other names like remix.asi.*

**Q: Why was this script developed?**  
**A**: *As suggested by its name, Lazy RTX Remix Companion was created to simplify the process of updating multiple game directories with RTX-Remix files, avoiding the repetitive manual effort.*

## Contributing
Contributions to the Lazy RTX Remix Companion are welcome! Please feel free to fork the repository, make your changes, and submit a pull request. For major changes, please open an issue first to discuss what you would like to change.
