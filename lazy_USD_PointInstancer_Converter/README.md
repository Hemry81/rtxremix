# lazy_USD_PointInstancer_Converter v0.2.0

A powerful USD Point Instancer converter for RTX Remix that automatically detects input format and applies appropriate conversion methods. Built specifically for optimizing USD files from Blender and other DCC tools for use in RTX Remix.

## 🆕 What's New in v0.2.0

- **🎯 Unified Face Counting**: Accurate face counts across all conversion types (forward/reverse/existing)
- **📊 Fixed PointInstancer Counting**: Now uses `protoIndices` for correct per-prototype instance counting
- **🎨 UV Generation**: Automatic placeholder UV generation for meshes missing UV coordinates
- **📋 Enhanced Reporting**: Detailed UV status in GUI with generated/failed/missing mesh lists
- **🔧 Transform Fix**: PointInstancer positions now correctly stored in local space (fixes Blender 3.6 non-instancing)
- **🔄 Blender 4.5.4 Support**: Full compatibility with Blender 4.5.4 LTS `over` specifier prototype structure
- **✅ Verified Accuracy**: Same mesh from different Blender versions shows identical face counts

## 🎯 Purpose

This tool converts USD files between different instancing formats to optimize performance and compatibility with RTX Remix:

- **Forward Conversion**: Instanceable References → PointInstancer (for files with instanceable prims)
- **Reverse Conversion**: Individual Objects → PointInstancer (for files with duplicate blender.data_name)
- **Existing Conversion**: Export external references from PointInstancers (Blender 4.5+ support)
- **Material Conversion**: PrincipledBSDF/OmniPBR → Remix Opacity Materials with automatic alpha blending
- **Texture Processing**: Convert textures to DDS using NVIDIA Texture Tools with GPU acceleration
- **Auto mod.usda Refresh**: Automatically triggers RTX Remix refresh after conversion

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- USD library (usd-core)
- NumPy and Pillow for image processing
- NVIDIA Texture Tools (optional, for DDS conversion)

### Installation

**Automatic (Recommended):**
```bash
# Run the auto-installer batch file
install_requirements.bat
```
The auto-installer will automatically install all required Python dependencies.

**Manual Installation:**
```bash
pip install -r requirements.txt
```

## 💻 Usage

### GUI Mode (Recommended)
```bash
python unified_PointInstancer_converter_ui.py
```

### CLI Mode
```bash
python unified_PointInstancer_converter.py input.usda output.usda [options]
```

## 🖥️ GUI Interface

### Single File Mode Tab
- **Input USD File**: Select source USD file (.usd, .usda, .usdc)
- **Output USD File**: Choose destination file with auto-suggestions
- **Convert Button**: Process single file conversion

### Folder Mode Tab
- **Source Folder**: Select folder containing USD files
- **Destination Folder**: Choose output directory
- **File Selection**: Individual file checkboxes with Select All/None options
- **Convert Selected**: Process only checked files
- **Convert All**: Process entire folder

### Conversion Options
- ✅ **Use External References**: Save prototypes to Instance_Objs folder (always .usd binary)
- ✅ **Export USD Binary**: Output as .usd instead of .usda format
- ✅ **Quiet Mode**: Reduce log verbosity for large files
- ✅ **Convert Textures**: Use NVIDIA Texture Tools for DDS conversion (enabled by default)
- ✅ **Interpolation Control**: vertex→faceVarying, faceVarying→vertex, or no conversion (for RTX Remix compatibility)
- ✅ **Auto-enable Blend Mode**: Automatically enable blend mode for alpha textures (enabled by default)
- ✅ **UV Validation**: Automatic detection and warning for meshes missing UV coordinates

### Processing Log
Real-time conversion progress with detailed status messages, error reporting, and mod.usda refresh status.

## 🔧 CLI Commands

### Basic Usage
```bash
# Simple conversion (textures converted by default)
python unified_PointInstancer_converter.py input.usda output.usda

# With external references
python unified_PointInstancer_converter.py input.usda output.usda --external-refs

# Binary output format
python unified_PointInstancer_converter.py input.usda output.usd --binary

# Disable texture conversion
python unified_PointInstancer_converter.py input.usda output.usda --no-texture-conversion
```

