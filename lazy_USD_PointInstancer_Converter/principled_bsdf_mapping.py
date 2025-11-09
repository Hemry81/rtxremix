#!/usr/bin/env python3
"""
Principled_BSDF to Remix Opacity Material Mapping
Converts Blender-exported Principled_BSDF materials to Remix-compatible materials
"""

# Mapping from Principled_BSDF parameters to Remix Opacity Material parameters
PRINCIPLED_BSDF_TO_REMIX_MAPPING = {
    # === DIFFUSE/ALBEDO PARAMETERS ===
    'diffuseColor': 'diffuse_color_constant',  # Base color value
    'diffuseColor.connect': 'diffuse_texture',  # Base color texture
    'inputs:diffuseColor': 'diffuse_color_constant',  # USD format
    'inputs:diffuseColor.connect': 'diffuse_texture',  # USD format
    
    # === METALLIC PARAMETERS ===
    'metallic': 'metallic_constant',  # Metallic value
    'metallic.connect': 'metallic_texture',  # Metallic texture
    'inputs:metallic': 'metallic_constant',  # USD format
    'inputs:metallic.connect': 'metallic_texture',  # USD format
    
    # === ROUGHNESS PARAMETERS ===
    'roughness': 'reflection_roughness_constant',  # Roughness value
    'roughness.connect': 'reflectionroughness_texture',  # Roughness texture
    'inputs:roughness': 'reflection_roughness_constant',  # USD format
    'inputs:roughness.connect': 'reflectionroughness_texture',  # USD format
    
    # === NORMAL MAP PARAMETERS ===
    'normal.connect': 'normalmap_texture',  # Normal map texture
    'inputs:normal.connect': 'normalmap_texture',  # USD format
    
    # === EMISSION PARAMETERS ===
    'emissiveColor': 'emissive_color_constant',  # Emission color
    'emissiveColor.connect': 'emissive_mask_texture',  # Emission texture
    'inputs:emissiveColor': 'emissive_color_constant',  # USD format
    'inputs:emissiveColor.connect': 'emissive_mask_texture',  # USD format
    
    # === OPACITY PARAMETERS ===
    'opacity': 'opacity_constant',  # Opacity value
    'opacity.connect': 'opacity_texture',  # Opacity texture
    'inputs:opacity': 'opacity_constant',  # USD format
    'inputs:opacity.connect': 'opacity_texture',  # USD format
    
    # === SPECULAR PARAMETERS ===
    'specular': 'specular_constant',  # Specular value
    'specular.connect': 'specular_texture',  # Specular texture
    'inputs:specular': 'specular_constant',  # USD format
    'inputs:specular.connect': 'specular_texture',  # USD format
    
    # === ANISOTROPY PARAMETERS ===
    'anisotropy': 'anisotropy_constant',  # Anisotropy value
    'anisotropy.connect': 'anisotropy_texture',  # Anisotropy texture
    'inputs:anisotropy': 'anisotropy_constant',  # USD format
    'inputs:anisotropy.connect': 'anisotropy_texture',  # USD format
    
    # === CLEARCOAT PARAMETERS ===
    'clearcoat': 'clearcoat_constant',  # Clearcoat value
    'clearcoat.connect': 'clearcoat_texture',  # Clearcoat texture
    'clearcoatRoughness': 'clearcoat_roughness_constant',  # Clearcoat roughness
    'clearcoatRoughness.connect': 'clearcoat_roughness_texture',  # Clearcoat roughness texture
    'inputs:clearcoat': 'clearcoat_constant',  # USD format
    'inputs:clearcoat.connect': 'clearcoat_texture',  # USD format
    'inputs:clearcoatRoughness': 'clearcoat_roughness_constant',  # USD format
    'inputs:clearcoatRoughness.connect': 'clearcoat_roughness_texture',  # USD format
    
    # === IOR PARAMETERS ===
    'ior': 'ior_constant',  # Index of refraction
    'inputs:ior': 'ior_constant',  # USD format
    
    # === SUBSURFACE PARAMETERS ===
    'subsurface': 'subsurface_constant',  # Subsurface value
    'subsurface.connect': 'subsurface_texture',  # Subsurface texture
    'subsurfaceColor': 'subsurface_color_constant',  # Subsurface color
    'subsurfaceColor.connect': 'subsurface_color_texture',  # Subsurface color texture
    'inputs:subsurface': 'subsurface_constant',  # USD format
    'inputs:subsurface.connect': 'subsurface_texture',  # USD format
    'inputs:subsurfaceColor': 'subsurface_color_constant',  # USD format
    'inputs:subsurfaceColor.connect': 'subsurface_color_texture',  # USD format
}

