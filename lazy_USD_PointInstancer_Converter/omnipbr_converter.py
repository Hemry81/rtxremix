#!/usr/bin/env python3
"""
OmniPBR to Remix Opacity Material Converter
Converts OmniPBR materials from MDL files to Remix-compatible USD materials
"""

import os
import re
from omnipbr_mapping import convert_to_remix as convert_omnipbr_to_remix

def parse_material(material_prim):
    """Standardized parse function - alias for parse_omnipbr_material"""
    return parse_omnipbr_material(material_prim)

def parse_omnipbr_material(material_prim):
    """Parse OmniPBR material from a material prim"""
    try:
        from pxr import UsdShade
        import os
        
        material = UsdShade.Material(material_prim)
        
        # Try standard surface output first
        surface_output = material.GetSurfaceOutput()
        shader_prim = None
        
        if surface_output:
            connected_source = surface_output.GetConnectedSource()
            if connected_source and len(connected_source) > 0:
                shader_prim = connected_source[0].GetPrim()
        
        # If no standard surface, try MDL surface output
        if not shader_prim:
            mdl_surface = material.GetOutput('mdl:surface')
            if mdl_surface:
                connected_source = mdl_surface.GetConnectedSource()
                if connected_source and len(connected_source) > 0:
                    shader_prim = connected_source[0].GetPrim()
        
        # If still no shader, look for Shader child prim directly
        if not shader_prim:
            for child in material_prim.GetChildren():
                if child.GetName() == 'Shader':
                    shader_prim = child
                    break
        
        if not shader_prim:
            return None
        
        # Check for MDL source asset
        mdl_attr = shader_prim.GetAttribute('info:mdl:sourceAsset')
        if not mdl_attr or not mdl_attr.HasValue():
            return None
        
        mdl_path = str(mdl_attr.Get()).strip('@')
        if not mdl_path or not mdl_path.endswith('.mdl'):
            return None
        
        # Resolve MDL path relative to USD file
        stage = material_prim.GetStage()
        root_layer = stage.GetRootLayer()
        usd_dir = os.path.dirname(root_layer.identifier)
        mdl_full_path = os.path.join(usd_dir, mdl_path)
        
        if not os.path.exists(mdl_full_path):
            print(f"WARNING MDL file not found: {mdl_full_path}")
            return None
        
        # Parse the MDL file to get OmniPBR parameters
        omnipbr_params = parse_omnipbr_mdl(mdl_full_path)
        
        # CRITICAL: Extract texture paths and mark them with _is_texture flag
        # This matches the PrincipledBSDF approach for texture conversion
        if omnipbr_params:
            mdl_dir = os.path.dirname(mdl_full_path)
            for param_name, param_value in list(omnipbr_params.items()):
                if isinstance(param_value, str) and 'texture_2d(' in param_value:
                    # Extract texture path from texture_2d("path", gamma) format
                    import re
                    match = re.search(r'texture_2d\("([^"]+)"', param_value)
                    if match:
                        texture_path = match.group(1)
                        # Skip empty texture_2d() entries
                        if not texture_path or texture_path == '':
                            continue
                        
                        # Resolve relative paths from MDL directory
                        if texture_path.startswith('./'):
                            resolved_path = os.path.join(mdl_dir, texture_path[2:])
                            resolved_path = os.path.normpath(resolved_path).replace('\\', '/')
                            texture_path = resolved_path
                        
                        # Mark as texture for conversion system
                        omnipbr_params[f"{param_name}_is_texture"] = True
                        # Store the clean texture path (without texture_2d wrapper)
                        omnipbr_params[param_name] = texture_path
        
        return omnipbr_params
        
    except Exception as e:
        print(f"ERROR Failed to parse OmniPBR material: {e}")
        return None

def parse_omnipbr_mdl(mdl_file_path):
    """
    Parse OmniPBR material from MDL file
    
    Args:
        mdl_file_path (str): Path to the MDL file
        
    Returns:
        dict: OmniPBR parameters
    """
    if not os.path.exists(mdl_file_path):
        raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
    
    with open(mdl_file_path, 'r', encoding='utf-8') as f:
        mdl_content = f.read()
    
    # Extract the OmniPBR function call parameters
    # Look for: OmniPBR(parameter1: value1, parameter2: value2, ...)
    # Handle multi-line function calls with nested parentheses
    # The function call ends with ); on the last line
    omnipbr_pattern = r'OmniPBR\s*\(\s*([\s\S]*?)\s*\);'
    match = re.search(omnipbr_pattern, mdl_content, re.DOTALL)
    
    if not match:
        raise ValueError(f"Could not find OmniPBR function call in {mdl_file_path}")
    
    # Parse the parameters using a dedicated OmniPBR parameter parser
    params_text = match.group(1)
    omnipbr_params = parse_omnipbr_parameters(params_text)
    
    return omnipbr_params

