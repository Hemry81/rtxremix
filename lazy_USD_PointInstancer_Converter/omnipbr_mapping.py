#!/usr/bin/env python3
"""
OmniPBR to Remix Opacity Material Mapping
Comprehensive mapping rules for converting OmniPBR materials to Remix-compatible materials
"""

# Mapping from OmniPBR parameters to Remix Opacity Material parameters
OMNIPBR_TO_REMIX_MAPPING = {
    # === DIFFUSE/ALBEDO PARAMETERS ===
    'diffuse_color_constant': 'diffuse_color_constant',  # Base color constant
    'diffuse_texture': 'diffuse_texture',  # Base color texture
    'diffuse_tint': 'diffuse_color_constant',  # Diffuse tint (overrides diffuse_color_constant)
    'albedo_desaturation': 'albedo_desaturation',  # Albedo desaturation
    'albedo_add': 'albedo_add',  # Albedo addition
    'albedo_brightness': 'albedo_brightness',  # Albedo brightness
    
    # === METALLIC PARAMETERS ===
    'metallic_constant': 'metallic_constant',  # Metallic value
    'metallic_texture': 'metallic_texture',  # Metallic texture
    'metallic_texture_influence': 'metallic_texture_influence',  # Metallic texture influence
    
    # === ROUGHNESS PARAMETERS ===
    'reflection_roughness_constant': 'reflection_roughness_constant',  # Roughness value
    'reflectionroughness_texture': 'reflectionroughness_texture',  # Roughness texture
    'reflection_roughness_texture_influence': 'reflection_roughness_texture_influence',  # Roughness texture influence
    
    # === NORMAL MAP PARAMETERS ===
    'normalmap_texture': 'normalmap_texture',  # Normal map texture
    'bump_factor': 'normalmap_factor',  # Normal map factor
    'detail_bump_factor': 'detail_normalmap_factor',  # Detail normal map factor
    'detail_normalmap_texture': 'detail_normalmap_texture',  # Detail normal map texture
    
    # === EMISSION PARAMETERS ===
    'enable_emission': 'enable_emission',  # Enable emission
    'emissive_color': 'emissive_color_constant',  # Emission color
    'emissive_mask_texture': 'emissive_mask_texture',  # Emission mask texture
    'emissive_intensity': 'emissive_intensity',  # Emission intensity
    
    # === OPACITY PARAMETERS ===
    'opacity_constant': 'opacity_constant',  # Opacity value
    'opacity_texture': 'opacity_texture',  # Opacity texture
    
    # === SPECULAR PARAMETERS ===
    'specular_level': 'specular_constant',  # Specular level
    
    # === CLEARCOAT PARAMETERS ===
    'clearcoat_constant': 'clearcoat_constant',  # Clearcoat value
    'clearcoat_texture': 'clearcoat_texture',  # Clearcoat texture
    'clearcoat_roughness_constant': 'clearcoat_roughness_constant',  # Clearcoat roughness
    'clearcoat_roughness_texture': 'clearcoat_roughness_texture',  # Clearcoat roughness texture
    
    # === IOR PARAMETERS ===
    'ior_constant': 'ior_constant',  # Index of refraction
    
    # === SUBSURFACE PARAMETERS ===
    'subsurface_constant': 'subsurface_constant',  # Subsurface value
    'subsurface_texture': 'subsurface_texture',  # Subsurface texture
    'subsurface_color_constant': 'subsurface_color_constant',  # Subsurface color
    'subsurface_color_texture': 'subsurface_color_texture',  # Subsurface color texture
    
    # === AO PARAMETERS ===
    'ao_to_diffuse': 'ao_to_diffuse',  # AO to diffuse
    'ao_texture': 'ao_texture',  # AO texture
    
    # === ORM PARAMETERS ===
    'enable_ORM_texture': 'enable_ORM_texture',  # Enable ORM texture
    'ORM_texture': 'ORM_texture',  # ORM texture
    
    # === UV TRANSFORM PARAMETERS ===
    'project_uvw': 'project_uvw',  # Project UVW
    'world_or_object': 'world_or_object',  # World or object space
    'uv_space_index': 'uv_space_index',  # UV space index
    'texture_translate': 'texture_translate',  # Texture translation
    'texture_rotate': 'texture_rotate',  # Texture rotation
    'texture_scale': 'texture_scale',  # Texture scale
    'detail_texture_translate': 'detail_texture_translate',  # Detail texture translation
    'detail_texture_rotate': 'detail_texture_rotate',  # Detail texture rotation
    'detail_texture_scale': 'detail_texture_scale',  # Detail texture scale
}

