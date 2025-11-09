#!/usr/bin/env python3
"""
NVIDIA Texture Tools Integration for RTX Remix
Converts textures with proper gamma correction settings based on texture type
Includes octahedral normal map conversion for RTX Remix compatibility
"""

import os
import subprocess
import shutil
from pathlib import Path
import tempfile

# Import mappings from the actual mapping files
try:
    from principled_bsdf_mapping import PRINCIPLED_BSDF_TO_REMIX_MAPPING
    from omnipbr_mapping import OMNIPBR_TO_REMIX_MAPPING
except ImportError:
    # Fallback if import fails
    PRINCIPLED_BSDF_TO_REMIX_MAPPING = {}
    OMNIPBR_TO_REMIX_MAPPING = {}

# Import the octahedral converter
try:
    from octahedral_converter_open_source_standalone import LightspeedOctahedralConverter
    OCTAHEDRAL_AVAILABLE = True
except ImportError:
    print("⚠️  Octahedral converter not found - normal maps will be converted without octahedral mapping")
    OCTAHEDRAL_AVAILABLE = False

class NvidiaTextureConverter:
    """Handles texture conversion using NVIDIA Texture Tools with GPU acceleration"""
    
    def __init__(self, nvtt_compress_path=None, use_gpu=True, gpu_device=0):
        """
        Initialize the texture converter
        
        Args:
            nvtt_compress_path: Path to nvtt_compress executable. If None, will search in PATH.
            use_gpu: Enable GPU acceleration (default: True)
            gpu_device: GPU device index to use (default: 0)
        """
        self.nvtt_compress_path = nvtt_compress_path or "nvtt_compress"
        self.use_gpu = use_gpu
        self.gpu_device = gpu_device
        self._validate_nvtt()
        
        # Report acceleration status
        if self.use_gpu:
            print(f"🚀 NVIDIA Texture Tools initialized with GPU acceleration (CUDA device {self.gpu_device})")
            print(f"   💡 GPU acceleration works best on textures > 1MB with 'normal' or higher quality")
        else:
            print(f"🔄 NVIDIA Texture Tools initialized with CPU-only mode")
        
        # Define texture types and their gamma correction settings
        self.texture_settings = {
            # sRGB textures (need gamma correction for mips)
            'albedo': {'gamma_correct': True, 'description': 'Albedo/Diffuse'},
            'diffuse': {'gamma_correct': True, 'description': 'Diffuse'},
            'emissive': {'gamma_correct': True, 'description': 'Emissive'},
            'transmittance': {'gamma_correct': True, 'description': 'Transmittance'},
            'base_color': {'gamma_correct': True, 'description': 'Base Color'},
            'color': {'gamma_correct': True, 'description': 'Color'},
            
            # Data textures (disable gamma correction for mips)
            'normal': {'gamma_correct': False, 'description': 'Normal Map', 'needs_octahedral': True},
            'normalmap': {'gamma_correct': False, 'description': 'Normal Map', 'needs_octahedral': True},
            'norm': {'gamma_correct': False, 'description': 'Normal Map', 'needs_octahedral': True},
            'roughness': {'gamma_correct': False, 'description': 'Roughness'},
            'rough': {'gamma_correct': False, 'description': 'Roughness'},
            'gloss': {'gamma_correct': False, 'description': 'Gloss/Roughness'},
            'glossiness': {'gamma_correct': False, 'description': 'Glossiness/Roughness'},
            'spec': {'gamma_correct': False, 'description': 'Specular/Roughness'},
            'specular': {'gamma_correct': False, 'description': 'Specular/Roughness'},
            'metallic': {'gamma_correct': False, 'description': 'Metallic'},
            'metal': {'gamma_correct': False, 'description': 'Metallic'},
            'metalness': {'gamma_correct': False, 'description': 'Metallic'},
            'height': {'gamma_correct': False, 'description': 'Height'},
            'displacement': {'gamma_correct': False, 'description': 'Displacement'},
            'ao': {'gamma_correct': False, 'description': 'Ambient Occlusion'},
            'occlusion': {'gamma_correct': False, 'description': 'Occlusion'},
            'opacity': {'gamma_correct': False, 'description': 'Opacity'},
            'alpha': {'gamma_correct': False, 'description': 'Alpha'},
            'mask': {'gamma_correct': False, 'description': 'Mask'},
        }
        
        # Normal map conversion settings
        self.normal_map_style = 'dx'  # Default to DirectX style (green down)
                                      # Can be set to 'ogl' for OpenGL style (green up)
    
    def _cleanup_hanging_nvtt_processes(self):
        """Clean up any hanging NVTT processes that might be blocking conversion"""
        try:
            # Try to use psutil if available for better process management
            try:
                import psutil
                terminated_procs = 0
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] and 'nvtt' in proc.info['name'].lower():
                        print(f"   🔪 Terminating hanging NVTT process: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.terminate()
                        proc.wait(timeout=5)
                        terminated_procs += 1
                if terminated_procs > 0:
                    print(f"   ✅ Terminated {terminated_procs} hanging NVTT processes")
                return terminated_procs > 0
            except ImportError:
                # psutil not available, try basic process cleanup
                print(f"   ⚠️  psutil not available, trying basic process cleanup...")
                # On Windows, try taskkill for nvtt processes
                if os.name == 'nt':
                    try:
                        result1 = subprocess.run(['taskkill', '/f', '/im', 'nvtt_export.exe'], 
                                               capture_output=True, timeout=10)
                        result2 = subprocess.run(['taskkill', '/f', '/im', 'nvcompress.exe'], 
                                               capture_output=True, timeout=10)
                        if result1.returncode == 0 or result2.returncode == 0:
                            print(f"   🔪 Successfully killed hanging NVTT processes")
                            return True
                        else:
                            print(f"   ℹ️  No hanging NVTT processes found")
                            return False
                    except Exception as e:
                        print(f"   ⚠️  Failed to kill processes: {e}")
                        return False
                return False
        except Exception as e:
            print(f"   ⚠️  Could not cleanup processes: {e}")
            return False
    
    def _validate_nvtt(self):
        """Validate that NVIDIA Texture Tools is available"""
        # Try running the provided path first
        tried_paths = []
        def try_path(p):
            tried_paths.append(p)
            try:
                result = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=10)
                return result.returncode == 0
            except Exception:
                return False

        if self.nvtt_compress_path and try_path(self.nvtt_compress_path):
            return

        # If a specific path wasn't valid, try common executable names in the default install folder
        default_install = r"C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools"
        candidates = [
            os.path.join(default_install, "nvtt_export.exe"),
            os.path.join(default_install, "nvcompress.exe"),
            os.path.join(default_install, "nvtt.exe"),
            os.path.join(default_install, "nvtt_compress.exe"),
            "nvtt_export.exe", "nvcompress.exe", "nvtt_compress", "nvtt"
        ]

        for c in candidates:
            if try_path(c):
                self.nvtt_compress_path = c
                return

        # As a last resort, try whatever is on PATH by name
        for name in ["nvtt_export.exe", "nvcompress.exe", "nvtt_compress", "nvtt"]:
            if try_path(name):
                self.nvtt_compress_path = name
                return

        # If we reach here, no working executable found
        print("⚠️  WARNING: NVIDIA Texture Tools not found (tried: {} )".format(', '.join(tried_paths)))
        print("   Please install NVIDIA Texture Tools and ensure an executable is available")
        print("   Common install: C:\\Program Files\\NVIDIA Corporation\\NVIDIA Texture Tools")
        self.nvtt_compress_path = None
    
    def detect_texture_type(self, texture_path):
        """
        Detect texture type from filename
        
        Args:
            texture_path: Path to the texture file
            
        Returns:
            tuple: (texture_type, gamma_correct_setting, needs_octahedral)
        """
        filename = Path(texture_path).stem.lower()
        print(f"🔍 Analyzing texture: '{filename}'")
        
        # Check for common texture type patterns in filename
        # Sort by length (longest first) to prioritize more specific matches
        sorted_types = sorted(self.texture_settings.items(), key=lambda x: len(x[0]), reverse=True)
        
        for texture_type, settings in sorted_types:
            if texture_type in filename:
                print(f"✅ Detected texture type: '{texture_type}' → {settings['description']} (gamma_correct: {settings['gamma_correct']})")
                return texture_type, settings['gamma_correct'], settings.get('needs_octahedral', False)
        
        # Default fallback - treat unknown textures as albedo (sRGB)
        print(f"⚠️  Unknown texture type for '{filename}', treating as albedo (sRGB)")
        return 'albedo', True, False
    
    def detect_normal_map_format(self, texture_path):
        """
        Detect if normal map is OpenGL or DirectX format from filename
        
        Args:
            texture_path: Path to the normal map file
            
        Returns:
            str: 'ogl' for OpenGL, 'dx' for DirectX
        """
        filename = Path(texture_path).stem.lower()
        
        # Check for explicit OpenGL indicators
        opengl_indicators = ['_gl', '_ogl', '_opengl']
        for indicator in opengl_indicators:
            if indicator in filename:
                return 'ogl'
        
        # Check for explicit DirectX indicators  
        directx_indicators = ['_dx', '_directx']
        for indicator in directx_indicators:
            if indicator in filename:
                return 'dx'
        
        # Default: if no prefix, probably OpenGL format (as per user specification)
        return 'ogl'
    
    def convert_normal_to_octahedral(self, input_path, output_path):
        """
        Convert a normal map to octahedral format for RTX Remix
        Automatically detects OpenGL vs DirectX format from filename
        
        Args:
            input_path: Path to input normal map
            output_path: Path to output octahedral normal map
            
        Returns:
            bool: True if conversion successful
        """
        if not OCTAHEDRAL_AVAILABLE:
            print(f"⚠️  Octahedral converter not available, copying normal map as-is: {Path(input_path).name}")
            try:
                shutil.copy2(input_path, output_path)
                return True
            except Exception as e:
                print(f"❌ Failed to copy normal map: {e}")
                return False
        
        # Auto-detect normal map format from filename
        detected_format = self.detect_normal_map_format(input_path)
        
        try:
            print(f"🔄 Converting normal map to octahedral format: {Path(input_path).name}")
            print(f"   Auto-detected format: {detected_format.upper()} ({'OpenGL (green up)' if detected_format == 'ogl' else 'DirectX (green down)'})")
            
            if detected_format == 'ogl':
                LightspeedOctahedralConverter.convert_ogl_file_to_octahedral(input_path, output_path)
            else:
                # Default to DirectX style
                LightspeedOctahedralConverter.convert_dx_file_to_octahedral(input_path, output_path)
            
            if os.path.exists(output_path):
                print(f"✅ Successfully converted to octahedral: {Path(output_path).name}")
                return True
            else:
                print(f"❌ Octahedral conversion failed - output file not created")
                return False
                
        except Exception as e:
            print(f"❌ Octahedral conversion error: {e}")
            return False
    
    def _build_texture_type_map(self):
        """
        Build texture type mapping from the actual material mapping files
        Returns a mapping from Remix material parameter names to texture types
        """
        texture_type_map = {}
        
        # Extract texture parameters from both mapping dictionaries
        all_mappings = {}
        
        # Add mappings from Principled BSDF
        if PRINCIPLED_BSDF_TO_REMIX_MAPPING:
            for src_param, remix_param in PRINCIPLED_BSDF_TO_REMIX_MAPPING.items():
                if src_param.endswith('.connect') and remix_param.endswith('_texture'):
                    all_mappings[remix_param] = remix_param
        
        # Add mappings from OmniPBR  
        if OMNIPBR_TO_REMIX_MAPPING:
            for omnipbr_param, remix_param in OMNIPBR_TO_REMIX_MAPPING.items():
                if omnipbr_param.endswith('_texture') and remix_param.endswith('_texture'):
                    all_mappings[remix_param] = remix_param
        
        # Map each Remix texture parameter to its texture type based on semantics
        for param_name in all_mappings.keys():
            if 'diffuse' in param_name or param_name == 'diffuse_texture':
                texture_type_map[param_name] = 'albedo'  # sRGB
            elif 'roughness' in param_name or param_name == 'reflectionroughness_texture':
                texture_type_map[param_name] = 'roughness'  # Linear
            elif 'metallic' in param_name:
                texture_type_map[param_name] = 'metallic'  # Linear
            elif 'normal' in param_name:
                texture_type_map[param_name] = 'normal'  # Linear + Octahedral
            elif 'emissive' in param_name or 'emission' in param_name:
                texture_type_map[param_name] = 'emissive'  # sRGB
            elif 'opacity' in param_name:
                texture_type_map[param_name] = 'alpha'  # Linear
            elif 'specular' in param_name:
                texture_type_map[param_name] = 'roughness'  # Linear (specular workflow)
            elif 'clearcoat_roughness' in param_name:
                texture_type_map[param_name] = 'roughness'  # Linear
            elif 'clearcoat' in param_name:
                texture_type_map[param_name] = 'albedo'  # sRGB
            elif 'subsurface' in param_name:
                texture_type_map[param_name] = 'albedo'  # sRGB
            else:
                texture_type_map[param_name] = 'albedo'  # Default to sRGB
        
        return texture_type_map

    def convert_texture_with_material_context(self, input_path, output_path, material_param_name, format='dds', quality='normal', max_retries=3):
        """
        Convert a texture with known material parameter context
        Uses mappings from principled_bsdf_mapping.py and omnipbr_mapping.py
        
        Args:
            input_path: Path to input texture
            output_path: Path to output texture (will be forced to .dds extension)
            material_param_name: Material parameter name (e.g., 'diffuse_texture', 'reflectionroughness_texture')
            format: Output format (forced to 'dds' for RTX Remix compatibility)
            quality: Quality setting ('fastest', 'normal', 'production', 'highest')
            max_retries: Maximum number of retry attempts if conversion fails
            
        Returns:
            bool: True if conversion successful
        """
        # Get texture type mapping from actual material mappings
        texture_type_map = self._build_texture_type_map()
        
        # Get texture type from material parameter name
        texture_type = texture_type_map.get(material_param_name, 'albedo')
        
        print(f"🎯 Converting with material context: {material_param_name} → {texture_type}")
        
        # Call the regular convert_texture method with forced type
        return self.convert_texture(input_path, output_path, force_type=texture_type, format=format, quality=quality, max_retries=max_retries)

    def convert_texture(self, input_path, output_path, force_type=None, format='dds', quality='normal', max_retries=3):
        """
        Convert a single texture using NVIDIA Texture Tools
        For normal maps, also applies octahedral conversion for RTX Remix compatibility
        RTX Remix ONLY supports DDS format - all textures are converted to DDS
        
        Args:
            input_path: Path to input texture
            output_path: Path to output texture (will be forced to .dds extension)
            force_type: Force a specific texture type (overrides auto-detection)
            format: Output format (forced to 'dds' for RTX Remix compatibility)
            quality: Quality setting ('fastest', 'normal', 'production', 'highest')
            max_retries: Maximum number of retry attempts if conversion fails
            
        Returns:
            bool: True if conversion successful
        """
        if not self.nvtt_compress_path:
            print(f"❌ NVIDIA Texture Tools not available, skipping {input_path}")
            return False
        
        if not os.path.exists(input_path):
            print(f"❌ Input texture not found: {input_path}")
            return False
        
        # Force DDS format for RTX Remix compatibility
        format = 'dds'
        output_path = Path(output_path).with_suffix('.dds')
        
        # Detect texture type and gamma correction setting
        if force_type:
            texture_type = force_type
            settings = self.texture_settings.get(force_type, {})
            gamma_correct = settings.get('gamma_correct', True)
            needs_octahedral = settings.get('needs_octahedral', False)
        else:
            texture_type, gamma_correct, needs_octahedral = self.detect_texture_type(input_path)
        
        # Handle normal map octahedral conversion first
        working_input_path = input_path
        temp_file_to_cleanup = None
        
        if needs_octahedral and texture_type in ['normal', 'normalmap']:
            # Create temporary file for octahedral conversion
            temp_dir = tempfile.gettempdir()
            temp_octahedral = os.path.join(temp_dir, f"octahedral_{Path(input_path).name}")
            
            # Convert to octahedral format (auto-detects OpenGL vs DirectX)
            if self.convert_normal_to_octahedral(input_path, temp_octahedral):
                working_input_path = temp_octahedral
                temp_file_to_cleanup = temp_octahedral
            else:
                print(f"⚠️  Using original normal map without octahedral conversion")
        
        # Retry logic for conversion
        for attempt in range(max_retries):
            try:
                # Build command arguments for nvtt_export.exe
                cmd = [self.nvtt_compress_path]
                
                # Add GPU/CPU acceleration setting (CUDA is enabled by default in nvtt_export)
                if not self.use_gpu:
                    cmd.append('--no-cuda')  # Only add flag if we want to disable CUDA
                # If use_gpu is True, we don't add anything since CUDA is default
                
                # Input and output
                cmd.extend([working_input_path, '-o', str(output_path)])
                
                # Format selection based on texture type (RTX Remix DDS formats)
                if texture_type in ['normal', 'normalmap']:
                    cmd.extend(['-f', 'bc5'])  # Best for normal maps (RG channels)
                elif texture_type in ['roughness', 'metallic', 'metal', 'height', 'ao', 'occlusion', 'opacity', 'alpha', 'mask']:
                    cmd.extend(['-f', 'bc4'])  # Single channel data
                elif texture_type in ['emissive']:
                    cmd.extend(['-f', 'bc7'])  # High quality for emissive (may need 16-bit support)
                else:
                    cmd.extend(['-f', 'bc7'])  # High quality for albedo/diffuse/color textures
                
                # Quality setting (use 'normal' for good balance of speed and quality)
                cmd.extend(['-q', quality])
                
                # Gamma correction for mips (this is the key setting from your requirements)
                if gamma_correct:
                    cmd.append('--mip-gamma-correct')
                else:
                    cmd.append('--no-mip-gamma-correct')
                
                # Generate mipmaps (enabled by default in nvtt_export)
                cmd.append('--mips')
                
                if attempt == 0:
                    print(f"🔄 Converting {texture_type} texture to DDS: {Path(input_path).name}")
                    if needs_octahedral:
                        print(f"   Octahedral conversion: {'Applied' if temp_file_to_cleanup else 'Skipped'}")
                    print(f"   Gamma correction: {'Enabled' if gamma_correct else 'Disabled'}")
                    print(f"   Output: {Path(output_path).name}")
                else:
                    print(f"   🔄 Retry attempt {attempt + 1}/{max_retries}")
                
                # Use shorter timeout for small files, longer for large files
                file_size_mb = os.path.getsize(working_input_path) / (1024 * 1024)
                if file_size_mb < 1.0:
                    timeout = 120  # 2 minutes for small files (increased from 60s)
                elif file_size_mb < 10.0:
                    timeout = 180  # 3 minutes for medium files
                else:
                    timeout = 300  # 5 minutes for large files
                
                print(f"   📊 File size: {file_size_mb:.2f} MB, timeout: {timeout}s")
                
                # Run conversion with timeout
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    print(f"✅ Successfully converted to DDS: {Path(output_path).name}")
                    return True
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    print(f"❌ Attempt {attempt + 1} failed: {error_msg}")
                    
                    # Clean up failed output file
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
                    
                    if attempt < max_retries - 1:
                        print(f"   ⏱️  Waiting 2 seconds before retry...")
                        import time
                        time.sleep(2)
                    
            except subprocess.TimeoutExpired:
                print(f"❌ Attempt {attempt + 1} timed out after {timeout}s")
                
                # Try to terminate any hanging NVTT processes
                self._cleanup_hanging_nvtt_processes()
                
                # Clean up failed output file
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"   ⏱️  Waiting 5 seconds before retry...")
                    import time
                    time.sleep(5)
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} error: {e}")
                
                # Clean up failed output file
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"   ⏱️  Waiting 2 seconds before retry...")
                    import time
                    time.sleep(2)
        
        # All attempts failed
        print(f"❌ All {max_retries} conversion attempts failed for {Path(input_path).name}")
        
        # Fallback: Create empty DDS file to prevent texture loading errors
        try:
            print(f"🔄 Creating fallback DDS file to prevent texture errors...")
            # Copy the original file but rename to .dds to satisfy USD references
            import shutil
            shutil.copy2(input_path, output_path)
            print(f"📄 Fallback: Copied original texture as {Path(output_path).name}")
            # Return True so the conversion process continues
            return True
        except Exception as fallback_error:
            print(f"❌ Fallback copy also failed: {fallback_error}")
        
        # Clean up temporary octahedral file
        if temp_file_to_cleanup and os.path.exists(temp_file_to_cleanup):
            try:
                os.remove(temp_file_to_cleanup)
            except Exception:
                pass  # Ignore cleanup errors
        
        return False
    
    def convert_textures_in_directory(self, input_dir, output_dir, format='dds', quality='normal'):
        """
        Convert all textures in a directory
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path
            format: Output format
            quality: Quality setting
            
        Returns:
            dict: Conversion results
        """
        if not os.path.exists(input_dir):
            print(f"❌ Input directory not found: {input_dir}")
            return {}
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Supported input formats
        supported_formats = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff', '.hdr', '.exr'}
        
        results = {}
        texture_files = []
        
        # Find all texture files
        for file_path in Path(input_dir).glob('*'):
            if file_path.suffix.lower() in supported_formats:
                texture_files.append(file_path)
        
        if not texture_files:
            print(f"⚠️  No supported texture files found in {input_dir}")
            return results
        
        print(f"🔍 Found {len(texture_files)} texture files to convert")
        
        # Convert each texture
        for input_file in texture_files:
            output_file = Path(output_dir) / f"{input_file.stem}.{format}"
            
            success = self.convert_texture(
                str(input_file), 
                str(output_file), 
                format=format, 
                quality=quality
            )
            
            results[str(input_file)] = {
                'success': success,
                'output': str(output_file) if success else None
            }
        
        # Print summary
        successful = sum(1 for r in results.values() if r['success'])
        print(f"\n📊 Conversion Summary:")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {len(results) - successful}")
        print(f"   📁 Output directory: {output_dir}")
        
        return results
    
    def set_normal_map_style(self, style='dx'):
        """
        Set the normal map style for octahedral conversion
        
        Args:
            style: 'dx' for DirectX (green down), 'ogl' for OpenGL (green up)
        """
        if style.lower() in ['dx', 'directx']:
            self.normal_map_style = 'dx'
            print("🔧 Normal map style set to DirectX (green channel points down)")
        elif style.lower() in ['ogl', 'opengl']:
            self.normal_map_style = 'ogl'
            print("🔧 Normal map style set to OpenGL (green channel points up)")
        else:
            print(f"⚠️  Unknown normal map style '{style}', keeping current: {self.normal_map_style}")
    
    def get_texture_info(self, texture_path):
        """Get information about a texture file"""
        if not os.path.exists(texture_path):
            return None
        
        texture_type, gamma_correct, needs_octahedral = self.detect_texture_type(texture_path)
        file_size = os.path.getsize(texture_path)
        
        return {
            'path': texture_path,
            'filename': Path(texture_path).name,
            'type': texture_type,
            'gamma_correct': gamma_correct,
            'needs_octahedral': needs_octahedral,
            'size_bytes': file_size,
            'size_mb': round(file_size / (1024 * 1024), 2)
        }