# Mapping from UsdPreviewSurface parameters to Remix Opacity Material parameters
# Only include parameters that actually exist in AperturePBR_Opacity.mdl
USD_PREVIEW_SURFACE_TO_REMIX_MAPPING = {
    # === DIFFUSE/ALBEDO PARAMETERS ===
    'inputs:diffuseColor.connect': 'diffuse_texture',  # Base color texture
    'inputs:diffuseColor': 'diffuse_color_constant',  # Base color value
    
    # === METALLIC PARAMETERS ===
    'inputs:metallic': 'metallic_constant',  # Metallic value
    'inputs:metallic.connect': 'metallic_texture',  # Metallic texture
    
    # === ROUGHNESS PARAMETERS ===
    'inputs:roughness': 'reflection_roughness_constant',  # Roughness value
    'inputs:roughness.connect': 'reflectionroughness_texture',  # Roughness texture
    
    # === NORMAL MAP PARAMETERS ===
    'inputs:normal.connect': 'normalmap_texture',  # Normal map texture
    
    # === EMISSION PARAMETERS ===
    'inputs:emissiveColor': 'emissive_color_constant',  # Emission color
    'inputs:emissiveColor.connect': 'emissive_mask_texture',  # Emission texture
    
    # === OPACITY PARAMETERS ===
    'inputs:opacity': 'opacity_constant',  # Opacity value
    'inputs:opacity.connect': 'opacity_texture',  # Opacity texture
    
    # === ANISOTROPY PARAMETERS ===
    'inputs:anisotropy': 'anisotropy_constant',  # Anisotropy value
    'inputs:anisotropy.connect': 'anisotropy_texture',  # Anisotropy texture
}

# Default values for Remix Opacity Material parameters
# Only include parameters that actually exist in AperturePBR_Opacity.mdl
REMIX_DEFAULT_VALUES = {
    'opacity_constant': 1.0,
    'enable_emission': False,
    'emissive_color_constant': 'color(0.0, 0.0, 0.0)',
    'emissive_intensity': 1.0,
    'enable_thin_film': False,
    'thin_film_thickness_constant': 200.0,
    'anisotropy_constant': 0.0,
    'use_legacy_alpha_state': True,
    'blend_enabled': False,
    'filter_mode': 'Linear',
    'wrap_mode_u': 'tex::wrap_repeat',
    'wrap_mode_v': 'tex::wrap_repeat',
    'encoding': 'AperturePBR_Normal::octahedral',
    'sprite_sheet_fps': 0,
    'sprite_sheet_cols': 1,
    'sprite_sheet_rows': 1,
    'preload_textures': False,
    'ignore_material': False,
    'alpha_test_type': 'Always',
    'alpha_test_reference_value': 0.0,
    'displace_in': 0.05,
    'displace_out': 0.0,
    'diffuse_color_constant': 'color(0.8, 0.8, 0.8)',
    'reflection_roughness_constant': 0.5,
    'metallic_constant': 0.0,
    'specular_constant': 0.04,  # Default specular value
    'ior_constant': 1.5,  # Default IOR for most materials
    'clearcoat_constant': 0.0,  # Default no clearcoat
    'clearcoat_roughness_constant': 0.1,  # Default clearcoat roughness
    'subsurface_constant': 0.0,  # Default no subsurface
    'subsurface_color_constant': 'color(1.0, 1.0, 1.0)',  # Default white subsurface
}

# Texture gamma modes for Remix Opacity Material
TEXTURE_GAMMA_MODES = {
    'diffuse_texture': 'tex::gamma_srgb',
    'reflectionroughness_texture': 'tex::gamma_linear',
    'metallic_texture': 'tex::gamma_linear',
    'normalmap_texture': 'tex::gamma_linear',
    'emissive_mask_texture': 'tex::gamma_srgb',
    'opacity_texture': 'tex::gamma_srgb',
    'specular_texture': 'tex::gamma_linear',
    'anisotropy_texture': 'tex::gamma_linear',
    'clearcoat_texture': 'tex::gamma_linear',
    'clearcoat_roughness_texture': 'tex::gamma_linear',
    'subsurface_texture': 'tex::gamma_linear',
    'subsurface_color_texture': 'tex::gamma_srgb',
    'ior_texture': 'tex::gamma_linear',
}