# Default values for Remix Opacity Material parameters
REMIX_DEFAULT_VALUES = {
    # === CORE MATERIAL PARAMETERS ===
    'opacity_constant': 1.0,
    'diffuse_color_constant': 'color(0.8, 0.8, 0.8)',
    'reflection_roughness_constant': 0.5,
    'metallic_constant': 0.0,
    'specular_constant': 0.5,
    
    # === EMISSION PARAMETERS ===
    'enable_emission': False,
    'emissive_color_constant': 'color(0.0, 0.0, 0.0)',
    'emissive_intensity': 1.0,
    
    # === ADVANCED MATERIAL PARAMETERS ===
    'enable_thin_film': False,
    'thin_film_thickness_constant': 200.0,
    'anisotropy_constant': 0.0,
    'use_legacy_alpha_state': True,
    'blend_enabled': False,
    
    # === CLEARCOAT PARAMETERS ===
    'clearcoat_constant': 0.0,
    'clearcoat_roughness_constant': 0.03,
    
    # === IOR PARAMETERS ===
    'ior_constant': 1.45,
    
    # === SUBSURFACE PARAMETERS ===
    'subsurface_constant': 0.0,
    'subsurface_color_constant': 'color(1.0, 1.0, 1.0)',
    
    # === TEXTURE SETTINGS ===
    'filter_mode': 'Linear',
    'wrap_mode_u': 'tex::wrap_repeat',
    'wrap_mode_v': 'tex::wrap_repeat',
    'encoding': 'AperturePBR_Normal::octahedral',
    
    # === SPRITE SHEET PARAMETERS ===
    'sprite_sheet_fps': 0,
    'sprite_sheet_cols': 1,
    'sprite_sheet_rows': 1,
    
    # === ALPHA TEST PARAMETERS ===
    'alpha_test_type': 'Always',
    'alpha_test_reference_value': 0.0,
    
    # === DISPLACEMENT PARAMETERS ===
    'displace_in': 0.05,
    'displace_out': 0.0,
    
    # === OTHER PARAMETERS ===
    'preload_textures': False,
    'ignore_material': False,
}

# Texture gamma modes for Remix Opacity Material
TEXTURE_GAMMA_MODES = {
    'diffuse_texture': 'tex::gamma_srgb',
    'reflectionroughness_texture': 'tex::gamma_linear',
    'metallic_texture': 'tex::gamma_linear',
    'normalmap_texture': 'tex::gamma_linear',
    'emissive_mask_texture': 'tex::gamma_srgb',
    'opacity_texture': 'tex::gamma_srgb',
    'clearcoat_texture': 'tex::gamma_linear',
    'clearcoat_roughness_texture': 'tex::gamma_linear',
    'subsurface_texture': 'tex::gamma_linear',
    'subsurface_color_texture': 'tex::gamma_srgb',
    'ao_texture': 'tex::gamma_linear',
    'ORM_texture': 'tex::gamma_linear',
    'detail_normalmap_texture': 'tex::gamma_linear',
}

