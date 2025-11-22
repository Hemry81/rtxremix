#!/usr/bin/env python3
"""
Principled_BSDF to Remix Opacity Material Mapping
Aligned with OmniPBR converter features
"""

from aperture_pbr_parameters import (
    get_texture_gamma_mode,
    matches_default_value
)
from principled_bsdf_parameters import PRINCIPLED_BSDF_TO_REMIX_MAPPING

# Global cache for alpha channel detection to avoid redundant checks
_texture_alpha_cache = {}



def _apply_specular_to_roughness_fallback(remix_params, original_params):
    """
    Apply specular-to-roughness fallback when no roughness texture exists.
    Marks material for texture inversion: roughness = 1 - specular
    """
    has_roughness_texture = 'reflectionroughness_texture' in remix_params
    has_specular_texture = '_specular_texture' in remix_params
    
    if not has_roughness_texture and has_specular_texture:
        # Mark for inversion and use specular texture as roughness source
        remix_params['_invert_for_roughness'] = True
        remix_params['_specular_source'] = remix_params['_specular_texture']
        # Add to original params so it gets processed
        original_params.add('reflectionroughness_texture')
    
    # Clean up temporary specular tracking
    if '_specular_texture' in remix_params:
        del remix_params['_specular_texture']
    if '_specular_constant' in remix_params:
        del remix_params['_specular_constant']
    
    return remix_params

def _check_texture_has_alpha(texture_path, source_textures_dir):
    """
    Check if a texture file has an alpha channel (cached).
    
    Args:
        texture_path: Texture path from material (e.g., './textures/file.png')
        source_textures_dir: Directory containing source textures
    
    Returns:
        bool: True if texture has alpha channel, False otherwise
    """
    global _texture_alpha_cache
    
    # Check cache first
    if texture_path in _texture_alpha_cache:
        return _texture_alpha_cache[texture_path]
    
    try:
        from PIL import Image
        import os
        
        # Extract filename from path
        filename = os.path.basename(texture_path.replace('./textures/', ''))
        base_name = os.path.splitext(filename)[0]
        
        # Try common image extensions
        for ext in ['.png', '.tga', '.bmp']:
            source_file = os.path.join(source_textures_dir, base_name + ext)
            if os.path.exists(source_file):
                img = Image.open(source_file)
                has_alpha = img.mode in ('RGBA', 'LA', 'PA')
                _texture_alpha_cache[texture_path] = has_alpha
                return has_alpha
        
        # File not found or no alpha
        _texture_alpha_cache[texture_path] = False
        return False
        
    except Exception:
        _texture_alpha_cache[texture_path] = False
        return False

def _detect_and_combine_opacity_texture(remix_params, original_params, source_textures_dir=None, auto_blend_alpha=True):
    """
    Detect if material has both diffuse and opacity textures that need combining.
    Also check if diffuse texture has alpha channel when no separate opacity texture exists.
    RTX Remix doesn't support separate opacity_texture - must be in diffuse alpha channel.
    
    Args:
        remix_params (dict): Remix parameters dictionary
        original_params (set): Set of original parameter names
        source_textures_dir (str): Directory containing source textures for alpha detection
        auto_blend_alpha (bool): Whether to auto-enable blend mode for alpha textures
    
    Returns:
        dict: Updated remix parameters with _combine_opacity_with_diffuse flag
    """
    has_diffuse_texture = 'diffuse_texture' in remix_params
    has_opacity_texture = 'opacity_texture' in remix_params
    
    # If we have both diffuse and opacity textures, mark for combination
    if has_diffuse_texture and has_opacity_texture:
        remix_params['_combine_opacity_with_diffuse'] = True
        # Use the ORIGINAL opacity texture path (stored before _fix_texture_parameter)
        if '_opacity_texture_original' in remix_params:
            remix_params['_opacity_texture_path'] = remix_params['_opacity_texture_original']
            del remix_params['_opacity_texture_original']
        else:
            remix_params['_opacity_texture_path'] = remix_params['opacity_texture']
        remix_params['blend_enabled'] = True
        original_params.add('blend_enabled')
        # Remove opacity_texture from final params (will be combined into diffuse alpha)
        del remix_params['opacity_texture']
        original_params.discard('opacity_texture')
    
    # Check if diffuse texture has alpha channel (only if no separate opacity texture and auto_blend enabled)
    elif has_diffuse_texture and not has_opacity_texture and auto_blend_alpha and source_textures_dir:
        # Use ORIGINAL path (before DDS conversion) for alpha detection
        diffuse_path = remix_params.get('_diffuse_texture_original', remix_params.get('diffuse_texture', ''))
        if diffuse_path and _check_texture_has_alpha(diffuse_path, source_textures_dir):
            # Diffuse has alpha channel - disable legacy alpha state and enable blend
            remix_params['use_legacy_alpha_state'] = False
            remix_params['blend_enabled'] = True
            original_params.add('use_legacy_alpha_state')
            original_params.add('blend_enabled')
        # Clean up temporary original path
        if '_diffuse_texture_original' in remix_params:
            del remix_params['_diffuse_texture_original']
    
    return remix_params


