#!/usr/bin/env python3
"""
Unified Material Converter
Detects and converts PrincipledBSDF, OmniPBR, and UsdPreviewSurface materials to Remix format
"""

from pxr import UsdShade

# Import all material converters
try:
    from principled_bsdf_mapping import convert_to_remix as convert_principled_to_remix
    from principled_bsdf_converter import parse_material as parse_principled_material
except ImportError:
    convert_principled_to_remix = None
    parse_principled_material = None

try:
    from omnipbr_mapping import convert_to_remix as convert_omnipbr_to_remix
    from omnipbr_converter import parse_material as parse_omnipbr_material
except ImportError:
    convert_omnipbr_to_remix = None
    parse_omnipbr_material = None


def detect_material_type(material_prim):
    """
    Detect the type of material shader
    
    Returns:
        str: 'principled_bsdf', 'omnipbr', 'usdpreviewsurface', or None
    """
    try:
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
        
        # UsdPreviewSurface functions migrated to principled_bsdf
        if shader_id == "UsdPreviewSurface":
            return 'principled_bsdf'
        
        # Check for OmniPBR by looking at MDL source
        mdl_attr = shader_prim.GetAttribute('info:mdl:sourceAsset')
        if mdl_attr and mdl_attr.HasValue():
            mdl_path = str(mdl_attr.Get())
            if 'OmniPBR' in mdl_path or mdl_path.endswith('.mdl'):
                return 'omnipbr'
        
        return None
        
    except Exception as e:
        print(f"ERROR Failed to detect material type: {e}")
        return None


def convert_material_to_remix(material_prim, auto_blend_alpha=True, source_textures_dir=None):
    """
    Detect material type and convert to Remix format
    
    Args:
        material_prim: Material prim to convert
        auto_blend_alpha: Enable automatic blend mode for alpha textures (default: True)
        source_textures_dir: Directory containing source textures for alpha detection
    
    Returns:
        dict: {
            'is_remix': True,
            'conversion_type': str,
            'remix_params': dict,
            'prim': material_prim
        } or None if conversion failed
    """
    material_type = detect_material_type(material_prim)
    
    if not material_type:
        return None
    
    try:
        if material_type == 'principled_bsdf' and parse_principled_material and convert_principled_to_remix:
            params = parse_principled_material(material_prim)
            if params:
                # Pass auto_blend_alpha flag and source_textures_dir to material converter
                params['_auto_blend_alpha'] = auto_blend_alpha
                params['_source_textures_dir'] = source_textures_dir
                remix_params = convert_principled_to_remix(params)
                return {
                    'is_remix': True,
                    'conversion_type': 'principled_bsdf',
                    'remix_params': remix_params,
                    'prim': material_prim
                }
        
        elif material_type == 'omnipbr' and parse_omnipbr_material and convert_omnipbr_to_remix:
            params = parse_omnipbr_material(material_prim)
            if params:
                # Pass auto_blend_alpha flag and source_textures_dir to material converter
                params['_auto_blend_alpha'] = auto_blend_alpha
                params['_source_textures_dir'] = source_textures_dir
                remix_params = convert_omnipbr_to_remix(params)
                return {
                    'is_remix': True,
                    'conversion_type': 'omnipbr',
                    'remix_params': remix_params,
                    'prim': material_prim
                }
        
    except Exception as e:
        print(f"ERROR Failed to convert {material_type} material: {e}")
    
    return None