### Advanced Options
```bash
# Full feature conversion
python unified_PointInstancer_converter.py input.usda output.usda \
  --external-refs \
  --binary \
  --interpolation faceVarying

# Disable automatic blend mode for alpha textures
python unified_PointInstancer_converter.py input.usda output.usda --disable-auto-blend

# Generate detailed conversion report
python unified_PointInstancer_converter.py input.usda output.usda --report conversion_report.json

# Help and version info
python unified_PointInstancer_converter.py --help
```

### CLI Arguments Reference

| Argument | Description | Default |
|----------|-------------|---------|
| `input` | Source USD file path | Required |
| `output` | Destination file path | Required |
| `--external-refs` | Use external references (Instance_Objs folder) | False |
| `--binary` | Export as USD binary (.usd) format | False |
| `--convert-textures` | Enable texture conversion (kept for compatibility) | True |
| `--no-texture-conversion` | Disable texture conversion to DDS | False |
| `--interpolation` | Interpolation mode: `faceVarying`, `vertex`, `none` | `faceVarying` |
| `--disable-auto-blend` | Disable automatic blend mode for alpha textures | False |
| `--report FILE` | Generate detailed JSON conversion report | None |
| `--help` | Show help message | - |

## 🎨 Material Conversion

### Supported Input Materials
- **PrincipledBSDF**: Blender's standard material system
- **OmniPBR**: NVIDIA Omniverse materials
- **Custom Materials**: Automatic detection and conversion

### Output Format
All materials are converted to **Remix Opacity Materials** with:
- Unified shader structure
- Optimized texture paths
- RTX Remix compatibility
- Proper alpha handling with automatic blend mode
- Color constants preserved
- Automatic roughness inversion from specular when needed

### Alpha Texture Support
- **Automatic Detection**: Detects opacity connections from diffuse texture alpha channels
- **Auto Blend Mode**: Automatically adds `blend_enabled=true` for alpha textures
- **Configurable**: Can be disabled via `--disable-auto-blend` flag or UI checkbox

## 🖼️ Texture Processing

### NVIDIA Texture Tools Integration
- **Automatic Detection**: Checks for NVTT installation
- **DDS Conversion**: Optimal format for RTX Remix (enabled by default)
- **GPU Acceleration**: CUDA-optimized texture conversion
- **Normal Map Processing**: Octahedral format conversion for RTX Remix
- **Auto-Detection**: Smart texture type recognition (color, normal, roughness, etc.)
- **Gamma Correction**: Automatic sRGB/Linear handling
- **Fallback Support**: Works without NVTT (conversion disabled)

### Supported Texture Types
- **Color/Albedo**: sRGB gamma correction applied
- **Normal Maps**: Octahedral format conversion for RTX Remix
- **Roughness/Metallic**: Linear processing
- **Opacity/Alpha**: Proper alpha channel handling with automatic blend mode
- **Custom Types**: Extensible texture type detection

### Supported Formats
- Input: PNG, JPG, TGA, BMP, HDR (processed directly by NVTT)
- Output: DDS, original format (if NVTT unavailable)

## 🔄 Auto mod.usda Refresh

### Automatic RTX Remix Refresh
- **Auto-Detection**: Searches parent directories for mod.usda file
- **File Watcher Trigger**: Updates mod.usda modification time to trigger RTX Remix auto-refresh
- **Status Reporting**: Shows refresh status in UI and debug output
- **Non-Intrusive**: Works without requiring external references mode

### How It Works
1. Converter searches for mod.usda in parent directories during initialization
2. After successful conversion, mod.usda is opened and saved as text
3. File modification timestamp triggers RTX Remix's file watcher
4. RTX Remix automatically reloads the scene with updated assets

## 📁 File Structure

