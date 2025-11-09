#!/usr/bin/env python3
"""
Unified Data Collector for USD PointInstancer Converter
Handles data collection for all conversion types (forward, reverse, existing PointInstancer)
"""

import os
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

class UnifiedDataCollector:
    """Unified data collection for all conversion modes"""
    
    def __init__(self, stage, input_type):
        self.stage = stage
        self.input_type = input_type
        self.unified_data = {}
        
    def collect_data(self):
        """Main data collection method"""
        print(f"COLLECT Collecting unified data for {self.input_type} conversion...")
        
        # Initialize data structure
        self.unified_data = {
            'prims': [],
            'materials': {},
            'pointinstancers': [],
            'base_geometry': [],
            'material_bindings': {},
            'stage_metadata': {},
            'root_path': "/Root",
            'input_type': self.input_type
        }
        
        # Collect stage metadata
        self._collect_stage_metadata()
        
        # Collect based on input type
        if self.input_type == 'forward_instanceable':
            self._collect_forward_data()
        elif self.input_type == 'reverse':
            self._collect_reverse_data()
        elif self.input_type in ['existing_pointinstancer', 'blender45_pointinstancer']:
            self._collect_existing_pointinstancer_data()
        else:
            print(f"ERROR Unknown input type: {self.input_type}")
            return False
        
        # Standardize material paths
        self._standardize_material_paths()
        
        print(f"COLLECT Collected {len(self.unified_data['prims'])} prims, {len(self.unified_data['materials'])} materials")
        return True
    
    def _collect_stage_metadata(self):
        """Collect stage metadata"""
        self.unified_data['stage_metadata'] = {
            'upAxis': self.stage.GetMetadata('upAxis') if self.stage.GetMetadata('upAxis') else 'Z',
            'defaultPrim': self.stage.GetDefaultPrim().GetName() if self.stage.GetDefaultPrim() else 'Root'
        }
    
    def _collect_forward_data(self):
        """Collect data for forward conversion (instanceable references → PointInstancer)"""
        print("COLLECT Forward conversion: Collecting instanceable references")
        
        data = {
            'prims': [],
            'materials': {},
            'instanceable_references': {},
            'all_meshes': [],
            'anchor_meshes': [],  # Non-instanceable meshes with their children
            'prototype_meshes': {}  # Prototype meshes by reference path
        }
        
        # First pass: collect ALL meshes and materials, and identify anchor meshes
        for prim in self.stage.TraverseAll():
            prim_path = str(prim.GetPath())
            prim_type = prim.GetTypeName()
            
            # Collect materials
            if prim.IsA(UsdShade.Material):
                material_name = prim.GetName()
                # Only collect materials from the main materials scope, not from prototypes
                if '/_materials/' in prim_path or '/root/_materials/' in prim_path:
                    # Only add if not already collected (prioritize main materials scope)
                    if material_name not in data['materials']:
                        data['materials'][material_name] = {
                            'prim': prim,
                            'path': prim_path,
                            'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                        }
                        print(f"COLLECT Collected material: {material_name} from {prim_path}")
                    else:
                        print(f"COLLECT Material {material_name} already collected from main scope")
                else:
                    print(f"COLLECT Skipped prototype material: {material_name} from {prim_path}")
            
            # Collect meshes
            if prim.IsA(UsdGeom.Mesh):
                mesh_data = {
                    'mesh_prim': prim,
                    'path': prim_path,
                    'transform': self._get_world_transform(prim),
                    'material_binding': self._get_material_binding(prim),
                    'parent': prim.GetParent(),
                    'parent_path': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                }
                data['all_meshes'].append(mesh_data)
        
        # Second pass: collect instanceable references and identify parent containers
        print("COLLECT Forward conversion: Looking for instanceable Xforms with references")
        instanceable_count = 0
        parent_containers = set()  # Track which containers actually have instanceable children
        
        # Use the working approach from unified_instancer_converter.py
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.Xform):
                # Check if this Xform is instanceable using multiple methods
                if self._is_instanceable(prim):
                    # Check if this Xform has references
                    if prim.GetReferences():
                        instanceable_count += 1
                        prim_path = str(prim.GetPath())
                        
                        # Extract transform data
                        translate = self._get_translate(prim)
                        rotate = self._get_rotate(prim)
                        scale = self._get_scale(prim)
                        
                        # Store the full transform matrix for proper PointInstancer extraction
                        transform_matrix = self._get_world_transform(prim)
                        
                        # Filter out instances that are at or very close to absolute world coordinates 0,0,0 (likely base prototype references)
                        if transform_matrix:
                            world_translation = transform_matrix.ExtractTranslation()
                            # Check if the instance is at or very close to absolute world coordinates 0,0,0 (within 1.0 units)
                            is_at_world_origin = abs(world_translation[0]) < 1.0 and abs(world_translation[1]) < 1.0 and abs(world_translation[2]) < 1.0
                            if is_at_world_origin:
                                print(f"FILTER: Excluding world-origin instance {prim.GetName()} at {world_translation} (likely base prototype)")
                                continue
                        
                        # Extract reference path
                        ref_path = self._extract_reference_path(prim)
                        if not ref_path:
                            print(f"WARNING: Could not extract reference path for {prim_path}")
                            continue
                        
                        # Get blender object name if available
                        blender_name = None
                        blender_name_attr = prim.GetAttribute('userProperties:blender:object_name')
                        if blender_name_attr and blender_name_attr.HasValue():
                            blender_name = blender_name_attr.Get()
                        
                        # Store instanceable reference data
                        if ref_path not in data['instanceable_references']:
                            data['instanceable_references'][ref_path] = []
                        
                        instance_data = {
                            'prim': prim,
                            'path': prim_path,
                            'reference_path': ref_path,
                            'translate': translate,
                            'rotate': rotate,
                            'scale': scale,
                            'transform': transform_matrix,  # Store full transform matrix
                            'blender_name': blender_name,
                            'parent': prim.GetParent(),
                            'parent_path': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                        }
                        
                        data['instanceable_references'][ref_path].append(instance_data)
                        
                        # Track the parent container that has instanceable children
                        parent_prim = prim.GetParent()
                        if parent_prim:
                            parent_containers.add(parent_prim)
                        
                        # Store prototype mesh if not already stored
                        if ref_path not in data['prototype_meshes']:
                            # Try to get the prototype prim
                            prototype_prim = self.stage.GetPrimAtPath(ref_path)
                            if prototype_prim:
                                # Try to access the mesh child directly using known paths
                                mesh_prim = None
                                
                                # Try different possible mesh child names based on our debug findings
                                possible_mesh_names = ['Plane_007', 'Plane_001', 'Plane_006']
                                for mesh_name in possible_mesh_names:
                                    mesh_path = f"{ref_path}/{mesh_name}"
                                    mesh_prim = self.stage.GetPrimAtPath(mesh_path)
                                    if mesh_prim and mesh_prim.IsA(UsdGeom.Mesh):
                                        pass
                                        break
                                
                                if mesh_prim:
                                    data['prototype_meshes'][ref_path] = {
                                        'mesh_prim': mesh_prim,
                                        'path': str(mesh_prim.GetPath()),
                                        'material_binding': self._get_material_binding(mesh_prim)
                                    }
                                    pass
                                    
                                    # Also collect materials from prototype references
                                    self._collect_materials_from_prototype(mesh_prim, data)
                                else:
                                    pass
        
        # Third pass: create anchor data only for containers that have instanceable children
        for parent_container in parent_containers:
            # Find the mesh child of this container
            mesh_child = None
            for child in parent_container.GetAllChildren():
                if child.IsA(UsdGeom.Mesh):
                    mesh_child = child
                    break
            
            if mesh_child:
                anchor_data = {
                    'container_prim': parent_container,  # The Xform container
                    'container_path': str(parent_container.GetPath()),
                    'mesh_prim': mesh_child,  # The actual mesh
                    'path': str(mesh_child.GetPath()),
                    'transform': self._get_world_transform(mesh_child),
                    'material_binding': self._get_material_binding(mesh_child),
                    'parent': mesh_child.GetParent(),
                    'parent_path': str(mesh_child.GetParent().GetPath()) if mesh_child.GetParent() else None,
                    'children': [],  # Will store instanceable references that are children of this container
                    'nested_pointinstancers': []  # Will store PointInstancers that should be nested under this container
                }
                data['anchor_meshes'].append(anchor_data)
        
        # Fourth pass: associate instanceable references with their parent containers
        for ref_path, instances in data['instanceable_references'].items():
            for instance_data in instances:
                parent_prim = instance_data['parent']
                if parent_prim:
                    # Find the anchor container that contains this instance
                    for anchor_data in data['anchor_meshes']:
                        if anchor_data['container_prim'] == parent_prim:
                            anchor_data['children'].append(instance_data)
                            break
        
        print(f"COLLECT Forward conversion: Found {instanceable_count} instanceable Xforms")
        print(f"COLLECT Forward conversion: Found {len(data['instanceable_references'])} unique prototype references")
        print(f"COLLECT Forward conversion: Found {len(data['anchor_meshes'])} anchor meshes")
        
        # Report parent-child relationships
        for anchor_data in data['anchor_meshes']:
            print(f"  📁 Anchor container {anchor_data['container_prim'].GetName()}: {len(anchor_data['children'])} child instances")
        
        # Update the unified_data with the forward conversion data
        self.unified_data.update(data)
        
        return True
    
    def _is_instanceable(self, prim):
        """Check if a prim is instanceable using multiple methods (from unified_instancer_converter.py)"""
        # Method 1: Check IsInstance()
        if prim.IsInstance():
            return True
            
        # Method 2: Check instanceable metadata directly
        try:
            if prim.GetMetadata('instanceable'):
                return True
        except:
            pass
            
        # Method 3: Check for references to prototypes
        try:
            # Access references through layer prim spec
            layer = self.stage.GetRootLayer()
            prim_spec = layer.GetPrimAtPath(prim.GetPath())
            ref_list = []
            
            if prim_spec and hasattr(prim_spec, 'referenceList'):
                ref_list = prim_spec.referenceList.GetAddedOrExplicitItems()
            elif prim_spec and hasattr(prim_spec, 'references'):
                ref_list = prim_spec.references.GetAddedOrExplicitItems()
                
            if ref_list:
                for ref in ref_list:
                    if '/prototypes/' in str(ref.assetPath) or '/prototypes/' in str(ref.primPath):
                        return True
        except:
            pass
            
        return False
    
    def _collect_materials_from_prototype(self, prototype_prim, data):
        """Collect materials from prototype references to ensure all materials are captured"""
        try:
            # Traverse the prototype to find materials
            for prim in prototype_prim.GetStage().TraverseAll():
                if prim.IsA(UsdShade.Material):
                    material_name = prim.GetName()
                    prim_path = str(prim.GetPath())
                    
                    # Only add if not already collected and only from main materials scope
                    if material_name not in data['materials'] and ('/_materials/' in prim_path or '/root/_materials/' in prim_path):
                        data['materials'][material_name] = {
                            'prim': prim,
                            'path': prim_path,
                            'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                        }
                        print(f"COLLECT Collected material from prototype: {material_name} from {prim_path}")
                    elif material_name not in data['materials']:
                        print(f"COLLECT Skipped prototype material: {material_name} from {prim_path}")
        except Exception as e:
            print(f"WARNING Could not collect materials from prototype: {e}")
    
    def _collect_reverse_data(self):
        """Collect data for reverse conversion (individual objects → PointInstancer)"""
        print("COLLECT Reverse conversion: Collecting individual objects with blender:data_name")
        
        # Track mesh groups by blender:data_name and hash
        self.unified_data['reverse_mesh_groups'] = {}
        self.unified_data['parent_objects'] = {}
        self.unified_data['unique_objects'] = []  # For anchor meshes and single instances
        
        # First pass: collect all meshes with blender:data_name and calculate hashes
        mesh_candidates = []
        
        for prim in self.stage.TraverseAll():
            prim_path = str(prim.GetPath())
            prim_type = prim.GetTypeName()
            
            # Collect all prims
            self.unified_data['prims'].append({
                'path': prim_path,
                'prim': prim,
                'type': prim_type,
                'parent': str(prim.GetParent().GetPath()) if prim.GetParent() else None
            })
            
            # Collect materials
            if prim_type == "Material":
                material_name = prim.GetName()
                self.unified_data['materials'][material_name] = {
                    'prim': prim,
                    'path': prim_path,
                    'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                }
            
            # Collect meshes with blender:data_name
            if prim.IsA(UsdGeom.Mesh):
                data_name_attr = prim.GetAttribute("userProperties:blender:data_name")
                if data_name_attr:
                    data_name = data_name_attr.Get()
                    if data_name:
                        # Calculate mesh hash for comparison
                        mesh_hash = self._calculate_mesh_hash(prim)
                        
                        # Get parent and root parent info
                        parent = prim.GetParent()
                        root_parent = parent.GetParent() if parent else None
                        root_parent_name = root_parent.GetName() if root_parent else "root"
                        
                        # Store mesh candidate
                        mesh_data = {
                            'mesh_prim': prim,
                            'transform_prim': parent,
                            'root_parent': root_parent,
                            'root_parent_name': root_parent_name,
                            'path': prim_path,
                            'transform_path': str(parent.GetPath()) if parent else None,
                            'data_name': data_name,
                            'mesh_hash': mesh_hash
                        }
                        
                        mesh_candidates.append(mesh_data)
                        
                        # Track parent objects
                        if data_name not in self.unified_data['parent_objects']:
                            self.unified_data['parent_objects'][data_name] = root_parent_name
                        
                        # Track materials
                        material_binding = self._get_material_binding(prim)
                        if material_binding:
                            self.unified_data['material_bindings'][prim_path] = material_binding
            
            # Collect base geometry (non-grouped meshes)
            elif prim.IsA(UsdGeom.Mesh):
                is_instanced = self._is_mesh_instanced(prim)
                if not is_instanced:
                    self.unified_data['base_geometry'].append({
                        'prim': prim,
                        'path': prim_path,
                        'parent': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                    })
        
        # Second pass: group by data_name and hash
        from collections import defaultdict
        hash_groups = defaultdict(list)
        
        for mesh_data in mesh_candidates:
            data_name = mesh_data['data_name']
            mesh_hash = mesh_data['mesh_hash']
            
            if mesh_hash:  # Only group if we have a valid hash
                group_key = f"{data_name}_{mesh_hash}"
                hash_groups[group_key].append(mesh_data)
        
        # Convert hash groups to reverse_mesh_groups format and create unique objects
        for group_key, instances in hash_groups.items():
            data_name = instances[0]['data_name']
            
            if len(instances) > 1:  # Multiple instances - create PointInstancer group
                if data_name not in self.unified_data['reverse_mesh_groups']:
                    self.unified_data['reverse_mesh_groups'][data_name] = []
                
                # Add all instances to the group
                for instance in instances:
                    # Remove hash info for output format
                    instance_data = {k: v for k, v in instance.items() if k not in ['data_name', 'mesh_hash']}
                    self.unified_data['reverse_mesh_groups'][data_name].append(instance_data)
            else:
                # Single instance - create as unique object
                instance = instances[0]
                # Handle root parent name properly
                parent_name = instance['root_parent_name']
                if parent_name == 'root':
                    parent_path = '/Root'
                    instance_path = f"/Root/{instance['data_name']}"
                else:
                    parent_path = f"/Root/{parent_name}"
                    instance_path = f"/Root/{parent_name}/{instance['data_name']}"
                
                unique_data = {
                    'type': 'single_instance',
                    'path': instance_path,
                    'mesh_prim': instance['mesh_prim'],
                    'transform_prim': instance['transform_prim'],
                    'parent_path': parent_path,
                    'material_binding': self._get_material_binding(instance['mesh_prim'])
                }
                self.unified_data['unique_objects'].append(unique_data)
                print(f"COLLECT Single instance: {instance['data_name']} under {parent_name}")
        
        # Create anchor meshes for parent containers
        parent_containers = set()
        for mesh_data in mesh_candidates:
            root_parent = mesh_data['root_parent']
            if root_parent and root_parent.GetName() != 'root':
                parent_containers.add(root_parent)
        
        for parent_container in parent_containers:
            # Skip the root container itself
            if parent_container.GetName() == 'root':
                continue
                
            anchor_data = {
                'type': 'anchor_mesh',
                'path': f"/Root/{parent_container.GetName()}",
                'mesh_prim': parent_container,  # The Xform container itself
                'transform': self._get_world_transform(parent_container),
                'material_binding': None  # Parent containers don't have materials
            }
            self.unified_data['unique_objects'].append(anchor_data)
            print(f"COLLECT Anchor mesh: {parent_container.GetName()}")
        
        # Report findings
        print("COLLECT Reverse analysis results:")
        total_instances = 0
        pointinstancer_groups = 0
        
        for data_name, instances in self.unified_data['reverse_mesh_groups'].items():
            parent_name = self.unified_data['parent_objects'].get(data_name, "unknown")
            total_instances += len(instances)
            print(f"  TARGET '{data_name}' (parent: {parent_name}): {len(instances)} instances")
            if len(instances) > 1:
                print(f"    OK Can be converted to PointInstancer (same geometry)")
                pointinstancer_groups += 1
            else:
                print(f"    SKIP Single instance, will remain as-is")
        
        print(f"COLLECT SUMMARY: {len(self.unified_data['reverse_mesh_groups'])} total groups, {pointinstancer_groups} PointInstancer groups, {total_instances} total instances")
        print(f"COLLECT UNIQUE OBJECTS: {len(self.unified_data['unique_objects'])} anchor meshes and single instances")
    
    def _collect_existing_pointinstancer_data(self):
        """Collect data for existing PointInstancer conversion"""
        print("COLLECT Existing PointInstancer conversion: Collecting existing PointInstancers")
        
        # Initialize unique_objects for proper hierarchy
        self.unified_data['unique_objects'] = []
        
        for prim in self.stage.TraverseAll():
            prim_path = str(prim.GetPath())
            prim_type = prim.GetTypeName()
            
            # Collect all prims
            self.unified_data['prims'].append({
                'path': prim_path,
                'prim': prim,
                'type': prim_type,
                'parent': str(prim.GetParent().GetPath()) if prim.GetParent() else None
            })
            
            # Collect materials
            if prim_type == "Material":
                material_name = prim.GetName()
                self.unified_data['materials'][material_name] = {
                    'prim': prim,
                    'path': prim_path,
                    'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                }
            
            # Collect PointInstancers
            elif prim.IsA(UsdGeom.PointInstancer):
                pi_info = self._analyze_pointinstancer(prim)
                if pi_info:
                    # Set parent path for PointInstancer
                    parent_path = str(prim.GetParent().GetPath()) if prim.GetParent() else '/Root'
                    pi_info['parent_path'] = parent_path
                    self.unified_data['pointinstancers'].append(pi_info)
            
            # Collect anchor meshes (parent containers) and individual meshes
            elif prim.IsA(UsdGeom.Xform) and prim.GetName() != 'root':
                # Check if this Xform contains PointInstancers or individual meshes
                has_pointinstancers = False
                has_individual_meshes = False
                
                for child in prim.GetAllChildren():
                    if child.IsA(UsdGeom.PointInstancer):
                        has_pointinstancers = True
                    elif child.IsA(UsdGeom.Mesh) and not self._is_mesh_instanced(child):
                        has_individual_meshes = True
                
                if has_pointinstancers or has_individual_meshes:
                    # This is an anchor mesh (parent container)
                    anchor_data = {
                        'type': 'anchor_mesh',
                        'path': prim_path,
                        'mesh_prim': prim,
                        'transform': self._get_world_transform(prim),
                        'material_binding': self._get_material_binding(prim)
                    }
                    self.unified_data['unique_objects'].append(anchor_data)
                    print(f"COLLECT Found anchor mesh: {prim.GetName()}")
            
            # Collect individual meshes (not part of PointInstancers)
            elif prim.IsA(UsdGeom.Mesh):
                is_instanced = self._is_mesh_instanced(prim)
                if not is_instanced:
                    # This is an individual mesh
                    parent_path = str(prim.GetParent().GetPath()) if prim.GetParent() else '/Root'
                    individual_data = {
                        'type': 'single_instance',
                        'path': prim_path,
                        'mesh_prim': prim,
                        'parent_path': parent_path,
                        'material_binding': self._get_material_binding(prim)
                    }
                    self.unified_data['unique_objects'].append(individual_data)
                    print(f"COLLECT Found individual mesh: {prim.GetName()}")
                else:
                    # This mesh is part of a PointInstancer structure, but we should still collect it
                    # if it's a standalone mesh that should be preserved
                    parent_path = str(prim.GetParent().GetPath()) if prim.GetParent() else '/Root'
                    
                    # Check if this is a standalone mesh that should be preserved (like Lilac_trunk)
                    if parent_path == '/Root' or prim.GetParent().GetName() in ['root', 'Root']:
                        individual_data = {
                            'type': 'single_instance',
                            'path': prim_path,
                            'mesh_prim': prim,
                            'parent_path': parent_path,
                            'material_binding': self._get_material_binding(prim)
                        }
                        self.unified_data['unique_objects'].append(individual_data)
                        print(f"COLLECT Found standalone mesh: {prim.GetName()}")
                    
                    # Also collect base meshes that are part of parent containers (like Cube_001_base)
                    parent = prim.GetParent()
                    if parent and parent.GetName() in ['Cube_001']:
                        # Check if this is a base mesh (ends with _base)
                        if prim.GetName().endswith('_base'):
                            individual_data = {
                                'type': 'single_instance',
                                'path': prim_path,
                                'mesh_prim': prim,
                                'parent_path': parent_path,
                                'material_binding': self._get_material_binding(prim)
                            }
                            self.unified_data['unique_objects'].append(individual_data)
                            print(f"COLLECT Found base mesh: {prim.GetName()}")
            
            # Collect material bindings
            if prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Xform) or prim.IsA(UsdGeom.PointInstancer):
                material_binding = self._get_material_binding(prim)
                if material_binding:
                    self.unified_data['material_bindings'][prim_path] = material_binding
        
        print(f"COLLECT Found {len(self.unified_data['pointinstancers'])} existing PointInstancers")
        print(f"COLLECT Found {len(self.unified_data['unique_objects'])} unique objects (anchors + individuals)")
    
    def _analyze_pointinstancer(self, pi_prim):
        """Analyze a PointInstancer and collect its data"""
        try:
            pi_geom = UsdGeom.PointInstancer(pi_prim)
            
            # Get basic info
            positions = pi_geom.GetPositionsAttr().Get()
            proto_indices = pi_geom.GetProtoIndicesAttr().Get()
            prototypes_rel = pi_geom.GetPrototypesRel()
            
            prototype_targets = list(prototypes_rel.GetTargets()) if prototypes_rel else []
            
            # Get the first prototype prim (for external reference creation)
            prototype_prim = None
            if prototype_targets:
                first_target = prototype_targets[0]
                if '@' not in str(first_target) and ':' not in str(first_target):
                    # Inline prototype - get the actual prim
                    target_prim = self.stage.GetPrimAtPath(first_target)
                    if target_prim and target_prim.IsValid():
                        # If the prototype is a Mesh, use it directly
                        if target_prim.IsA(UsdGeom.Mesh):
                            prototype_prim = target_prim
                        else:
                            # If it's a container, find the first mesh child
                            for child in target_prim.GetAllChildren():
                                if child.IsA(UsdGeom.Mesh):
                                    prototype_prim = child
                                    break
                            # If no mesh child found, use the container itself
                            if not prototype_prim:
                                prototype_prim = target_prim
            
            return {
                'prim': pi_prim,
                'path': str(pi_prim.GetPath()),
                'name': pi_prim.GetName(),
                'instance_count': len(positions) if positions else 0,
                'prototype_count': len(prototype_targets),
                'prototype_targets': prototype_targets,
                'prototype_prim': prototype_prim,  # Add the prototype prim
                'has_external_refs': any('@' in str(target) or ':' in str(target) for target in prototype_targets),
                'has_inline_prototypes': any('@' not in str(target) and ':' not in str(target) for target in prototype_targets)
            }
            
        except Exception as e:
            print(f"WARNING Failed to analyze PointInstancer {pi_prim.GetPath()}: {e}")
            return None
    
    def _is_mesh_instanced(self, mesh_prim):
        """Check if a mesh is part of a PointInstancer structure"""
        parent = mesh_prim.GetParent()
        while parent:
            if parent.IsA(UsdGeom.PointInstancer):
                return True
            # Check if parent contains PointInstancers
            for child in parent.GetAllChildren():
                if child.IsA(UsdGeom.PointInstancer):
                    return True
            parent = parent.GetParent()
        return False
    
    def _get_material_binding(self, prim):
        """Get material binding information for a prim"""
        try:
            binding_api = UsdShade.MaterialBindingAPI(prim)
            binding = binding_api.GetDirectBinding()
            if binding and binding.GetMaterialPath():
                return {
                    'target_path': str(binding.GetMaterialPath()),
                    'bind_as': 'weakerThanDescendants'  # Default binding strength
                }
        except:
            pass
        return None
    
    def _calculate_mesh_hash(self, mesh_prim):
        """Calculate a hash of mesh properties for comparison"""
        try:
            import hashlib
            
            # Get key mesh attributes
            mesh = UsdGeom.Mesh(mesh_prim)
            
            # Collect geometry data
            points = mesh.GetPointsAttr().Get()
            face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
            face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()
            
            # Convert to hashable format
            points_str = str([(p[0], p[1], p[2]) for p in points]) if points else ""
            counts_str = str(list(face_vertex_counts)) if face_vertex_counts else ""
            indices_str = str(list(face_vertex_indices)) if face_vertex_indices else ""
            
            # Combine all geometry data
            geometry_data = f"{points_str}|{counts_str}|{indices_str}"
            
            # Calculate hash
            mesh_hash = hashlib.md5(geometry_data.encode()).hexdigest()
            
            return mesh_hash
            
        except Exception as e:
            print(f"WARNING Failed to calculate mesh hash for {mesh_prim.GetPath()}: {e}")
            return None
    
    def _extract_reference_path(self, prim):
        """Extract reference path from prepend references using the working approach from unified_instancer_converter.py"""
        try:
            # Access references through layer prim spec
            layer = self.stage.GetRootLayer()
            prim_spec = layer.GetPrimAtPath(prim.GetPath())
            ref_list = []
            
            if prim_spec and hasattr(prim_spec, 'referenceList'):
                ref_list = prim_spec.referenceList.GetAddedOrExplicitItems()
            elif prim_spec and hasattr(prim_spec, 'references'):
                ref_list = prim_spec.references.GetAddedOrExplicitItems()
                
            if ref_list:
                for ref in ref_list:
                    if ref.primPath:
                        prim_path_str = str(ref.primPath)
                        # Extract prototype path from reference like </root/prototypes/Plane_001__938870308>
                        if '/prototypes/' in prim_path_str:
                            # Return the full path, not just the name
                            return prim_path_str
        except Exception as e:
            print(f"WARNING Reference extraction failed for {prim.GetPath()}: {e}")
        return None

    def _get_world_transform(self, prim):
        """Get world transform matrix for a prim"""
        try:
            xformable = UsdGeom.Xformable(prim)
            return xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        except:
            return None
    
    def _get_translate(self, prim):
        """Get translate transform from prim using transform matrix (like unified_instancer_converter.py)"""
        try:
            xformable = UsdGeom.Xformable(prim)
            transform_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            if transform_matrix:
                # Get parent container transform for coordinate space conversion
                parent_prim = prim.GetParent()
                parent_world_transform_inverse = None
                
                if parent_prim and parent_prim.IsValid():
                    parent_xformable = UsdGeom.Xformable(parent_prim)
                    if parent_xformable:
                        parent_world_transform = parent_xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                        if parent_world_transform:
                            parent_world_transform_inverse = parent_world_transform.GetInverse()
                
                # Convert from world space to parent-relative space if needed
                if parent_world_transform_inverse is not None:
                    relative_transform = transform_matrix * parent_world_transform_inverse
                    translation = relative_transform.ExtractTranslation()
                else:
                    # Use world coordinates as-is (no parent container)
                    translation = transform_matrix.ExtractTranslation()
                
                return translation
        except:
            pass
        return None

    def _get_rotate(self, prim):
        """Get rotate transform from prim using transform matrix (like unified_instancer_converter.py)"""
        try:
            xformable = UsdGeom.Xformable(prim)
            transform_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            if transform_matrix:
                # Get parent container transform for coordinate space conversion
                parent_prim = prim.GetParent()
                parent_world_transform_inverse = None
                
                if parent_prim and parent_prim.IsValid():
                    parent_xformable = UsdGeom.Xformable(parent_prim)
                    if parent_xformable:
                        parent_world_transform = parent_xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                        if parent_world_transform:
                            parent_world_transform_inverse = parent_world_transform.GetInverse()
                
                # Convert from world space to parent-relative space if needed
                if parent_world_transform_inverse is not None:
                    relative_transform = transform_matrix * parent_world_transform_inverse
                    final_transform = relative_transform
                else:
                    # Use world coordinates as-is (no parent container)
                    final_transform = transform_matrix
                
                # Extract rotation matrix and convert to quaternion
                rotation_matrix = final_transform.RemoveScaleShear()
                quat = rotation_matrix.ExtractRotation().GetQuat()
                # Return as quaternion (Gf.Quatd)
                return quat
        except:
            pass
        return None

    def _get_scale(self, prim):
        """Get scale transform from prim using transform matrix (like unified_instancer_converter.py)"""
        try:
            xformable = UsdGeom.Xformable(prim)
            transform_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            if transform_matrix:
                # Get parent container transform for coordinate space conversion
                parent_prim = prim.GetParent()
                parent_world_transform_inverse = None
                
                if parent_prim and parent_prim.IsValid():
                    parent_xformable = UsdGeom.Xformable(parent_prim)
                    if parent_xformable:
                        parent_world_transform = parent_xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                        if parent_world_transform:
                            parent_world_transform_inverse = parent_world_transform.GetInverse()
                
                # Convert from world space to parent-relative space if needed
                if parent_world_transform_inverse is not None:
                    relative_transform = transform_matrix * parent_world_transform_inverse
                    final_transform = relative_transform
                else:
                    # Use world coordinates as-is (no parent container)
                    final_transform = transform_matrix
                
                # Extract scale using matrix decomposition
                scale_x = Gf.Vec3d(final_transform[0][0], final_transform[1][0], final_transform[2][0]).GetLength()
                scale_y = Gf.Vec3d(final_transform[0][1], final_transform[1][1], final_transform[2][1]).GetLength()
                scale_z = Gf.Vec3d(final_transform[0][2], final_transform[1][2], final_transform[2][2]).GetLength()
                return Gf.Vec3f(scale_x, scale_y, scale_z)
        except:
            pass
        return None
    
    def _extract_reference_name(self, ref_str):
        """Extract reference name from reference string"""
        try:
            # Handle different reference formats
            if '@' in ref_str:
                # External reference: @path/to/file.usd@
                parts = ref_str.split('@')
                if len(parts) >= 2:
                    file_path = parts[1]
                    return os.path.splitext(os.path.basename(file_path))[0]
            else:
                # Internal reference: /path/to/prim
                return ref_str.split('/')[-1]
        except:
            pass
        return None
    
    def _standardize_material_paths(self):
        """Standardize all material paths to use /Root/Looks/ structure"""
        # Create material path mapping
        material_path_mapping = self._create_material_path_mapping()
        
        # Update material bindings with standardized paths
        for prim_path, binding_info in self.unified_data['material_bindings'].items():
            original_path = binding_info['target_path']
            if original_path in material_path_mapping:
                binding_info['standardized_path'] = material_path_mapping[original_path]
            else:
                # Fallback: extract material name and use standardized path
                material_name = original_path.split("/")[-1]
                binding_info['standardized_path'] = f"/Root/Looks/{material_name}"
    
    def _create_material_path_mapping(self):
        """Create mapping from original material paths to standardized paths"""
        mapping = {}
        
        for material_name, material_info in self.unified_data['materials'].items():
            original_path = material_info['path']
            standardized_path = f"/Root/Looks/{material_name}"
            mapping[original_path] = standardized_path
        
        return mapping
