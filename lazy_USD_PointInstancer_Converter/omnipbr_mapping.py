#!/usr/bin/env python3
"""
OmniPBR to Remix Opacity Material Mapping
Aligned with PrincipledBSDF converter features
"""

from aperture_pbr_parameters import (
    get_texture_gamma_mode,
    matches_default_value
)
from omnipbr_parameters import OMNIPBR_TO_REMIX_MAPPING

def _fix_color_parameter(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, (tuple, list)) and len(value) >= 3:
        return f"color({value[0]}, {value[1]}, {value[2]})"
    return value

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

def _fix_texture_parameter(value, texture_param_name=None):
    """Fix texture parameter format for Remix materials.
    Only adds PBR suffix if texture doesn't already have one."""
    import os, re
    
    gamma_mode = get_texture_gamma_mode(texture_param_name) if texture_param_name else 'linear'
    tex_gamma = 'tex::gamma_srgb' if gamma_mode == 'srgb' else 'tex::gamma_linear'
    
    if not value or value == '""':
        return f'texture_2d("", {tex_gamma})'
    
    texture_path = value
    if isinstance(value, str):
        if 'texture_2d(' in value:
            match = re.search(r'texture_2d\("([^"]+)"', value)
            if match:
                texture_path = match.group(1)
            else:
                return value
        texture_path = texture_path.strip('@').replace('\\', '/')
    
    if texture_param_name and texture_path and isinstance(texture_path, str):
        slot_type = texture_param_name.replace('_texture', '').replace('map', '')
        clean_path = texture_path.replace('./textures/', '')
        base_name = os.path.splitext(os.path.basename(clean_path))[0]
        
        # Check if texture already has a PBR suffix
        if _has_pbr_suffix(base_name):
            unique_name = f"{base_name}.dds"
        elif slot_type == 'diffuse':
            unique_name = f"{base_name}_albedo.dds"
        else:
            suffix = 'roughness' if slot_type == 'reflectionroughness' else slot_type
            unique_name = f"{base_name}_{suffix}.dds"
        
        return f'texture_2d("./textures/{unique_name}", {tex_gamma})'
    
    return f'texture_2d("{texture_path}", {tex_gamma})'

def _fix_float_parameter(value):
    if isinstance(value, str) and value.endswith('f'):
        return float(value[:-1])
    return value

def _detect_and_combine_opacity_texture(remix_params):
    """
    Detect if material has both diffuse and opacity textures that need combining.
    RTX Remix doesn't support separate opacity_texture - must be in diffuse alpha channel.
    """
    has_diffuse_texture = 'diffuse_texture' in remix_params
    has_opacity_texture = 'opacity_texture' in remix_params
    
    if has_diffuse_texture and has_opacity_texture:
        remix_params['_combine_opacity_with_diffuse'] = True
        remix_params['_opacity_texture_path'] = remix_params['opacity_texture']
        remix_params['use_legacy_alpha_state'] = False
        remix_params['blend_enabled'] = True
        del remix_params['opacity_texture']
    
    return remix_params

