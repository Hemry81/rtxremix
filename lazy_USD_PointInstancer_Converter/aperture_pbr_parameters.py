#!/usr/bin/env python3
"""
AperturePBR_Opacity Material Parameters
Standardized parameter definitions based on AperturePBR_Opacity.mdl
"""

# Complete list of AperturePBR_Opacity parameters from the actual MDL file
APERTURE_PBR_OPACITY_PARAMETERS = {
    'diffuse_texture',
    'diffuse_color_constant',
    'albedo_add',
    'albedo_brightness',
    'albedo_desaturation',
    'metallic_texture',
    'metallic_constant',
    'reflectionroughness_texture',
    'reflection_roughness_constant',
    'reflection_roughness_texture_influence',
    'anisotropy_constant',
    'anisotropy_texture',
    'normalmap_texture',
    'normalmap_strength',
    'normalmap_encoding',
    'height_texture',
    'height_offset',
    'height_scale',
    'emissive_mask_texture',
    'emissive_color_constant',
    'emissive_intensity',
    'enable_emission',
    'opacity_constant',
    'opacity_texture', # fallback for combined opacity to alpha textures
    'opacity_mode',
    'enable_thin_film',
    'thin_film_thickness_constant',
    'subsurface_transmittance_color',
    'subsurface_transmittance_texture',
    'subsurface_measurement_distance',
    'subsurface_thickness_texture',
    'subsurface_single_scattering_albedo',
    'subsurface_volumetric_anisotropy',
    'use_legacy_alpha_state',
    'blend_enabled',
    'cutout_opacity',
    'preload_textures',
    'ignore_material',
}

# Default values for AperturePBR_Opacity parameters
APERTURE_PBR_OPACITY_DEFAULTS = {
    'diffuse_color_constant': 'color(0.8, 0.8, 0.8)',
    'albedo_add': 0.0,
    'albedo_brightness': 0.0,
    'albedo_desaturation': 0.0,
    'metallic_constant': 0.0,
    'reflection_roughness_constant': 0.5,
    'reflection_roughness_texture_influence': 1.0,
    'anisotropy_constant': 0.0,
    'normalmap_strength': 1.0,
    'normalmap_encoding': 0,
    'height_offset': 0.0,
    'height_scale': 1.0,
    'emissive_intensity': 1.0,
    'enable_emission': False,
    'opacity_constant': 1.0,
    'opacity_mode': 1,
    'enable_thin_film': False,
    'thin_film_thickness_constant': 200.0,
    'subsurface_measurement_distance': 0.0,
    'subsurface_single_scattering_albedo': 'color(0.5, 0.5, 0.5)',
    'subsurface_volumetric_anisotropy': 0.0,
    'use_legacy_alpha_state': True,
    'blend_enabled': False,
    'cutout_opacity': 0.5,
    'preload_textures': False,
    'ignore_material': False,
}

# Texture gamma modes for each texture parameter
TEXTURE_GAMMA_MODES = {
    'diffuse_texture': 'srgb',
    'metallic_texture': 'linear',
    'reflectionroughness_texture': 'linear',
    'anisotropy_texture': 'linear',
    'normalmap_texture': 'linear',
    'height_texture': 'linear',
    'emissive_mask_texture': 'srgb',
    'opacity_texture': 'linear',
    'subsurface_transmittance_texture': 'srgb',
    'subsurface_thickness_texture': 'linear',
}

def get_texture_gamma_mode(texture_param_name):
    """Get the correct gamma mode for a texture parameter"""
    return TEXTURE_GAMMA_MODES.get(texture_param_name, 'linear')

def get_standard_remix_material_template():
    """Get a standard Remix material template with default values"""
    return APERTURE_PBR_OPACITY_DEFAULTS.copy()

def validate_remix_parameters(params):
    """Validate that parameters exist in AperturePBR_Opacity.mdl"""
    valid_params = {}
    invalid_params = []
    
    for param_name, param_value in params.items():
        if param_name.startswith('_'):
            valid_params[param_name] = param_value
        elif param_name in APERTURE_PBR_OPACITY_PARAMETERS:
            valid_params[param_name] = param_value
        else:
            invalid_params.append(param_name)
    
    if invalid_params:
        print(f"WARNING: Invalid parameters removed: {invalid_params}")
    
    return valid_params

def clean_remix_parameters(params):
    """Remove invalid parameters and apply defaults"""
    cleaned = validate_remix_parameters(params)
    
    for param_name, default_value in APERTURE_PBR_OPACITY_DEFAULTS.items():
        if param_name not in cleaned:
            cleaned[param_name] = default_value
    
    return cleaned

def matches_default_value(param_name, value):
    """Check if a parameter value matches the Remix default value"""
    if param_name not in APERTURE_PBR_OPACITY_DEFAULTS:
        return False
    
    default = APERTURE_PBR_OPACITY_DEFAULTS[param_name]
    
    # Handle color comparisons
    if isinstance(default, str) and default.startswith('color('):
        if isinstance(value, str) and value.startswith('color('):
            return value == default
        elif isinstance(value, (tuple, list)) and len(value) >= 3:
            # Parse default color
            import re
            match = re.search(r'color\(([^)]+)\)', default)
            if match:
                default_vals = [float(x.strip()) for x in match.group(1).split(',')]
                return (abs(value[0] - default_vals[0]) < 0.001 and 
                        abs(value[1] - default_vals[1]) < 0.001 and 
                        abs(value[2] - default_vals[2]) < 0.001)
    
    # Handle float/int comparisons
    if isinstance(default, (int, float)) and isinstance(value, (int, float)):
        return abs(float(value) - float(default)) < 0.001
    
    # Handle bool comparisons
    if isinstance(default, bool) and isinstance(value, bool):
        return value == default
    
    # Direct comparison
    return value == default