def _has_pbr_suffix(filename):
    """Check if filename already has a PBR suffix"""
    lower = filename.lower()
    pbr_suffixes = ['_diffuse', '_albedo', '_basecolor', '_color', 
                    '_normal', '_norm', '_bump', '_height',
                    '_roughness', '_rough', '_gloss', '_glossiness',
                    '_metallic', '_metal', '_metalness',
                    '_ao', '_occlusion', '_ambient',
                    '_emissive', '_emission', '_glow',
                    '_opacity', '_alpha', '_transparency']
    return any(lower.endswith(suffix) for suffix in pbr_suffixes)

def _fix_texture_parameter(value, texture_param_name):
    """
    Fix texture parameter format for Remix materials.
    Only adds PBR suffix if texture doesn't already have one.
    
    Args:
        value: The texture path value
        texture_param_name: The name of the texture parameter
    
    Returns:
        str: Properly formatted texture_2d() string
    """
    import os
    
    gamma_mode = get_texture_gamma_mode(texture_param_name)
    tex_gamma = 'tex::gamma_srgb' if gamma_mode == 'srgb' else 'tex::gamma_linear'
    
    if not value or value == '""' or (value.startswith('</') and value.endswith('.outputs:rgb>')):
        return f'texture_2d("", {tex_gamma})'
    
    texture_path = value.strip('@')
    
    if texture_path and isinstance(texture_path, str):
        slot_type = texture_param_name.replace('_texture', '').replace('map', '')
        base_name = os.path.splitext(os.path.basename(texture_path))[0]
        
        # Check if texture already has a PBR suffix
        if _has_pbr_suffix(base_name):
            # Already has suffix, don't add another
            unique_name = f"{base_name}.dds"
        elif slot_type == 'diffuse':
            # Diffuse without suffix gets _albedo
            unique_name = f"{base_name}_albedo.dds"
        else:
            # Add appropriate suffix
            suffix = 'roughness' if slot_type == 'reflectionroughness' else slot_type
            unique_name = f"{base_name}_{suffix}.dds"
        
        return f'texture_2d("./textures/{unique_name}", {tex_gamma})'
    
    return f'texture_2d("{value}", {tex_gamma})'


def convert_to_remix(principled_params):
    """Standardized conversion function - converts Principled_BSDF parameters to Remix parameters"""
    return convert_principled_bsdf_to_remix(principled_params)