# Parameter transformations for specific types
PARAMETER_TRANSFORMATIONS = {
    'diffuseColor': lambda value: _fix_color_parameter(value),
    'diffuseColor.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_srgb'),
    'metallic': lambda value: _fix_float_parameter(value),
    'metallic.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'roughness': lambda value: _fix_float_parameter(value),
    'roughness.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'normal.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'emissiveColor': lambda value: _fix_color_parameter(value),
    'emissiveColor.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_srgb'),
    'opacity': lambda value: _fix_float_parameter(value),
    'opacity.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_srgb'),
    'specular': lambda value: _fix_float_parameter(value),
    'specular.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'clearcoat': lambda value: _fix_float_parameter(value),
    'clearcoat.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'clearcoatRoughness': lambda value: _fix_float_parameter(value),
    'clearcoatRoughness.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'ior': lambda value: _fix_float_parameter(value),
    'subsurface': lambda value: _fix_float_parameter(value),
    'subsurface.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_linear'),
    'subsurfaceColor': lambda value: _fix_color_parameter(value),
    'subsurfaceColor.connect': lambda value: _fix_texture_parameter(value, 'tex::gamma_srgb'),
}

def _fix_texture_parameter(value, gamma_mode):
    """Fix texture parameter format for Remix materials"""
    if not value or value == '""':
        return f'texture_2d("", {gamma_mode})'
    
    # Handle USD connection paths - extract the actual texture file
    if value.startswith('</') and value.endswith('.outputs:rgb>'):
        # This is a USD connection path, we need to find the actual texture file
        # For now, return empty texture - the actual texture path extraction would need
        # to parse the USD file to find the texture shader and its file path
        return f'texture_2d("", {gamma_mode})'
    
    # Extract texture path from USD asset reference
    if value.startswith('@') and value.endswith('@'):
        texture_path = value[1:-1]  # Remove @ symbols
        # For Principled_BSDF, textures are in ./textures/ relative to the input file
        # No need to change the path - keep it as ./textures/
        # Convert relative path to texture_2d format
        return f'texture_2d("{texture_path}", {gamma_mode})'
    
    # Handle direct texture paths
    if isinstance(value, str):
        # For Principled_BSDF, textures are in ./textures/ relative to the input file
        # No need to change the path - keep it as ./textures/
        pass
    
    return f'texture_2d("{value}", {gamma_mode})'

def _fix_color_parameter(value):
    """Fix color parameter format for Remix materials"""
    if isinstance(value, str):
        # Handle USD color format (r, g, b) -> color(r, g, b)
        if value.startswith('(') and value.endswith(')'):
            return f'color{value}'
        return value
    return value

def _fix_float_parameter(value):
    """Fix float parameter format for Remix materials"""
    if isinstance(value, (int, float)):
        return f'{value}f'
    return value