def convert_to_remix(omnipbr_params):
    """Standardized conversion function - converts OmniPBR parameters to Remix parameters"""
    remix_params = {}
    original_params = set()
    
    # Extract auto_blend_alpha flag (default True)
    auto_blend_alpha = omnipbr_params.get('_auto_blend_alpha', True)
    
    # === TEXTURE BENDING FALLBACKS ===
    has_roughness_texture = 'reflectionroughness_texture' in omnipbr_params
    has_specular_texture = 'specular_texture' in omnipbr_params
    has_diffuse_texture = 'diffuse_texture' in omnipbr_params or 'albedo_texture' in omnipbr_params
    
    roughness_texture_value = omnipbr_params.get('reflectionroughness_texture') or omnipbr_params.get('roughness_texture')
    specular_texture_value = omnipbr_params.get('specular_texture')
    diffuse_texture_value = omnipbr_params.get('diffuse_texture') or omnipbr_params.get('albedo_texture')
    
    # Helper to normalize paths for comparison
    def normalize_path(path):
        if not path or not isinstance(path, str):
            return None
        import os, re
        # Extract path from texture_2d() if present
        if 'texture_2d(' in path:
            match = re.search(r'texture_2d\("([^"]+)"', path)
            if match:
                path = match.group(1)
        clean = path.strip('@').replace('./textures/', '').replace('\\', '/')
        return os.path.basename(clean).lower()
    
    roughness_file = normalize_path(roughness_texture_value)
    diffuse_file = normalize_path(diffuse_texture_value)
    specular_file = normalize_path(specular_texture_value)
    
    # Check if roughness texture is same as diffuse (Blender blending trick)
    if has_roughness_texture and has_diffuse_texture and roughness_file and diffuse_file and roughness_file == diffuse_file:
        import os, re
        # Roughness uses same texture as diffuse - need grayscale conversion
        # Store ORIGINAL diffuse path BEFORE _fix_texture_parameter for texture conversion
        remix_params['_diffuse_source'] = diffuse_texture_value
        
        # Extract base name for roughness texture output path
        diff_path = _fix_texture_parameter(diffuse_texture_value, 'diffuse_texture')
        match = re.search(r'texture_2d\("([^"]+)"', diff_path)
        if match:
            clean_path = match.group(1).strip('@').replace('./textures/', '')
            base_name = os.path.splitext(os.path.basename(clean_path))[0]
            roughness_texture = f"./textures/{base_name}_rough.dds"
            
            remix_params['_use_diffuse_for_roughness'] = True
            remix_params['reflectionroughness_texture'] = _fix_texture_parameter(roughness_texture, 'reflectionroughness_texture')
            original_params.add('reflectionroughness_texture')
    elif not has_roughness_texture and has_specular_texture and specular_texture_value:
        # No roughness texture - check if specular is same as diffuse
        if diffuse_file and specular_file == diffuse_file:
            # Specular uses same texture as diffuse - use diffuse source with inversion
            import os, re
            remix_params['_diffuse_source'] = diffuse_texture_value
            
            diff_path = _fix_texture_parameter(diffuse_texture_value, 'diffuse_texture')
            match = re.search(r'texture_2d\("([^"]+)"', diff_path)
            if match:
                clean_path = match.group(1).strip('@').replace('./textures/', '')
                base_name = os.path.splitext(os.path.basename(clean_path))[0]
                roughness_texture = f"./textures/{base_name}_rough.dds"
                
                remix_params['_invert_for_roughness'] = True
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(roughness_texture, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
        else:
            # Specular has its own texture - use specular source with inversion
            import os, re
            remix_params['_specular_source'] = specular_texture_value
            
            spec_path = _fix_texture_parameter(specular_texture_value, 'specular_texture')
            match = re.search(r'texture_2d\("([^"]+)"', spec_path)
            if match:
                clean_path = match.group(1).strip('@').replace('./textures/', '')
                base_name = os.path.splitext(os.path.basename(clean_path))[0]
                roughness_texture = f"./textures/{base_name}_rough.dds"
                
                remix_params['_invert_for_roughness'] = True
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(roughness_texture, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
    
    # === PROCESS ALL PARAMETERS ===
    for omnipbr_param, value in omnipbr_params.items():
        # Skip internal flags and _is_texture markers
        if omnipbr_param.startswith('_') or omnipbr_param.endswith('_is_texture'):
            continue
        
        # Check if this parameter is a texture (marked by converter)
        is_texture_param = omnipbr_params.get(f"{omnipbr_param}_is_texture", False)
        
        # Handle texture parameters extracted from MDL
        if is_texture_param:
            # Skip empty texture_2d() values
            if not value or value == 'texture_2d()' or (isinstance(value, str) and value.strip() == ''):
                continue
            
            if omnipbr_param in ['diffuse_texture', 'albedo_texture']:
                # Store source path for texture conversion (absolute path from MDL resolution)
                remix_params['_diffuse_texture_source'] = value
                # Store output path for USD (./textures/ format)
                remix_params['diffuse_texture'] = _fix_texture_parameter(value, 'diffuse_texture')
                original_params.add('diffuse_texture')
                # Preserve color constant as tint
                if 'diffuse_tint' in omnipbr_params:
                    color_value = omnipbr_params['diffuse_tint']
                    if isinstance(color_value, (tuple, list)) and len(color_value) >= 3:
                        remix_params['diffuse_color_constant'] = (float(color_value[0]), float(color_value[1]), float(color_value[2]))
                        original_params.add('diffuse_color_constant')
            elif omnipbr_param == 'metallic_texture':
                remix_params['_metallic_texture_source'] = value
                remix_params['metallic_texture'] = _fix_texture_parameter(value, 'metallic_texture')
                original_params.add('metallic_texture')
            elif omnipbr_param in ['reflectionroughness_texture', 'roughness_texture']:
                remix_params['_reflectionroughness_texture_source'] = value
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(value, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
            elif omnipbr_param == 'normalmap_texture':
                remix_params['_normalmap_texture_source'] = value
                remix_params['normalmap_texture'] = _fix_texture_parameter(value, 'normalmap_texture')
                original_params.add('normalmap_texture')
            elif omnipbr_param == 'emissive_mask_texture':
                remix_params['_emissive_mask_texture_source'] = value
                remix_params['emissive_mask_texture'] = _fix_texture_parameter(value, 'emissive_mask_texture')
                original_params.add('emissive_mask_texture')
            elif omnipbr_param == 'opacity_texture':
                remix_params['_opacity_texture_source'] = value
                if auto_blend_alpha:
                    remix_params['use_legacy_alpha_state'] = True
                    remix_params['blend_enabled'] = True
                    original_params.add('use_legacy_alpha_state')
                    original_params.add('blend_enabled')
            continue
        
        # Handle texture connections
        if omnipbr_param.endswith('.connect'):
            base_param = omnipbr_param.replace('.connect', '')
            if base_param == 'diffuse_texture':
                remix_params['diffuse_texture'] = _fix_texture_parameter(value, 'diffuse_texture')
                original_params.add('diffuse_texture')
                # Preserve color constant as tint
                color_key = 'diffuse_color_constant'
                if color_key in omnipbr_params:
                    color_value = omnipbr_params[color_key]
                    if isinstance(color_value, (tuple, list)) and len(color_value) >= 3:
                        remix_params['diffuse_color_constant'] = (float(color_value[0]), float(color_value[1]), float(color_value[2]))
                        original_params.add('diffuse_color_constant')
            elif base_param == 'metallic_texture':
                remix_params['metallic_texture'] = _fix_texture_parameter(value, 'metallic_texture')
                original_params.add('metallic_texture')
            elif base_param == 'reflectionroughness_texture':
                remix_params['reflectionroughness_texture'] = _fix_texture_parameter(value, 'reflectionroughness_texture')
                original_params.add('reflectionroughness_texture')
            elif base_param == 'specular_texture':
                remix_params['_specular_texture'] = value
            elif base_param == 'anisotropy_texture':
                remix_params['anisotropy_texture'] = _fix_texture_parameter(value, 'anisotropy_texture')
                original_params.add('anisotropy_texture')
            elif base_param == 'normalmap_texture':
                remix_params['normalmap_texture'] = _fix_texture_parameter(value, 'normalmap_texture')
                original_params.add('normalmap_texture')
            elif base_param == 'opacity_texture':
                if auto_blend_alpha:
                    remix_params['use_legacy_alpha_state'] = True
                    remix_params['blend_enabled'] = True
                    original_params.add('use_legacy_alpha_state')
                    original_params.add('blend_enabled')
        else:
            # Handle constant parameters
            if value is not None:
                # === DIFFUSE COLOR ===
                if omnipbr_param in ['diffuse_color_constant', 'diffuse_tint']:
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        remix_params['diffuse_color_constant'] = (float(value[0]), float(value[1]), float(value[2]))
                    elif isinstance(value, str) and value.startswith('color('):
                        remix_params['diffuse_color_constant'] = value
                    else:
                        remix_params['diffuse_color_constant'] = value
                    original_params.add('diffuse_color_constant')
                
                # === DIFFUSE TEXTURE ===
                elif omnipbr_param == 'diffuse_texture':
                    # Skip empty texture_2d()
                    if value and value != 'texture_2d()':
                        remix_params['diffuse_texture'] = _fix_texture_parameter(value, 'diffuse_texture')
                        original_params.add('diffuse_texture')
                
                # === METALLIC ===
                elif omnipbr_param == 'metallic_constant':
                    metal_val = float(value) if isinstance(value, (int, float, str)) else 0.0
                    if not matches_default_value('metallic_constant', metal_val):
                        remix_params['metallic_constant'] = metal_val
                        original_params.add('metallic_constant')
                
                elif omnipbr_param == 'metallic_texture':
                    # Skip empty texture_2d()
                    if value and value != 'texture_2d()':
                        remix_params['metallic_texture'] = _fix_texture_parameter(value, 'metallic_texture')
                        original_params.add('metallic_texture')
                
                # === ROUGHNESS ===
                elif omnipbr_param == 'reflection_roughness_constant':
                    if not remix_params.get('_invert_for_roughness'):
                        rough_val = float(value) if isinstance(value, (int, float, str)) else 0.5
                        if not matches_default_value('reflection_roughness_constant', rough_val):
                            remix_params['reflection_roughness_constant'] = rough_val
                            original_params.add('reflection_roughness_constant')
                
                elif omnipbr_param == 'reflectionroughness_texture':
                    if 'reflectionroughness_texture' not in remix_params and value and value != 'texture_2d()':
                        remix_params['reflectionroughness_texture'] = _fix_texture_parameter(value, 'reflectionroughness_texture')
                        original_params.add('reflectionroughness_texture')
                
                # === SPECULAR (for roughness inversion) ===
                elif omnipbr_param == 'specular_level':
                    specular_val = float(value) if isinstance(value, (int, float, str)) else 0.0
                    roughness_val = omnipbr_params.get('reflection_roughness_constant', 0.5)
                    if isinstance(roughness_val, (int, float)) and roughness_val == 1.0 and specular_val != 0.0:
                        remix_params['reflection_roughness_constant'] = 1.0 - specular_val
                        original_params.add('reflection_roughness_constant')
                    remix_params['_specular_constant'] = specular_val
                
                elif omnipbr_param == 'specular_texture':
                    remix_params['_specular_texture'] = value
                
                # === ANISOTROPY ===
                elif omnipbr_param == 'anisotropy_constant':
                    aniso_val = float(value) if isinstance(value, (int, float, str)) else 0.0
                    if not matches_default_value('anisotropy_constant', aniso_val):
                        remix_params['anisotropy_constant'] = aniso_val
                        original_params.add('anisotropy_constant')
                
                elif omnipbr_param == 'anisotropy_texture':
                    remix_params['anisotropy_texture'] = _fix_texture_parameter(value, 'anisotropy_texture')
                    original_params.add('anisotropy_texture')
                
                # === NORMAL MAP ===
                elif omnipbr_param == 'normalmap_texture':
                    if value and value != 'texture_2d()':
                        remix_params['normalmap_texture'] = _fix_texture_parameter(value, 'normalmap_texture')
                        original_params.add('normalmap_texture')
                
                # === EMISSIVE ===
                elif omnipbr_param == 'emissive_color':
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        remix_params['emissive_color_constant'] = (float(value[0]), float(value[1]), float(value[2]))
                    elif isinstance(value, str) and value.startswith('color('):
                        remix_params['emissive_color_constant'] = value
                    else:
                        remix_params['emissive_color_constant'] = value
                    original_params.add('emissive_color_constant')
                
                elif omnipbr_param == 'emissive_mask_texture':
                    if value and value != 'texture_2d()':
                        remix_params['emissive_mask_texture'] = _fix_texture_parameter(value, 'emissive_mask_texture')
                        original_params.add('emissive_mask_texture')
                
                elif omnipbr_param == 'emissive_intensity':
                    remix_params['emissive_intensity'] = float(value) if isinstance(value, (int, float, str)) else 1.0
                    original_params.add('emissive_intensity')
                
                elif omnipbr_param == 'enable_emission':
                    remix_params['enable_emission'] = bool(value)
                    original_params.add('enable_emission')
                
                # === OPACITY ===
                elif omnipbr_param == 'opacity_texture':
                    if value and value != 'texture_2d()' and auto_blend_alpha:
                        remix_params['use_legacy_alpha_state'] = True
                        remix_params['blend_enabled'] = True
                        original_params.add('use_legacy_alpha_state')
                        original_params.add('blend_enabled')
    
    # === EMISSION HANDLING ===
    has_emissive_texture = 'emissive_mask_texture' in remix_params
    if has_emissive_texture:
        remix_params['enable_emission'] = True
        if 'emissive_intensity' not in remix_params:
            remix_params['emissive_intensity'] = 1.0
        original_params.add('enable_emission')
        original_params.add('emissive_intensity')
    else:
        remix_params.pop('emissive_color_constant', None)
        remix_params.pop('emissive_intensity', None)
        remix_params.pop('enable_emission', None)
        original_params.discard('emissive_color_constant')
        original_params.discard('emissive_intensity')
        original_params.discard('enable_emission')
    
    remix_params['_original_params'] = original_params
    
    # === OPACITY TEXTURE COMBINATION ===
    remix_params = _detect_and_combine_opacity_texture(remix_params)
    
    # === BUMP-TO-NORMAL DETECTION ===
    normal_tex_source = remix_params.get('_normalmap_texture_source')
    if normal_tex_source:
        import os, re
        # Extract path from texture_2d() if present
        if 'texture_2d(' in normal_tex_source:
            match = re.search(r'texture_2d\("([^"]+)"', normal_tex_source)
            if match:
                normal_tex_source = match.group(1)
        
        normal_clean = normal_tex_source.strip('@').replace('./textures/', '')
        filename_lower = os.path.splitext(normal_clean)[0].lower()
        
        if filename_lower.endswith(('_bump', 'bump', '_height', 'height', '_displacement', 'displacement')):
            remix_params['_is_bump_texture'] = True
            # Get base name without bump/height/displacement suffix
            base_name = os.path.splitext(os.path.basename(normal_clean))[0]
            for suffix in ['_bump', '_height', '_displacement']:
                if base_name.lower().endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
            # Update normalmap_texture to use _normal suffix (needs bump-to-normal conversion)
            remix_params['normalmap_texture'] = f'texture_2d("./textures/{base_name}_normal.dds", tex::gamma_linear)'
            # Height texture uses _height suffix (just DDS conversion, no processing)
            remix_params['_height_texture_source'] = normal_tex_source
            remix_params['height_texture'] = f'texture_2d("./textures/{base_name}_height.dds", tex::gamma_linear)'
            original_params.add('height_texture')
    
    return remix_params