# Parameter transformations for specific types
PARAMETER_TRANSFORMATIONS = {
    # === COLOR PARAMETERS ===
    'diffuse_color_constant': lambda value: _fix_color_parameter(value),
    'diffuse_tint': lambda value: _fix_color_parameter(value),
    'emissive_color': lambda value: _fix_color_parameter(value),
    'subsurface_color_constant': lambda value: _fix_color_parameter(value),
    
    # === TEXTURE PARAMETERS ===
    'diffuse_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_srgb', mdl_file_path),
    'reflectionroughness_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'metallic_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'normalmap_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'emissive_mask_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_srgb', mdl_file_path),
    'opacity_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_srgb', mdl_file_path),
    'clearcoat_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'clearcoat_roughness_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'subsurface_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'subsurface_color_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_srgb', mdl_file_path),
    'ao_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'ORM_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    'detail_normalmap_texture': lambda value, mdl_file_path=None: _fix_texture_parameter(value, 'tex::gamma_linear', mdl_file_path),
    
    # === FLOAT PARAMETERS ===
    'metallic_constant': lambda value: _fix_float_parameter(value),
    'reflection_roughness_constant': lambda value: _fix_float_parameter(value),
    'specular_level': lambda value: _fix_float_parameter(value),
    'clearcoat_constant': lambda value: _fix_float_parameter(value),
    'clearcoat_roughness_constant': lambda value: _fix_float_parameter(value),
    'ior_constant': lambda value: _fix_float_parameter(value),
    'subsurface_constant': lambda value: _fix_float_parameter(value),
    'opacity_constant': lambda value: _fix_float_parameter(value),
    'emissive_intensity': lambda value: _fix_float_parameter(value),
    'bump_factor': lambda value: _fix_float_parameter(value),
    'detail_bump_factor': lambda value: _fix_float_parameter(value),
    'metallic_texture_influence': lambda value: _fix_float_parameter(value),
    'reflection_roughness_texture_influence': lambda value: _fix_float_parameter(value),
    'albedo_desaturation': lambda value: _fix_float_parameter(value),
    'albedo_add': lambda value: _fix_float_parameter(value),
    'albedo_brightness': lambda value: _fix_float_parameter(value),
    'ao_to_diffuse': lambda value: _fix_float_parameter(value),
    'texture_rotate': lambda value: _fix_float_parameter(value),
    'detail_texture_rotate': lambda value: _fix_float_parameter(value),
    'uv_space_index': lambda value: _fix_float_parameter(value),
}

def _fix_texture_parameter(value, gamma_mode, mdl_file_path=None):
    """Fix texture parameter format for Remix materials"""
    if not value or value == 'texture_2d()':
        return ""  # Return empty string for empty textures
    
    # Extract texture path from texture_2d("./path", gamma_mode)
    if value.startswith('texture_2d('):
        import re
        import os
        texture_match = re.search(r'texture_2d\("([^"]*)"', value)
        if texture_match:
            texture_path = texture_match.group(1)
            if texture_path:  # Only return if path is not empty
                # The path in MDL is relative to the MDL file location
                # When referenced from USD, we need to adjust the path
                if texture_path.startswith('./') and mdl_file_path:
                    # Get the directory of the MDL file
                    mdl_dir = os.path.dirname(mdl_file_path)
                    # Resolve the texture path relative to the MDL file location
                    resolved_path = os.path.join(mdl_dir, texture_path[2:])  # Remove './' prefix
                    # Convert to forward slashes for USD compatibility
                    resolved_path = resolved_path.replace('\\', '/')
                    return resolved_path
                else:
                    return texture_path  # Return just the path, not wrapped in texture_2d()
    
    return ""  # Return empty string for unrecognized formats

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
        return float(value)  # Return as Python float, not MDL format
    elif isinstance(value, str) and value.endswith('f'):
        # Convert MDL format to Python float
        try:
            return float(value.rstrip('f'))
        except ValueError:
            return 0.0
    return value

