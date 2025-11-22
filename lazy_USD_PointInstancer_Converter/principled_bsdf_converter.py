#!/usr/bin/env python3
"""
Principled_BSDF Converter for USD PointInstancer
Converts Blender-exported Principled_BSDF materials to Remix-compatible materials
"""

import os
import re
from typing import Dict, Any, Optional
from principled_bsdf_mapping import convert_to_remix as convert_principled_to_remix

def parse_material(material_prim):
    """Standardized parse function - parses Principled_BSDF or UsdPreviewSurface material from USD prim"""
    try:
        from pxr import UsdShade
        
        material = UsdShade.Material(material_prim)
        surface_output = material.GetSurfaceOutput()
        
        if not surface_output:
            return None
        
        connected_source = surface_output.GetConnectedSource()
        if not connected_source or len(connected_source) == 0:
            return None
        
        shader_prim = connected_source[0].GetPrim()
        shader = UsdShade.Shader(shader_prim)
        shader_id = shader.GetIdAttr().Get()
        
        # Handle UsdPreviewSurface (Blender's standard export)
        if shader_id == "UsdPreviewSurface":
            return _parse_usdpreviewsurface_from_shader(shader, material_prim)
        
        return None
        
    except Exception as e:
        print(f"ERROR Failed to parse Principled_BSDF material: {e}")
        return None

def _parse_usdpreviewsurface_from_shader(shader, material_prim):
    """Parse UsdPreviewSurface shader to extract parameters"""
    from pxr import UsdShade
    import os
    
    params = {}
    shader_inputs = shader.GetInputs()
    
    for shader_input in shader_inputs:
        input_name = shader_input.GetBaseName()
        
        # Check if connected to texture
        connected_source = shader_input.GetConnectedSource()
        if connected_source and len(connected_source) > 0:
            texture_shader = UsdShade.Shader(connected_source[0].GetPrim())
            file_input = texture_shader.GetInput('file')
            if file_input:
                texture_path = file_input.Get()
                if texture_path:
                    # Store raw path with proper ./textures/ format
                    raw_path = str(texture_path.path)
                    # Ensure path has ./textures/ prefix if it's just a filename
                    if not raw_path.startswith('./') and not os.path.isabs(raw_path):
                        raw_path = f"./textures/{os.path.basename(raw_path)}"
                    params[f"inputs:{input_name}"] = raw_path
                    params[f"inputs:{input_name}_is_texture"] = True
        else:
            # Get constant value
            value = shader_input.Get()
            if value is not None:
                params[f"inputs:{input_name}"] = value
    
    return params

