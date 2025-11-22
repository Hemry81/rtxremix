#!/usr/bin/env python3
"""
OmniPBR Material Parameters
Complete parameter definitions based on OmniPBR.mdl
"""

# Complete list of OmniPBR parameters from the actual MDL file
OMNIPBR_PARAMETERS = {
    'diffuse_texture',
    'diffuse_color_constant',
    'diffuse_tint',
    'albedo_add',
    'albedo_brightness',
    'albedo_desaturation',
    'metallic_texture',
    'metallic_constant',
    'metallic_texture_influence',
    'reflectionroughness_texture',
    'reflection_roughness_constant',
    'reflection_roughness_texture_influence',
    'specular_level',
    'specular_texture',
    'anisotropy_constant',
    'anisotropy_texture',
    'normalmap_texture',
    'bump_factor',
    'detail_normalmap_texture',
    'detail_bump_factor',
    'emissive_mask_texture',
    'emissive_color',
    'emissive_intensity',
    'enable_emission',
    'opacity_constant',
    'opacity_texture',
    'enable_ORM_texture',
    'ORM_texture',
    'ao_texture',
    'ao_to_diffuse',
    'project_uvw',
    'world_or_object',
    'uv_space_index',
    'texture_translate',
    'texture_rotate',
    'texture_scale',
    'detail_texture_translate',
    'detail_texture_rotate',
    'detail_texture_scale',
}

# Mapping from OmniPBR to AperturePBR_Opacity parameters
OMNIPBR_TO_REMIX_MAPPING = {
    'diffuse_color_constant': 'diffuse_color_constant',
    'diffuse_texture': 'diffuse_texture',
    'diffuse_tint': 'diffuse_color_constant',
    'metallic_constant': 'metallic_constant',
    'metallic_texture': 'metallic_texture',
    'reflection_roughness_constant': 'reflection_roughness_constant',
    'reflectionroughness_texture': 'reflectionroughness_texture',
    'anisotropy_constant': 'anisotropy_constant',
    'anisotropy_texture': 'anisotropy_texture',
    'normalmap_texture': 'normalmap_texture',
    'enable_emission': 'enable_emission',
    'emissive_color': 'emissive_color_constant',
    'emissive_mask_texture': 'emissive_mask_texture',
    'emissive_intensity': 'emissive_intensity',
    'opacity_constant': 'opacity_constant',
    'opacity_texture': 'opacity_texture',
    
    # Specular parameters (for fallback to roughness)
    'specular_level': None,  # Not directly mapped, used for roughness fallback
    'specular_texture': None,  # Specular texture for roughness fallback
}

def validate_omnipbr_parameters(params):
    """Validate that parameters exist in OmniPBR.mdl"""
    valid_params = {}
    invalid_params = []
    
    for param_name, param_value in params.items():
        if param_name.startswith('_'):
            valid_params[param_name] = param_value
        elif param_name in OMNIPBR_PARAMETERS:
            valid_params[param_name] = param_value
        else:
            invalid_params.append(param_name)
    
    if invalid_params:
        print(f"WARNING: Invalid OmniPBR parameters removed: {invalid_params}")
    
    return valid_params
