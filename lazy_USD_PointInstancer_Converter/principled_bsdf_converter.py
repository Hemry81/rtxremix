#!/usr/bin/env python3
"""
Principled_BSDF Converter for USD PointInstancer
Converts Blender-exported Principled_BSDF materials to Remix-compatible materials
"""

import os
import re
import shutil
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from principled_bsdf_mapping import (
    convert_principled_bsdf_to_remix, 
    get_remix_material_template,
    parse_principled_bsdf_from_usd
)

class PrincipledBSDFConverter:
    """
    Converts Principled_BSDF materials from USD files to Remix-compatible materials
    """
    
    def __init__(self):
        pass
    
    def _replace_principled_bsdf_materials(self, content: str, material_mapping: Dict[str, str], 
                                         material_prefix: str) -> str:
        """
        Replace Principled_BSDF material definitions with Remix USD material definitions
        """
        # For each material, replace the definition
        for original_name, converted_name in material_mapping.items():
            # Read the converted material content
            converted_material_path = os.path.join("converted_materials", f"{converted_name}.usda")
            if os.path.exists(converted_material_path):
                with open(converted_material_path, 'r', encoding='utf-8') as f:
                    converted_material_content = f.read()
                
                # Find the material definition in the original USD
                start_pos = content.find(f'def Material "{original_name}"')
                if start_pos != -1:
                    # Find the matching closing brace using state machine
                    brace_count = 0
                    end_pos = start_pos
                    in_material = False
                    
                    for i in range(start_pos, len(content)):
                        if content[i] == '{':
                            if not in_material:
                                in_material = True
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if in_material and brace_count == 0:
                                end_pos = i + 1
                                break
                    
                    if end_pos > start_pos:
                        # Replace the entire material definition
                        old_material_def = content[start_pos:end_pos]
                        # Extract just the material definition part from the converted content
                        # Remove the "def Material "name" (" and closing ")" parts
                        material_start = converted_material_content.find('(')
                        material_end = converted_material_content.rfind(')')
                        if material_start != -1 and material_end != -1:
                            # Extract the content between the parentheses
                            material_content = converted_material_content[converted_material_content.find('{', material_start):converted_material_content.rfind('}')+1]
                            # Create the new material definition
                            new_material_def = f'def Material "{original_name}" (\n    references = @./materials/AperturePBR_Opacity.usda@</Looks/mat_AperturePBR_Opacity>\n)\n{material_content}'
                            content = content.replace(old_material_def, new_material_def)
        
        return content