def convert_principled_bsdf_to_remix(principled_params):
    """
    Convert Principled_BSDF or UsdPreviewSurface parameters to Remix Opacity Material parameters
    Ensures ALL compatible values are copied including albedo/diffuse color, roughness, metalness
    
    Args:
        principled_params (dict): Dictionary of Principled_BSDF or UsdPreviewSurface parameters
        
    Returns:
        dict: Converted Remix parameters with all compatible values
    """
    remix_params = {}
    
    # Start with essential default values
    essential_defaults = {
        'opacity_constant': 1.0,
        'use_legacy_alpha_state': True,
        'blend_enabled': False,
        'diffuse_color_constant': 'color(0.8, 0.8, 0.8)',  # Default gray
        'reflection_roughness_constant': 0.5,  # Default medium roughness
        'metallic_constant': 0.0,  # Default non-metallic
    }
    remix_params.update(essential_defaults)
    
    # Check if emission is enabled
    emission_enabled = False
    emissive_color = None
    emissive_texture = None
    
    # First pass: check for emission parameters
    for principled_param, value in principled_params.items():
        if principled_param.endswith('_is_texture'):
            continue
            
        # Check for emission color
        if principled_param in ['inputs:emissiveColor', 'emissiveColor']:
            if value and value != (0, 0, 0) and value != 'color(0, 0, 0)' and str(value) != '(0, 0, 0)':
                emission_enabled = True
                emissive_color = value
                
        # Check for emission texture
        is_texture = principled_params.get(f"{principled_param}_is_texture", False)
        if is_texture and principled_param in ['emissiveColor', 'inputs:emissiveColor']:
            emission_enabled = True
            emissive_texture = value
        elif principled_param.endswith('.connect') and 'emissiveColor' in principled_param:
            emission_enabled = True
            emissive_texture = value
    
    # Set emission parameters only if emission is enabled and has content
    if emission_enabled:
        remix_params['enable_emission'] = True
        remix_params['emissive_intensity'] = 1.0
        if emissive_color:
            if isinstance(emissive_color, (tuple, list)) and len(emissive_color) >= 3:
                remix_params['emissive_color_constant'] = f"color({emissive_color[0]}, {emissive_color[1]}, {emissive_color[2]})"
            elif isinstance(emissive_color, str) and not emissive_color.startswith('color('):
                remix_params['emissive_color_constant'] = f"color({emissive_color})"
            else:
                remix_params['emissive_color_constant'] = str(emissive_color)
        if emissive_texture:
            remix_params['emissive_mask_texture'] = emissive_texture
    else:
        # Explicitly disable emission if no emissive content found
        remix_params['enable_emission'] = False
    
    # Second pass: copy ALL texture values and constant values
    for principled_param, value in principled_params.items():
        # Skip texture markers
        if principled_param.endswith('_is_texture'):
            continue
            
        # Check if this is a texture parameter
        is_texture = principled_params.get(f"{principled_param}_is_texture", False)
        
        if is_texture:
            # This is a resolved texture parameter - copy ALL texture types
            if principled_param in ['diffuseColor', 'inputs:diffuseColor']:
                remix_params['diffuse_texture'] = value
            elif principled_param in ['metallic', 'inputs:metallic']:
                remix_params['metallic_texture'] = value
            elif principled_param in ['roughness', 'inputs:roughness']:
                remix_params['reflectionroughness_texture'] = value
            elif principled_param in ['normal', 'inputs:normal']:
                remix_params['normalmap_texture'] = value
            elif principled_param in ['opacity', 'inputs:opacity']:
                remix_params['opacity_texture'] = value
            elif principled_param in ['anisotropy', 'inputs:anisotropy']:
                remix_params['anisotropy_texture'] = value
            elif principled_param in ['specular', 'inputs:specular']:
                remix_params['specular_texture'] = value
            elif principled_param in ['clearcoat', 'inputs:clearcoat']:
                remix_params['clearcoat_texture'] = value
            elif principled_param in ['clearcoatRoughness', 'inputs:clearcoatRoughness']:
                remix_params['clearcoat_roughness_texture'] = value
            elif principled_param in ['subsurface', 'inputs:subsurface']:
                remix_params['subsurface_texture'] = value
            elif principled_param in ['subsurfaceColor', 'inputs:subsurfaceColor']:
                remix_params['subsurface_color_texture'] = value
            elif principled_param in ['ior', 'inputs:ior']:
                remix_params['ior_texture'] = value
            # Note: emission texture is already handled above
            
        elif principled_param.endswith('.connect'):
            # Handle resolved texture connections
            base_param = principled_param.replace('inputs:', '').replace('.connect', '')
            if base_param in ['diffuseColor']:
                remix_params['diffuse_texture'] = value
            elif base_param in ['metallic']:
                remix_params['metallic_texture'] = value
            elif base_param in ['roughness']:
                remix_params['reflectionroughness_texture'] = value
            elif base_param in ['normal']:
                remix_params['normalmap_texture'] = value
            elif base_param in ['opacity']:
                remix_params['opacity_texture'] = value
            elif base_param in ['anisotropy']:
                remix_params['anisotropy_texture'] = value
            elif base_param in ['specular']:
                remix_params['specular_texture'] = value
            elif base_param in ['clearcoat']:
                remix_params['clearcoat_texture'] = value
            elif base_param in ['clearcoatRoughness']:
                remix_params['clearcoat_roughness_texture'] = value
            elif base_param in ['subsurface']:
                remix_params['subsurface_texture'] = value
            elif base_param in ['subsurfaceColor']:
                remix_params['subsurface_color_texture'] = value
            elif base_param in ['ior']:
                remix_params['ior_texture'] = value
            # Note: emission texture is already handled above
            
        else:
            # This is a constant parameter - copy ALL compatible constants
            if value is not None and not (principled_param in ['emissiveColor', 'inputs:emissiveColor'] and not emission_enabled):
                
                # === DIFFUSE/ALBEDO COLOR ===
                if principled_param in ['diffuseColor', 'inputs:diffuseColor']:
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        remix_params['diffuse_color_constant'] = f"color({value[0]}, {value[1]}, {value[2]})"
                    elif isinstance(value, str) and value.startswith('(') and value.endswith(')'):
                        # Handle string tuples like "(0.8, 0.8, 0.8)"
                        remix_params['diffuse_color_constant'] = f"color{value}"
                    elif isinstance(value, str) and not value.startswith('color('):
                        remix_params['diffuse_color_constant'] = f"color({value})"
                    else:
                        remix_params['diffuse_color_constant'] = str(value)
                
                # === METALLIC VALUE ===
                elif principled_param in ['metallic', 'inputs:metallic']:
                    if isinstance(value, (int, float)):
                        remix_params['metallic_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['metallic_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === ROUGHNESS VALUE ===
                elif principled_param in ['roughness', 'inputs:roughness']:
                    if isinstance(value, (int, float)):
                        remix_params['reflection_roughness_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['reflection_roughness_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === OPACITY VALUE ===
                elif principled_param in ['opacity', 'inputs:opacity']:
                    if isinstance(value, (int, float)):
                        remix_params['opacity_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['opacity_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === SPECULAR VALUE ===
                elif principled_param in ['specular', 'inputs:specular']:
                    if isinstance(value, (int, float)):
                        remix_params['specular_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['specular_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === ANISOTROPY VALUE ===
                elif principled_param in ['anisotropy', 'inputs:anisotropy']:
                    if isinstance(value, (int, float)):
                        remix_params['anisotropy_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['anisotropy_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === IOR VALUE ===
                elif principled_param in ['ior', 'inputs:ior']:
                    if isinstance(value, (int, float)):
                        remix_params['ior_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['ior_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === CLEARCOAT VALUES ===
                elif principled_param in ['clearcoat', 'inputs:clearcoat']:
                    if isinstance(value, (int, float)):
                        remix_params['clearcoat_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['clearcoat_constant'] = float(value)
                        except ValueError:
                            pass
                
                elif principled_param in ['clearcoatRoughness', 'inputs:clearcoatRoughness']:
                    if isinstance(value, (int, float)):
                        remix_params['clearcoat_roughness_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['clearcoat_roughness_constant'] = float(value)
                        except ValueError:
                            pass
                
                # === SUBSURFACE VALUES ===
                elif principled_param in ['subsurface', 'inputs:subsurface']:
                    if isinstance(value, (int, float)):
                        remix_params['subsurface_constant'] = float(value)
                    elif isinstance(value, str):
                        try:
                            remix_params['subsurface_constant'] = float(value)
                        except ValueError:
                            pass
                
                elif principled_param in ['subsurfaceColor', 'inputs:subsurfaceColor']:
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        remix_params['subsurface_color_constant'] = f"color({value[0]}, {value[1]}, {value[2]})"
                    elif isinstance(value, str) and value.startswith('(') and value.endswith(')'):
                        remix_params['subsurface_color_constant'] = f"color{value}"
                    elif isinstance(value, str) and not value.startswith('color('):
                        remix_params['subsurface_color_constant'] = f"color({value})"
                    else:
                        remix_params['subsurface_color_constant'] = str(value)
    
    # Handle opacity for transparency - enable blending if opacity < 1.0
    if 'opacity_texture' in remix_params or 'opacity_constant' in remix_params:
        opacity_value = remix_params.get('opacity_constant', 1.0)
        if isinstance(opacity_value, (int, float)) and opacity_value < 1.0:
            remix_params['blend_enabled'] = True
    
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

def get_remix_material_template(material_name, remix_params):
    """
    Generate Remix USD Material template
    Only includes parameters that are actually present in the original material
    
    Args:
        material_name (str): Name of the material
        remix_params (dict): Remix parameters (may be pre-filtered)
        
    Returns:
        str: Complete USD material content
    """
    
    # Build parameter list for USD format
    param_list = []
    
    # Check if emissive texture exists
    has_emissive_texture = any(param_name == 'emissive_mask_texture' and param_value.startswith('./') 
                              for param_name, param_value in remix_params.items())
    
    # Handle different parameter types for USD
    for param_name, param_value in remix_params.items():
        # Skip internal parameters that shouldn't be in USD
        if param_name in ['filter_mode', 'wrap_mode_u', 'wrap_mode_v', 'encoding', 
                         'sprite_sheet_fps', 'sprite_sheet_cols', 'sprite_sheet_rows',
                         'preload_textures', 'ignore_material', 'alpha_test_type',
                         'alpha_test_reference_value', 'displace_in', 'displace_out']:
            continue
        
        # Skip the _original_params check - accept all parameters passed in
        # This allows pre-filtered parameters to be included
        
        usd_param_name = f"inputs:{param_name}"
        
        # Handle texture parameters
        if param_name.endswith('_texture') and isinstance(param_value, str):
            if param_value.startswith('./'):
                # This is a texture parameter with relative path
                param_list.append(f'                asset {usd_param_name} = @{param_value}@')
            elif param_value.startswith('D:/') or param_value.startswith('C:/'):
                # Convert absolute path to relative path
                import os
                # Extract just the filename from the absolute path
                filename = os.path.basename(param_value)
                relative_path = f'./textures/{filename}'
                param_list.append(f'                asset {usd_param_name} = @{relative_path}@')
        
        # Handle boolean parameters
        elif isinstance(param_value, bool):
            param_list.append(f'                bool {usd_param_name} = {1 if param_value else 0}')
        
        # Handle numeric parameters (int, float)
        elif isinstance(param_value, (int, float)):
            param_list.append(f'                float {usd_param_name} = {param_value}')
        
        # Handle string parameters (for constants, etc.)
        elif isinstance(param_value, str):
            param_list.append(f'                string {usd_param_name} = "{param_value}"')
    
    params_str = '\n'.join(param_list)
    
    # Generate the USD material template with the correct indentation structure
    # This matches the original material's indentation (8 spaces base + 4 spaces relative)
    template = f'''def Material "{material_name}" (
            references = @./materials/AperturePBR_Opacity.usda@</Looks/mat_AperturePBR_Opacity>
        )
        {{
            over "Shader"
            {{
{params_str}
                token outputs:out (
                    renderType = "material"
                )
            }}
        }}'''
    
    return template

def parse_principled_bsdf_from_usd(usd_content):
    """
    Parse Principled_BSDF materials from USD content
    
    Args:
        usd_content (str): USD file content
        
    Returns:
        dict: Dictionary of material names to their parameters
    """
    import re
    
    materials = {}
    
    # First, extract all texture file paths from the USD content
    texture_paths = _extract_texture_paths(usd_content)
    
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
    
    return parse_principled_bsdf_from_usd(usd_content)

def parse_principled_bsdf_material(material_prim):
    """
    Parse Principled_BSDF material from a single material prim
    
    Args:
        material_prim: USD material prim
        
    Returns:
        dict: Principled_BSDF parameters or None if not found
    """
    try:
        # Get the stage content to parse Principled_BSDF
        stage_layer = material_prim.GetStage().GetRootLayer()
        stage_content = stage_layer.ExportToString()
        
        # Parse Principled_BSDF materials from the content
        principled_materials = parse_principled_bsdf_from_usd(stage_content)
        
        material_name = material_prim.GetName()
        if material_name in principled_materials:
            return principled_materials[material_name]
        else:
            return None
            
    except Exception as e:
        print(f"Error parsing Principled_BSDF material {material_prim.GetName()}: {e}")
        return None


def _extract_texture_paths(usd_content):
    """Extract texture file paths from USD content"""
    import re
    
    texture_paths = {}
    
    # Find all texture shaders and their file paths
    texture_pattern = r'def Shader "([^"]+)"\s*{[^}]*asset inputs:file\s*=\s*@([^@]+)@[^}]*}'
    texture_matches = re.finditer(texture_pattern, usd_content, re.DOTALL)
    
    for match in texture_matches:
        shader_name = match.group(1)
        file_path = match.group(2)
        
        # For Principled_BSDF, textures are in ./textures/ relative to the input file
        # No need to change the path - keep it as ./textures/
        
        texture_paths[shader_name] = file_path
    
    return texture_paths

def _resolve_texture_connections(principled_params, texture_paths, material_name):
    """Resolve texture connections to actual file paths"""
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
                        # Replace the connection with the actual texture path
                        base_param = param_name[:-8]  # Remove '.connect'
                        # Add the texture path with the correct parameter name
                        resolved_params[base_param] = texture_paths[shader_name]
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