def convert_omnipbr_to_remix(omnipbr_params, mdl_file_path=None):
    """
    Convert OmniPBR parameters to Remix Opacity Material parameters
    
    Args:
        omnipbr_params (dict): OmniPBR parameters from MDL file
        mdl_file_path (str): Path to the MDL file for texture path resolution
        
    Returns:
        dict: Converted Remix parameters
    """
    remix_params = {}
    
    # Start with default values
    remix_params.update(REMIX_DEFAULT_VALUES)
    
    # Map and convert parameters
    for omnipbr_param, value in omnipbr_params.items():
        if omnipbr_param in OMNIPBR_TO_REMIX_MAPPING:
            remix_param = OMNIPBR_TO_REMIX_MAPPING[omnipbr_param]
            
            # Apply transformation if available
            if omnipbr_param in PARAMETER_TRANSFORMATIONS:
                # For texture parameters, pass the MDL file path
                if omnipbr_param.endswith('_texture'):
                    transformed_value = PARAMETER_TRANSFORMATIONS[omnipbr_param](value, mdl_file_path)
                else:
                    transformed_value = PARAMETER_TRANSFORMATIONS[omnipbr_param](value)
            else:
                transformed_value = value
            
            # Handle special cases
            if omnipbr_param == 'diffuse_tint' and 'diffuse_color_constant' in remix_params:
                # If we have both diffuse_color_constant and diffuse_tint, 
                # diffuse_tint takes precedence
                remix_params[remix_param] = transformed_value
            else:
                remix_params[remix_param] = transformed_value
    
    # Handle special cases
    _apply_omnipbr_special_transformations(remix_params, omnipbr_params)
    
    return remix_params

def _apply_omnipbr_special_transformations(remix_params, omnipbr_params):
    """Apply special transformations for OmniPBR to Remix conversion"""
    
    # Enable emission if emissive texture exists or emissive color is not black
    if 'emissive_mask_texture' in remix_params:
        # Check if emissive texture is not empty
        emissive_texture = remix_params['emissive_mask_texture']
        if isinstance(emissive_texture, str) and emissive_texture != 'texture_2d("", tex::gamma_srgb)':
            remix_params['enable_emission'] = True
    elif 'emissive_color_constant' in remix_params:
        emissive_color = remix_params['emissive_color_constant']
        if isinstance(emissive_color, str) and 'color(0.0, 0.0, 0.0)' not in emissive_color:
            remix_params['enable_emission'] = True
    
    # Handle opacity for transparency
    if 'opacity_constant' in remix_params:
        opacity = remix_params['opacity_constant']
        if isinstance(opacity, (int, float)) and opacity < 1.0:
            remix_params['blend_enabled'] = True
    
    # Handle texture influence parameters
    if 'metallic_texture_influence' in remix_params and 'metallic_texture' in remix_params:
        influence = remix_params['metallic_texture_influence']
        if isinstance(influence, (int, float)) and influence < 1.0:
            # If texture influence is less than 1.0, we might need to blend with constant
            pass  # Could implement blending logic here
    
    if 'reflection_roughness_texture_influence' in remix_params and 'reflectionroughness_texture' in remix_params:
        influence = remix_params['reflection_roughness_texture_influence']
        if isinstance(influence, (int, float)) and influence < 1.0:
            # If texture influence is less than 1.0, we might need to blend with constant
            pass  # Could implement blending logic here