```
# lazy_USD_PointInstancer_Converter v0.2.0

Convert USD scenes into efficient PointInstancers and Remix‑ready materials. Designed for Blender exports and other DCC USD pipelines.

## 1. Compatibility
- Tested Blender: 3.6, 4.3, 4.4.3, 4.5, 4.5.4, 5.0
- Python 3.8+ • Windows / Linux / macOS
- Works with `.usd`, `.usda`, `.usdc`

## 2. Core Capabilities
| Area | What It Does |
|------|---------------|
| Conversion | Forward (instanceable refs → PointInstancer), Reverse (duplicates → PointInstancer), Existing (extract external prototypes) |
| Materials | PrincipledBSDF & OmniPBR → Remix opacity material (alpha auto‑blend) |
| Textures | Optional DDS conversion via NVIDIA Texture Tools (GPU); normal → octahedral; gamma modes applied |
| Remix Integration | Auto `mod.usda` timestamp bump triggers scene reload |
| Geometry Hygiene | Interpolation fixes, UV validation, attribute cleanup |
| Reporting | Optional JSON conversion report |

## 3. Installation
Recommended:
```bash
install_requirements.bat
```
Manual:
```bash
pip install -r requirements.txt
```

## 4. Quick Start
GUI (recommended):
```bash
python unified_PointInstancer_converter_ui.py
```
CLI basic:
```bash
python unified_PointInstancer_converter.py input.usda output.usda
```

## 5. CLI Reference
Common flags:
- `--external-refs`  store prototypes in `Instance_Objs` as external `.usd`
- `--binary` export output as binary `.usd`
- `--no-texture-conversion` skip DDS conversion
- `--convert-textures` force texture conversion (on by default if available)
- `--interpolation {faceVarying|vertex|none}` control UV/normal interpolation (default `faceVarying`)
- `--disable-auto-blend` keep alpha materials opaque
- `--report FILE` write JSON summary

Examples:
```bash
# External references + binary output
python unified_PointInstancer_converter.py scene.usda optimized.usd --external-refs --binary

# Skip textures
python unified_PointInstancer_converter.py scene.usda optimized.usda --no-texture-conversion

# Vertex interpolation instead of faceVarying
python unified_PointInstancer_converter.py scene.usda optimized.usda --interpolation vertex
```

## 6. Typical Workflows
| Goal | Command |
|------|---------|
| Convert Blender export quickly | `python unified_PointInstancer_converter.py in.usda out.usda` |
| Optimize duplicate meshes | Use reverse mode (auto-detected) |
| Extract external prototypes | Add `--external-refs` |
| Produce small binary | Add `--binary` |
| Skip textures for testing | Add `--no-texture-conversion` |

## 7. Materials & Alpha
- Converts supported shaders into a single Remix opacity material format.
- Diffuse alpha triggers automatic blend (unless disabled).
- Roughness/specular handled with proper channel usage.
- Gamma modes: color/emissive → sRGB; normal/roughness/metallic → linear.

## 8. Texture Handling
- NVTT used if available (GPU accelerated); otherwise textures are left unchanged.
- Normal maps converted to octahedral format when processed.
- Safe fallback if NVTT missing.

## 9. Remix Integration
- Searches parent folders for `mod.usda`.
- Touches file after successful conversion to trigger auto‑reload.

## 10. Troubleshooting
| Issue | Fix |
|-------|-----|
| `ImportError: No module named 'pxr'` | `pip install usd-core` or `pip install usd-python` |
| GUI fails (tkinter) | Install OS package (Linux: `sudo apt-get install python3-tk`) |
| Textures not converting | Install NVIDIA Texture Tools; ensure executable in PATH |
| Alpha not blending | Remove `--disable-auto-blend` flag; ensure diffuse has alpha |
| No auto refresh | Confirm `mod.usda` exists in ancestor path |

## 11. Project Layout
```
unified_PointInstancer_converter_ui.py  # GUI
unified_PointInstancer_converter.py     # CLI coordinator
unified_data_collector.py               # Reads and classifies input
unified_data_converter.py               # Prepares instancing data
unified_output_generator.py             # Writes output + textures + materials
principled_bsdf_mapping.py              # Principled material mapping
omnipbr_mapping.py                      # OmniPBR mapping
nvidia_texture_converter.py             # DDS + normal processing
octahedral_converter_open_source_standalone.py  # Normal map helper
```

## 12. Support
- Open an issue for bugs/questions.

## 13. License & Contribution
- Open source; submit pull requests for improvements.

Made for the RTX Remix community.
- **Python**: 3.8 or higher
- **Operating System**: Windows, Linux, macOS
- **Memory**: 4GB RAM minimum (8GB recommended for large files)
- **Storage**: 1GB free space for temporary files
- **Optional**: NVIDIA Texture Tools for DDS conversion
- **Optional**: CUDA GPU for accelerated texture processing

## 🛠️ Troubleshooting

### Common Issues

**ImportError: No module named 'pxr'**
```bash
pip install usd-core
# or
pip install usd-python
```

**tkinter not found**
- Windows: Usually included with Python
- Linux: `sudo apt-get install python3-tk`
- macOS: Usually included with Python

**Texture conversion fails**
- Install NVIDIA Texture Tools
- Ensure Pillow and NumPy are installed
- Check if nvtt_export.exe is in PATH

**Memory errors with large files**
- Enable quiet mode
- Close other applications
- Increase available RAM

**mod.usda not refreshing**
- Ensure mod.usda exists in parent directories
- Check debug output for mod.usda path detection
- Verify RTX Remix is running and monitoring the mod folder

## 💡 Usage Examples

### Basic Usage
```python
from unified_PointInstancer_converter import CleanUnifiedConverter

