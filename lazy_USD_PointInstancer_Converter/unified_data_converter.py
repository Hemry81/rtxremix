#!/usr/bin/env python3
"""
Unified Data Converter for USD PointInstancer Converter
Prepares all data for output generation - transforms collected data into output-ready format
"""

import os
import re
import time
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

# Import material conversion modules
try:
    from principled_bsdf_mapping import (
        convert_principled_bsdf_to_remix,
        parse_principled_bsdf_from_usd,
        get_remix_material_template,
        parse_principled_bsdf_material
    )
    from omnipbr_mapping import (
        convert_omnipbr_to_remix,
        get_remix_material_template as get_omnipbr_remix_template
    )
    from omnipbr_converter import parse_omnipbr_mdl
    MATERIAL_CONVERSION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Material conversion modules not available: {e}")
    MATERIAL_CONVERSION_AVAILABLE = False

class UnifiedDataConverter:
    """Converts collected data into output-ready format"""
    
    def __init__(self, unified_data, use_external_references=False):
        self.unified_data = unified_data
        self.use_external_references = use_external_references
        self.output_data = {}
        
        # Material conversion settings
        self.enable_principled_bsdf_conversion = True
        self.enable_omnipbr_conversion = True
        
    def convert_data(self):
        """Convert collected data into output-ready format"""
        print("CONVERT Converting collected data for output generation...")
        
        # Initialize output data structure
        self.output_data = {
            'materials': {},
            'stage_metadata': self.unified_data['stage_metadata'],
            'pointinstancers': [],
            'unique_objects': [],
            'external_prototypes': [],
            'input_type': self.unified_data['input_type']  # Preserve input type for operation reporting
        }
        
        # Convert materials to Remix format
        self._convert_materials_to_remix()
        
        input_type = self.unified_data['input_type']
        
        if input_type == 'forward_instanceable':
            self._convert_forward_data()
        elif input_type == 'reverse':
            self._convert_reverse_data()
        elif input_type in ['existing_pointinstancer', 'blender45_pointinstancer']:
            self._convert_existing_pointinstancer_data()
        
        print(f"CONVERT Converted data ready for output generation")
        return self.output_data
    
    def _convert_materials_to_remix(self):
        """Convert all materials to Remix format"""
        if not MATERIAL_CONVERSION_AVAILABLE:
            print("WARNING Material conversion modules not available, copying materials as-is")
            self.output_data['materials'] = self.unified_data['materials']
            return
        
        converted_materials = {}
        
        for material_name, material_info in self.unified_data['materials'].items():
            material_prim = material_info['prim']
            
            # Convert material to Remix format
            conversion_type, remix_params = self._detect_and_parse_material(material_prim)
            
            if conversion_type and remix_params:
                # Create Remix material structure
                remix_material_info = {
                    'prim': material_prim,
                    'path': material_info['path'],
                    'conversion_type': conversion_type,
                    'remix_params': remix_params,
                    'is_remix': True
                }
                converted_materials[material_name] = remix_material_info
            else:
                # Keep original material if conversion not possible
                material_info['is_remix'] = False
                converted_materials[material_name] = material_info
        
        self.output_data['materials'] = converted_materials
    
    def _detect_and_parse_material(self, material_prim):
        """
        Detect material type and parse parameters
        
        Args:
            material_prim: Source material prim
            
        Returns:
            tuple: (conversion_type, remix_params) or (None, None) if no conversion possible
        """
        material_name = material_prim.GetName()
        
        # Check if this is a Principled_BSDF material by looking for Principled_BSDF shader children
        if self.enable_principled_bsdf_conversion:
            # Check if the material has a Principled_BSDF shader child
            children = list(material_prim.GetChildren())
            for child in children:
                if child.GetTypeName() == "Shader" and "Principled_BSDF" in str(child.GetName()):
                    # Parse Principled_BSDF parameters
                    try:
                        principled_params = parse_principled_bsdf_material(material_prim)
                        if principled_params:
                            remix_params = convert_principled_bsdf_to_remix(principled_params)
                            if remix_params:
                                return "principled_bsdf", remix_params
                    except Exception as e:
                        print(f"WARNING Error parsing Principled_BSDF material {material_name}: {e}")
                        continue
        
        # Check if this is an OmniPBR material
        if self.enable_omnipbr_conversion:
            # Check for info:mdl:sourceAsset on the material prim itself
            mdl_source = material_prim.GetAttribute("info:mdl:sourceAsset")
            if mdl_source and mdl_source.Get():
                # Parse OmniPBR parameters
                mdl_file_path = str(mdl_source.Get())
                clean_mdl_path = mdl_file_path.strip('@')
                if os.path.exists(clean_mdl_path):
                    omnipbr_params = parse_omnipbr_mdl(clean_mdl_path)
                    remix_params = convert_omnipbr_to_remix(omnipbr_params, clean_mdl_path)
                    if remix_params:
                        return "omnipbr", remix_params
            else:
                # Check child shader prims
                for child in material_prim.GetChildren():
                    if child.GetTypeName() == "Shader":
                        child_mdl_source = child.GetAttribute("info:mdl:sourceAsset")
                        if child_mdl_source and child_mdl_source.Get():
                            # Parse OmniPBR parameters
                            mdl_file_path = str(child_mdl_source.Get())
                            
                            # Strip @ symbols from USD asset path
                            clean_mdl_path = mdl_file_path.strip('@')
                            
                            if os.path.exists(clean_mdl_path):
                                omnipbr_params = parse_omnipbr_mdl(clean_mdl_path)
                                if omnipbr_params:
                                    remix_params = convert_omnipbr_to_remix(omnipbr_params, clean_mdl_path)
                                    if remix_params:
                                        return "omnipbr", remix_params
        
        return None, None
    
    def _convert_forward_data(self):
        """Convert forward conversion data for output generation"""
        # Initialize output data
        self.output_data = {
            'unique_objects': [],
            'pointinstancers': [],
            'external_prototypes': [],
            'materials': self.output_data['materials'],  # Use the converted materials
            'stage_metadata': self.unified_data['stage_metadata'],
            'input_type': 'forward_instanceable'
        }
        
        # Process anchor meshes and their children
        for anchor_data in self.unified_data['anchor_meshes']:
            anchor_name = anchor_data['container_prim'].GetName()
            
            # Group children by reference path to create PointInstancers
            children_by_reference = {}
            for child in anchor_data['children']:
                ref_path = child['reference_path']
                if ref_path not in children_by_reference:
                    children_by_reference[ref_path] = []
                children_by_reference[ref_path].append(child)
            
            # Create PointInstancers for each reference group
            for ref_path, instances in children_by_reference.items():
                if len(instances) > 1:
                    # Multiple instances - create PointInstancer
                    pointinstancer_data = {
                        'type': 'pointinstancer',
                        'path': f"/Root/{anchor_name}/PointInstancer_{len(self.output_data['pointinstancers'])}",
                        'prototype_mesh': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'],
                        'prototype_name': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'].GetName(),
                        'instances': instances,
                        'parent_anchor': anchor_data,  # Store parent anchor information
                        'parent_path': f"/Root/{anchor_name}"  # Path where this PointInstancer should be created
                    }
                    self.output_data['pointinstancers'].append(pointinstancer_data)
                else:
                    # Single instance - create as unique object
                    single_instance_data = {
                        'type': 'single_instance',
                        'path': f"/Root/{anchor_name}/{instances[0]['blender_name'] or 'SingleInstance'}",
                        'mesh_prim': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'],
                        'translate': instances[0]['translate'],
                        'rotate': instances[0]['rotate'],
                        'scale': instances[0]['scale'],
                        'material_binding': self.unified_data['prototype_meshes'][ref_path]['material_binding'],
                        'parent_anchor': anchor_data,  # Store parent anchor information
                        'parent_path': f"/Root/{anchor_name}"  # Path where this single instance should be created
                    }
                    self.output_data['unique_objects'].append(single_instance_data)
            
            # Add the anchor mesh itself as a unique object
            anchor_object_data = {
                'type': 'anchor_mesh',
                'path': f"/Root/{anchor_name}",
                'mesh_prim': anchor_data['mesh_prim'],
                'transform': anchor_data['transform'],
                'material_binding': anchor_data['material_binding'],
                'has_children': len(anchor_data['children']) > 0  # Flag to indicate this anchor has children
            }
            self.output_data['unique_objects'].append(anchor_object_data)
        
        return self.output_data
    
    def _create_forward_pointinstancer_data(self, ref_path, instances, prototype_data):
        """Create PointInstancer data for forward conversion"""
        # Extract transforms
        positions = []
        orientations = []
        scales = []
        
        for instance in instances:
            # Extract position from translate
            if instance['translate']:
                positions.append(instance['translate'])
            else:
                positions.append(Gf.Vec3d(0, 0, 0))
            
            # Extract orientation from rotate
            if instance['rotate']:
                # Convert rotateXYZ to quaternion
                quat = Gf.Quatd(Gf.Rotation(Gf.Vec3d(1, 0, 0), instance['rotate'][0]) * 
                               Gf.Rotation(Gf.Vec3d(0, 1, 0), instance['rotate'][1]) * 
                               Gf.Rotation(Gf.Vec3d(0, 0, 1), instance['rotate'][2]))
                orientations.append(quat)
            else:
                orientations.append(Gf.Quatd(1, 0, 0, 0))
            
            # Extract scale
            if instance['scale']:
                scales.append(instance['scale'])
            else:
                scales.append(Gf.Vec3f(1, 1, 1))
        
        # Create PointInstancer data
        instancer_name = f"{prototype_data['name']}_instancer"
        pointinstancer_data = {
            'type': 'pointinstancer',
            'name': instancer_name,
            'prototype_prim': prototype_data['prim'],
            'prototype_name': f"{prototype_data['name']}_prototype",
            'positions': positions,
            'orientations': orientations,
            'scales': scales,
            'proto_indices': [0] * len(instances),  # All instances use prototype 0
            'conversion_type': 'forward'
        }
        
        return pointinstancer_data
    
    def _convert_reverse_data(self):
        """Convert reverse conversion data"""
        # Process reverse mesh groups (create PointInstancers)
        for data_name, instances in self.unified_data['reverse_mesh_groups'].items():
            if len(instances) > 1:
                # Create PointInstancer data
                pointinstancer_data = self._create_reverse_pointinstancer_data(
                    data_name=data_name,
                    instances=instances,
                    prototype_prim=instances[0]['mesh_prim']
                )
                self.output_data['pointinstancers'].append(pointinstancer_data)
        
        # Process unique objects (anchor meshes and single instances)
        if 'unique_objects' in self.unified_data:
            for unique_obj in self.unified_data['unique_objects']:
                # Copy the unique object data as-is, but ensure proper paths
                if unique_obj['type'] == 'anchor_mesh':
                    # Anchor mesh - create as parent container
                    anchor_data = {
                        'type': 'anchor_mesh',
                        'path': unique_obj['path'],
                        'mesh_prim': unique_obj['mesh_prim'],
                        'transform': unique_obj.get('transform'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(anchor_data)
                
                elif unique_obj['type'] == 'single_instance':
                    # Individual mesh - create as single instance
                    individual_data = {
                        'type': 'single_instance',
                        'path': unique_obj['path'],
                        'mesh_prim': unique_obj['mesh_prim'],
                        'parent_path': unique_obj.get('parent_path', '/Root'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(individual_data)
    
    def _convert_existing_pointinstancer_data(self):
        """Convert existing PointInstancer data"""
        # Process existing PointInstancers
        for instancer_data in self.unified_data['pointinstancers']:
            pointinstancer_data = self._create_existing_pointinstancer_data(instancer_data)
            self.output_data['pointinstancers'].append(pointinstancer_data)
        
        # Process unique objects (anchor meshes and individual meshes)
        if 'unique_objects' in self.unified_data:
            for unique_obj in self.unified_data['unique_objects']:
                # Copy the unique object data as-is, but ensure proper paths
                if unique_obj['type'] == 'anchor_mesh':
                    # Anchor mesh - create as parent container
                    anchor_data = {
                        'type': 'anchor_mesh',
                        'path': f"/Root/{unique_obj['mesh_prim'].GetName()}",
                        'mesh_prim': unique_obj['mesh_prim'],
                        'transform': unique_obj.get('transform'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(anchor_data)
                
                elif unique_obj['type'] == 'single_instance':
                    # Individual mesh - create as single instance
                    individual_data = {
                        'type': 'single_instance',
                        'path': f"/Root/{unique_obj['mesh_prim'].GetName()}",
                        'mesh_prim': unique_obj['mesh_prim'],
                        'parent_path': unique_obj.get('parent_path', '/Root'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(individual_data)
        
        # Process base geometry (fallback for old format)
        for geom_data in self.unified_data.get('base_geometry', []):
            unique_object_data = {
                'type': 'base_geometry',
                'prim': geom_data['prim'],
                'path': f"/Root/{geom_data['prim'].GetName()}"
            }
            self.output_data['unique_objects'].append(unique_object_data)
    
    def _create_pointinstancer_data(self, name, instances, prototype_prim, conversion_type):
        """Create PointInstancer data structure"""
        # Extract transforms
        positions = []
        orientations = []
        scales = []
        
        for instance in instances:
            if conversion_type == 'reverse':
                # For reverse conversion, extract transform from transform_prim
                transform_prim = instance['transform_prim']
                if transform_prim:
                    # Get transform attributes
                    translate = transform_prim.GetAttribute("xformOp:translate")
                    rotate = transform_prim.GetAttribute("xformOp:rotateXYZ") 
                    scale = transform_prim.GetAttribute("xformOp:scale")
                    
                    # Extract position
                    if translate:
                        pos = translate.Get()
                        positions.append(Gf.Vec3f(pos) if pos else Gf.Vec3f(0, 0, 0))
                    else:
                        positions.append(Gf.Vec3f(0, 0, 0))
                    
                    # Extract rotation (convert from Euler to quaternion)
                    if rotate:
                        rot_xyz = rotate.Get()
                        if rot_xyz:
                            # Convert degrees to radians and create quaternion
                            import math
                            rx, ry, rz = [math.radians(r) for r in rot_xyz]
                            # Create quaternion from Euler angles (XYZ order)
                            qx = Gf.Quatf(math.cos(rx/2), math.sin(rx/2), 0, 0)
                            qy = Gf.Quatf(math.cos(ry/2), 0, math.sin(ry/2), 0)
                            qz = Gf.Quatf(math.cos(rz/2), 0, 0, math.sin(rz/2))
                            # Combine rotations: Z * Y * X
                            quat = qz * qy * qx
                            orientations.append(Gf.Quath(quat.GetReal(), quat.GetImaginary()[0], quat.GetImaginary()[1], quat.GetImaginary()[2]))
                        else:
                            orientations.append(Gf.Quath(1, 0, 0, 0))
                    else:
                        orientations.append(Gf.Quath(1, 0, 0, 0))
                    
                    # Extract scale
                    if scale:
                        sc = scale.Get()
                        scales.append(Gf.Vec3f(sc) if sc else Gf.Vec3f(1, 1, 1))
                    else:
                        scales.append(Gf.Vec3f(1, 1, 1))
                else:
                    # Fallback to identity transforms
                    positions.append(Gf.Vec3f(0, 0, 0))
                    orientations.append(Gf.Quath(1, 0, 0, 0))
                    scales.append(Gf.Vec3f(1, 1, 1))
            else:
                # For forward conversion, use the transform directly
                transform = instance['transform']
                positions.append(transform.ExtractTranslation())
                orientations.append(transform.ExtractRotationQuat())
                scales.append(transform.ExtractScale())
        
        return {
            'type': 'pointinstancer',
            'name': name,
            'path': f"/Root/{name}",
            'conversion_type': conversion_type,
            'prototype_prim': prototype_prim,
            'prototype_name': self._generate_clean_filename(prototype_prim.GetName()),
            'instances': instances,
            'positions': positions,
            'orientations': orientations,
            'scales': scales,
            'proto_indices': [0] * len(instances)
        }
    
    def _create_unique_object_data(self, instance, conversion_type):
        """Create unique object data structure"""
        if conversion_type == 'forward':
            return {
                'type': 'unique_object',
                'conversion_type': conversion_type,
                'prim': instance['ref_prim'],
                'path': f"/Root/{self._generate_clean_filename(instance['ref_prim'].GetName())}",
                'transform': instance['transform']
            }
        elif conversion_type == 'reverse':
            # Calculate transform from transform_prim
            transform = None
            if instance['transform_prim']:
                from pxr import Gf
                transform = Gf.Matrix4d(1.0)  # Identity matrix
                # Get the transform from the transform prim
                xformable = UsdGeom.Xformable(instance['transform_prim'])
                if xformable:
                    transform = xformable.GetLocalTransformation()
            
            return {
                'type': 'unique_object',
                'conversion_type': conversion_type,
                'mesh_prim': instance['mesh_prim'],
                'transform_prim': instance['transform_prim'],
                'transform': transform
            }
    
    def _create_reverse_pointinstancer_data(self, data_name, instances, prototype_prim):
        """Create PointInstancer data for reverse conversion"""
        # Extract transforms from transform_prim
        positions = []
        orientations = []
        scales = []
        
        for instance in instances:
            transform_prim = instance['transform_prim']
            if transform_prim:
                # Get transform attributes
                translate = transform_prim.GetAttribute("xformOp:translate")
                rotate = transform_prim.GetAttribute("xformOp:rotateXYZ") 
                scale = transform_prim.GetAttribute("xformOp:scale")
                
                # Extract position
                if translate:
                    pos = translate.Get()
                    positions.append(Gf.Vec3f(pos) if pos else Gf.Vec3f(0, 0, 0))
                else:
                    positions.append(Gf.Vec3f(0, 0, 0))
                
                # Extract rotation (convert from Euler to quaternion)
                if rotate:
                    rot_xyz = rotate.Get()
                    if rot_xyz:
                        # Convert degrees to radians and create quaternion
                        import math
                        rx, ry, rz = [math.radians(r) for r in rot_xyz]
                        # Create quaternion from Euler angles (XYZ order)
                        qx = Gf.Quatf(math.cos(rx/2), math.sin(rx/2), 0, 0)
                        qy = Gf.Quatf(math.cos(ry/2), 0, math.sin(ry/2), 0)
                        qz = Gf.Quatf(math.cos(rz/2), 0, 0, math.sin(rz/2))
                        # Combine rotations: Z * Y * X
                        quat = qz * qy * qx
                        orientations.append(Gf.Quath(quat.GetReal(), quat.GetImaginary()[0], quat.GetImaginary()[1], quat.GetImaginary()[2]))
                    else:
                        orientations.append(Gf.Quath(1, 0, 0, 0))
                else:
                    orientations.append(Gf.Quath(1, 0, 0, 0))
                
                # Extract scale
                if scale:
                    sc = scale.Get()
                    scales.append(Gf.Vec3f(sc) if sc else Gf.Vec3f(1, 1, 1))
                else:
                    scales.append(Gf.Vec3f(1, 1, 1))
            else:
                # Fallback to identity transforms
                positions.append(Gf.Vec3f(0, 0, 0))
                orientations.append(Gf.Quath(1, 0, 0, 0))
                scales.append(Gf.Vec3f(1, 1, 1))
        
        # Create PointInstancer data
        clean_name = self._generate_clean_filename(data_name)
        pointinstancer_data = {
            'type': 'pointinstancer',
            'name': f"{clean_name}_instancer",
            'path': f"/Root/{clean_name}_instancer",
            'prototype_mesh': prototype_prim,
            'prototype_name': clean_name,
            'positions': positions,
            'orientations': orientations,
            'scales': scales,
            'proto_indices': [0] * len(instances),
            'conversion_type': 'reverse'
        }
        
        return pointinstancer_data
    
    def _create_existing_pointinstancer_data(self, instancer_data):
        """Create existing PointInstancer data structure"""
        return {
            'type': 'existing_pointinstancer',
            'name': instancer_data['name'],
            'path': f"/Root/{instancer_data['name']}",
            'prim': instancer_data['prim'],
            'prototype_prim': instancer_data.get('prototype_prim'),
            'prototype_name': self._generate_clean_filename(instancer_data.get('prototype_prim', instancer_data['prim']).GetName()) if instancer_data.get('prototype_prim') else None
        }
    
    def prepare_external_prototypes(self, use_external_references):
        """Prepare external prototype data if needed"""
        if not use_external_references:
            return
        
        self.output_data['external_prototypes'] = []
        
        for pointinstancer_data in self.output_data['pointinstancers']:
            # Handle both prototype_prim and prototype_mesh keys
            prototype_prim = pointinstancer_data.get('prototype_prim') or pointinstancer_data.get('prototype_mesh')
            if prototype_prim:
                # Generate prototype name if not available
                prototype_name = pointinstancer_data.get('prototype_name')
                if not prototype_name:
                    prototype_name = self._generate_clean_filename(prototype_prim.GetName())
                
                external_prototype_data = {
                    'name': prototype_name,
                    'prim': prototype_prim,
                    'materials': self.output_data['materials'],  # Use converted materials
                    'reference_path': f"Instance_Objs/{prototype_name}.usd"
                }
                self.output_data['external_prototypes'].append(external_prototype_data)
    
    def _generate_clean_filename(self, name):
        """Generate clean filename from name"""
        # Remove special characters and spaces
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Remove multiple underscores
        clean_name = re.sub(r'_+', '_', clean_name)
        # Remove leading/trailing underscores
        clean_name = clean_name.strip('_')
        return clean_name