def parse_omnipbr_parameters(params_text):
    """
    Parse OmniPBR parameters from the parameters text
    
    Args:
        params_text (str): Parameters text from OmniPBR function call
        
    Returns:
        dict: Parsed parameters
    """
    parameters = {}
    
    # Split by commas, but be careful with nested parentheses
    i = 0
    current_param = ""
    current_value = ""
    paren_level = 0
    in_string = False
    
    while i < len(params_text):
        char = params_text[i]
        
        if char == '"' and (i == 0 or params_text[i-1] != '\\'):
            in_string = not in_string
        
        if not in_string:
            if char == '(':
                paren_level += 1
            elif char == ')':
                paren_level -= 1
            elif char == ':' and paren_level == 0:
                # Start of parameter value
                current_param = params_text[:i].strip()
                current_value = ""
                params_text = params_text[i+1:]
                i = -1  # Reset index
            elif char == ',' and paren_level == 0:
                # End of parameter
                if current_param:
                    current_value += params_text[:i]
                    param_name = current_param.strip()
                    param_value = current_value.strip()
                    parameters[param_name] = param_value
                    
                    # Start next parameter
                    params_text = params_text[i+1:]
                    current_param = ""
                    current_value = ""
                    i = -1  # Reset index
        
        i += 1
    
    # Handle the last parameter
    if current_param:
        current_value += params_text
        param_name = current_param.strip()
        param_value = current_value.strip()
        parameters[param_name] = param_value
    
    # Clean up parameter values
    cleaned_parameters = {}
    for param_name, param_value in parameters.items():
        # Remove trailing commas and clean up whitespace
        param_value = param_value.rstrip(',').strip()
        
        # Handle different parameter types
        if param_value.startswith('color('):
            cleaned_parameters[param_name] = param_value
        elif param_value.startswith('texture_2d('):
            cleaned_parameters[param_name] = param_value
        elif param_value.endswith('f'):
            try:
                cleaned_parameters[param_name] = float(param_value.rstrip('f'))
            except ValueError:
                cleaned_parameters[param_name] = param_value
        elif param_value.lower() in ['true', 'false']:
            cleaned_parameters[param_name] = param_value.lower() == 'true'
        else:
            try:
                cleaned_parameters[param_name] = float(param_value)
            except ValueError:
                cleaned_parameters[param_name] = param_value
    
    return cleaned_parameters

def parse_omnipbr_materials_from_usd(usd_content):
    """
    Parse OmniPBR materials from USD content
    
    Args:
        usd_content (str): USD file content
        
    Returns:
        dict: Dictionary of material names to their MDL file paths and parameters
    """
    import re
    
    materials = {}
    
    # Find all Material definitions with MDL source assets
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
        
        # Check if this material has MDL source asset
        mdl_source_match = re.search(r'uniform asset info:mdl:sourceAsset\s*=\s*@([^@]+)@', material_content)
        if mdl_source_match:
            mdl_file_path = mdl_source_match.group(1)
            
            # Check if it's an OmniPBR material (contains OmniPBR in the path or is a .mdl file)
            if mdl_file_path.endswith('.mdl') and 'OmniPBR' in mdl_file_path or mdl_file_path.endswith('.mdl'):
                try:
                    # Parse the MDL file
                    omnipbr_params = parse_omnipbr_mdl(mdl_file_path)
                    materials[material_name] = {
                        'mdl_file_path': mdl_file_path,
                        'omnipbr_params': omnipbr_params
                    }
                except Exception as e:
                    print(f"Warning: Could not parse MDL file {mdl_file_path} for material {material_name}: {e}")
        
        # Move to next position
        i = j
    
    return materials

def convert_omnipbr_materials_in_usd(usd_content):
    """
    Convert all OmniPBR materials in USD content to Remix format
    
    Args:
        usd_content (str): USD file content
        
    Returns:
        str: Updated USD content with converted materials
    """
    # Parse OmniPBR materials
    omnipbr_materials = parse_omnipbr_materials_from_usd(usd_content)
    
    if not omnipbr_materials:
        return usd_content  # No OmniPBR materials found
    
    # Convert each material
    converted_materials = {}
    for material_name, material_info in omnipbr_materials.items():
        omnipbr_params = material_info['omnipbr_params']
        mdl_file_path = material_info['mdl_file_path']
        remix_params = convert_omnipbr_to_remix(omnipbr_params, mdl_file_path)
        converted_materials[material_name] = remix_params
    
    # Replace material definitions in USD content
    updated_content = usd_content
    
    for material_name, remix_params in converted_materials.items():
        # Generate new material definition
        new_material_def = get_remix_material_template(material_name, remix_params)
        
        # Find and replace the old material definition
        old_material_pattern = rf'def Material "{re.escape(material_name)}"[^{{]*\{{[^}}]*(?:\{{[^}}]*\}}[^}}]*)*\}}'
        updated_content = re.sub(old_material_pattern, new_material_def, updated_content, flags=re.DOTALL)
    
    return updated_content