# Create converter
converter = CleanUnifiedConverter('input.usda')

# Convert with external references and texture conversion
result = converter.convert(
    'output.usda', 
    use_external_references=True,
    convert_textures=True,
    auto_blend_alpha=True
)

print(f"Converted {result['pointinstancers_processed']} PointInstancers")
print(f"Converted {result['textures_converted']} textures")
print(f"mod.usda refreshed: {result['mod_refreshed']}")
```

### Advanced Usage
```python
# Convert with specific settings
converter = CleanUnifiedConverter('input.usd', export_binary=False)

result = converter.convert(
    output_path='optimized_scene.usda',
    use_external_references=True,      # Create external prototype files
    export_binary=False,               # Output in ASCII format
    convert_textures=True,             # Convert textures to DDS
    normal_map_format="OGL",           # Force OpenGL normal map format
    auto_blend_alpha=True              # Auto-enable blend for alpha textures
)

# Results include detailed metrics
print(f"Operation: {result['operation']}")
print(f"PointInstancers processed: {result['pointinstancers_processed']}")
print(f"External files created: {result['external_files_created']}")
print(f"Materials converted: {result['materials_converted']}")
print(f"Textures converted: {result['textures_converted']}")
print(f"mod.usda refreshed: {result['mod_refreshed']}")
if result['mod_file']:
    print(f"mod.usda path: {result['mod_file']}")
```

## 📋 File Output Structure

```
project/
├── pointInstancer_mesh.usda       # Main scene
├── Instance_Objs/                 # External prototypes (.usd binary)
│   ├── Prototype_0.usd
│   └── Prototype_1.usd
├── textures/                      # Converted DDS textures
│   ├── texture_Color.dds
│   ├── texture_Rough.dds
│   ├── texture_Metal.dds
│   └── texture_Normal.dds
└── materials/                     # RTX Remix materials
    └── AperturePBR_Opacity.usda
```

## 🏆 Key Features

- ✅ **Production Ready**: Successfully tested on real Liberty Remix assets
- ✅ **GPU Accelerated**: NVIDIA Texture Tools integration with CUDA
- ✅ **RTX Remix Optimized**: Unified mesh fixes with configurable interpolation
- ✅ **Accurate Face Counting**: Unified counting system across all conversion types (v0.2.0)
- ✅ **UV Generation**: Automatic placeholder UVs for meshes missing coordinates (v0.2.0)
- ✅ **UV Validation**: Automatic detection with detailed reporting in GUI (v0.2.0)
- ✅ **Transform Accuracy**: Correct local space positioning for all Blender versions (v0.2.0)
- ✅ **Blender 4.5.4 Compatible**: Full support for `over` specifier prototype structure (v0.2.0)
- ✅ **Auto Alpha Blending**: Automatic blend mode for alpha textures
- ✅ **Auto Refresh**: Triggers RTX Remix refresh after conversion
- ✅ **Comprehensive Testing**: 100% success rate on diverse USD files
- ✅ **Professional Architecture**: Clean, modular, and maintainable codebase
- ✅ **Clean Output**: Filtered console output removes technical USD library warnings for better readability

## 📝 License

This project is open source. See individual file headers for specific license information.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

**Made for RTX Remix Community** 🎮✨

**❓ Need Help?**
Just Ask me @Hemry in Discod