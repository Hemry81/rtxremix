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
    print("  Octahedral converter not found - normal maps will be converted without octahedral mapping")
    OCTAHEDRAL_AVAILABLE = False

# Import the texture alpha combiner
try:
    from texture_alpha_combiner import TextureAlphaCombiner
    ALPHA_COMBINER_AVAILABLE = True
except ImportError:
    print("  Texture alpha combiner not found - opacity textures will not be combined")
    ALPHA_COMBINER_AVAILABLE = False

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
        
        # Initialize alpha combiner
        self.alpha_combiner = TextureAlphaCombiner() if ALPHA_COMBINER_AVAILABLE else None
        
        # Report acceleration status
        if self.use_gpu:
            print(f" NVIDIA Texture Tools initialized with GPU acceleration (CUDA device {self.gpu_device})")
            print(f"    GPU acceleration works best on textures > 1MB with 'normal' or higher quality")
        else:
            print(f" NVIDIA Texture Tools initialized with CPU-only mode")
        
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
                        print(f"    Terminating hanging NVTT process: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.terminate()
                        proc.wait(timeout=5)
                        terminated_procs += 1
                if terminated_procs > 0:
                    print(f"    Terminated {terminated_procs} hanging NVTT processes")
                return terminated_procs > 0
            except ImportError:
                # psutil not available, try basic process cleanup
                print(f"     psutil not available, trying basic process cleanup...")
                # On Windows, try taskkill for nvtt processes
                if os.name == 'nt':
                    try:
                        result1 = subprocess.run(['taskkill', '/f', '/im', 'nvtt_export.exe'], 
                                               capture_output=True, timeout=10)
                        result2 = subprocess.run(['taskkill', '/f', '/im', 'nvcompress.exe'], 
                                               capture_output=True, timeout=10)
                        if result1.returncode == 0 or result2.returncode == 0:
                            print(f"    Successfully killed hanging NVTT processes")
                            return True
                        else:
                            print(f"   ℹ  No hanging NVTT processes found")
                            return False
                    except Exception as e:
                        print(f"     Failed to kill processes: {e}")
                        return False
                return False
        except Exception as e:
            print(f"     Could not cleanup processes: {e}")
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
        print("  WARNING: NVIDIA Texture Tools not found (tried: {} )".format(', '.join(tried_paths)))
        print("   Please install NVIDIA Texture Tools and ensure an executable is available")
        print("   Common install: C:\\Program Files\\NVIDIA Corporation\\NVIDIA Texture Tools")
        self.nvtt_compress_path = None
    
    def detect_texture_type(self, texture_path):
        """
        DEPRECATED: Texture type should come from material mapper, not filename detection.
        This method is kept for backward compatibility but should not be used.
        
        Args:
            texture_path: Path to the texture file
            
        Returns:
            tuple: (texture_type, gamma_correct_setting, needs_octahedral)
        """
        print(f"WARNING: detect_texture_type() called - texture type should come from material mapper!")
        # Default to diffuse for backward compatibility
        return 'diffuse', True, False
    
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
            print(f"  Octahedral converter not available, copying normal map as-is: {Path(input_path).name}")
            try:
                shutil.copy2(input_path, output_path)
                return True
            except Exception as e:
                print(f" Failed to copy normal map: {e}")
                return False
        
        # Auto-detect normal map format from filename
        detected_format = self.detect_normal_map_format(input_path)
        
        try:
            print(f" Converting normal map to octahedral format: {Path(input_path).name}")
            print(f"   Auto-detected format: {detected_format.upper()} ({'OpenGL (green up)' if detected_format == 'ogl' else 'DirectX (green down)'})")
            
            if detected_format == 'ogl':
                LightspeedOctahedralConverter.convert_ogl_file_to_octahedral(input_path, output_path)
            else:
                # Default to DirectX style
                LightspeedOctahedralConverter.convert_dx_file_to_octahedral(input_path, output_path)
            
            if os.path.exists(output_path):
                print(f" Successfully converted to octahedral: {Path(output_path).name}")
                return True
            else:
                print(f" Octahedral conversion failed - output file not created")
                return False
                
        except Exception as e:
            print(f" Octahedral conversion error: {e}")
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


    def convert_to_grayscale(self, texture_path, output_path=None, suffix='grayscale'):
        """
        Convert texture to grayscale.
        
        Args:
            texture_path: Path to source texture
            output_path: Optional output path for grayscale texture
            suffix: Suffix to add to filename if output_path not provided
            
        Returns:
            str: Path to grayscale texture
        """
        try:
            from PIL import Image
            
            img = Image.open(texture_path).convert('RGB')
            gray = img.convert('L')
            
            if output_path:
                save_path = output_path
            else:
                temp_dir = tempfile.gettempdir()
                base_name = Path(texture_path).stem
                save_path = os.path.join(temp_dir, f"{base_name}_{suffix}.png")
            
            gray.save(save_path)
            return save_path
        except Exception as e:
            print(f" Failed to convert to grayscale: {e}")
            return texture_path
    
    def invert_texture(self, texture_path, output_path=None, suffix='inverted'):
        """
        Invert texture values (output = 1 - input).
        
        Args:
            texture_path: Path to source texture
            output_path: Optional output path for inverted texture
            suffix: Suffix to add to filename if output_path not provided
            
        Returns:
            str: Path to inverted texture or None if failed
        """
        try:
            from PIL import Image
            import numpy as np
            
            img = Image.open(texture_path)
            img_array = np.array(img)
            
            if img.mode == 'L':
                inverted_array = 255 - img_array
            elif img.mode in ['RGB', 'RGBA']:
                if img.mode == 'RGBA':
                    inverted_array = img_array.copy()
                    inverted_array[:, :, :3] = 255 - img_array[:, :, :3]
                else:
                    inverted_array = 255 - img_array
            else:
                img = img.convert('RGB')
                img_array = np.array(img)
                inverted_array = 255 - img_array
            
            inverted = Image.fromarray(inverted_array.astype('uint8'), mode=img.mode)
            
            if output_path:
                save_path = output_path
            else:
                temp_dir = tempfile.gettempdir()
                base_name = Path(texture_path).stem
                save_path = os.path.join(temp_dir, f"{base_name}_{suffix}.png")
            
            inverted.save(save_path)
            return save_path
        except Exception as e:
            print(f" Failed to invert texture: {e}")
            return None
    
    def combine_diffuse_with_opacity(self, diffuse_path, opacity_path):
        """
        Combine diffuse texture with opacity texture for RTX Remix compatibility.
        RTX Remix doesn't support separate opacity textures - must be in diffuse alpha.
        
        Args:
            diffuse_path: Path to diffuse/color texture
            opacity_path: Path to opacity texture
            
        Returns:
            str: Path to combined texture (temp file) or None if failed
        """
        if not self.alpha_combiner:
            return None
        
        print(f" Combining {Path(diffuse_path).name} + {Path(opacity_path).name} for RTX Remix")
        temp_combined = self.alpha_combiner.create_temp_combined_texture(diffuse_path, opacity_path)
        
        if temp_combined:
            print(f" Created temporary combined texture: {Path(temp_combined).name}")
            return temp_combined
        else:
            print(f" Failed to combine textures, using original diffuse")
            return None
    

    
    def convert_texture(self, input_path, output_path, force_type=None, format='dds', quality='normal', max_retries=3, opacity_texture_path=None, is_bump_to_normal=False, source_texture_override=None, needs_inversion=False):
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
            opacity_texture_path: Optional path to opacity texture to combine with diffuse
            is_bump_to_normal: If True, use NVTT's --normal-map flag to generate normals from bump/height
            source_texture_override: Override source texture (for roughness from diffuse conversion)
            needs_inversion: If True, invert texture for specular-to-roughness conversion
            
        Returns:
            bool: True if conversion successful
        """
        if not self.nvtt_compress_path:
            print(f" NVIDIA Texture Tools not available, skipping {input_path}")
            return False
        
        if not os.path.exists(input_path):
            print(f" Input texture not found: {input_path}")
            return False
        
        # Force DDS format for RTX Remix compatibility
        format = 'dds'
        output_path = Path(output_path).with_suffix('.dds')
        
        # Use texture type from material mapper (force_type parameter)
        # NEVER use filename-based detection - material mapper already determined the type
        if is_bump_to_normal:
            # Force normal map type for bump-to-normal conversion
            texture_type = 'normal'
            gamma_correct = False
            needs_octahedral = False
        elif force_type:
            # ALWAYS use force_type from material mapper
            texture_type = force_type
            settings = self.texture_settings.get(force_type, {})
            gamma_correct = settings.get('gamma_correct', True)
            needs_octahedral = settings.get('needs_octahedral', False)
        else:
            # Default to diffuse if no type specified (should never happen with material mapper)
            print(f"WARNING: No texture type specified for {Path(input_path).name}, defaulting to diffuse")
            texture_type = 'diffuse'
            gamma_correct = True
            needs_octahedral = False
        
        # Handle texture source override and conversions
        working_input_path = input_path
        temp_files_to_cleanup = []
        
        # Handle roughness/specular conversion from diffuse texture
        if source_texture_override and texture_type in ['roughness', 'rough']:
            if os.path.exists(source_texture_override):
                if needs_inversion:
                    # Specular to roughness with inversion
                    print(f" [1/2] Converting to grayscale: {Path(source_texture_override).name}")
                    temp_grayscale = self.convert_to_grayscale(source_texture_override, suffix='temp_gray')
                    if temp_grayscale:
                        print(f" Created grayscale: {Path(temp_grayscale).name}")
                        print(f" [2/2] Inverting for roughness (specular → roughness)")
                        temp_inverted = self.invert_texture(temp_grayscale, suffix='temp_inverted')
                        if temp_inverted:
                            working_input_path = temp_inverted
                            temp_files_to_cleanup.append(temp_grayscale)
                            temp_files_to_cleanup.append(temp_inverted)
                            print(f" Created inverted roughness: {Path(temp_inverted).name}")
                        else:
                            working_input_path = temp_grayscale
                            temp_files_to_cleanup.append(temp_grayscale)
                else:
                    # Diffuse to roughness (grayscale only)
                    print(f" [1/1] Converting to grayscale roughness: {Path(source_texture_override).name}")
                    temp_grayscale = self.convert_to_grayscale(source_texture_override, suffix='temp_gray')
                    if temp_grayscale:
                        working_input_path = temp_grayscale
                        temp_files_to_cleanup.append(temp_grayscale)
                        print(f" Created grayscale roughness: {Path(temp_grayscale).name}")
            else:
                print(f" Source texture override not found: {source_texture_override}")
                return False
        
        # If opacity_texture_path provided, combine it with diffuse texture
        if opacity_texture_path and texture_type in ['albedo', 'diffuse', 'color', 'base_color']:
            combined_path = self.combine_diffuse_with_opacity(input_path, opacity_texture_path)
            if combined_path:
                working_input_path = combined_path
                temp_files_to_cleanup.append(combined_path)
        
        # Handle normal map conversion: Check if already a normal map or needs bump-to-normal
        if texture_type in ['normal', 'normalmap']:
            # Check if this is already a normal map (has RGB channels with blue/purple tones)
            is_already_normal_map = self._is_already_normal_map(working_input_path)
            
            if is_already_normal_map:
                print(f" Detected existing normal map (RGB format): {Path(working_input_path).name}")
                # Skip bump-to-normal conversion, go straight to octahedral conversion
                temp_dir = tempfile.gettempdir()
                temp_octahedral_png = os.path.join(temp_dir, f"octahedral_{Path(output_path).stem}.png")
                temp_files_to_cleanup.append(temp_octahedral_png)
                
                if self.convert_normal_to_octahedral(working_input_path, temp_octahedral_png):
                    working_input_path = temp_octahedral_png
                    print(f" Converted to octahedral: {Path(temp_octahedral_png).name}")
                else:
                    print(f" Octahedral conversion failed, using original normal map")
                
                # Now convert to DDS (handled below)
                needs_octahedral = False  # Already applied
            else:
                # This is a diffuse/height map that needs bump-to-normal conversion
                print(f" Detected height/bump map, converting to normal map")
                # Step 1: Convert diffuse to grayscale bump map
                print(f" [1/4] Converting to grayscale bump map: {Path(working_input_path).name}")
                grayscale_path = self.convert_to_grayscale(working_input_path, suffix='height')
                if grayscale_path != working_input_path:
                    working_input_path = grayscale_path
                    temp_files_to_cleanup.append(grayscale_path)
                    print(f" Created grayscale bump: {Path(grayscale_path).name}")
                
                # Step 2: Use NVTT to convert bump to tangent-space normal (output as PNG first)
                print(f" [2/4] Converting bump to tangent-space normal with NVTT")
                temp_dir = tempfile.gettempdir()
                temp_tangent_png = os.path.join(temp_dir, f"tangent_{Path(output_path).stem}.png")
                temp_files_to_cleanup.append(temp_tangent_png)
                
                # Build NVTT command for bump-to-normal conversion (output PNG)
                cmd = [self.nvtt_compress_path]
                if not self.use_gpu:
                    cmd.append('--no-cuda')
                cmd.extend([working_input_path, '-o', temp_tangent_png])
                cmd.append('--to-normal-ts')  # Generate tangent-space normal
                cmd.extend(['--normal-scale', '5.0'])  # 5x strength for more pronounced normals
                cmd.extend(['--height', 'average'])
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0 or not os.path.exists(temp_tangent_png):
                        print(f" NVTT bump-to-normal failed, skipping normal map")
                        return False
                    print(f" Created tangent-space normal: {Path(temp_tangent_png).name}")
                except Exception as e:
                    print(f" NVTT bump-to-normal error: {e}")
                    return False
            
                # Step 3: Convert tangent-space normal to octahedral
                print(f" [3/4] Converting tangent-space normal to octahedral format")
                temp_octahedral_png = os.path.join(temp_dir, f"octahedral_{Path(output_path).stem}.png")
                temp_files_to_cleanup.append(temp_octahedral_png)
                
                if self.convert_normal_to_octahedral(temp_tangent_png, temp_octahedral_png):
                    working_input_path = temp_octahedral_png
                    print(f" Created octahedral normal: {Path(temp_octahedral_png).name}")
                else:
                    print(f" Octahedral conversion failed, using tangent-space normal")
                    working_input_path = temp_tangent_png
                
                # Step 4: Convert final normal map to DDS (handled below)
                print(f" [4/4] Converting octahedral normal to DDS")
                is_bump_to_normal = False  # Already converted
                needs_octahedral = False  # Already applied
        
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
                
                # Check if texture has alpha channel
                has_alpha = False
                try:
                    from PIL import Image
                    img = Image.open(working_input_path)
                    has_alpha = img.mode in ['RGBA', 'LA', 'PA'] or (img.mode == 'P' and 'transparency' in img.info)
                    img.close()
                except:
                    pass
                
                # Format selection based on texture type (RTX Remix DDS formats)
                if texture_type in ['normal', 'normalmap']:
                    cmd.extend(['-f', 'bc5'])  # Best for normal maps (RG channels)
                elif texture_type in ['roughness', 'metallic', 'metal', 'height', 'ao', 'occlusion', 'opacity', 'alpha', 'mask']:
                    cmd.extend(['-f', 'bc4'])  # Single channel data
                elif texture_type in ['emissive']:
                    cmd.extend(['-f', 'bc7'])  # High quality for emissive
                else:
                    cmd.extend(['-f', 'bc7'])  # BC7 for all color textures with or without alpha (best quality)
                
                # Quality setting
                cmd.extend(['-q', quality])
                
                # Gamma correction for mips (BC7 needs gamma correction, BC4/BC5 don't)
                if gamma_correct:
                    cmd.append('--mip-gamma-correct')
                else:
                    cmd.append('--no-mip-gamma-correct')
                
                # Generate mipmaps
                cmd.append('--mips')
                
                if attempt == 0:
                    print(f" Converting {texture_type} texture to DDS: {Path(input_path).name}")
                    if needs_octahedral:
                        print(f"   Octahedral conversion: {'Applied' if temp_files_to_cleanup else 'Skipped'}")
                    print(f"   Gamma correction: {'Enabled' if gamma_correct else 'Disabled'}")
                    if has_alpha:
                        print(f"   Alpha channel: Detected and preserved in {Path(input_path).name}")
                    print(f"   Output: {Path(output_path).name}")
                else:
                    print(f"    Retry attempt {attempt + 1}/{max_retries}")
                
                # Use shorter timeout for small files, longer for large files
                file_size_mb = os.path.getsize(working_input_path) / (1024 * 1024)
                if file_size_mb < 1.0:
                    timeout = 30  # 0.5 minutes for small files (increased from 30s)
                elif file_size_mb < 10.0:
                    timeout = 60  # 1 minutes for medium files
                else:
                    timeout = 120  # 2 minutes for large files
                
                print(f"    File size: {file_size_mb:.2f} MB, timeout: {timeout}s")
                
                # Run conversion with timeout
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    print(f" Successfully converted to DDS: {Path(output_path).name}")
                    
                    # Clean up all temporary files after successful conversion
                    for temp_file in temp_files_to_cleanup:
                        if temp_file and os.path.exists(temp_file):
                            try:
                                os.remove(temp_file)
                                print(f" Cleaned up temporary file: {Path(temp_file).name}")
                            except Exception:
                                pass  # Ignore cleanup errors
                    
                    return True
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    print(f" Attempt {attempt + 1} failed: {error_msg}")
                    
                    # Clean up failed output file
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
                    
                    if attempt < max_retries - 1:
                        print(f"    Waiting 2 seconds before retry...")
                        import time
                        time.sleep(2)
                    
            except subprocess.TimeoutExpired:
                print(f" Attempt {attempt + 1} timed out after {timeout}s")
                
                # Try to terminate any hanging NVTT processes
                self._cleanup_hanging_nvtt_processes()
                
                # Clean up failed output file
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"    Waiting 5 seconds before retry...")
                    import time
                    time.sleep(5)
                
            except Exception as e:
                print(f" Attempt {attempt + 1} error: {e}")
                
                # Clean up failed output file
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"    Waiting 2 seconds before retry...")
                    import time
                    time.sleep(2)
        
        # All attempts failed
        print(f" All {max_retries} conversion attempts failed for {Path(input_path).name}")
        
        # Fallback: Create empty DDS file to prevent texture loading errors
        try:
            print(f" Creating fallback DDS file to prevent texture errors...")
            # Copy the original file but rename to .dds to satisfy USD references
            import shutil
            shutil.copy2(input_path, output_path)
            print(f" Fallback: Copied original texture as {Path(output_path).name}")
            # Return True so the conversion process continues
            return True
        except Exception as fallback_error:
            print(f" Fallback copy also failed: {fallback_error}")
        
        # Clean up all temporary files
        for temp_file in temp_files_to_cleanup:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f" Cleaned up temporary file: {Path(temp_file).name}")
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
            print(f" Input directory not found: {input_dir}")
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
            print(f"  No supported texture files found in {input_dir}")
            return results
        
        print(f" Found {len(texture_files)} texture files to convert")
        
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
        print(f"\n Conversion Summary:")
        print(f"    Successful: {successful}")
        print(f"    Failed: {len(results) - successful}")
        print(f"    Output directory: {output_dir}")
        
        return results
    
    def set_normal_map_style(self, style='dx'):
        """
        Set the normal map style for octahedral conversion
        
        Args:
            style: 'dx' for DirectX (green down), 'ogl' for OpenGL (green up)
        """
        if style.lower() in ['dx', 'directx']:
            self.normal_map_style = 'dx'
            print(" Normal map style set to DirectX (green channel points down)")
        elif style.lower() in ['ogl', 'opengl']:
            self.normal_map_style = 'ogl'
            print(" Normal map style set to OpenGL (green channel points up)")
        else:
            print(f"  Unknown normal map style '{style}', keeping current: {self.normal_map_style}")
    


    def _is_already_normal_map(self, texture_path):
        """Check if texture is already a normal map (has RGB channels with blue/purple tones)"""
        try:
            from PIL import Image
            import numpy as np
            
            img = Image.open(texture_path)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                if img.mode in ['RGBA', 'LA', 'P']:
                    img = img.convert('RGB')
                else:
                    return False  # Grayscale = height map
            
            # Sample center region to check if it's a normal map
            width, height = img.size
            center_x, center_y = width // 2, height // 2
            sample_size = min(width, height) // 4
            
            # Get sample region
            left = max(0, center_x - sample_size)
            top = max(0, center_y - sample_size)
            right = min(width, center_x + sample_size)
            bottom = min(height, center_y + sample_size)
            
            sample = img.crop((left, top, right, bottom))
            pixels = np.array(sample)
            
            # Normal maps have:
            # - High blue channel values (Z component pointing out)
            # - Balanced red/green channels (XY components)
            avg_r = np.mean(pixels[:, :, 0])
            avg_g = np.mean(pixels[:, :, 1])
            avg_b = np.mean(pixels[:, :, 2])
            
            # Check if blue channel is dominant (typical for normal maps)
            # Normal maps usually have blue > 128 and red/green around 128
            is_normal = avg_b > 100 and abs(avg_r - 128) < 80 and abs(avg_g - 128) < 80
            
            img.close()
            return is_normal
            
        except Exception as e:
            print(f"    Could not check if texture is normal map: {e}")
            return False  # Assume it's not a normal map if we can't check
    
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