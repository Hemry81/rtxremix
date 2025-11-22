#!/usr/bin/env python3
"""
Unified Data Collector for USD PointInstancer Converter
Handles data collection for all conversion types (forward, reverse, existing PointInstancer)
"""

import os
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
from unified_material_converter import convert_material_to_remix

class UnifiedDataCollector:
    """Unified data collection for all conversion modes"""
    
    def __init__(self, stage, input_type, auto_blend_alpha=True):
        self.stage = stage
        self.input_type = input_type
        self.auto_blend_alpha = auto_blend_alpha
        
        # Calculate source textures directory for alpha detection
        import os
        try:
            root_layer = stage.GetRootLayer()
            input_identifier = getattr(root_layer, 'realPath', None) or getattr(root_layer, 'identifier', None)
            if input_identifier:
                input_dir = os.path.dirname(input_identifier)
                self.source_textures_dir = os.path.join(input_dir, 'textures')
            else:
                self.source_textures_dir = None
        except:
            self.source_textures_dir = None
        self.unified_data = {}
        self.materials_seen = set()  # Track materials already logged
        self.failed_prototypes = []  # Track prototypes that failed to collect mesh
        
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
        """Collect data for forward conversion (instanceable references ??PointInstancer)"""
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
                        converted = convert_material_to_remix(prim, auto_blend_alpha=self.auto_blend_alpha, source_textures_dir=self.source_textures_dir)
                        if converted:
                            data['materials'][material_name] = converted
                            if material_name not in self.materials_seen:
                                print(f"COLLECT Converted {converted['conversion_type']} material: {material_name}")
                                self.materials_seen.add(material_name)
                        else:
                            data['materials'][material_name] = {
                                'prim': prim,
                                'path': prim_path,
                                'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                            }
            
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
        
        # Track prototypes already logged to reduce spam
        prototypes_logged = set()
        
        # Check for instanceable Xforms or Meshes with prepend references
        for prim in self.stage.TraverseAll():
            # Check both Xforms (particle systems) and Meshes (Blender 3.6 style)
            if prim.IsInstanceable() or prim.IsA(UsdGeom.Xform) or prim.IsA(UsdGeom.Mesh):
                # Check if this prim has references
                layer = self.stage.GetRootLayer()
                prim_spec = layer.GetPrimAtPath(prim.GetPath())
                ref_list = []
                
                if prim_spec and hasattr(prim_spec, 'referenceList'):
                    ref_list = prim_spec.referenceList.GetAddedOrExplicitItems()
                elif prim_spec and hasattr(prim_spec, 'references'):
                    ref_list = prim_spec.references.GetAddedOrExplicitItems()
                
                if ref_list:
                    for ref in ref_list:
                        if ref.primPath:  # Internal reference
                            instanceable_count += 1
                            # For Meshes, use parent Xform; for Xforms, use the Xform itself
                            if prim.IsA(UsdGeom.Mesh):
                                prim = prim.GetParent()
                            prim_path = str(prim.GetPath())
                        
                        # Extract transform data
                        translate = self._get_translate(prim)
                        rotate = self._get_rotate(prim)
                        scale = self._get_scale(prim)
                        
                        # Store the full transform matrix for proper PointInstancer extraction
                        transform_matrix = self._get_world_transform(prim)
                        
                        # Extract reference path from the mesh
                        ref_path = str(ref.primPath)
                        if not ref_path:
                            print(f"WARNING: Could not extract reference path for {prim_path}")
                            continue
                        
                        # Filter out the prototype definition itself (not an instance)
                        if prim_path == ref_path or str(prim.GetPath()) == ref_path:
                            print(f"FILTER: Excluding prototype definition {prim.GetName()} (not an instance)")
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
                            if ref_path not in prototypes_logged:
                                print(f"COLLECT Attempting to access prototype: {ref_path}")
                                prototypes_logged.add(ref_path)
                            
                            # Try to get the prototype prim
                            prototype_prim = self._get_prototype_prim(ref_path)
                            
                            # If abstract/empty, search siblings for one with actual mesh
                            if prototype_prim and prototype_prim.IsAbstract() and len(list(prototype_prim.GetAllChildren())) == 0:
                                proto_name = prototype_prim.GetName()
                                parent_prim = prototype_prim.GetParent()
                                if parent_prim:
                                    # Search all siblings for one containing the base name and has mesh
                                    for sibling in parent_prim.GetAllChildren():
                                        if proto_name in sibling.GetName() and sibling != prototype_prim:
                                            # Check if this sibling has mesh
                                            for desc in Usd.PrimRange.AllPrims(sibling):
                                                if desc.IsA(UsdGeom.Mesh):
                                                    print(f"COLLECT Empty abstract, using sibling {sibling.GetName()} instead")
                                                    prototype_prim = sibling
                                                    ref_path = str(sibling.GetPath())
                                                    break
                                            if prototype_prim == sibling:
                                                break
                            
                            if prototype_prim and prototype_prim.IsValid():
                                print(f"COLLECT Successfully accessed prototype prim: {prototype_prim.GetName()}")
                                # Find the mesh - it could be the prim itself or a child
                                mesh_prim = None
                                
                                # Check if the prototype itself is a mesh
                                if prototype_prim.IsA(UsdGeom.Mesh):
                                    mesh_prim = prototype_prim
                                    print(f"COLLECT Prototype is a mesh directly")
                                else:
                                    # Look for mesh children recursively
                                    children = list(prototype_prim.GetAllChildren())
                                    print(f"COLLECT Prototype has {len(children)} children, searching for mesh...")
                                    
                                    # Search for mesh
                                    mesh_prim = None
                                    
                                    # Try Usd.PrimRange with all prims
                                    for desc in Usd.PrimRange.AllPrims(prototype_prim):
                                        if desc != prototype_prim and desc.IsA(UsdGeom.Mesh):
                                            mesh_prim = desc
                                            print(f"COLLECT Found mesh descendant: {mesh_prim.GetName()}")
                                            break
                                    
                                    # If no mesh and prototype is abstract, try Mesh_ prefix variant
                                    if not mesh_prim and prototype_prim.IsAbstract():
                                        proto_name = prototype_prim.GetName()
                                        parent_path = str(prototype_prim.GetParent().GetPath())
                                        alt_name = f"Mesh_{proto_name}"
                                        alt_path = f"{parent_path}/{alt_name}"
                                        alt_prim = self.stage.GetPrimAtPath(alt_path)
                                        
                                        if alt_prim and alt_prim.IsValid():
                                            for desc in Usd.PrimRange.AllPrims(alt_prim):
                                                if desc != alt_prim and desc.IsA(UsdGeom.Mesh):
                                                    mesh_prim = desc
                                                    print(f"COLLECT Found mesh in alternate {alt_name}: {mesh_prim.GetName()}")
                                                    ref_path = alt_path
                                                    break
                                    
                                    if not mesh_prim:
                                        print(f"COLLECT No mesh found in prototype hierarchy")
                                
                                if mesh_prim:
                                    # Get face count from mesh
                                    face_count = 0
                                    try:
                                        mesh = UsdGeom.Mesh(mesh_prim)
                                        face_counts_attr = mesh.GetFaceVertexCountsAttr().Get()
                                        if face_counts_attr:
                                            face_count = len(face_counts_attr)
                                    except:
                                        pass
                                    
                                    # Get transform from the prototype prim (not the instance)
                                    proto_transform = self._get_world_transform(prototype_prim)
                                    
                                    data['prototype_meshes'][ref_path] = {
                                        'mesh_prim': mesh_prim,
                                        'path': str(mesh_prim.GetPath()),
                                        'material_binding': self._get_material_binding(mesh_prim),
                                        'face_count': face_count,
                                        'transform': proto_transform  # Store prototype transform
                                    }
                                    print(f"COLLECT Stored prototype mesh: {ref_path} -> {mesh_prim.GetName()} ({face_count} faces)")
                                    self._collect_materials_from_prototype(mesh_prim, data)
                                else:
                                    print(f"WARNING: No mesh found in prototype: {ref_path}")
                                    # Track failed prototype with blender name
                                    if blender_name:
                                        self.failed_prototypes.append(blender_name)
                            else:
                                print(f"WARNING: Could not access prototype prim: {ref_path}")
                        
                        # Only process the first reference
                        break
        
        # Third pass: create anchor data for containers OR create a default root anchor if no containers
        if parent_containers:
            for parent_container in parent_containers:
                # Check if parent is root - if so, skip creating anchor for it
                if parent_container.GetName() in ['root', 'Root']:
                    continue
                    
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
        
        # Always create a virtual root anchor for flat hierarchy (handles instances directly under /root)
        root_prim = self.stage.GetPrimAtPath('/root') or self.stage.GetPrimAtPath('/Root')
        if root_prim:
            anchor_data = {
                'container_prim': root_prim,
                'container_path': '/Root',
                'mesh_prim': None,  # No mesh for virtual root
                'path': '/Root',
                'transform': None,
                'material_binding': None,
                'parent': None,
                'parent_path': None,
                'children': [],
                'nested_pointinstancers': [],
                'is_virtual_root': True  # Flag to identify virtual root
            }
            data['anchor_meshes'].append(anchor_data)
            print("COLLECT Created virtual root anchor for flat hierarchy")
        
        # Fourth pass: associate instanceable references with their parent containers
        for ref_path, instances in data['instanceable_references'].items():
            for instance_data in instances:
                parent_prim = instance_data['parent']
                if parent_prim:
                    # Find the anchor container that contains this instance
                    matched = False
                    for anchor_data in data['anchor_meshes']:
                        if anchor_data['container_prim'] == parent_prim:
                            anchor_data['children'].append(instance_data)
                            matched = True
                            break
                    
                    # If no match, add to virtual root anchor
                    if not matched:
                        for anchor_data in data['anchor_meshes']:
                            if anchor_data.get('is_virtual_root', False):
                                anchor_data['children'].append(instance_data)
                                break
        
        # Summary of prototype reuse
        prototype_reuse_count = sum(len(instances) for instances in data['instanceable_references'].values())
        unique_prototypes = len(data['prototype_meshes'])
        if unique_prototypes > 0:
            print(f"COLLECT Prototype summary: {unique_prototypes} unique prototypes reused {prototype_reuse_count} times")
        
        print(f"COLLECT Forward conversion: Found {instanceable_count} instanceable Xforms")
        print(f"COLLECT Forward conversion: Found {len(data['instanceable_references'])} unique prototype references")
        print(f"COLLECT Forward conversion: Found {len(data['anchor_meshes'])} anchor meshes")
        
        # Report parent-child relationships
        for anchor_data in data['anchor_meshes']:
            if anchor_data.get('is_virtual_root', False):
                print(f"   Virtual root anchor: {len(anchor_data['children'])} child instances (flat hierarchy)")
            else:
                print(f"   Anchor container {anchor_data['container_prim'].GetName()}: {len(anchor_data['children'])} child instances")
        
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
            
        # Method 3: Check for references (Blender 3.6+ style and prototype style)
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
                    ref_prim_path = str(ref.primPath) if ref.primPath else ''
                    # Check for prototype references OR any internal reference (Blender 3.6 style)
                    if '/prototypes/' in str(ref.assetPath) or '/prototypes/' in ref_prim_path or ref_prim_path:
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
        """Collect data for reverse conversion (individual objects ??PointInstancer)"""
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
                converted = convert_material_to_remix(prim, auto_blend_alpha=self.auto_blend_alpha, source_textures_dir=self.source_textures_dir)
                if converted:
                    self.unified_data['materials'][material_name] = converted
                    if material_name not in self.materials_seen:
                        print(f"COLLECT Converted {converted['conversion_type']} material: {material_name}")
                        self.materials_seen.add(material_name)
                else:
                    self.unified_data['materials'][material_name] = {
                        'prim': prim,
                        'path': prim_path,
                        'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                    }
            
            # Collect Xforms with blender:object_name OR Xform name patterns (Blender 3.6)
            if prim.IsA(UsdGeom.Xform) and prim.GetName() not in ['root', 'Root']:
                # Check if THIS Xform has blender:object_name
                object_name_attr = prim.GetAttribute("userProperties:blender:object_name")
                object_name = None
                
                if object_name_attr:
                    object_name = object_name_attr.Get()
                else:
                    # Blender 3.6 non-instancing: extract base name from pattern like "Cone__123"
                    import re
                    name = prim.GetName()
                    match = re.match(r'^([A-Za-z0-9_]+?)(?:__|_)\d+', name)
                    if match:
                        object_name = match.group(1)  # Use base name as grouping key
                
                if object_name:
                        # Find the first mesh in this hierarchy (recursively)
                        def find_first_mesh(p):
                            if p.IsA(UsdGeom.Mesh):
                                return p
                            for child in p.GetAllChildren():
                                mesh = find_first_mesh(child)
                                if mesh:
                                    return mesh
                            return None
                        
                        mesh_prim = find_first_mesh(prim)
                        if mesh_prim:
                            # Calculate mesh hash for comparison
                            mesh_hash = self._calculate_mesh_hash(mesh_prim)
                            
                            # Get parent info
                            root_parent = prim.GetParent()
                            root_parent_name = root_parent.GetName() if root_parent else "root"
                            
                            # Store mesh candidate - use object_name as the grouping key
                            mesh_data = {
                                'mesh_prim': mesh_prim,
                                'transform_prim': prim,  # Use the TOP anchor Xform
                                'root_parent': root_parent,
                                'root_parent_name': root_parent_name,
                                'path': prim_path,
                                'transform_path': prim_path,
                                'data_name': object_name,  # Use object_name for grouping
                                'mesh_hash': mesh_hash,
                                'prim': prim  # Store the Xform prim for parent checking
                            }
                            
                            mesh_candidates.append(mesh_data)
                            
                            # Track parent objects
                            if object_name not in self.unified_data['parent_objects']:
                                self.unified_data['parent_objects'][object_name] = root_parent_name
                            
                            # Track materials
                            material_binding = self._get_material_binding(mesh_prim)
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
        
        # Second pass: Count occurrences of each object_name first
        from collections import defaultdict, Counter
        object_name_counts = Counter()
        
        for mesh_data in mesh_candidates:
            object_name_counts[mesh_data['data_name']] += 1
        
        # Filter: only keep objects where name appears multiple times (real instances)
        # Skip objects where name appears only once (containers/anchors)
        # Also skip if parent's object_name appears multiple times (nested child)
        filtered_candidates = []
        for mesh_data in mesh_candidates:
            if object_name_counts[mesh_data['data_name']] > 1:
                # Check if parent also has object_name that appears multiple times
                parent_prim = mesh_data['prim'].GetParent()
                skip = False
                while parent_prim and parent_prim.GetName() not in ['root', 'Root']:
                    parent_obj_attr = parent_prim.GetAttribute("userProperties:blender:object_name")
                    if parent_obj_attr:
                        parent_obj_name = parent_obj_attr.Get()
                        if parent_obj_name and object_name_counts.get(parent_obj_name, 0) > 1:
                            # Parent is also a multi-instance object, this is a nested child
                            skip = True
                            break
                    parent_prim = parent_prim.GetParent()
                
                if not skip:
                    filtered_candidates.append(mesh_data)
        
        # Group by data_name and hash
        hash_groups = defaultdict(list)
        
        for mesh_data in filtered_candidates:
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
            
            # Find the mesh child of this container (same name as container)
            mesh_child = None
            for child in parent_container.GetAllChildren():
                if child.IsA(UsdGeom.Mesh) and child.GetName() == parent_container.GetName():
                    mesh_child = child
                    break
            
            if mesh_child:
                anchor_data = {
                    'type': 'anchor_mesh',
                    'path': f"/Root/{parent_container.GetName()}",
                    'mesh_prim': mesh_child,  # The actual mesh child
                    'container_prim': parent_container,  # Store container for hierarchy
                    'transform': self._get_world_transform(mesh_child),
                    'material_binding': self._get_material_binding(mesh_child)
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
                # Check if already Remix material first
                if self._is_remix_material(prim):
                    self.unified_data['materials'][material_name] = {
                        'prim': prim,
                        'path': prim_path,
                        'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None,
                        'is_remix': True
                    }
                else:
                    converted = convert_material_to_remix(prim, auto_blend_alpha=self.auto_blend_alpha, source_textures_dir=self.source_textures_dir)
                    if converted:
                        self.unified_data['materials'][material_name] = converted
                        if material_name not in self.materials_seen:
                            print(f"COLLECT Converted {converted['conversion_type']} material: {material_name}")
                            self.materials_seen.add(material_name)
                    else:
                        self.unified_data['materials'][material_name] = {
                            'prim': prim,
                            'path': prim_path,
                            'parent_scope': str(prim.GetParent().GetPath()) if prim.GetParent() else None
                        }
            
            # Collect PointInstancers
            elif prim.IsA(UsdGeom.PointInstancer):
                pi_info = self._analyze_pointinstancer(prim)
                if pi_info:
                    # For Blender 4.5, preserve parent hierarchy
                    parent = prim.GetParent()
                    if parent and parent.GetName() not in ['root', 'Root']:
                        # PointInstancer is inside a container - preserve this structure
                        # Convert path to use /Root instead of /root
                        parent_path = str(parent.GetPath()).replace('/root/', '/Root/')
                        pi_info['parent_path'] = parent_path
                        pi_info['preserve_parent'] = True
                    else:
                        pi_info['parent_path'] = '/Root'
                        pi_info['preserve_parent'] = False
                    self.unified_data['pointinstancers'].append(pi_info)
            
            # Collect anchor meshes (parent containers) and individual meshes
            elif prim.IsA(UsdGeom.Xform) and prim.GetName() != 'root':
                # Blender 4.5.4: Skip Xforms inside 'over' containers (prototype Xforms)
                parent = prim.GetParent()
                if parent and parent.GetSpecifier() == Sdf.SpecifierOver:
                    continue
                
                # Check if this Xform contains PointInstancers or individual meshes
                has_pointinstancers = False
                has_individual_meshes = False
                mesh_child = None
                
                for child in prim.GetAllChildren():
                    if child.IsA(UsdGeom.PointInstancer):
                        has_pointinstancers = True
                    elif child.IsA(UsdGeom.Mesh) and not self._is_mesh_instanced(child):
                        has_individual_meshes = True
                        if not mesh_child:
                            mesh_child = child
                
                if has_pointinstancers or has_individual_meshes:
                    # This is an anchor mesh (parent container)
                    anchor_data = {
                        'type': 'anchor_mesh',
                        'path': prim_path,
                        'mesh_prim': mesh_child if mesh_child else prim,
                        'container_prim': prim,
                        'transform': self._get_world_transform(mesh_child if mesh_child else prim),
                        'material_binding': self._get_material_binding(mesh_child if mesh_child else prim)
                    }
                    self.unified_data['unique_objects'].append(anchor_data)
                    print(f"COLLECT Found anchor mesh: {prim.GetName()}")
            
            # Collect individual meshes (not part of PointInstancers)
            elif prim.IsA(UsdGeom.Mesh):
                # Blender 4.5.4: Skip meshes whose ancestor has 'over' specifier (prototype references)
                ancestor = prim.GetParent()
                is_prototype_ref = False
                while ancestor and ancestor.GetName() not in ['root', 'Root']:
                    if ancestor.GetSpecifier() == Sdf.SpecifierOver:
                        is_prototype_ref = True
                        break
                    ancestor = ancestor.GetParent()
                if is_prototype_ref:
                    continue
                
                is_instanced = self._is_mesh_instanced(prim)
                
                # Check if this mesh is inside a Prototypes folder (prototype mesh)
                is_prototype = '/Prototypes/' in prim_path or prim_path.endswith('/Prototypes')
                
                if not is_instanced and not is_prototype:
                    # This is an individual mesh (not a prototype)
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
                elif is_instanced and not is_prototype:
                    # This mesh is part of a PointInstancer but NOT a prototype
                    parent_path = str(prim.GetParent().GetPath()) if prim.GetParent() else '/Root'
                    
                    # Check if this is a standalone mesh that should be preserved
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
                    else:
                        # Check if parent has PointInstancer sibling
                        parent = prim.GetParent()
                        if parent and parent.GetName() not in ['root', 'Root', 'Prototypes'] and parent.IsA(UsdGeom.Xform):
                            has_pi_sibling = any(child.IsA(UsdGeom.PointInstancer) for child in parent.GetAllChildren())
                            if not has_pi_sibling:
                                individual_data = {
                                    'type': 'single_instance',
                                    'path': prim_path,
                                    'mesh_prim': prim,
                                    'parent_path': parent_path,
                                    'material_binding': self._get_material_binding(prim)
                                }
                                self.unified_data['unique_objects'].append(individual_data)
                                print(f"COLLECT Found container child mesh: {prim.GetName()}")
            
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
            prototype_face_counts = {}  # Store face counts per prototype
            
            if prototype_targets:
                for proto_idx, proto_target in enumerate(prototype_targets):
                    if '@' not in str(proto_target) and ':' not in str(proto_target):
                        # Inline prototype - get the actual prim
                        target_prim = self.stage.GetPrimAtPath(proto_target)
                        if target_prim and target_prim.IsValid():
                            mesh_prim = None
                            
                            # Blender 4.5.4: Check if prototype has a reference to actual mesh
                            layer = self.stage.GetRootLayer()
                            prim_spec = layer.GetPrimAtPath(target_prim.GetPath())
                            if prim_spec and hasattr(prim_spec, 'referenceList'):
                                ref_list = prim_spec.referenceList.prependedItems
                                if ref_list:
                                    for ref in ref_list:
                                        if ref.primPath:
                                            # Follow the reference to get the actual mesh
                                            ref_prim = self.stage.GetPrimAtPath(ref.primPath)
                                            if ref_prim and ref_prim.IsValid():
                                                # Find mesh in referenced prim - recursively search ALL descendants
                                                if ref_prim.IsA(UsdGeom.Mesh):
                                                    mesh_prim = ref_prim
                                                else:
                                                    # Recursively search all descendants
                                                    for desc in Usd.PrimRange.AllPrims(ref_prim):
                                                        if desc != ref_prim and desc.IsA(UsdGeom.Mesh):
                                                            mesh_prim = desc
                                                            break
                                                break
                            
                            # Fallback: If no reference, check if prototype is a Mesh directly
                            if not mesh_prim:
                                if target_prim.IsA(UsdGeom.Mesh):
                                    mesh_prim = target_prim
                                else:
                                    # If it's a container, recursively search for mesh (handles nested Prototypes folders)
                                    for desc in Usd.PrimRange.AllPrims(target_prim):
                                        if desc != target_prim and desc.IsA(UsdGeom.Mesh):
                                            mesh_prim = desc
                                            break
                            
                            # Store first prototype for external reference
                            if proto_idx == 0 and mesh_prim:
                                prototype_prim = mesh_prim
                            
                            # Calculate face count for this prototype
                            if mesh_prim:
                                face_count = 0
                                try:
                                    mesh = UsdGeom.Mesh(mesh_prim)
                                    face_counts_attr = mesh.GetFaceVertexCountsAttr().Get()
                                    if face_counts_attr:
                                        face_count = len(face_counts_attr)
                                except:
                                    pass
                                
                                # Use mesh name as key (the actual mesh, not the Prototype_N container)
                                mesh_name = mesh_prim.GetName()
                                prototype_face_counts[mesh_name] = face_count
            
            return {
                'prim': pi_prim,
                'path': str(pi_prim.GetPath()),
                'name': pi_prim.GetName(),
                'instance_count': len(positions) if positions else 0,
                'prototype_count': len(prototype_targets),
                'prototype_targets': prototype_targets,
                'prototype_prim': prototype_prim,  # Add the prototype prim
                'prototype_face_counts': prototype_face_counts,  # Add face counts
                'has_external_refs': any('@' in str(target) or ':' in str(target) for target in prototype_targets),
                'has_inline_prototypes': any('@' not in str(target) and ':' not in str(target) for target in prototype_targets)
            }
            
        except Exception as e:
            print(f"WARNING Failed to analyze PointInstancer {pi_prim.GetPath()}: {e}")
            return None
    
    def _is_mesh_instanced(self, mesh_prim):
        """Check if a mesh is part of a PointInstancer structure (child/descendant of PointInstancer)"""
        parent = mesh_prim.GetParent()
        while parent:
            if parent.IsA(UsdGeom.PointInstancer):
                return True
            # Check if parent is named 'Prototypes' (both 'def' and 'over' specifiers)
            if parent.GetName() == 'Prototypes':
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
            
            # Get material binding
            material_binding = self._get_material_binding(mesh_prim)
            material_str = material_binding['target_path'] if material_binding else "none"
            
            # Get UV map names (primvars)
            uv_names = []
            for attr in mesh_prim.GetAttributes():
                attr_name = attr.GetName()
                if attr_name.startswith('primvars:') and 'UV' in attr_name or 'uv' in attr_name.lower():
                    uv_names.append(attr_name)
            uv_str = ','.join(sorted(uv_names))
            
            # Quick metadata: vertex count, face count
            vertex_count = len(points) if points else 0
            face_count = len(face_vertex_counts) if face_vertex_counts else 0
            
            # Convert to hashable format
            points_str = str([(p[0], p[1], p[2]) for p in points]) if points else ""
            counts_str = str(list(face_vertex_counts)) if face_vertex_counts else ""
            indices_str = str(list(face_vertex_indices)) if face_vertex_indices else ""
            
            # Combine all geometry data + metadata
            geometry_data = f"{vertex_count}|{face_count}|{material_str}|{uv_str}|{points_str}|{counts_str}|{indices_str}"
            
            # Calculate hash
            mesh_hash = hashlib.md5(geometry_data.encode()).hexdigest()
            
            return mesh_hash
            
        except Exception as e:
            print(f"WARNING Failed to calculate mesh hash for {mesh_prim.GetPath()}: {e}")
            return None
    
    def _extract_reference_path(self, prim):
        """Extract reference path from prepend references (supports Blender 3.6+ and prototype styles)"""
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
                        # Return any internal reference path (Blender 3.6 style or prototype style)
                        # Examples: </Plane/Cylinder_449182092/Cylinder> or </root/prototypes/Plane_001__938870308>
                        if prim_path_str:
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
    
    def _is_remix_material(self, material_prim):
        """Check if material is already a Remix material (AperturePBR_Opacity)"""
        try:
            layer = self.stage.GetRootLayer()
            prim_spec = layer.GetPrimAtPath(material_prim.GetPath())
            if prim_spec and hasattr(prim_spec, 'referenceList'):
                for ref in prim_spec.referenceList.GetAddedOrExplicitItems():
                    ref_path = str(ref.assetPath)
                    if 'AperturePBR_Opacity' in ref_path:
                        return True
        except:
            pass
        return False
    
    def _get_prototype_prim(self, ref_path):
        """Get prototype prim, handling both def and class prototypes"""
        try:
            # Method 1: Try direct GetPrimAtPath (works for def prims)
            prototype_prim = self.stage.GetPrimAtPath(ref_path)
            if prototype_prim and prototype_prim.IsValid():
                return prototype_prim
            
            # Method 2: Try with case-insensitive path (handle /root/ vs /Root/)
            if '/root/' in ref_path.lower():
                # Try both lowercase and uppercase variants
                alt_paths = [
                    ref_path.replace('/root/', '/Root/'),
                    ref_path.replace('/Root/', '/root/')
                ]
                for alt_path in alt_paths:
                    if alt_path != ref_path:
                        prototype_prim = self.stage.GetPrimAtPath(alt_path)
                        if prototype_prim and prototype_prim.IsValid():
                            print(f"COLLECT Found prototype using alternate path: {alt_path}")
                            return prototype_prim
            
            # Method 3: Access via layer spec (works for both def and class)
            layer = self.stage.GetRootLayer()
            prim_spec = layer.GetPrimAtPath(ref_path)
            
            if prim_spec:
                # For class prims, we need to use OverridePrim to make them accessible
                # Create a temporary override to access the class prim
                prototype_prim = self.stage.OverridePrim(ref_path)
                if prototype_prim and prototype_prim.IsValid():
                    return prototype_prim
            
            # Method 4: Traverse stage including inactive/class prims
            for prim in self.stage.TraverseAll():
                prim_path_str = str(prim.GetPath())
                # Case-insensitive comparison
                if prim_path_str.lower() == ref_path.lower():
                    print(f"COLLECT Found prototype via traversal: {prim_path_str}")
                    return prim
            
            print(f"WARNING: Could not find prototype at {ref_path}")
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get prototype prim {ref_path}: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
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
            # Handle both converted and non-converted materials
            if 'path' in material_info:
                original_path = material_info['path']
            elif 'prim' in material_info:
                original_path = str(material_info['prim'].GetPath())
            else:
                # Fallback: use material name
                original_path = f"/Root/Looks/{material_name}"
            
            standardized_path = f"/Root/Looks/{material_name}"
            mapping[original_path] = standardized_path
        
        return mapping
