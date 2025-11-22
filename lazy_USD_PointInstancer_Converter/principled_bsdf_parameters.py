#!/usr/bin/env python3
"""
PrincipledBSDF Material Parameters
Complete parameter definitions based on Blender's Principled BSDF shader
"""

# Complete list of PrincipledBSDF parameters
PRINCIPLED_BSDF_PARAMETERS = {
    'diffuseColor',
    'inputs:diffuseColor',
    'metallic',
    'inputs:metallic',
    'roughness',
    'inputs:roughness',
    'specular',
    'inputs:specular',
    'anisotropy',
    'inputs:anisotropy',
    'normal',
    'inputs:normal',
    'emissiveColor',
    'inputs:emissiveColor',
    'opacity',
    'inputs:opacity',
    'ior',
    'inputs:ior',
    'clearcoat',
    'inputs:clearcoat',
    'clearcoatRoughness',
    'inputs:clearcoatRoughness',
}

# Mapping from PrincipledBSDF to AperturePBR_Opacity parameters
PRINCIPLED_BSDF_TO_REMIX_MAPPING = {
    'diffuseColor': 'diffuse_color_constant',
    'inputs:diffuseColor': 'diffuse_color_constant',
    'diffuseColor.connect': 'diffuse_texture',
    'inputs:diffuseColor.connect': 'diffuse_texture',
    'metallic': 'metallic_constant',
    'inputs:metallic': 'metallic_constant',
    'metallic.connect': 'metallic_texture',
    'inputs:metallic.connect': 'metallic_texture',
    'roughness': 'reflection_roughness_constant',
    'inputs:roughness': 'reflection_roughness_constant',
    'roughness.connect': 'reflectionroughness_texture',
    'inputs:roughness.connect': 'reflectionroughness_texture',
    'specular': None,  # Used for roughness fallback
    'inputs:specular': None,  # Used for roughness fallback
    'specular.connect': None,  # Used for roughness fallback
    'inputs:specular.connect': None,  # Used for roughness fallback
    'anisotropy': 'anisotropy_constant',
    'inputs:anisotropy': 'anisotropy_constant',
    'anisotropy.connect': 'anisotropy_texture',
    'inputs:anisotropy.connect': 'anisotropy_texture',
    'normal': 'normalmap_texture',
    'inputs:normal': 'normalmap_texture',
    'normal.connect': 'normalmap_texture',
    'inputs:normal.connect': 'normalmap_texture',
    'emissiveColor': 'emissive_color_constant',
    'inputs:emissiveColor': 'emissive_color_constant',
    'opacity': None,  # Triggers blend mode
    'inputs:opacity': None,  # Triggers blend mode
    'opacity.connect': None,  # Triggers blend mode
    'inputs:opacity.connect': None,  # Triggers blend mode
}

def validate_principled_bsdf_parameters(params):
    """Validate that parameters exist in PrincipledBSDF"""
    valid_params = {}
    invalid_params = []
    
    for param_name, param_value in params.items():
        if param_name.startswith('_'):
            valid_params[param_name] = param_value
        elif param_name in PRINCIPLED_BSDF_PARAMETERS or param_name.endswith('.connect'):
            valid_params[param_name] = param_value
        else:
            invalid_params.append(param_name)
    
    if invalid_params:
        print(f"WARNING: Invalid PrincipledBSDF parameters removed: {invalid_params}")
    
    return valid_params