def get_remix_material_template(material_name, remix_params):
    """
    Generate Remix USD Material template for OmniPBR conversion
    Only includes texture references and emissive settings (if emissive texture exists)
    
    Args:
        material_name (str): Name of the material
        remix_params (dict): Remix parameters
        
    Returns:
        str: Complete USD material content
    """
    
    # Build parameter list for USD format
    param_list = []
    
    # Check if emissive texture exists
    has_emissive_texture = any(param_name == 'emissive_mask_texture' and 
                              isinstance(param_value, str) and 
                              param_value and not param_value.startswith('texture_2d("",') 
                              for param_name, param_value in remix_params.items())
    
    # Handle different parameter types for USD
    for param_name, param_value in remix_params.items():
        # Skip internal parameters that shouldn't be in USD
        skip_params = ['filter_mode', 'wrap_mode_u', 'wrap_mode_v', 'encoding', 
                      'sprite_sheet_fps', 'sprite_sheet_cols', 'sprite_sheet_rows',
                      'preload_textures', 'ignore_material', 'alpha_test_type',
                      'alpha_test_reference_value', 'displace_in', 'displace_out',
                      'metallic_texture_influence', 'reflection_roughness_texture_influence',
                      'albedo_desaturation', 'albedo_add', 'albedo_brightness',
                      'ao_to_diffuse', 'project_uvw', 'world_or_object', 'uv_space_index',
                      'texture_translate', 'texture_rotate', 'texture_scale',
                      'detail_texture_translate', 'detail_texture_rotate', 'detail_texture_scale',
                      'enable_ORM_texture']
        
        if param_name in skip_params:
            continue
        
        usd_param_name = f"inputs:{param_name}"
        
        # Handle texture parameters
        if param_name.endswith('_texture') and isinstance(param_value, str):
            texture_path = None
            
            # Handle resolved texture paths (already processed by _fix_texture_parameter)
            if param_value and not param_value.startswith('texture_2d("",') and not param_value.startswith('texture_2d()'):
                # The texture path should already be resolved by _fix_texture_parameter
                texture_path = param_value
            elif param_value.startswith('texture_2d("./'):
                # Fallback: Extract texture path from texture_2d("./path", gamma_mode)
                import re
                texture_match = re.search(r'texture_2d\("([^"]*)"', param_value)
                if texture_match:
                    texture_path = texture_match.group(1)
            elif param_value.startswith('D:/') or param_value.startswith('C:/'):
                # Convert absolute path to relative path
                import os
                # Extract just the filename from the absolute path
                filename = os.path.basename(param_value)
                texture_path = f'./textures/{filename}'
            
            if texture_path:
                # Map texture parameter names to Remix input names
                remix_param_mapping = {
                    'albedo_texture': 'diffuse_texture',
                    'base_color_texture': 'diffuse_texture',
                    'diffuse_texture': 'diffuse_texture',
                    'normal_texture': 'normalmap_texture',
                    'normalmap_texture': 'normalmap_texture',
                    'roughness_texture': 'reflectionroughness_texture',
                    'metallic_texture': 'metallic_texture',
                    'reflection_roughness_texture': 'reflectionroughness_texture',
                    'emissive_mask_texture': 'emissive_mask_texture',
                    'emissive_color_texture': 'emissive_color_texture'
                }
                
                remix_param_name = remix_param_mapping.get(param_name, param_name)
                usd_param_name = f"inputs:{remix_param_name}"
                param_list.append(f'        asset {usd_param_name} = @{texture_path}@')
        
        # Handle boolean parameters
        elif isinstance(param_value, bool):
            param_list.append(f'        bool {usd_param_name} = {1 if param_value else 0}')
        
        # Handle numeric parameters (int, float)
        elif isinstance(param_value, (int, float)):
            param_list.append(f'        float {usd_param_name} = {param_value}')
        
        # Handle string parameters (for constants, etc.)
        elif isinstance(param_value, str):
            param_list.append(f'        string {usd_param_name} = "{param_value}"')
    
    params_str = '\n'.join(param_list)
    
    # Generate the USD material template with 0 indentation
    # The _indent_material_definition method will add the correct base indentation
    template = f'''def Material "{material_name}" (
    references = @./materials/AperturePBR_Opacity.usda@</Looks/mat_AperturePBR_Opacity>
)
{{
    over "Shader"
    {{
{params_str}
    }}
}}'''
    
    return template