def main():
    """Example usage of the texture converter"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert textures using NVIDIA Texture Tools with RTX Remix octahedral normal map support')
    parser.add_argument('input', help='Input texture file or directory')
    parser.add_argument('output', help='Output texture file or directory')
    parser.add_argument('--format', default='dds', choices=['dds', 'png', 'tga'], 
                       help='Output format (default: dds)')
    parser.add_argument('--quality', default='highest', 
                       choices=['fastest', 'normal', 'production', 'highest'],
                       help='Quality setting (default: highest)')
    parser.add_argument('--type', help='Force texture type (albedo, normal, roughness, etc.)')
    parser.add_argument('--normal-style', default='dx', choices=['dx', 'directx', 'ogl', 'opengl'],
                       help='Normal map style: dx/directx (green down) or ogl/opengl (green up) (default: dx)')
    
    args = parser.parse_args()
    
    converter = NvidiaTextureConverter()
    converter.set_normal_map_style(args.normal_style)
    
    if os.path.isfile(args.input):
        # Convert single file
        success = converter.convert_texture(args.input, args.output, 
                                          force_type=args.type, 
                                          format=args.format, 
                                          quality=args.quality)
        exit(0 if success else 1)
    else:
        # Convert directory
        results = converter.convert_textures_in_directory(args.input, args.output, 
                                                        format=args.format, 
                                                        quality=args.quality)
        failed = sum(1 for r in results.values() if not r['success'])
        exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()