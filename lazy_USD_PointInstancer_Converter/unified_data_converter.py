#!/usr/bin/env python3
"""
Unified Data Converter for USD PointInstancer Converter
Prepares all data for output generation - transforms collected data into output-ready format
"""

import os
import re
import time
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

# Import material conversion modules with standardized names
try:
    from principled_bsdf_mapping import parse_material as parse_principled_bsdf, convert_to_remix as convert_principled_to_remix
    from omnipbr_mapping import convert_to_remix as convert_omnipbr_to_remix
    from omnipbr_converter import parse_omnipbr_mdl
    MATERIAL_CONVERSION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Material conversion modules not available: {e}")
    MATERIAL_CONVERSION_AVAILABLE = False
    def parse_principled_bsdf(prim): return None
    def convert_principled_to_remix(params): return None
    def convert_omnipbr_to_remix(params): return None
    def parse_omnipbr_mdl(path): return None
    def _is_already_remix_material(prim): return False

class UnifiedDataConverter:
    """Converts collected data into output-ready format"""
    
    def __init__(self, unified_data, use_external_references=False):
        self.unified_data = unified_data
        self.use_external_references = use_external_references
        self.output_data = {}
        
        # Material conversion settings - ENABLE by default for texture conversion
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
            'input_type': self.unified_data['input_type'],  # Preserve input type for operation reporting
            'prototype_meshes': self.unified_data.get('prototype_meshes', {})  # Pass through face counts
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
        material_type_counts = {'principled_bsdf': 0, 'omnipbr': 0, 'already_remix': 0, 'unknown': 0}
        
        for material_name, material_info in self.unified_data['materials'].items():
            material_prim = material_info['prim']
            
            # Check if material was already converted by collector (has conversion_type)
            if 'conversion_type' in material_info:
                # Material was already converted by collector
                conversion_type = material_info['conversion_type']
                material_type_counts[conversion_type] += 1
                print(f"MATERIAL Converted '{material_name}' from {conversion_type.upper()} to Remix")
                converted_materials[material_name] = material_info
                continue
            
            # Check if already marked as Remix in collector (original Remix material)
            if material_info.get('is_remix'):
                material_type_counts['already_remix'] += 1
                print(f"MATERIAL '{material_name}' is already Remix (AperturePBR_Opacity)")
                converted_materials[material_name] = material_info
                continue
            
            # Convert material to Remix format
            conversion_type, remix_params = self._detect_and_parse_material(material_prim)
            
            if conversion_type == 'already_remix':
                material_type_counts['already_remix'] += 1
                print(f"MATERIAL '{material_name}' is already Remix (AperturePBR_Opacity)")
                # Keep as-is, already Remix
                material_info['is_remix'] = True
                material_info['conversion_type'] = 'already_remix'
                converted_materials[material_name] = material_info
            elif conversion_type and remix_params:
                material_type_counts[conversion_type] += 1
                print(f"MATERIAL Converted '{material_name}' from {conversion_type.upper()} to Remix")
                # Create Remix material structure
                remix_material_info = {
                    'prim': material_prim,
                    'path': material_info.get('path', str(material_prim.GetPath())),
                    'conversion_type': conversion_type,
                    'remix_params': remix_params,
                    'is_remix': True
                }
                converted_materials[material_name] = remix_material_info
            else:
                material_type_counts['unknown'] += 1
                print(f"MATERIAL Creating empty Remix material for '{material_name}' (unknown type - user can add textures manually)")
                # Create empty Remix material for unknown types so user can add textures manually
                empty_remix_params = {
                    '_original_params': set()  # Empty params - no defaults
                }
                remix_material_info = {
                    'prim': material_prim,
                    'path': material_info.get('path', str(material_prim.GetPath())),
                    'conversion_type': 'unknown',
                    'remix_params': empty_remix_params,
                    'is_remix': True
                }
                converted_materials[material_name] = remix_material_info
        
        # Print summary
        if any(material_type_counts.values()):
            print(f"MATERIAL Summary: PrincipledBSDF/UsdPreviewSurface={material_type_counts['principled_bsdf']}, "
                  f"OmniPBR={material_type_counts['omnipbr']}, "
                  f"AlreadyRemix={material_type_counts['already_remix']}, "
                  f"Unknown={material_type_counts['unknown']}")
        
        self.output_data['materials'] = converted_materials
    
    def _detect_and_parse_material(self, material_prim):
        """
        Detect material type and parse parameters using standardized functions
        Priority: Already Remix > Principled_BSDF/UsdPreviewSurface > OmniPBR
        
        Args:
            material_prim: Source material prim
            
        Returns:
            tuple: (conversion_type, remix_params) or (None, None) if no conversion possible
        """
        material_name = material_prim.GetName()
        
        # Priority 0: Check if already Remix material (AperturePBR_Opacity)
        if self._is_already_remix_material(material_prim):
            return "already_remix", None
        
        # Priority 1: Check for Principled_BSDF/UsdPreviewSurface (merged)
        if self.enable_principled_bsdf_conversion:
            try:
                principled_params = parse_principled_bsdf(material_prim)
                if principled_params:
                    remix_params = convert_principled_to_remix(principled_params)
                    if remix_params:
                        return "principled_bsdf", remix_params
            except Exception as e:
                pass
        
        # Priority 2: Check for OmniPBR
        if self.enable_omnipbr_conversion:
            try:
                from omnipbr_converter import parse_omnipbr_material
                omnipbr_params = parse_omnipbr_material(material_prim)
                if omnipbr_params:
                    remix_params = convert_omnipbr_to_remix(omnipbr_params)
                    if remix_params:
                        return "omnipbr", remix_params
            except Exception as e:
                pass
        
        return None, None
    
    def _is_already_remix_material(self, material_prim):
        """Check if material is already a Remix material (AperturePBR_Opacity)"""
        try:
            # Check if material has reference to AperturePBR_Opacity
            refs = material_prim.GetReferences()
            if refs:
                for ref in refs.GetAddedOrExplicitItems():
                    ref_path = str(ref.assetPath)
                    if 'AperturePBR_Opacity' in ref_path:
                        return True
        except:
            pass
        return False
    
    def _convert_forward_data(self):
        """Convert forward conversion data for output generation"""
        # Update output data (don't overwrite prototype_meshes)
        self.output_data['unique_objects'] = []
        self.output_data['pointinstancers'] = []
        self.output_data['external_prototypes'] = []
        
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
                # Skip if prototype has no mesh (empty prototype or nested PointInstancer)
                if ref_path not in self.unified_data['prototype_meshes']:
                    if len(instances) > 5:  # Only log if significant number
                        print(f"CONVERT Skipping {len(instances)} instances of {ref_path} (no mesh - possible blank anchor mesh)")
                    continue
                
                if len(instances) > 1:
                    # Multiple instances - create PointInstancer
                    # Use blender_name from first instance if available
                    blender_name = instances[0].get('blender_name')
                    if blender_name:
                        pi_name = self._generate_clean_filename(blender_name)
                    else:
                        pi_name = f"PointInstancer_{len(self.output_data['pointinstancers'])}"
                    
                    pointinstancer_data = {
                        'type': 'pointinstancer',
                        'path': f"/RootNode/{anchor_name}/{pi_name}",
                        'name': pi_name,
                        'blender_name': blender_name,  # Store for reporting
                        'prototype_mesh': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'],
                        'prototype_name': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'].GetName(),
                        'instances': instances,
                        'parent_anchor': anchor_data,  # Store parent anchor information
                        'parent_path': f"/RootNode/{anchor_name}"  # Path where this PointInstancer should be created
                    }
                    self.output_data['pointinstancers'].append(pointinstancer_data)
                else:
                    # Single instance - create as unique object
                    single_instance_data = {
                        'type': 'single_instance',
                        'path': f"/RootNode/{anchor_name}/{instances[0]['blender_name'] or 'SingleInstance'}",
                        'mesh_prim': self.unified_data['prototype_meshes'][ref_path]['mesh_prim'],
                        'translate': instances[0]['translate'],
                        'rotate': instances[0]['rotate'],
                        'scale': instances[0]['scale'],
                        'material_binding': self.unified_data['prototype_meshes'][ref_path]['material_binding'],
                        'parent_anchor': anchor_data,  # Store parent anchor information
                        'parent_path': f"/RootNode/{anchor_name}"  # Path where this single instance should be created
                    }
                    self.output_data['unique_objects'].append(single_instance_data)
            
            # Add the anchor mesh itself as a unique object (skip virtual root)
            if not anchor_data.get('is_virtual_root', False) and anchor_data['mesh_prim'] is not None:
                anchor_object_data = {
                    'type': 'anchor_mesh',
                    'path': f"/RootNode/{anchor_name}",
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
                # Get parent name from parent_objects
                parent_name = self.unified_data.get('parent_objects', {}).get(data_name, 'Root')
                parent_path = f"/RootNode/{parent_name}" if parent_name != 'RootNode' else "/RootNode"
                
                # Create PointInstancer data
                pointinstancer_data = self._create_reverse_pointinstancer_data(
                    data_name=data_name,
                    instances=instances,
                    prototype_prim=instances[0]['mesh_prim'],
                    parent_path=parent_path
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
                        'parent_path': unique_obj.get('parent_path', '/RootNode'),
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
                        'path': f"/RootNode/{unique_obj['mesh_prim'].GetName()}",
                        'mesh_prim': unique_obj['mesh_prim'],
                        'transform': unique_obj.get('transform'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(anchor_data)
                
                elif unique_obj['type'] == 'single_instance':
                    # Individual mesh - create as single instance
                    individual_data = {
                        'type': 'single_instance',
                        'path': f"/RootNode/{unique_obj['mesh_prim'].GetName()}",
                        'mesh_prim': unique_obj['mesh_prim'],
                        'parent_path': unique_obj.get('parent_path', '/RootNode'),
                        'material_binding': unique_obj.get('material_binding')
                    }
                    self.output_data['unique_objects'].append(individual_data)
        
        # Process base geometry (fallback for old format)
        for geom_data in self.unified_data.get('base_geometry', []):
            unique_object_data = {
                'type': 'base_geometry',
                'prim': geom_data['prim'],
                'path': f"/RootNode/{geom_data['prim'].GetName()}"
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
            'path': f"/RootNode/{name}",
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
                'path': f"/RootNode/{self._generate_clean_filename(instance['ref_prim'].GetName())}",
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
    
    def _create_reverse_pointinstancer_data(self, data_name, instances, prototype_prim, parent_path='/RootNode'):
        """Create PointInstancer data for reverse conversion"""
        # Get blenderName:object from first instance if available (for external file naming)
        blender_name = None
        if instances and instances[0].get('transform_prim'):
            blender_name_attr = instances[0]['transform_prim'].GetAttribute('blenderName:object')
            if blender_name_attr and blender_name_attr.HasValue():
                blender_name = blender_name_attr.Get()
        
        # Get parent anchor transform to convert world space to local space
        parent_transform = Gf.Matrix4d(1.0)  # Identity by default
        if parent_path != '/RootNode':
            # Extract parent prim from path
            parent_prim = instances[0]['transform_prim'].GetStage().GetPrimAtPath(parent_path)
            if parent_prim and parent_prim.IsValid():
                parent_xformable = UsdGeom.Xformable(parent_prim)
                parent_transform = parent_xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        
        # Extract transforms from transform_prim
        positions = []
        orientations = []
        scales = []
        
        # Skip first instance if it's at origin (likely base prototype reference)
        instance_count = 0
        for instance in instances:
            instance_count += 1
            transform_prim = instance['transform_prim']
            
            # Skip the first instance if it's at origin (0,0,0)
            if instance_count == 1 and transform_prim:
                xformable = UsdGeom.Xformable(transform_prim)
                transform_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                if transform_matrix:
                    position = transform_matrix.ExtractTranslation()
                    if abs(position[0]) < 0.001 and abs(position[1]) < 0.001 and abs(position[2]) < 0.001:
                        print(f"FILTER: Skipping first instance of {data_name} at origin (likely base prototype reference)")
                        continue
            if transform_prim:
                # Use LOCAL transform (relative to parent anchor)
                xformable = UsdGeom.Xformable(transform_prim)
                local_transform = xformable.GetLocalTransformation()
                
                if local_transform:
                    # Extract position (already in local space)
                    position = local_transform.ExtractTranslation()
                    positions.append(Gf.Vec3f(position[0], position[1], position[2]))
                    
                    # Extract rotation
                    rotation_matrix = local_transform.RemoveScaleShear()
                    orientation = rotation_matrix.ExtractRotation().GetQuat()
                    orientations.append(Gf.Quath(orientation.GetReal(), orientation.GetImaginary()[0], orientation.GetImaginary()[1], orientation.GetImaginary()[2]))
                    
                    # Extract scale
                    scale_x = Gf.Vec3d(local_transform[0][0], local_transform[1][0], local_transform[2][0]).GetLength()
                    scale_y = Gf.Vec3d(local_transform[0][1], local_transform[1][1], local_transform[2][1]).GetLength()
                    scale_z = Gf.Vec3d(local_transform[0][2], local_transform[1][2], local_transform[2][2]).GetLength()
                    scale = Gf.Vec3f(scale_x, scale_y, scale_z)
                    scales.append(scale)
                else:
                    # Fallback to identity transforms
                    positions.append(Gf.Vec3f(0, 0, 0))
                    orientations.append(Gf.Quath(1, 0, 0, 0))
                    scales.append(Gf.Vec3f(1, 1, 1))
            else:
                # Fallback to identity transforms
                positions.append(Gf.Vec3f(0, 0, 0))
                orientations.append(Gf.Quath(1, 0, 0, 0))
                scales.append(Gf.Vec3f(1, 1, 1))
        
        # Create PointInstancer data
        # Use blenderName:object if available, otherwise fall back to data_name
        clean_name = self._generate_clean_filename(blender_name if blender_name else data_name)
        if not clean_name:  # Fallback if name is empty
            clean_name = "Mesh"
        
        # Get face count from prototype mesh
        face_count = 0
        try:
            mesh = UsdGeom.Mesh(prototype_prim)
            face_counts_attr = mesh.GetFaceVertexCountsAttr().Get()
            if face_counts_attr:
                face_count = len(face_counts_attr)
        except:
            pass
        
        pointinstancer_data = {
            'type': 'pointinstancer',
            'name': f"{clean_name}_instancer",
            'path': f"{parent_path}/{clean_name}_instancer",
            'prototype_mesh': prototype_prim,
            'prototype_name': clean_name,
            'blender_name': blender_name,  # Store for external file naming
            'face_count': face_count,  # Store face count for reporting
            'positions': positions,
            'orientations': orientations,
            'scales': scales,
            'proto_indices': [0] * len(instances),
            'conversion_type': 'reverse',
            'parent_path': parent_path
        }
        
        return pointinstancer_data
    
    def _create_existing_pointinstancer_data(self, instancer_data):
        """Create existing PointInstancer data structure"""
        return {
            'type': 'existing_pointinstancer',
            'name': instancer_data['name'],
            'path': f"/RootNode/{instancer_data['name']}",
            'prim': instancer_data['prim'],
            'prototype_prim': instancer_data.get('prototype_prim'),
            'prototype_name': self._generate_clean_filename(instancer_data.get('prototype_prim', instancer_data['prim']).GetName()) if instancer_data.get('prototype_prim') else None,
            'preserve_parent': instancer_data.get('preserve_parent', False),
            'parent_path': instancer_data.get('parent_path', '/RootNode'),
            'prototype_face_counts': instancer_data.get('prototype_face_counts', {})  # Pass through face counts
        }
    
    def prepare_external_prototypes(self, use_external_references):
        """Prepare external prototype data if needed"""
        if not use_external_references:
            return
        
        self.output_data['external_prototypes'] = []
        
        for pointinstancer_data in self.output_data['pointinstancers']:
            # For Blender 4.5 PointInstancers, extract ALL prototypes from the source
            if pointinstancer_data.get('type') == 'existing_pointinstancer':
                source_prim = pointinstancer_data.get('prim')
                if source_prim and source_prim.IsA(UsdGeom.PointInstancer):
                    # Get all prototype targets from the PointInstancer
                    pi = UsdGeom.PointInstancer(source_prim)
                    proto_rel = pi.GetPrototypesRel()
                    if proto_rel:
                        proto_targets = proto_rel.GetTargets()
                        for proto_path in proto_targets:
                            proto_prim = source_prim.GetStage().GetPrimAtPath(proto_path)
                            if proto_prim and proto_prim.IsValid():
                                # Find the actual mesh inside the prototype container (recursively)
                                mesh_prim = None
                                if proto_prim.IsA(UsdGeom.Mesh):
                                    mesh_prim = proto_prim
                                else:
                                    # Recursively look for mesh children (handles Xform wrappers)
                                    def find_mesh_recursive(prim):
                                        for child in prim.GetAllChildren():
                                            if child.IsA(UsdGeom.Mesh):
                                                return child
                                            # Recursively search Xform children
                                            if child.IsA(UsdGeom.Xform):
                                                result = find_mesh_recursive(child)
                                                if result:
                                                    return result
                                        return None
                                    
                                    mesh_prim = find_mesh_recursive(proto_prim)
                                
                                if mesh_prim:
                                    prototype_name = self._generate_clean_filename(mesh_prim.GetName())
                                    # Get only materials used by this mesh
                                    mesh_materials = self._get_materials_for_prim(mesh_prim)
                                    # Get face count from PointInstancer's prototype_face_counts (Blender 4.5.4)
                                    face_count = 0
                                    if 'prototype_face_counts' in pointinstancer_data:
                                        mesh_name = mesh_prim.GetName()
                                        face_count = pointinstancer_data['prototype_face_counts'].get(mesh_name, 0)
                                    # Fallback: check prototype_meshes
                                    if face_count == 0:
                                        for ref_path, proto_data in self.unified_data.get('prototype_meshes', {}).items():
                                            if proto_data['mesh_prim'].GetName() == mesh_prim.GetName():
                                                face_count = proto_data.get('face_count', 0)
                                                break
                                    # Get transform from prototype container (proto_prim, not mesh_prim)
                                    proto_transform = None
                                    try:
                                        xformable = UsdGeom.Xformable(proto_prim)
                                        proto_transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                                    except:
                                        pass
                                    external_prototype_data = {
                                        'name': prototype_name,
                                        'prim': mesh_prim,
                                        'materials': mesh_materials,
                                        'reference_path': f"Instance_Objs/{prototype_name}.usd",
                                        'face_count': face_count,
                                        'transform': proto_transform
                                    }
                                    self.output_data['external_prototypes'].append(external_prototype_data)
            else:
                # Handle both prototype_prim and prototype_mesh keys for other types
                prototype_prim = pointinstancer_data.get('prototype_prim') or pointinstancer_data.get('prototype_mesh')
                if prototype_prim:
                    # Use blender_name if available, otherwise use prototype_name
                    blender_name = pointinstancer_data.get('blender_name')
                    if blender_name:
                        prototype_name = self._generate_clean_filename(blender_name)
                    else:
                        prototype_name = pointinstancer_data.get('prototype_name')
                        if not prototype_name:
                            prototype_name = self._generate_clean_filename(prototype_prim.GetName())
                    
                    # Skip if already added (avoid duplicates)
                    if any(ep['name'] == prototype_name for ep in self.output_data['external_prototypes']):
                        continue
                    
                    # Get only materials used by this mesh
                    mesh_materials = self._get_materials_for_prim(prototype_prim)
                    # Get face count from prototype_meshes if available
                    face_count = 0
                    for ref_path, proto_data in self.unified_data.get('prototype_meshes', {}).items():
                        if proto_data['mesh_prim'].GetName() == prototype_prim.GetName():
                            face_count = proto_data.get('face_count', 0)
                            break
                    external_prototype_data = {
                        'name': prototype_name,
                        'prim': prototype_prim,
                        'materials': mesh_materials,
                        'reference_path': f"Instance_Objs/{prototype_name}.usd",
                        'face_count': face_count
                    }
                    self.output_data['external_prototypes'].append(external_prototype_data)
    
    def _get_materials_for_prim(self, prim):
        """Get only the materials used by this prim and its children (including GeomSubsets)"""
        used_materials = {}
        
        # Traverse prim and all children to find material bindings
        for p in Usd.PrimRange(prim):
            # Check for material:binding relationship on mesh and GeomSubsets
            mat_binding_rel = p.GetRelationship('material:binding')
            if mat_binding_rel:
                targets = mat_binding_rel.GetTargets()
                for target in targets:
                    # Extract material name from path
                    target_str = str(target)
                    material_name = None
                    if '/_materials/' in target_str:
                        material_name = target_str.split('/_materials/')[-1]
                    elif '/Looks/' in target_str:
                        material_name = target_str.split('/Looks/')[-1]
                    elif '/materials/' in target_str:
                        material_name = target_str.split('/materials/')[-1]
                    elif '/root/Looks/' in target_str:
                        material_name = target_str.split('/root/Looks/')[-1]
                    elif '/Root/Looks/' in target_str:
                        material_name = target_str.split('/Root/Looks/')[-1]
                    
                    # Add material if found in output_data
                    if material_name and material_name in self.output_data['materials']:
                        if material_name not in used_materials:
                            used_materials[material_name] = self.output_data['materials'][material_name]
        
        return used_materials
    
    def _generate_clean_filename(self, name):
        """Generate clean filename from name"""
        if not name:
            return "Mesh"
        # Remove special characters and spaces
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        # Remove multiple underscores
        clean_name = re.sub(r'_+', '_', clean_name)
        # Remove leading/trailing underscores
        clean_name = clean_name.strip('_')
        # Fallback if empty after cleaning
        if not clean_name:
            clean_name = "Mesh"
        # USD paths cannot start with a number - prefix with underscore
        if clean_name[0].isdigit():
            clean_name = f"_{clean_name}"
        return clean_name
