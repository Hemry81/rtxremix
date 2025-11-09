#!/usr/bin/env python3
"""
OmniPBR to Remix Opacity Material Converter
Converts OmniPBR materials from MDL files to Remix-compatible USD materials
"""

import os
import re
from omnipbr_mapping import (
    convert_omnipbr_to_remix,
    get_remix_material_template
)

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