def convert_principled_bsdf_to_remix(principled_params):
    """
    Convert Principled_BSDF or UsdPreviewSurface parameters to Remix Opacity Material parameters
    Ensures ALL compatible values are copied including albedo/diffuse color, roughness, metalness
    
    Args:
        principled_params (dict): Dictionary of Principled_BSDF or UsdPreviewSurface parameters
        
    Returns:
        dict: Converted Remix parameters with _original_params tracking
    """
    remix_params = {}
    original_params = set()
    
    # Don't start with defaults - only add parameters that exist in source
    
    # CRITICAL: First pass - check if emission exists in original material
    has_emission_params = False
    emissive_color = None
    emissive_texture = None
    
    for principled_param, value in principled_params.items():
        if principled_param.endswith('_is_texture'):
            continue
            
        # Check for emission color parameter existence
        if principled_param in ['inputs:emissiveColor', 'emissiveColor']:
            has_emission_params = True
            emissive_color = value
                
        # Check for emission texture parameter existence
        is_texture = principled_params.get(f"{principled_param}_is_texture", False)
        if is_texture and principled_param in ['emissiveColor', 'inputs:emissiveColor']:
            has_emission_params = True
            emissive_texture = value
        elif principled_param.endswith('.connect') and 'emissiveColor' in principled_param:
            has_emission_params = True
            emissive_texture = value
    
    # Check for texture bending fallbacks BEFORE processing parameters
    has_roughness_texture = principled_params.get('inputs:roughness_is_texture', False)
    has_specular_texture = principled_params.get('inputs:specular_is_texture', False)
    has_diffuse_texture = principled_params.get('inputs:diffuseColor_is_texture', False)
    
    roughness_path = principled_params.get('inputs:roughness')
    diffuse_path = principled_params.get('inputs:diffuseColor')
    specular_path = principled_params.get('inputs:specular')
    
    # Helper to normalize paths for comparison
    def normalize_path(path):
        if not path or not isinstance(path, str):
            return None
        import os
        clean = path.strip('@').replace('./textures/', '').replace('\\', '/')
        return os.path.basename(clean).lower()
    
    roughness_file = normalize_path(roughness_path)
    diffuse_file = normalize_path(diffuse_path)
    specular_file = normalize_path(specular_path)
    
    # Check if roughness texture is same as diffuse (Blender blending trick)
    if has_roughness_texture and has_diffuse_texture and roughness_file and diffuse_file and roughness_file == diffuse_file:
        # Roughness uses same texture as diffuse - need grayscale conversion
        import os
        clean_path = diffuse_path.strip('@').replace('./textures/', '')
        base_name = os.path.splitext(os.path.basename(clean_path))[0]
        roughness_texture = f"./textures/{base_name}_roughness.dds"
        
        remix_params['_use_diffuse_for_roughness'] = True
        remix_params['_diffuse_source'] = diffuse_path  # Store ORIGINAL path before _fix_texture_parameter
        remix_params['reflectionroughness_texture'] = roughness_texture
        original_params.add('reflectionroughness_texture')
    elif not has_roughness_texture and has_specular_texture:
        # No roughness texture - check if specular is same as diffuse
        if specular_path and diffuse_file and specular_file == diffuse_file:
            # Specular uses same texture as diffuse - use diffuse source with inversion
            import os
            clean_path = diffuse_path.strip('@').replace('./textures/', '')
            base_name = os.path.splitext(os.path.basename(clean_path))[0]
            roughness_texture = f"./textures/{base_name}_roughness.dds"
            
            remix_params['_invert_for_roughness'] = True
            remix_params['_diffuse_source'] = diffuse_path  # Use diffuse as source, not specular
            remix_params['reflectionroughness_texture'] = roughness_texture
            original_params.add('reflectionroughness_texture')
        elif specular_path:
            # Specular has its own texture - use specular source with inversion
            import os
            clean_path = specular_path.strip('@').replace('./textures/', '')
            base_name = os.path.splitext(os.path.basename(clean_path))[0]
            roughness_texture = f"./textures/{base_name}_roughness.dds"
            
            remix_params['_invert_for_roughness'] = True
            remix_params['_specular_source'] = specular_path  # Store ORIGINAL path before _fix_texture_parameter
            remix_params['reflectionroughness_texture'] = roughness_texture
            original_params.add('reflectionroughness_texture')
    
    # CRITICAL: Check for opacity texture BEFORE processing other parameters
    # If opacity is a texture (alpha channel from diffuse), enable alpha blending
    # Only if auto_blend_alpha is enabled (default True)
    auto_blend_alpha = principled_params.get('_auto_blend_alpha', True)
    if principled_params.get('inputs:opacity_is_texture', False):
        if auto_blend_alpha:
            remix_params['use_legacy_alpha_state'] = True
            remix_params['blend_enabled'] = True
            original_params.add('use_legacy_alpha_state')
            original_params.add('blend_enabled')
    
    # Second pass: copy ALL texture values and constant values (skip emission if not in original)
    for principled_param, value in principled_params.items():
        # Skip texture markers
        if principled_param.endswith('_is_texture'):
            continue
        
        # Skip emission parameters if no emission in original
        if not has_emission_params and 'emissive' in principled_param.lower():
            continue
        
        # Skip specular if using it for roughness fallback
        if principled_param == 'inputs:specular' and remix_params.get('_invert_for_roughness'):
            continue
        
        # Skip opacity CONSTANT - we don't use opacity_constant in Remix
        # But DO process opacity TEXTURE connections (will be combined with diffuse alpha)
        if principled_param in ['inputs:opacity', 'opacity'] and not is_texture:
            continue
            
        # Check if this is a texture parameter
        is_texture = principled_params.get(f"{principled_param}_is_texture", False)
        
        if is_texture:
            # This is a resolved texture parameter - apply _fix_texture_parameter for slot suffixes
            if principled_param in ['diffuseColor', 'inputs:diffuseColor']:
                # Store ORIGINAL path for alpha detection (before DDS conversion)
                remix_params['_diffuse_texture_original'] = value
                remix_params['_diffuse_texture_source'] = value
                remix_params['diffuse_texture'] = _fix_texture_parameter(value, 'diffuse_texture')
                original_params.add('diffuse_texture')
            elif principled_param in ['metallic', 'inputs:metallic']:
                remix_params['_metallic_texture_source'] = value
                remix_params['metallic_texture'] = _fix_texture_parameter(value, 'metallic_texture')
                original_params.add('metallic_texture')
            elif principled_param in ['roughness', 'inputs:roughness']:
                remix_params['_reflectionroughness_texture_source'] = value
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(value, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
            elif principled_param in ['anisotropy', 'inputs:anisotropy']:
                remix_params['_anisotropy_texture_source'] = value
                remix_params['anisotropy_texture'] = _fix_texture_parameter(value, 'anisotropy_texture')
                original_params.add('anisotropy_texture')
            elif principled_param in ['normal', 'inputs:normal']:
                remix_params['_normalmap_texture_source'] = value
                remix_params['normalmap_texture'] = _fix_texture_parameter(value, 'normalmap_texture')
                original_params.add('normalmap_texture')
            elif principled_param in ['opacity', 'inputs:opacity']:
                # Store ORIGINAL path for opacity combination (before _fix_texture_parameter)
                remix_params['_opacity_texture_original'] = value
                remix_params['_opacity_texture_source'] = value
                remix_params['opacity_texture'] = _fix_texture_parameter(value, 'opacity_texture')
                original_params.add('opacity_texture')
            
        elif principled_param.endswith('.connect'):
            # Handle resolved texture connections - apply _fix_texture_parameter for slot suffixes
            base_param = principled_param.replace('inputs:', '').replace('.connect', '')
            if base_param in ['diffuseColor']:
                # Store ORIGINAL path for alpha detection (before DDS conversion)
                remix_params['_diffuse_texture_original'] = value
                remix_params['_diffuse_texture_source'] = value
                remix_params['diffuse_texture'] = _fix_texture_parameter(value, 'diffuse_texture')
                original_params.add('diffuse_texture')
            elif base_param in ['metallic']:
                remix_params['_metallic_texture_source'] = value
                remix_params['metallic_texture'] = _fix_texture_parameter(value, 'metallic_texture')
                original_params.add('metallic_texture')
            elif base_param in ['roughness']:
                remix_params['_reflectionroughness_texture_source'] = value
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(value, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
            elif base_param in ['specular']:
                # Store specular texture for potential roughness fallback (don't fix yet, will be fixed when used)
                remix_params['_specular_texture'] = value
            elif base_param in ['anisotropy']:
                remix_params['_anisotropy_texture_source'] = value
                remix_params['anisotropy_texture'] = _fix_texture_parameter(value, 'anisotropy_texture')
                original_params.add('anisotropy_texture')
            elif base_param in ['normal']:
                remix_params['_normalmap_texture_source'] = value
                remix_params['normalmap_texture'] = _fix_texture_parameter(value, 'normalmap_texture')
                original_params.add('normalmap_texture')
            elif base_param in ['opacity']:
                # Opacity connection detected - add opacity texture for combination
                remix_params['_opacity_texture_source'] = value
                remix_params['opacity_texture'] = _fix_texture_parameter(value, 'opacity_texture')
                original_params.add('opacity_texture')
                # Only enable blend if auto_blend_alpha is True
                if principled_params.get('_auto_blend_alpha', True):
                    remix_params['use_legacy_alpha_state'] = True
                    remix_params['blend_enabled'] = True
                    original_params.add('use_legacy_alpha_state')
                    original_params.add('blend_enabled')
            
        else:
            # This is a constant parameter - copy ALL compatible constants
            if value is not None:
                
                # === DIFFUSE/ALBEDO COLOR ===
                if principled_param in ['diffuseColor', 'inputs:diffuseColor']:
                    # Only store color constant if there's NO texture (avoid assigning texture path to constant)
                    has_diffuse_texture = 'diffuse_texture' in remix_params or any(k.endswith('diffuseColor.connect') for k in principled_params.keys())
                    if not has_diffuse_texture:
                        if isinstance(value, (tuple, list)) and len(value) >= 3:
                            # Store as tuple for proper USD conversion
                            remix_params['diffuse_color_constant'] = (float(value[0]), float(value[1]), float(value[2]))
                        elif isinstance(value, str) and value.startswith('(') and value.endswith(')'):
                            # Parse string tuple like "(0.8, 0.8, 0.8)"
                            try:
                                values = value.strip('()').split(',')
                                remix_params['diffuse_color_constant'] = (float(values[0]), float(values[1]), float(values[2]))
                            except:
                                remix_params['diffuse_color_constant'] = value
                        else:
                            # Skip if value looks like a texture path
                            if not isinstance(value, str) or not ('.png' in value or '.jpg' in value or '.dds' in value or '.tga' in value):
                                remix_params['diffuse_color_constant'] = value
                        if 'diffuse_color_constant' in remix_params:
                            original_params.add('diffuse_color_constant')
                
                # === METALLIC VALUE ===
                elif principled_param in ['metallic', 'inputs:metallic']:
                    if isinstance(value, (int, float)):
                        metal_val = float(value)
                        if not matches_default_value('metallic_constant', metal_val):
                            remix_params['metallic_constant'] = metal_val
                            original_params.add('metallic_constant')
                    elif isinstance(value, str):
                        try:
                            metal_val = float(value)
                            if not matches_default_value('metallic_constant', metal_val):
                                remix_params['metallic_constant'] = metal_val
                                original_params.add('metallic_constant')
                        except ValueError:
                            pass
                
                # === ROUGHNESS VALUE ===
                elif principled_param in ['roughness', 'inputs:roughness']:
                    # Skip roughness constant if using specular-to-roughness fallback
                    if not remix_params.get('_invert_for_roughness'):
                        if isinstance(value, (int, float)):
                            rough_val = float(value)
                            if not matches_default_value('reflection_roughness_constant', rough_val):
                                remix_params['reflection_roughness_constant'] = rough_val
                                original_params.add('reflection_roughness_constant')
                        elif isinstance(value, str):
                            try:
                                rough_val = float(value)
                                if not matches_default_value('reflection_roughness_constant', rough_val):
                                    remix_params['reflection_roughness_constant'] = rough_val
                                    original_params.add('reflection_roughness_constant')
                            except ValueError:
                                pass
                
                # === SPECULAR VALUE (for roughness inversion when roughness=1 and specular!=0) ===
                elif principled_param in ['specular', 'inputs:specular']:
                    specular_val = float(value) if isinstance(value, (int, float)) else (float(value) if isinstance(value, str) else 0.0)
                    # Check if roughness is 1.0 and specular is not 0 - need to invert
                    roughness_val = principled_params.get('inputs:roughness', principled_params.get('roughness', 0.0))
                    if isinstance(roughness_val, (int, float)) and roughness_val == 1.0 and specular_val != 0.0:
                        # Invert: roughness = 1 - specular
                        remix_params['reflection_roughness_constant'] = 1.0 - specular_val
                        original_params.add('reflection_roughness_constant')
                    # Store specular for potential texture fallback
                    remix_params['_specular_constant'] = specular_val
                
                # === ANISOTROPY VALUE ===
                elif principled_param in ['anisotropy', 'inputs:anisotropy']:
                    if isinstance(value, (int, float)):
                        aniso_val = float(value)
                        if not matches_default_value('anisotropy_constant', aniso_val):
                            remix_params['anisotropy_constant'] = aniso_val
                            original_params.add('anisotropy_constant')
                    elif isinstance(value, str):
                        try:
                            aniso_val = float(value)
                            if not matches_default_value('anisotropy_constant', aniso_val):
                                remix_params['anisotropy_constant'] = aniso_val
                                original_params.add('anisotropy_constant')
                        except ValueError:
                            pass
                
                # === EMISSIVE COLOR ===
                elif principled_param in ['emissiveColor', 'inputs:emissiveColor']:
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        # Store as tuple for proper USD conversion
                        remix_params['emissive_color_constant'] = (float(value[0]), float(value[1]), float(value[2]))
                    elif isinstance(value, str) and value.startswith('(') and value.endswith(')'):
                        # Parse string tuple
                        try:
                            values = value.strip('()').split(',')
                            remix_params['emissive_color_constant'] = (float(values[0]), float(values[1]), float(values[2]))
                        except:
                            remix_params['emissive_color_constant'] = value
                    else:
                        remix_params['emissive_color_constant'] = value
                    original_params.add('emissive_color_constant')
                
                # Skip opacity_constant (not used in Remix, only opacity_texture for alpha)
                
                # NOTE: The following parameters are NOT processed because they don't exist in AperturePBR_Opacity.mdl:
                # - inputs:specular -> specular_constant (no specular parameter exists)
                # - inputs:ior -> ior_constant (no IOR parameter exists)
                # - inputs:clearcoat -> clearcoat_constant (no clearcoat parameters exist)
                # - inputs:clearcoatRoughness -> clearcoat_roughness_constant (no clearcoat parameters exist)
                # - inputs:subsurface -> subsurface_constant (no subsurface_constant parameter exists)
                # - inputs:subsurfaceColor -> subsurface_color_constant (no subsurface_color_constant parameter exists)
    
    # CRITICAL: Only add emission parameters if there's an emissive TEXTURE (not just color)
    if has_emission_params and emissive_texture:
        # Only enable emission if there's a texture
        remix_params['enable_emission'] = True
        original_params.add('enable_emission')
        remix_params['emissive_intensity'] = 1.0
        original_params.add('emissive_intensity')
    else:
        # Remove emissive_color_constant if no texture (don't pass color-only emission)
        if 'emissive_color_constant' in remix_params:
            del remix_params['emissive_color_constant']
            original_params.discard('emissive_color_constant')
    
    # Remove opacity_constant if present (not used in Remix, only opacity_texture for alpha)
    if 'opacity_constant' in remix_params:
        del remix_params['opacity_constant']
        original_params.discard('opacity_constant')
    
    # Apply specular-to-roughness fallback if needed
    remix_params = _apply_specular_to_roughness_fallback(remix_params, original_params)
    
    # Detect and handle opacity texture combination
    source_textures_dir = principled_params.get('_source_textures_dir')
    auto_blend_alpha = principled_params.get('_auto_blend_alpha', True)
    remix_params = _detect_and_combine_opacity_texture(remix_params, original_params, source_textures_dir, auto_blend_alpha)
    
    # Texture deduplication is now handled by _fix_texture_parameter with slot prefixes
    # No need for manual split detection - each slot gets unique prefix automatically
    
    # Check if normal map texture is actually a bump/height map (needs bump-to-normal conversion)
    normal_tex_source = remix_params.get('_normalmap_texture_source')
    if normal_tex_source:
        import os
        normal_clean = normal_tex_source.strip('@').replace('./textures/', '')
        filename_lower = os.path.splitext(normal_clean)[0].lower()
        
        # Detect bump textures by filename ending with bump/height/displacement
        if filename_lower.endswith('_bump') or filename_lower.endswith('bump') or \
           filename_lower.endswith('_height') or filename_lower.endswith('height') or \
           filename_lower.endswith('_displacement') or filename_lower.endswith('displacement'):
            # Mark this as a bump texture that needs normal generation
            remix_params['_is_bump_texture'] = True
            # Get base name without bump/height/displacement suffix
            base_name = os.path.splitext(os.path.basename(normal_clean))[0]
            for suffix in ['_bump', '_height', '_displacement']:
                if base_name.lower().endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
            # Update normalmap_texture to use _normal suffix (needs bump-to-normal conversion)
            remix_params['_normalmap_texture_source'] = normal_tex_source
            remix_params['normalmap_texture'] = f'texture_2d("./textures/{base_name}_normal.dds", tex::gamma_linear)'
            # Height texture uses _height suffix (just DDS conversion, no processing)
            remix_params['_height_texture_source'] = normal_tex_source
            remix_params['height_texture'] = f'texture_2d("./textures/{base_name}_height.dds", tex::gamma_linear)'
            original_params.add('height_texture')
    
    # Store original parameter names for filtering
    remix_params['_original_params'] = original_params
    
    return remix_params

def _apply_special_transformations(remix_params, principled_params):
    """Apply special transformations for complex parameter relationships"""
    
    # Check if emission is explicitly disabled
    enable_emission = remix_params.get('enable_emission', True)  # Default to True for backward compatibility
    
    # Only enable emission if explicitly enabled AND (emissive texture exists OR emissive color is not black)
    if enable_emission:
        if 'emissive_mask_texture' in remix_params:
            remix_params['enable_emission'] = True
        elif 'emissive_color_constant' in remix_params:
            emissive_color = remix_params['emissive_color_constant']
            if isinstance(emissive_color, str) and 'color(0.0, 0.0, 0.0)' not in emissive_color:
                remix_params['enable_emission'] = True
            else:
                remix_params['enable_emission'] = False
        else:
            remix_params['enable_emission'] = False
    else:
        # If emission is explicitly disabled, remove all emission-related parameters
        remix_params['enable_emission'] = False
        # Remove emission-related parameters if no emission mask texture is assigned
        if 'emissive_mask_texture' not in remix_params:
            if 'emissive_color_constant' in remix_params:
                del remix_params['emissive_color_constant']
            if 'emissive_intensity' in remix_params:
                del remix_params['emissive_intensity']
    
    # Handle opacity for transparency
    if 'opacity_constant' in remix_params:
        opacity = remix_params['opacity_constant']
        if isinstance(opacity, (int, float)) and opacity < 1.0:
            remix_params['blend_enabled'] = True

def parse_principled_bsdf_from_usd(usd_content, usd_file_dir=None):
    """
    Parse Principled_BSDF materials from USD content
    
    Args:
        usd_content (str): USD file content
        usd_file_dir (str): Directory of USD file for texture verification
        
    Returns:
        dict: Dictionary of material names to their parameters
    """
    import re
    
    materials = {}
    
    # First, extract all texture file paths from the USD content (with existence check)
    texture_paths = _extract_texture_paths(usd_content, usd_file_dir)
    
    # Find all Material definitions using state machine for nested braces
    i = 0
    while i < len(usd_content):
        # Find next Material definition
        material_start = usd_content.find('def Material "', i)
        if material_start == -1:
            break
        
        # Find the material name
        name_start = material_start + len('def Material "')
        name_end = usd_content.find('"', name_start)
        if name_end == -1:
            i = material_start + 1
            continue
        
        material_name = usd_content[name_start:name_end]
        
        # Find the opening brace
        brace_start = usd_content.find('{', name_end)
        if brace_start == -1:
            i = name_end + 1
            continue
        
        # Find the matching closing brace using state machine
        brace_count = 1
        j = brace_start + 1
        while j < len(usd_content) and brace_count > 0:
            if usd_content[j] == '{':
                brace_count += 1
            elif usd_content[j] == '}':
                brace_count -= 1
            j += 1
        
        if brace_count > 0:
            i = brace_start + 1
            continue
        
        # Extract the material content
        material_content = usd_content[brace_start + 1:j - 1]
        
        # Check if this material has a Principled_BSDF shader
        if 'Principled_BSDF' in material_content:
            # Extract Principled_BSDF parameters
            principled_params = _extract_principled_bsdf_params(material_content)
            
            # Resolve texture connections to actual file paths
            principled_params = _resolve_texture_connections(principled_params, texture_paths, material_name)
            
            materials[material_name] = principled_params
        
        # Move to next position
        i = j
    
    return materials

def parse_principled_bsdf_from_usda_file(usda_file_path):
    """
    Parse Principled_BSDF material from USD file
    
    Args:
        usda_file_path (str): Path to the USD file
        
    Returns:
        dict: Dictionary of material names to their parameters
    """
    import os
    
    if not os.path.exists(usda_file_path):
        raise FileNotFoundError(f"USD file not found: {usda_file_path}")
    
    with open(usda_file_path, 'r', encoding='utf-8') as f:
        usd_content = f.read()
    
    usd_file_dir = os.path.dirname(usda_file_path)
    return parse_principled_bsdf_from_usd(usd_content, usd_file_dir)

def parse_material(material_prim):
    """Standardized parse function - parses Principled_BSDF or UsdPreviewSurface material from USD prim"""
    return parse_principled_bsdf_material(material_prim)

def parse_principled_bsdf_material(material_prim):
    """
    Parse Principled_BSDF or UsdPreviewSurface material from a single material prim.
    UsdPreviewSurface is essentially PrincipledBSDF without the shader name (old Blender export).
    
    Args:
        material_prim: USD material prim
        
    Returns:
        dict: Material parameters or None if not found
    """
    try:
        from pxr import UsdShade
        
        # Try UsdPreviewSurface detection first (more common in Blender exports)
        material = UsdShade.Material(material_prim)
        surface_output = material.GetSurfaceOutput()
        
        if surface_output:
            connected_source = surface_output.GetConnectedSource()
            if connected_source and len(connected_source) > 0 and connected_source[0]:
                shader = UsdShade.Shader(connected_source[0])
                shader_id = shader.GetIdAttr().Get()
                
                # Detect UsdPreviewSurface (old Blender format)
                if shader_id == 'UsdPreviewSurface':
                    return _parse_usdpreviewsurface_from_shader(shader, material_prim)
        
        # Fallback to Principled_BSDF text parsing
        stage_layer = material_prim.GetStage().GetRootLayer()
        stage_content = stage_layer.ExportToString()
        
        import os
        usd_file_path = stage_layer.identifier
        usd_file_dir = os.path.dirname(usd_file_path) if usd_file_path else None
        
        principled_materials = parse_principled_bsdf_from_usd(stage_content, usd_file_dir)
        
        material_name = material_prim.GetName()
        if material_name in principled_materials:
            return principled_materials[material_name]
        
        return None
            
    except Exception as e:
        print(f"Error parsing material {material_prim.GetName()}: {e}")
        return None

def _parse_usdpreviewsurface_from_shader(shader, material_prim):
    """Parse UsdPreviewSurface shader inputs (same structure as PrincipledBSDF)"""
    from pxr import UsdShade
    params = {}
    
    shader_obj = UsdShade.Shader(shader) if not isinstance(shader, UsdShade.Shader) else shader
    
    for shader_input in shader_obj.GetInputs():
        input_name = shader_input.GetBaseName()
        
        # Check if connected to texture
        connected_source = shader_input.GetConnectedSource()
        if connected_source and len(connected_source) > 0 and connected_source[0]:
            # Texture connection
            texture_shader = UsdShade.Shader(connected_source[0])
            file_input = texture_shader.GetInput('file')
            if file_input:
                texture_path = file_input.Get()
                if texture_path:
                    clean_path = str(texture_path.path) if hasattr(texture_path, 'path') else str(texture_path)
                    params[f"inputs:{input_name}"] = clean_path.strip('@')
                    params[f"inputs:{input_name}_is_texture"] = True
        else:
            # Constant value
            value = shader_input.Get()
            if value is not None:
                params[f"inputs:{input_name}"] = value
    
    return params


def _extract_texture_paths(usd_content, usd_file_dir=None):
    """Extract texture file paths from USD content and verify they exist"""
    import re
    import os
    
    texture_paths = {}
    texture_check_cache = {}  # Lookup table to avoid redundant file checks
    
    # Find all texture shaders and their file paths
    texture_pattern = r'def Shader "([^"]+)"\s*{[^}]*asset inputs:file\s*=\s*@([^@]+)@[^}]*}'
    texture_matches = re.finditer(texture_pattern, usd_content, re.DOTALL)
    
    for match in texture_matches:
        shader_name = match.group(1)
        file_path = match.group(2)
        
        # Check cache first to avoid redundant file system checks
        if file_path in texture_check_cache:
            if texture_check_cache[file_path]:
                texture_paths[shader_name] = file_path
            continue
        
        # Verify texture file exists (skip procedural/non-existent textures)
        if usd_file_dir and file_path.startswith('./'):
            full_path = os.path.join(usd_file_dir, file_path[2:])
            exists = os.path.isfile(full_path)
        else:
            exists = os.path.isfile(file_path) if os.path.isabs(file_path) else True
        
        # Cache result
        texture_check_cache[file_path] = exists
        
        # Only add if texture file exists
        if exists:
            texture_paths[shader_name] = file_path
    
    return texture_paths

def _resolve_texture_connections(principled_params, texture_paths, material_name):
    """Resolve texture connections to actual file paths with proper ./textures/ format"""
    resolved_params = principled_params.copy()
    
    for param_name, param_value in principled_params.items():
        if param_name.endswith('.connect') and isinstance(param_value, str):
            # Extract shader name from connection path
            # Example: </root/_materials/Bush/Image_Texture.outputs:rgb>
            # Extract: Image_Texture
            if '.outputs:' in param_value:
                # Find the shader name in the connection path
                # Look for the pattern: /ShaderName.outputs:
                import re
                shader_match = re.search(r'/([^/]+)\.outputs:', param_value)
                if shader_match:
                    shader_name = shader_match.group(1)
                    if shader_name in texture_paths:
                        # Get the actual texture file path from inputs:file
                        texture_file_path = texture_paths[shader_name]
                        
                        # Extract the actual texture filename from the file path
                        import os
                        texture_filename = os.path.basename(texture_file_path)
                        
                        # FIX: If the filename is generic (like "Image_Texture_001.jpg"), 
                        # use a meaningful name based on material name and texture type
                        if texture_filename.startswith('Image_Texture') or texture_filename.startswith('image_texture'):
                            # Determine texture type from parameter name
                            base_param = param_name[:-8]  # Remove '.connect'
                            texture_type_map = {
                                'diffuseColor': 'BaseColor',
                                'metallic': 'Metallic',
                                'roughness': 'Roughness',
                                'normal': 'Normal',
                                'emissiveColor': 'Emissive',
                                'opacity': 'Opacity',
                                'anisotropy': 'Anisotropy'
                            }
                            texture_type = texture_type_map.get(base_param, base_param)
                            
                            # Get file extension
                            file_ext = os.path.splitext(texture_filename)[1]
                            
                            # Create meaningful filename: MaterialName_TextureType.ext
                            texture_filename = f"{material_name}_{texture_type}{file_ext}"
                        
                        formatted_path = f"./textures/{texture_filename}"
                        
                        # Replace the connection with the formatted texture path
                        base_param = param_name[:-8]  # Remove '.connect'
                        resolved_params[base_param] = formatted_path
                        # Mark this as a texture parameter by adding a special suffix
                        resolved_params[f"{base_param}_is_texture"] = True
                        # Remove the connection parameter
                        resolved_params.pop(param_name)
    
    return resolved_params

def _extract_principled_bsdf_params(material_content):
    """
    Extract Principled_BSDF parameters from material content
    
    Args:
        material_content (str): Material definition content
        
    Returns:
        dict: Principled_BSDF parameters
    """
    import re
    
    params = {}
    
    # Find the start of Principled_BSDF shader definition
    start_pos = material_content.find('def Shader "Principled_BSDF"')
    if start_pos == -1:
        return params
    
    # Find the opening brace
    brace_start = material_content.find('{', start_pos)
    if brace_start == -1:
        return params
    
    # Find the matching closing brace using a simple state machine
    brace_count = 1
    i = brace_start + 1
    while i < len(material_content) and brace_count > 0:
        if material_content[i] == '{':
            brace_count += 1
        elif material_content[i] == '}':
            brace_count -= 1
        i += 1
    
    if brace_count > 0:
        return params  # Unmatched braces
    
    # Extract the Principled_BSDF content
    principled_content = material_content[brace_start + 1:i - 1]
    
    # Extract input parameters - handle both direct values and connections
    input_pattern = r'(\w+) inputs:(\w+)(?:\.connect)?\s*=\s*([^\n]+)'
    input_matches = re.finditer(input_pattern, principled_content)
    
    for input_match in input_matches:
        param_type = input_match.group(1)  # float, color3f, etc.
        param_name = input_match.group(2)  # diffuseColor, metallic, etc.
        param_value = input_match.group(3).strip()
        
        # Check if this is a connection (.connect)
        is_connection = '.connect' in input_match.group(0)
        param_key = f"{param_name}.connect" if is_connection else param_name
        
        # Handle different parameter types
        if param_type == 'color3f':
            if is_connection:
                # This is a texture connection
                params[param_key] = param_value
            else:
                # Parse color value
                color_match = re.search(r'\(([^)]+)\)', param_value)
                if color_match:
                    color_values = color_match.group(1).split(',')
                    if len(color_values) == 3:
                        r, g, b = [float(x.strip()) for x in color_values]
                        params[param_name] = f'color({r}, {g}, {b})'
                else:
                    params[param_name] = param_value
        elif param_type == 'float':
            if is_connection:
                # This is a texture connection
                params[param_key] = param_value
            else:
                # Parse float value
                try:
                    float_value = float(param_value)
                    params[param_name] = float_value
                except ValueError:
                    params[param_name] = param_value
        else:
            if is_connection:
                params[param_key] = param_value
            else:
                params[param_name] = param_value
    
    return params
