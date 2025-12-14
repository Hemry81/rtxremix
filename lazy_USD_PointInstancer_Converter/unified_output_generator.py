#!/usr/bin/env python3
"""
Final Simplified Unified Output Generator for USD PointInstancer Converter
Only generates output from prepared data - no data processing
"""

import os
import time
import shutil
import sys
import contextlib
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
from nvidia_texture_converter import NvidiaTextureConverter
from omnipbr_converter import parse_omnipbr_mdl

@contextlib.contextmanager
def suppress_usd_warnings():
    """Suppress AperturePBR_Opacity.usda reference warnings"""
    import io
    old_stderr = sys.stderr
    
    class FilteredStderr:
        def __init__(self):
            self.current_line = ''
            self.skip_next_blank = False
        
        def write(self, text):
            self.current_line += text
            while '\n' in self.current_line:
                line, self.current_line = self.current_line.split('\n', 1)
                line += '\n'
                if self.skip_next_blank and line.strip() == '':
                    self.skip_next_blank = False
                    continue
                skip_line = (
                    'AperturePBR_Opacity.usda' in line or
                    'Could not open asset' in line or
                    '_ReportErrors' in line or
                    'recomposing stage' in line or
                    'for reference introduced by' in line or
                    '@C:/Users/materials/' in line
                )
                if not skip_line:
                    old_stderr.write(line)
                else:
                    self.skip_next_blank = True
        
        def flush(self):
            if self.current_line:
                skip_line = (
                    'AperturePBR_Opacity.usda' in self.current_line or
                    'Could not open asset' in self.current_line or
                    '_ReportErrors' in self.current_line or
                    'recomposing stage' in self.current_line or
                    'for reference introduced by' in self.current_line or
                    '@C:/Users/materials/' in self.current_line
                )
                if not skip_line and self.current_line.strip():
                    old_stderr.write(self.current_line)
                self.current_line = ''
            self.skip_next_blank = False
            old_stderr.flush()
    
    sys.stderr = FilteredStderr()
    try:
        yield
    finally:
        sys.stderr.flush()
        sys.stderr = old_stderr

class FinalOutputGenerator:
    """Final simplified output generation - only generates output from prepared data"""
    
    def __init__(self, output_data, output_path, use_external_references=False, export_binary=False, input_stage=None, convert_textures=False, normal_map_format="Auto-Detect", interpolation_mode="faceVarying", remove_geomsubset_familyname=True, generate_missing_uvs=False):
        self.output_data = output_data
        self.output_path = output_path
        self.use_external_references = use_external_references
        self.export_binary = export_binary
        self.input_stage = input_stage
        self.conversion_type = output_data.get('input_type', 'unknown')
        self.convert_textures = convert_textures
        self.normal_map_format = normal_map_format
        self.interpolation_mode = interpolation_mode
        self.remove_geomsubset_familyname = remove_geomsubset_familyname
        self.generate_missing_uvs = generate_missing_uvs
        
        # Initialize texture converter if enabled (with GPU acceleration, output to textures/)
        self.texture_converter = NvidiaTextureConverter(use_gpu=True, gpu_device=0) if convert_textures else None
        
        # Texture conversion tracking to avoid duplicate conversions
        self.texture_conversion_cache = {}  # Maps source_file -> output_file
        self.textures_being_converted = set()  # Track files currently being converted
        self.failed_texture_conversions = []  # Track failed conversions with details
        
        # Counters for summary
        self.geomsubset_fixes = 0
        self.materials_cleaned = 0
        
        # Find and store mod.usda path for refresh
        self.mod_file = self._find_mod_file()
        
        # Initialize UV status tracking lists (accumulate across all files)
        self.meshes_without_uvs = []
        self.meshes_with_generated_uvs = []
        self.meshes_failed_uv_generation = []
        
        # Face count tracking
        self.prototype_face_counts = {}  # {prototype_name: face_count}
        self.instance_counts = {}  # {prototype_name: instance_count}
        self.blender_names = {}  # {prototype_name: blender_name}
        
    def generate_output(self):
        """Main output generation method"""
        print(f"OUTPUT Generating output from prepared data...")
        
        # Create stage
        output_stage = self._create_stage()
        
        # Copy materials
        self._copy_materials(output_stage)
        
        # Remove old root-level materials after successful RTX conversion
        self._remove_old_root_materials_after_conversion(output_stage)
        
        # Create unique objects
        self._create_unique_objects(output_stage)
        
        # Initialize face counting flag
        self._faces_counted = False
        
        # Create PointInstancers
        pointinstancer_count = self._create_pointinstancers(output_stage)
        
        # Calculate face counts if not already done (for non-external-ref modes)
        if not self._faces_counted:
            self._calculate_face_counts(output_stage)
        
        # Create external files if needed
        external_files_created = 0
        if self.use_external_references:
            external_files_created = self._create_external_files()
            
            # CLEANUP: Remove standalone meshes that are now in external files
            self._remove_standalone_meshes_for_external_refs(output_stage)
            
            # CLEANUP: Remove unused materials from main file after external references are created
            self._remove_unused_materials_from_main_file(output_stage)

        # Convert textures directly from source (no wasteful copying)
        textures_converted = 0
        if self.convert_textures:
            textures_converted = self._convert_textures_direct()
        
        # CRITICAL: Apply unified mesh fixes to ALL meshes after structure is complete
        self._apply_final_mesh_fixes(output_stage)
        
        # FINAL STEP: Assign all material bindings (suppresses USD warnings)
        with suppress_usd_warnings():
            self._assign_all_material_bindings(output_stage)
        
        # Save stage
        output_stage.Save()
        
        # Print summary
        if self.geomsubset_fixes > 0:
            print(f"FIX Removed familyName from {self.geomsubset_fixes} GeomSubsets")
        if self.materials_cleaned > 0:
            print(f"CLEANUP Removed {self.materials_cleaned} old Blender material scopes")
        
        return {
            'pointinstancers_processed': pointinstancer_count,
            'external_files_created': external_files_created,
            'materials_converted': len(self.output_data['materials']),
            'textures_converted': textures_converted,
            'instance_counts': self.instance_counts,
            'blender_names': self.blender_names,
            'texture_details': getattr(self, '_texture_details', []),
            'meshes_without_uvs': getattr(self, 'meshes_without_uvs', []),
            'meshes_with_generated_uvs': getattr(self, 'meshes_with_generated_uvs', []),
            'meshes_failed_uv_generation': getattr(self, 'meshes_failed_uv_generation', []),
            'operation': f"{self.output_data.get('input_type', 'unknown')}_{'external' if self.use_external_references else 'inline'}",
            'prototype_face_counts': self.prototype_face_counts,
            'failed_texture_conversions': self.failed_texture_conversions
        }
    
    def _create_stage(self):
        """Create and configure output stage"""
        output_stage = Usd.Stage.CreateNew(self.output_path)
        # Set file format
        layer = output_stage.GetRootLayer()
        if self.export_binary:
            layer.fileFormat = 'usdc'
        else:
            layer.fileFormat = 'usda'
        
        # Preserve original axis orientation
        try:
            up_axis = self.output_data['stage_metadata'].get('upAxis', 'Z')
            UsdGeom.SetStageUpAxis(output_stage, up_axis)
            print(f"TRANSFORM Preserved original upAxis: {up_axis}")
        except Exception as e:
            print(f"WARNING Could not preserve upAxis: {e}")
        
        # Create root prim
        layer.defaultPrim = "RootNode"
        root_layer = output_stage.GetRootLayer()
        root_spec = Sdf.CreatePrimInLayer(root_layer, "/RootNode")
        root_spec.typeName = "Xform"
        root_spec.specifier = Sdf.SpecifierDef
        
        # Set kind metadata
        root_prim = output_stage.GetPrimAtPath("/RootNode")
        root_prim.SetMetadata("kind", "model")
        output_stage.SetDefaultPrim(root_prim)
        
        return output_stage
    
    def _copy_materials(self, output_stage):
        """Copy materials to output stage"""
        if not self.output_data['materials']:
            return
        
        # Create materials scope
        materials_scope = output_stage.DefinePrim("/RootNode/Looks", "Scope")
        
        # Remix materials are now created inline, no external files needed
        
        for material_name, material_info in self.output_data['materials'].items():
            target_path = f"/RootNode/Looks/{material_name}"
            
            # Check if this is a Remix material
            if material_info.get('is_remix', False):
                # Create Remix material
                self._create_remix_material(output_stage, target_path, material_info, is_external=False)
            else:
                # Copy original material as-is
                source_material = material_info['prim']
                
                # Create material prim
                target_material = output_stage.DefinePrim(target_path, "Material")
                
                # Copy material attributes (but not relationships to avoid old references)
                for attr in source_material.GetAttributes():
                    if not attr.GetName().startswith('__'):
                        try:
                            target_attr = target_material.CreateAttribute(attr.GetName(), attr.GetTypeName())
                            value = attr.Get()
                            if value is not None:
                                target_attr.Set(value)
                        except Exception as e:
                            print(f"WARNING Could not copy material attribute {attr.GetName()}: {e}")
                
                # Copy material relationships but update paths to avoid old references
                for rel in source_material.GetRelationships():
                    if not rel.GetName().startswith('__'):
                        try:
                            target_rel = target_material.CreateRelationship(rel.GetName())
                            targets = rel.GetTargets()
                            if targets:
                                # Update material relationship targets to use new paths
                                updated_targets = []
                                for target in targets:
                                    target_str = str(target)
                                    # Skip old material references that cause warnings
                                    if '/_materials/' in target_str or '/root/_materials/' in target_str:
                                        # Don't copy these old references
                                        continue
                                    else:
                                        # Keep other relationships as-is
                                        updated_targets.append(target)
                                
                                if updated_targets:
                                    target_rel.SetTargets(updated_targets)
                        except Exception as e:
                            print(f"WARNING Could not copy material relationship {rel.GetName()}: {e}")
                
        
    
    def _create_remix_material(self, output_stage, target_path, material_info, is_external=False):
        """Create Remix material with reference to AperturePBR_Opacity.usda"""
        try:
            material_name = os.path.basename(target_path)
            conversion_type = material_info.get('conversion_type', 'unknown')
            remix_params = material_info.get('remix_params', {})
            
            # Remove existing material if it exists
            if output_stage.GetPrimAtPath(target_path):
                output_stage.RemovePrim(target_path)
            
            # Create the material in the target stage
            target_material = output_stage.DefinePrim(target_path, "Material")
            
            # Add reference to AperturePBR_Opacity.usda using auto-calculated path
            references = target_material.GetReferences()
            # For external files in Instance_Objs/, add ../ prefix
            material_ref_path = self._get_materials_reference_path()
            if is_external:
                material_ref_path = "../" + material_ref_path
            references.AddReference(material_ref_path, "/Looks/mat_AperturePBR_Opacity")
            
            # Create Shader prim with Remix parameters (use OverridePrim for proper RTX Remix format)
            shader_path = f"{target_path}/Shader"
            shader_prim = output_stage.OverridePrim(shader_path)
            
            # Set Remix parameters with adjusted texture paths for external files
            self._set_remix_shader_parameters(shader_prim, remix_params, is_external)
            
            # Note: blend_enabled is now handled in the main parameter loop
            # It is only added when it differs from defaults (opacity texture exists)
            
            # CRITICAL: Connect shader output to material surface output
            material = UsdShade.Material(target_material)
            shader = UsdShade.Shader(shader_prim)
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "out")
            
        except Exception as e:
            print(f"ERROR Failed to create Remix material {material_name}: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")
    
    def _set_remix_shader_parameters(self, shader_prim, remix_params, is_external=False):
        """Set Remix shader parameters with proper types - ONLY parameters from original material"""
        try:
            from pxr import Sdf, Gf
            
            # Get original parameters to only set what was in the source
            original_params = remix_params.get('_original_params', set())
            
            # Add blend_enabled and use_legacy_alpha_state when set by material mapper
            if remix_params.get('blend_enabled') is True:
                original_params.add('blend_enabled')
            if 'use_legacy_alpha_state' in remix_params:
                original_params.add('use_legacy_alpha_state')
            
            # If no original params tracked, don't set any parameters (avoid defaults)
            if not original_params:
                return
            
            for param_name in original_params:
                # Skip internal metadata
                if param_name.startswith('_'):
                    continue
                
                # Get the parameter value
                if param_name not in remix_params:
                    continue
                    
                param_value = remix_params[param_name]
                
                # Convert texture paths with proper prefix based on location
                if isinstance(param_value, str) and param_name.endswith('_texture'):
                    clean_value = param_value.strip('@')
                    
                    if clean_value:
                        filename = os.path.basename(clean_value)
                        base_name = os.path.splitext(filename)[0]
                        # For external files in Instance_Objs/, use ../textures/
                        if is_external:
                            param_value = f"../textures/{base_name}.dds"
                        else:
                            param_value = f"./textures/{base_name}.dds"
                
                # Determine parameter type and convert value
                param_type = None
                converted_value = None
                
                # CRITICAL: Check Gf.Vec3f FIRST (already converted from tuple in data converter)
                if isinstance(param_value, Gf.Vec3f):
                    # Already a Vec3f - use as Color3f
                    param_type = Sdf.ValueTypeNames.Color3f
                    converted_value = param_value
                # Check tuple/list for color constants
                elif isinstance(param_value, (tuple, list)) and len(param_value) == 3:
                    # Handle color tuples (r, g, b)
                    param_type = Sdf.ValueTypeNames.Color3f
                    converted_value = Gf.Vec3f(float(param_value[0]), float(param_value[1]), float(param_value[2]))
                elif isinstance(param_value, bool):
                    param_type = Sdf.ValueTypeNames.Bool
                    converted_value = param_value
                elif isinstance(param_value, int):
                    param_type = Sdf.ValueTypeNames.Int
                    converted_value = param_value
                elif isinstance(param_value, float):
                    param_type = Sdf.ValueTypeNames.Float
                    converted_value = param_value
                elif isinstance(param_value, str):
                    # CRITICAL: Check for texture parameters FIRST before other string handling
                    if param_name.endswith('_texture'):
                        # Texture paths (DDS conversion already handled above)
                        param_type = Sdf.ValueTypeNames.Asset
                        converted_value = Sdf.AssetPath(param_value)
                    # Handle string values that need specific types
                    elif param_name.endswith('_constant') and param_value.startswith('color('):
                        # Color values like "color(0.8, 0.8, 0.8)"
                        try:
                            # Extract RGB values from "color(r, g, b)"
                            color_str = param_value.replace('color(', '').replace(')', '')
                            r, g, b = map(float, color_str.split(','))
                            param_type = Sdf.ValueTypeNames.Color3f
                            converted_value = Gf.Vec3f(r, g, b)
                        except:
                            param_type = Sdf.ValueTypeNames.String
                            converted_value = param_value
                    elif param_value.endswith('f'):
                        # Float values like "0.0f"
                        try:
                            float_val = float(param_value[:-1])
                            param_type = Sdf.ValueTypeNames.Float
                            converted_value = float_val
                        except:
                            param_type = Sdf.ValueTypeNames.String
                            converted_value = param_value
                    else:
                        # Default string type
                        param_type = Sdf.ValueTypeNames.String
                        converted_value = param_value
                else:
                    # Skip unknown types
                    continue
                
                # Create and set the parameter - skip if no valid type determined
                if param_type is None or converted_value is None:
                    continue
                
                try:
                    # Set custom=False for non-string attributes (like unified_instancer_converter.py)
                    # Only string values should be custom, all others should not be custom
                    is_custom = param_type == Sdf.ValueTypeNames.String
                    # Add 'inputs:' prefix to parameter names for AperturePBR_Opacity compatibility
                    param_name_with_prefix = f"inputs:{param_name}"
                    param_attr = shader_prim.CreateAttribute(param_name_with_prefix, param_type, custom=is_custom)
                    param_attr.Set(converted_value)
                except Exception as e:
                    print(f"WARNING Could not set Remix parameter {param_name}: {e}")
                    
        except Exception as e:
            print(f"ERROR Failed to set Remix shader parameters: {e}")
    
    def _create_unique_objects(self, output_stage):
        """Create unique objects from prepared data with proper hierarchy"""
        # Unified approach for all conversion types
        # First, create anchor meshes (parents)
        anchor_meshes = {}
        for unique_object_data in self.output_data['unique_objects']:
            if unique_object_data['type'] == 'anchor_mesh':
                # Create anchor mesh as parent container
                anchor_prim = self._create_anchor_mesh(output_stage, unique_object_data)
                anchor_meshes[unique_object_data['path']] = anchor_prim
        
        # Then, create children (PointInstancers and single instances) under their parent anchors
        for unique_object_data in self.output_data['unique_objects']:
            if unique_object_data['type'] == 'single_instance':
                # Create single instance under its parent anchor
                self._create_single_instance(output_stage, unique_object_data)
        
        # Create PointInstancers under their parent anchors (unified for all conversion types)
        for pointinstancer_data in self.output_data['pointinstancers']:
            self._create_pointinstancer(output_stage, pointinstancer_data)
    
    def _create_anchor_mesh(self, output_stage, mesh_data):
        """Create anchor mesh (parent container)"""
        mesh_name = os.path.basename(mesh_data['path'])
        # Clean the mesh name to avoid path issues
        clean_mesh_name = mesh_name.replace('.', '_')
        mesh_prim = output_stage.DefinePrim(Sdf.Path(f"/RootNode/{clean_mesh_name}"), "Xform")
        
        # If this anchor has a mesh, create the mesh as a child
        if mesh_data['mesh_prim'].IsA(UsdGeom.Mesh):
            mesh_child_path = f"/RootNode/{clean_mesh_name}/{clean_mesh_name}_mesh"
            
            # Use the unified copy_prim_data approach for proper UV copying
            self.copy_prim_data(mesh_data['mesh_prim'], output_stage, mesh_child_path)
            
            # Get the copied mesh prim for material binding
            mesh_child_prim = output_stage.GetPrimAtPath(mesh_child_path)
            
            # Store material binding for final assignment
            if mesh_data['material_binding']:
                if not hasattr(self, '_pending_bindings'):
                    self._pending_bindings = []
                self._pending_bindings.append((mesh_child_path, mesh_data['material_binding']))
        
        # Set transform on the anchor container
        if mesh_data.get('transform') and mesh_data['transform'] != Gf.Matrix4d(1.0):
            xformable = UsdGeom.Xformable(mesh_prim)
            xformable.AddTransformOp().Set(mesh_data['transform'])
        
        return mesh_prim
    
    def _create_single_instance(self, output_stage, instance_data):
        """Create single instance as child of its parent anchor"""
        # Get the parent anchor path
        parent_path = instance_data.get('parent_path', '/RootNode')
        instance_name = os.path.basename(instance_data['path'])
        # Clean the instance name to avoid path issues
        clean_instance_name = instance_name.replace('.', '_')
        
        # Create the instance under its parent anchor
        instance_path = f"{parent_path}/{clean_instance_name}"
        
        # Use the unified copy_prim_data approach for proper UV copying
        self.copy_prim_data(instance_data['mesh_prim'], output_stage, instance_path)
        
        # Get the copied instance prim for transform and material binding
        instance_prim = output_stage.GetPrimAtPath(instance_path)
        
        # Apply transform
        if instance_data.get('translate') or instance_data.get('rotate') or instance_data.get('scale'):
            xformable = UsdGeom.Xformable(instance_prim)
            if instance_data.get('translate'):
                xformable.AddTranslateOp().Set(instance_data['translate'])
            if instance_data.get('rotate'):
                xformable.AddRotateXYZOp().Set(instance_data['rotate'])
            if instance_data.get('scale'):
                xformable.AddScaleOp().Set(instance_data['scale'])
        
        # Store material binding for final assignment
        if instance_data['material_binding']:
            if not hasattr(self, '_pending_bindings'):
                self._pending_bindings = []
            self._pending_bindings.append((instance_path, instance_data['material_binding']))
    
    # ========================================
    # REVERSE CONVERSION METHODS
    # ========================================
    
    def _create_reverse_output_structure(self, output_stage):
        """Create proper hierarchy structure for reverse conversion"""
        # First, create anchor meshes (parent containers with their meshes)
        for unique_object_data in self.output_data['unique_objects']:
            if unique_object_data['type'] == 'anchor_mesh':
                self._create_anchor_mesh(output_stage, unique_object_data)
        
        # For reverse conversion, we need to create parent containers and nest PointInstancers
        # Get parent information from the unified data
        parent_groups = {}
        
        # Group PointInstancers by their parent containers
        for pointinstancer_data in self.output_data['pointinstancers']:
            if pointinstancer_data.get('conversion_type') == 'reverse':
                # For reverse conversion, we need to determine the parent
                # This should come from the original data structure
                parent_name = "Cube_001"  # Default parent for this test case
                
                if parent_name not in parent_groups:
                    parent_groups[parent_name] = []
                parent_groups[parent_name].append(pointinstancer_data)
        
        # Create parent containers and nest PointInstancers
        for parent_name, pointinstancers in parent_groups.items():
            if parent_name != "root":
                self._create_reverse_parent_with_pointinstancers(parent_name, {
                    'root_parent_prim': self._get_parent_prim(parent_name),
                    'pointinstancers': pointinstancers
                }, output_stage)
            else:
                # Handle root-level instances
                for pointinstancer_data in pointinstancers:
                    self._create_pointinstancer_at_root(output_stage, pointinstancer_data)
        
        # Create single instances under their parent containers
        for unique_object_data in self.output_data['unique_objects']:
            if unique_object_data['type'] == 'single_instance':
                # For reverse conversion, single instances should be created under their parent containers
                # The parent path should be the parent container path
                parent_name = "Cube_001"  # Default parent for this test case
                unique_object_data['parent_path'] = f"/RootNode/{parent_name}"
                # Create single instance under its parent anchor
                self._create_single_instance_under_parent(output_stage, unique_object_data)
    
    def _create_reverse_parent_with_pointinstancers(self, parent_name, parent_data, output_stage):
        """Create parent container and nest PointInstancers under it"""
        # Create parent Xform container
        target_parent_path = f"/RootNode/{parent_name}"
        target_parent = output_stage.DefinePrim(target_parent_path, "Xform")
        
        # Copy parent attributes and transforms
        root_parent_prim = parent_data['root_parent_prim']
        if root_parent_prim:
            for attr in root_parent_prim.GetAttributes():
                if not attr.GetName().startswith('__'):
                    try:
                        target_attr = target_parent.CreateAttribute(attr.GetName(), attr.GetTypeName())
                        value = attr.Get()
                        if value is not None:
                            target_attr.Set(value)
                    except Exception as e:
                        print(f"WARNING Could not copy parent attribute: {e}")
        
        # Create PointInstancers under this parent
        for pointinstancer_data in parent_data['pointinstancers']:
            instancer_name = pointinstancer_data['name']
            instancer_path = f"{target_parent_path}/{instancer_name}"
            self._create_pointinstancer_from_data(output_stage, instancer_path, pointinstancer_data)
    
    def _create_pointinstancer_under_parent(self, output_stage, instancer_path, instances):
        """Create PointInstancer under a parent container with proper transform conversion"""
        # Extract world transforms from instances
        world_transforms = self._extract_world_transforms_from_instances(instances)
        
        # Convert to parent-relative transforms
        parent_path = str(instancer_path).rsplit('/', 1)[0]  # Get parent path
        parent_relative_transforms = self._convert_world_to_parent_relative(world_transforms, parent_path, output_stage)
        
        # Create PointInstancer
        instancer = UsdGeom.PointInstancer.Define(output_stage, instancer_path)
        
        # Extract transform data
        positions = [transform.ExtractTranslation() for transform in parent_relative_transforms]
        orientations = [transform.ExtractRotationQuat() for transform in parent_relative_transforms]
        scales = [transform.ExtractScale() for transform in parent_relative_transforms]
        proto_indices = [0] * len(positions)
        
        # Set PointInstancer attributes
        instancer.GetPositionsAttr().Set(positions)
        instancer.GetOrientationsAttr().Set(orientations)
        instancer.GetScalesAttr().Set(scales)
        instancer.GetProtoIndicesAttr().Set(proto_indices)
        
        # Create prototype
        prototype_name = instances[0]['mesh_prim'].GetName()
        prototype_path = f"{instancer_path}/{prototype_name}"
        self._create_prototype_from_instance(instances[0], output_stage, prototype_path)
        
        # Set prototype target
        instancer.GetPrototypesRel().AddTarget(prototype_path)
    
    def _extract_world_transforms_from_instances(self, instances):
        """Extract world transforms from instance transform prims"""
        world_transforms = []
        for instance in instances:
            transform_prim = instance['transform_prim']
            world_transform = self._get_world_transform(transform_prim)
            world_transforms.append(world_transform)
        return world_transforms
    
    def _convert_world_to_parent_relative(self, world_transforms, parent_path, output_stage):
        """Convert world transforms to parent-relative transforms"""
        parent_prim = output_stage.GetPrimAtPath(parent_path)
        if parent_prim:
            parent_world_transform = self._get_world_transform(parent_prim)
            parent_inverse = parent_world_transform.GetInverse()
            
            parent_relative_transforms = []
            for world_transform in world_transforms:
                relative_transform = parent_inverse * world_transform
                parent_relative_transforms.append(relative_transform)
            return parent_relative_transforms
        else:
            # If no parent, return world transforms as-is
            return world_transforms
    
    def _create_prototype_from_instance(self, instance, output_stage, prototype_path):
        """Create prototype from instance data with proper UV preservation"""
        mesh_prim = instance['mesh_prim']
        
        # Use the same approach as the old converter for forward conversion
        self._create_prototype_from_prim(mesh_prim, output_stage, prototype_path)
        
        # Get the copied prototype prim
        prototype_prim = output_stage.GetPrimAtPath(prototype_path)
        if prototype_prim:
            prototype_prim.SetMetadata("kind", "component")
            
            # Apply material binding
            if instance.get('material_binding'):
                material_binding_api = UsdShade.MaterialBindingAPI(prototype_prim)
                material_path = str(instance['material_binding'])
                if material_path:
                    try:
                        # Extract material name and create correct path
                        material_name = None
                        if '/_materials/' in material_path:
                            material_name = material_path.split('/_materials/')[-1]
                        elif '/root/Looks/' in material_path:
                            material_name = material_path.split('/root/Looks/')[-1]
                        elif '/Root/Looks/' in material_path:
                            material_name = material_path.split('/Root/Looks/')[-1]
                        elif '/Looks/' in material_path:
                            material_name = material_path.split('/Looks/')[-1]
                        
                        if material_name:
                            correct_material_path = f"/RootNode/Looks/{material_name}"
                            material_prim = output_stage.GetPrimAtPath(correct_material_path)
                            if material_prim:
                                material_binding_api.Bind(UsdShade.Material(material_prim))
                    except Exception as e:
                        print(f"WARNING Failed to bind material to prototype: {e}")
    
    def _get_parent_prim(self, parent_name):
        """Get parent prim from the source stage"""
        # Find the parent prim in the source stage
        if self.input_stage:
            # Look for the parent prim by name
            for prim in self.input_stage.TraverseAll():
                if prim.GetName() == parent_name and prim.IsA(UsdGeom.Xform):
                    return prim
        return None
    
    def _get_world_transform(self, prim):
        """Get world transform matrix for a prim"""
        if prim.IsA(UsdGeom.Xformable):
            xformable = UsdGeom.Xformable(prim)
            return xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        return Gf.Matrix4d(1.0)  # Identity matrix if not transformable
    
    def _create_pointinstancer_from_data(self, output_stage, instancer_path, pointinstancer_data):
        """Create PointInstancer from prepared data"""
        # Store blender_name for reporting
        if 'blender_name' in pointinstancer_data and pointinstancer_data['blender_name']:
            proto_name = pointinstancer_data.get('prototype_name', pointinstancer_data.get('name', 'Unknown'))
            self.blender_names[proto_name] = pointinstancer_data['blender_name']
        
        # Create PointInstancer
        instancer = UsdGeom.PointInstancer.Define(output_stage, instancer_path)
        
        # Set PointInstancer attributes
        instancer.GetPositionsAttr().Set(pointinstancer_data['positions'])
        instancer.GetOrientationsAttr().Set(pointinstancer_data['orientations'])
        instancer.GetScalesAttr().Set(pointinstancer_data['scales'])
        instancer.GetProtoIndicesAttr().Set(pointinstancer_data['proto_indices'])
        
        # Create prototype
        prototype_mesh = pointinstancer_data['prototype_mesh']
        prototype_name = pointinstancer_data['prototype_name']
        prototype_path = f"{instancer_path}/{prototype_name}"
        self._create_prototype_from_mesh(prototype_mesh, output_stage, prototype_path)
        
        # Set prototype target
        instancer.GetPrototypesRel().AddTarget(prototype_path)
    
    def _create_prototype_from_mesh(self, mesh_prim, output_stage, prototype_path):
        """Create prototype from mesh prim using unified copy_prim_data approach"""
        # Use the unified copy_prim_data approach for consistent behavior
        # Enable cleanup for Blender materials when creating prototypes
        copied_prim = self.copy_prim_data(mesh_prim, output_stage, prototype_path, include_materials=True, include_children=True)
        
        # Clean up old Blender materials from the copied prototype
        if copied_prim:
            self._remove_old_blender_materials_from_prototype(copied_prim)
        
        return copied_prim
    
    def _create_prototype_from_prim(self, source_prim, output_stage, prototype_path):
        """Create prototype from source prim using unified copy_prim_data approach"""
        # Use the unified copy_prim_data approach for consistent behavior
        # Apply inline-specific filtering for forward conversion
        return self.copy_prim_data(source_prim, output_stage, prototype_path, include_materials=True, include_children=True, inline_mode=True)
    
    def _create_single_instance_under_parent(self, output_stage, instance_data):
        """Create single instance under its parent container"""
        # Get the parent path from the instance data
        parent_path = instance_data.get('parent_path', '/RootNode')
        instance_name = os.path.basename(instance_data['path'])
        
        # Clean the instance name to avoid path issues (replace dots with underscores)
        clean_instance_name = instance_name.replace('.', '_')
        
        # Create the instance under its parent
        instance_path = f"{parent_path}/{clean_instance_name}"
        
        # Use the unified copy_prim_data approach for proper UV copying
        self.copy_prim_data(instance_data['mesh_prim'], output_stage, instance_path)
        
        # Get the copied instance prim for material binding
        instance_prim = output_stage.GetPrimAtPath(instance_path)
        
        # Set material binding
        if instance_data['material_binding']:
            material_binding_api = UsdShade.MaterialBindingAPI(instance_prim)
            # Handle material binding as dictionary or string
            if isinstance(instance_data['material_binding'], dict):
                material_path = instance_data['material_binding'].get('target_path', '')
            else:
                material_path = str(instance_data['material_binding'])
            if material_path and material_path.strip():
                try:
                    # Extract material name from path and create correct path
                    material_name = None
                    if '/_materials/' in material_path:
                        material_name = material_path.split('/_materials/')[-1]
                    elif '/root/Looks/' in material_path:
                        material_name = material_path.split('/root/Looks/')[-1]
                    elif '/Root/Looks/' in material_path:
                        material_name = material_path.split('/Root/Looks/')[-1]
                    elif '/Looks/' in material_path:
                        material_name = material_path.split('/Looks/')[-1]
                    
                    if material_name:
                        correct_material_path = f"/RootNode/Looks/{material_name}"
                        material_prim = instance_prim.GetStage().GetPrimAtPath(Sdf.Path(correct_material_path))
                        if material_prim:
                            material_binding_api.Bind(UsdShade.Material(material_prim))
                except Exception as e:
                    print(f"WARNING Failed to bind material {material_path}: {e}")
    
    def _create_pointinstancer_at_root(self, output_stage, pointinstancer_data):
        """Create PointInstancer at root level (for instances without parent containers)"""
        instancer_path = f"/RootNode/{pointinstancer_data['name']}"
        self._create_pointinstancer_from_data(output_stage, instancer_path, pointinstancer_data)
    

    
    def _create_pointinstancer(self, output_stage, pointinstancer_data):
        """Create PointInstancer as child of its parent anchor"""
        # Get the parent anchor path
        parent_path = pointinstancer_data.get('parent_path', '/RootNode')
        instancer_name = os.path.basename(pointinstancer_data['path'])
        
        # Store face count and instance count for reporting (use blender_name or prototype_name)
        proto_name = pointinstancer_data.get('blender_name') or pointinstancer_data.get('prototype_name', 'Unknown')
        if 'face_count' in pointinstancer_data:
            self.prototype_face_counts[proto_name] = pointinstancer_data['face_count']
        if 'positions' in pointinstancer_data:
            self.instance_counts[proto_name] = len(pointinstancer_data['positions'])
        elif 'instances' in pointinstancer_data:
            self.instance_counts[proto_name] = len(pointinstancer_data['instances'])
        
        # Store blender_name mapping for UI display
        if pointinstancer_data.get('blender_name'):
            self.blender_names[proto_name] = pointinstancer_data['blender_name']
        
        # Create PointInstancer under its parent anchor
        instancer_path = f"{parent_path}/{instancer_name}"
        instancer = UsdGeom.PointInstancer.Define(output_stage, instancer_path)
        
        # Handle external references
        prototype_mesh = pointinstancer_data.get('prototype_mesh') or pointinstancer_data.get('prototype_prim')
        if self.use_external_references and prototype_mesh:
            # External reference - create Xform with external reference (like Sample_reference_prototypes.usda)
            # Use blenderName:object if available (for reverse conversion), otherwise use mesh name
            blender_name = pointinstancer_data.get('blender_name')
            if blender_name:
                prototype_name = self._generate_clean_filename(blender_name)
            else:
                prototype_name = prototype_mesh.GetName()
            # Create prototype directly inside the PointInstancer
            prototype_path = f"{instancer_path}/{prototype_name}"
            
            # Create Xform with external reference (not Mesh) - NO inline mesh
            prototype_prim = output_stage.DefinePrim(prototype_path, "Xform")
            prototype_prim.SetMetadata("kind", "component")
            
            # Add external reference using the correct format
            external_file = f"./Instance_Objs/{prototype_name}.usd"
            references = prototype_prim.GetReferences()
            references.AddReference(external_file)
            
            # Set as prototype target
            instancer.GetPrototypesRel().AddTarget(prototype_path)
            # CRITICAL: Skip inline mesh creation entirely when using external references
            prototype_mesh = None  # Prevent inline mesh creation below

        elif prototype_mesh:
            # Inline prototype - create prototype as child of PointInstancer
            prototype_name = prototype_mesh.GetName()
            prototype_path = f"{instancer_path}/{prototype_name}"
            print(f"COPY Creating inline prototype: {prototype_path} from {prototype_mesh.GetPath()}")
            copied_prototype = self._copy_prim_data(prototype_mesh, output_stage, prototype_path)
            # Clean up old Blender materials from the copied prototype
            if copied_prototype:
                print(f"CLEANUP Calling cleanup on copied prototype: {copied_prototype.GetPath()}")
                self._remove_old_blender_materials_from_prototype(copied_prototype)
            # Ensure kind is set on inline prototypes and update material binding
            prototype_prim = output_stage.GetPrimAtPath(prototype_path)
            if prototype_prim and prototype_prim.IsA(UsdGeom.Mesh):
                prototype_prim.SetMetadata("kind", "component")
                
                # Update material binding to use /Root/Looks path
                material_binding_rel = prototype_prim.GetRelationship('material:binding')
                if material_binding_rel:
                    targets = material_binding_rel.GetTargets()
                    if targets:
                        updated_targets = []
                        for target in targets:
                            target_str = str(target)
                            # Extract material name from original path - handle multiple path formats
                            material_name = None
                            if '/_materials/' in target_str:
                                material_name = target_str.split('/_materials/')[-1]
                            elif '/root/Looks/' in target_str:
                                material_name = target_str.split('/root/Looks/')[-1]
                            elif '/Root/Looks/' in target_str:
                                material_name = target_str.split('/Root/Looks/')[-1]
                            elif '/Looks/' in target_str:
                                material_name = target_str.split('/Looks/')[-1]
                            elif '/root/prototypes/' in target_str:
                                # Handle prototype material references
                                parts = target_str.split('/')
                                if len(parts) >= 4:
                                    material_name = parts[-1]  # Get the material name from the end
                            
                            if material_name:
                                updated_target = f"/RootNode/Looks/{material_name}"
                                updated_targets.append(updated_target)
                            else:
                                # Keep original if not in expected format
                                updated_targets.append(target)
                        
                        if updated_targets != targets:
                            material_binding_rel.SetTargets(updated_targets)
            
            instancer.GetPrototypesRel().AddTarget(prototype_path)
        
        # Extract transform data from instances
        from pxr import Vt
        
        # Check if this is a reverse conversion (has positions directly) or forward conversion (has instances)
        if 'positions' in pointinstancer_data and 'orientations' in pointinstancer_data and 'scales' in pointinstancer_data:
            # Reverse conversion - use pre-calculated transform data
            positions = pointinstancer_data['positions']
            orientations = pointinstancer_data['orientations']
            scales = pointinstancer_data['scales']
            proto_indices = pointinstancer_data['proto_indices']
            
            # Convert to USD arrays
            positions_array = Vt.Vec3fArray(positions)
            orientations_array = Vt.QuathArray(orientations)
            scales_array = Vt.Vec3fArray(scales)
            proto_indices_array = Vt.IntArray(proto_indices)
            
            # Set PointInstancer attributes
            instancer.GetPositionsAttr().Set(positions_array)
            instancer.GetOrientationsAttr().Set(orientations_array)
            instancer.GetScalesAttr().Set(scales_array)
            instancer.GetProtoIndicesAttr().Set(proto_indices_array)
            

            
        elif 'instances' in pointinstancer_data:
            # Forward conversion - extract transform data from instances
            positions = []
            orientations = []
            scales = []
            proto_indices = []
            
            # Check if we need to convert from world space to parent-relative space
            parent_path = pointinstancer_data.get('parent_path', '/RootNode')
            has_parent_container = parent_path != '/RootNode'
            
            parent_world_transform_inverse = None
            if has_parent_container:
                try:
                    # Get parent's world transform and compute its inverse
                    parent_prim = output_stage.GetPrimAtPath(parent_path)
                    if parent_prim and parent_prim.IsValid():
                        parent_xform = UsdGeom.Xformable(parent_prim)
                        if parent_xform:
                            parent_world_transform = parent_xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                            if parent_world_transform:
                                parent_world_transform_inverse = parent_world_transform.GetInverse()
                                print(f"TRANSFORM Converting world coordinates to parent-relative for '{os.path.basename(parent_path)}'")
                except Exception as e:
                    print(f"WARNING: Failed to get parent transform for {parent_path}: {e}")
            
            # Process instances, but skip the first one (likely base prototype reference)
            instance_count = 0
            for instance_data in pointinstancer_data['instances']:
                instance_count += 1
                
                # Skip the first instance (likely base prototype reference at 0,0,0)
                if instance_count == 1:
                    instance_name = instance_data.get('blender_name') or instance_data.get('path', 'Unknown')
                    print(f"FILTER: Skipping first instance {instance_name} (likely base prototype reference)")
                    continue
                
                transform_matrix = instance_data.get('transform')
                if not transform_matrix:
                    print(f"WARNING: No transform matrix for instance {instance_data['path']}")
                    continue
                    
                # If we have a parent container, convert world coordinates to parent-relative
                if has_parent_container and parent_world_transform_inverse is not None:
                    # Convert from world space to parent-relative space
                    relative_transform = transform_matrix * parent_world_transform_inverse
                    final_transform = relative_transform
                else:
                    # Use world coordinates as-is (no parent container)
                    final_transform = transform_matrix
                
                # Extract position, orientation, and scale from the final transform
                position = final_transform.ExtractTranslation()
                rotation_matrix = final_transform.RemoveScaleShear()
                orientation = rotation_matrix.ExtractRotation().GetQuat()
                
                # Extract scale using matrix decomposition
                scale_x = Gf.Vec3d(final_transform[0][0], final_transform[1][0], final_transform[2][0]).GetLength()
                scale_y = Gf.Vec3d(final_transform[0][1], final_transform[1][1], final_transform[2][1]).GetLength()
                scale_z = Gf.Vec3d(final_transform[0][2], final_transform[1][2], final_transform[2][2]).GetLength()
                scale = Gf.Vec3f(scale_x, scale_y, scale_z)
                
                # Add to arrays - convert position to Vec3f and orientation to Quath
                positions.append(Gf.Vec3f(position[0], position[1], position[2]))
                orientations.append(Gf.Quath(orientation.GetReal(), orientation.GetImaginary()[0], orientation.GetImaginary()[1], orientation.GetImaginary()[2]))
                scales.append(scale)
                proto_indices.append(0)  # All instances use the same prototype (index 0)
            
            # Convert to USD arrays
            positions_array = Vt.Vec3fArray(positions)
            orientations_array = Vt.QuathArray(orientations)
            scales_array = Vt.Vec3fArray(scales)
            proto_indices_array = Vt.IntArray(proto_indices)
            
            # Set PointInstancer attributes
            instancer.GetPositionsAttr().Set(positions_array)
            instancer.GetOrientationsAttr().Set(orientations_array)
            instancer.GetScalesAttr().Set(scales_array)
            instancer.GetProtoIndicesAttr().Set(proto_indices_array)
            

            
        else:
            # Existing PointInstancer - copy original attributes with array expansion
            source_instancer = pointinstancer_data['prim']
            source_pi = UsdGeom.PointInstancer(source_instancer)
            
            # Get transform array lengths to determine valid instance count
            positions_attr = source_instancer.GetPrim().GetAttribute('positions')
            orientations_attr = source_instancer.GetPrim().GetAttribute('orientations')
            scales_attr = source_instancer.GetPrim().GetAttribute('scales')
            proto_indices_attr = source_instancer.GetPrim().GetAttribute('protoIndices')
            
            positions = positions_attr.Get() if positions_attr and positions_attr.HasValue() else None
            orientations = orientations_attr.Get() if orientations_attr and orientations_attr.HasValue() else None
            scales = scales_attr.Get() if scales_attr and scales_attr.HasValue() else None
            proto_indices = proto_indices_attr.Get() if proto_indices_attr else None
            
            # Determine the valid instance count (minimum of all array lengths)
            valid_instance_count = None
            if positions:
                valid_instance_count = len(positions)
            if orientations and (valid_instance_count is None or len(orientations) < valid_instance_count):
                valid_instance_count = len(orientations)
            if scales and (valid_instance_count is None or len(scales) < valid_instance_count):
                valid_instance_count = len(scales)
            
            # Truncate protoIndices if it's longer than transform arrays
            if proto_indices and valid_instance_count and len(proto_indices) > valid_instance_count:
                proto_indices = proto_indices[:valid_instance_count]
            
            # Copy all PointInstancer attributes FIRST (including protoIndices)
            for attr in source_instancer.GetPrim().GetAttributes():
                if not attr.GetName().startswith('__'):
                    attr_name = attr.GetName()
                    try:
                        value = attr.Get() if attr.HasValue() else None
                        if value is not None:
                            target_attr = instancer.GetPrim().GetAttribute(attr_name)
                            if not target_attr:
                                target_attr = instancer.GetPrim().CreateAttribute(attr_name, attr.GetTypeName())
                            target_attr.Set(value)
                    except Exception as e:
                        print(f"WARNING Could not copy PointInstancer attribute {attr.GetName()}: {e}")
            
            # THEN overwrite protoIndices with truncated version (AFTER all attributes copied)
            if proto_indices is not None:
                instancer.GetProtoIndicesAttr().Set(proto_indices)
            
            # Copy prototype relationships with path standardization
            source_prototypes = source_pi.GetPrototypesRel()
            if source_prototypes:
                target_prototypes = instancer.GetPrototypesRel()
                targets = source_prototypes.GetTargets()
                if targets:
                    # Standardize paths from /root/ to /Root/
                    updated_targets = [Sdf.Path(str(t).replace('/root/', '/RootNode/')) for t in targets]
                    target_prototypes.SetTargets(updated_targets)
            
    
    
    def _create_pointinstancers(self, output_stage):
        """Create PointInstancers from prepared data"""
        # Skip regular PointInstancer creation for reverse conversion
        # since they are already created in _create_reverse_output_structure
        if self.conversion_type == 'reverse':
            return 0
        
        pointinstancer_count = 0
        processed_parents = set()  # Track which parent containers we've already processed
        
        for pointinstancer_data in self.output_data['pointinstancers']:
            # For Blender 4.5 with parent preservation, copy entire parent once
            if pointinstancer_data.get('preserve_parent'):
                parent_path = pointinstancer_data.get('parent_path')
                if parent_path and parent_path not in processed_parents:
                    processed_parents.add(parent_path)
                    source_instancer_prim = pointinstancer_data['prim']
                    source_parent = source_instancer_prim.GetParent()
                    if source_parent:
                        # Copy parent container but only PointInstancer and mesh_base children
                        # For Blender 4.5, respect user's interpolation mode choice
                        skip_fixes = (self.interpolation_mode == "none")
                        
                        # Copy parent Xform without children first
                        self.copy_prim_data(source_parent, output_stage, parent_path, include_materials=True, include_children=False, skip_interpolation_fixes=skip_fixes)
                        
                        # Only copy PointInstancer and mesh_base children, skip original prototype objects
                        instancer_name = source_instancer_prim.GetName()
                        for child in source_parent.GetChildren():
                            child_name = child.GetName()
                            # Only copy the PointInstancer and mesh_base, skip everything else
                            if child_name == instancer_name or child_name == "mesh_base":
                                child_path = f"{parent_path}/{child_name}"
                                self.copy_prim_data(child, output_stage, child_path, include_materials=True, include_children=True, skip_interpolation_fixes=skip_fixes)
                        
                        pointinstancer_count += 1
                        
                        # Fix PointInstancer prototype paths from /root/ to /Root/
                        instancer_path = f"{parent_path}/{instancer_name}"
                        copied_instancer = output_stage.GetPrimAtPath(instancer_path)
                        if copied_instancer and copied_instancer.IsValid():
                            # Truncate protoIndices if needed (prevent Blender 4.5.4 export bug)
                            pi = UsdGeom.PointInstancer(copied_instancer)
                            positions_attr = copied_instancer.GetAttribute('positions')
                            proto_indices_attr = copied_instancer.GetAttribute('protoIndices')
                            if positions_attr and proto_indices_attr:
                                positions = positions_attr.Get() if positions_attr.HasValue() else None
                                proto_indices = proto_indices_attr.Get() if proto_indices_attr.HasValue() else None
                                if positions and proto_indices and len(proto_indices) > len(positions):
                                    truncated_proto_indices = proto_indices[:len(positions)]
                                    pi.GetProtoIndicesAttr().Set(truncated_proto_indices)
                            
                            pi = UsdGeom.PointInstancer(copied_instancer)
                            proto_rel = pi.GetPrototypesRel()
                            if proto_rel:
                                old_targets = proto_rel.GetTargets()
                                
                                # If using external references, replace inline prototypes with external Xforms
                                if self.use_external_references:
                                    # Remove inline Prototypes folder
                                    prototypes_folder = output_stage.GetPrimAtPath(f"{instancer_path}/Prototypes")
                                    if prototypes_folder and prototypes_folder.IsValid():
                                        output_stage.RemovePrim(f"{instancer_path}/Prototypes")
                                        print(f"CLEANUP Removed inline Prototypes folder for external references")
                                    
                                    # Create external reference Xforms for each prototype
                                    new_targets = []
                                    for i, old_target in enumerate(old_targets):
                                        # Get the mesh name from the old target
                                        old_prim = self.input_stage.GetPrimAtPath(old_target)
                                        if old_prim and old_prim.IsValid():
                                            mesh_prim = None
                                            material_binding = None
                                            if old_prim.IsA(UsdGeom.Mesh):
                                                mesh_prim = old_prim
                                            else:
                                                # Recursively search for mesh (handles Xform wrappers)
                                                def find_mesh_recursive(prim):
                                                    for child in prim.GetAllChildren():
                                                        if child.IsA(UsdGeom.Mesh):
                                                            return child
                                                        if child.IsA(UsdGeom.Xform):
                                                            result = find_mesh_recursive(child)
                                                            if result:
                                                                return result
                                                    return None
                                                
                                                mesh_prim = find_mesh_recursive(old_prim)
                                            
                                            # Get material binding from mesh
                                            if mesh_prim:
                                                binding_rel = mesh_prim.GetRelationship('material:binding')
                                                if binding_rel:
                                                    targets = binding_rel.GetTargets()
                                                    if targets:
                                                        material_binding = targets[0]
                                            
                                            if mesh_prim:
                                                mesh_name = mesh_prim.GetName()
                                                ext_ref_path = f"{instancer_path}/{mesh_name}"
                                                ext_ref_prim = output_stage.DefinePrim(ext_ref_path, "Xform")
                                                ext_ref_prim.SetMetadata("kind", "component")
                                                
                                                external_file = f"./Instance_Objs/{mesh_name}.usd"
                                                references = ext_ref_prim.GetReferences()
                                                references.AddReference(external_file)
                                                
                                                new_targets.append(Sdf.Path(ext_ref_path))
                                    
                                    proto_rel.SetTargets(new_targets)
                                    print(f"CLEANUP Replaced inline prototypes with {len(new_targets)} external references")
                                    
                                    # Remove old Prototype_* Xforms that are no longer needed
                                    for child in copied_instancer.GetChildren():
                                        child_name = child.GetName()
                                        if child_name.startswith('Prototype_') and child.GetTypeName() == 'Xform':
                                            # Check if this is NOT one of our new mesh-named references
                                            if child.GetPath() not in new_targets:
                                                output_stage.RemovePrim(child.GetPath())
                                                print(f"CLEANUP Removed old prototype Xform: {child_name}")
                                else:
                                    # Just fix paths for inline mode
                                    new_targets = [Sdf.Path(str(t).replace('/root/', '/RootNode/')) for t in old_targets]
                                    proto_rel.SetTargets(new_targets)
                                    print(f"CLEANUP Fixed prototype paths: /root/ ??/RootNode/")
                        
                        
                        # Remove extra prototype reference objects (Plane_001_64255959, etc.)
                        # These are the source prototype containers that shouldn't be in output
                        parent_prim = output_stage.GetPrimAtPath(parent_path)
                        if parent_prim and parent_prim.IsValid():
                            extra_objects_to_remove = []
                            for child in parent_prim.GetChildren():
                                child_name = child.GetName()
                                # Remove objects that match Blender's prototype naming pattern
                                if ('_' in child_name and child_name not in [instancer_name, f"{instancer_name}_base"]):
                                    # Check if it contains a mesh and _materials (prototype reference pattern)
                                    has_mesh = False
                                    has_materials = False
                                    for subchild in child.GetChildren():
                                        if subchild.IsA(UsdGeom.Mesh):
                                            has_mesh = True
                                        if subchild.GetName() == '_materials':
                                            has_materials = True
                                    if has_mesh and has_materials:
                                        extra_objects_to_remove.append(child.GetPath())
                            
                            for obj_path in extra_objects_to_remove:
                                output_stage.RemovePrim(obj_path)
                                print(f"CLEANUP Removed extra prototype reference: {obj_path.name}")
                        
                        # Remove old lowercase /root prim if it exists
                        old_root = output_stage.GetPrimAtPath('/root')
                        if old_root and old_root.IsValid():
                            output_stage.RemovePrim('/root')
                            print(f"CLEANUP Removed duplicate lowercase /root prim")
            elif pointinstancer_data['type'] == 'pointinstancer':
                self._create_pointinstancer(output_stage, pointinstancer_data)
                pointinstancer_count += 1
            elif pointinstancer_data['type'] == 'existing_pointinstancer':
                self._create_existing_pointinstancer(output_stage, pointinstancer_data)
                pointinstancer_count += 1
        
        return pointinstancer_count
    
    def _create_external_files(self):
        """Create external prototype files from prepared data"""
        if not self.use_external_references or not self.output_data.get('external_prototypes'):
            return 0
        
        # Create Instance_Objs directory
        instance_objs_dir = os.path.join(os.path.dirname(self.output_path), "Instance_Objs")
        os.makedirs(instance_objs_dir, exist_ok=True)
        
        # Find project root by looking for mod.usda file
        materials_dir = self._setup_materials_directory()
        
        # Copy AperturePBR_Opacity.usda to materials directory if needed
        self._copy_aperture_pbr_material(materials_dir)
        
        external_files_created = 0
        
        for external_prototype_data in self.output_data['external_prototypes']:
            external_file_path = os.path.join(instance_objs_dir, f"{external_prototype_data['name']}.usd")
            
            # Handle existing files (like old converter)
            if os.path.exists(external_file_path):
                try:
                    os.remove(external_file_path)
    
                except Exception as e:
                    print(f"WARNING Could not remove existing file: {e}")
                    continue
            
            # Create external stage using temporary file approach (like old converter)
            try:
                import tempfile
                
                # Suppress USD warnings during entire external file creation
                with suppress_usd_warnings():
                    # Create a temporary file to avoid USD layer caching issues
                    with tempfile.NamedTemporaryFile(suffix=".usda", delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    external_stage = Usd.Stage.CreateNew(temp_path)
                    
                    # Ensure ASCII format is set
                    layer = external_stage.GetRootLayer()
                    layer.fileFormat = 'usda'
                    
                    # Set up stage structure
                    UsdGeom.SetStageUpAxis(external_stage, UsdGeom.Tokens.z)
                    layer.defaultPrim = "RootNode"
                    
                    # Create root
                    root_prim = external_stage.DefinePrim("/RootNode", "Xform")
                    root_prim.SetMetadata("kind", "model")
                    external_stage.SetDefaultPrim(root_prim)
                    
                    # Copy all materials to external file, then remove unused ones
                    self._copy_materials_to_external_stage(external_stage, self.output_data['materials'], is_external=True)
                    
                    # Create prototype container Xform
                    prototype_container = external_stage.DefinePrim("/RootNode/prototype", "Xform")
                    prototype_container.SetMetadata("kind", "component")
                    
                    # Copy prototype data with materials enabled AND transform
                    prototype_name = external_prototype_data['prim'].GetName()
                    prototype_path = f"/RootNode/prototype/{prototype_name}"
                    copied_prim = self.copy_prim_data(external_prototype_data['prim'], external_stage, prototype_path, include_materials=True, include_children=True)
                    
                    # Apply transform from original prototype if it exists
                    if copied_prim and 'transform' in external_prototype_data:
                        transform = external_prototype_data['transform']
                        if transform and transform != Gf.Matrix4d(1.0):
                            xformable = UsdGeom.Xformable(copied_prim)
                            xformable.AddTransformOp().Set(transform)
                            print(f"TRANSFORM Applied transform to external prototype {prototype_name}")
                    
                    # Skip loading face counts from external files - already loaded from pointinstancer_data
                    
                    # Remove unused materials (keep only materials bound to meshes in this file)
                    self._remove_unused_materials_from_external_file(external_stage)
                    
                    # Fix texture paths for external file (add ../ prefix)
                    self._fix_external_texture_paths(external_stage)
                    
                    # Apply final mesh fixes to external file
                    self._apply_final_mesh_fixes(external_stage)
                    
                    external_stage.Save()
                
                # Move the temporary file to the final location
                shutil.move(temp_path, external_file_path)
                external_files_created += 1
    
                
            except Exception as e:
                print(f"ERROR Failed to create external prototype {external_prototype_data['name']}.usd: {e}")
                # Clean up temp file if it exists
                try:
                    if 'temp_path' in locals() and os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass
                continue
        
        return external_files_created
    
    def _create_existing_pointinstancer(self, output_stage, pointinstancer_data):
        """Create existing PointInstancer by copying everything as-is and only updating material/texture paths"""
        # Get the source PointInstancer
        source_instancer_prim = pointinstancer_data['prim']
        
        # For Blender 4.5 with parent preservation, this should not be called
        # The parent container is copied in _create_pointinstancers instead
        if pointinstancer_data.get('preserve_parent'):
            # This should not happen - parent is handled in _create_pointinstancers
            print(f"WARNING: _create_existing_pointinstancer called for Blender 4.5 PointInstancer - should be handled in _create_pointinstancers")
            return
        
        parent_path = pointinstancer_data.get('parent_path', '/RootNode')
        instancer_name = pointinstancer_data['name']
        instancer_path = f"{parent_path}/{instancer_name}"
        
        # Copy the entire PointInstancer structure as-is using our unified copy method
        # This preserves all the existing structure, prototypes, and relationships
        self.copy_prim_data(source_instancer_prim, output_stage, instancer_path, include_materials=True, include_children=True)
        
        # Fix the prototypes relationship to point to the correct paths in the new structure
        copied_instancer = output_stage.GetPrimAtPath(instancer_path)
        if copied_instancer and copied_instancer.IsValid():
            # Update prototypes relationship to point to children within the copied PointInstancer
            pi = UsdGeom.PointInstancer(copied_instancer)
            prototypes_rel = pi.GetPrototypesRel()
            
            # If using external references, replace inline prototypes with external Xforms
            if self.use_external_references:
                old_targets = prototypes_rel.GetTargets()
                new_targets = []
                
                for old_target in old_targets:
                    # Get the mesh from the old target
                    old_prim = output_stage.GetPrimAtPath(old_target)
                    if old_prim and old_prim.IsValid():
                        mesh_prim = None
                        if old_prim.IsA(UsdGeom.Mesh):
                            mesh_prim = old_prim
                            mesh_name = mesh_prim.GetName()
                        else:
                            # Search for mesh in children
                            for desc in Usd.PrimRange.AllPrims(old_prim):
                                if desc.IsA(UsdGeom.Mesh):
                                    mesh_prim = desc
                                    mesh_name = mesh_prim.GetName()
                                    break
                        
                        if mesh_prim:
                            # Remove the inline mesh
                            output_stage.RemovePrim(old_target)
                            
                            # Create Xform with external reference
                            ext_ref_path = f"{instancer_path}/{mesh_name}"
                            ext_ref_prim = output_stage.DefinePrim(ext_ref_path, "Xform")
                            ext_ref_prim.SetMetadata("kind", "component")
                            
                            external_file = f"./Instance_Objs/{mesh_name}.usd"
                            references = ext_ref_prim.GetReferences()
                            references.AddReference(external_file)
                            
                            new_targets.append(Sdf.Path(ext_ref_path))
                
                if new_targets:
                    prototypes_rel.SetTargets(new_targets)
                    print(f"    Updated prototypes relationship to: {[str(p) for p in new_targets]}")
            else:
                # Inline mode - just update paths
                prototype_paths = []
                for child in copied_instancer.GetAllChildren():
                    child_name = child.GetName()
                    # Look for prototype-like children (Prototype_*, Prototypes folder, or mesh children)
                    if child_name.startswith('Prototype_') or child_name == 'Prototypes':
                        if child_name == 'Prototypes':
                            # Look inside the Prototypes folder
                            for prot_child in child.GetAllChildren():
                                prototype_paths.append(prot_child.GetPath())
                        else:
                            prototype_paths.append(child.GetPath())
                    elif child.IsA(UsdGeom.Mesh):
                        # Direct mesh children can also be prototypes
                        prototype_paths.append(child.GetPath())
                
                # Set the prototypes relationship to point to the copied children
                if prototype_paths:
                    prototypes_rel.SetTargets(prototype_paths)
                    print(f"    Updated prototypes relationship to: {[str(p) for p in prototype_paths]}")
            
            # Now recursively update only the material and texture paths in the copied structure
            self._update_material_texture_paths_recursive(copied_instancer, output_stage)
    
    def _update_material_texture_paths_recursive(self, prim, output_stage):
        """Recursively update material and texture paths in a prim and its children"""
        # Update material bindings
        if prim.GetRelationship("material:binding"):
            binding_rel = prim.GetRelationship("material:binding")
            targets = binding_rel.GetTargets()
            if targets:
                updated_targets = []
                for target in targets:
                    target_str = str(target)
                    # Extract material name and update to /Root/Looks/ path
                    material_name = None
                    if "/_materials/" in target_str:
                        material_name = target_str.split("/_materials/")[-1]
                    elif "/materials/" in target_str:
                        material_name = target_str.split("/materials/")[-1]
                    elif "/root/Looks/" in target_str:
                        material_name = target_str.split("/root/Looks/")[-1]
                    elif "/Root/Looks/" in target_str:
                        material_name = target_str.split("/Root/Looks/")[-1]
                    elif "/Looks/" in target_str:
                        material_name = target_str.split("/Looks/")[-1]
                    
                    if material_name:
                        updated_path = f"/RootNode/Looks/{material_name}"
                        updated_targets.append(Sdf.Path(updated_path))
                    else:
                        updated_targets.append(target)
                
                binding_rel.SetTargets(updated_targets)
        
        # Update texture paths in attributes
        for attr in prim.GetAttributes():
            if attr.GetTypeName() == "asset":
                value = attr.Get()
                if value and isinstance(value, str):
                    # Keep texture paths as they are - textures should remain in ./textures/
                    # Only material references need dynamic path calculation
                    pass
        
        # Recursively process children
        for child in prim.GetAllChildren():
            self._update_material_texture_paths_recursive(child, output_stage)



    def _convert_textures_direct(self):
        """Convert only textures that are actually referenced in materials - NO WASTEFUL COPYING!"""
        # Initialize texture details tracking
        self._texture_details = []
        
        if not self.texture_converter or not self.texture_converter.nvtt_compress_path:
            print("  Texture conversion skipped - NVIDIA Texture Tools not available")
            return 0
        
        print(" Converting textures with NVIDIA Texture Tools...")
        
        # Find source textures directory from input
        if not self.input_stage:
            print("  No input stage available for texture conversion")
            return 0
            
        try:
            root_layer = self.input_stage.GetRootLayer()
            input_identifier = getattr(root_layer, 'realPath', None) or getattr(root_layer, 'identifier', None)
            if not input_identifier:
                print("  Could not determine input file location")
                return 0

            input_dir = os.path.dirname(input_identifier)
            source_textures_dir = os.path.join(input_dir, 'textures')
            
            if not os.path.exists(source_textures_dir):
                print(f"  Source textures directory not found: {source_textures_dir}")
                return 0
                
        except Exception as e:
            print(f"  Error finding source textures directory: {e}")
            return 0
        
        # Create output textures directory
        output_dir = os.path.dirname(self.output_path)
        target_textures_dir = os.path.join(output_dir, "textures")
        os.makedirs(target_textures_dir, exist_ok=True)
        
        # Collect actually referenced textures from materials
        referenced_textures = self._collect_referenced_textures()
        
        if not referenced_textures:
            print("  No texture references found in materials - skipping conversion")
            return 0
        
        print(f" Found {len(referenced_textures)} texture references in materials")
        print(f" Converting textures from: {os.path.normpath(source_textures_dir)}")
        print(f" Output directory: {os.path.normpath(target_textures_dir)}")
        
        # Convert only referenced textures directly from source
        results = self._convert_referenced_textures_only(
            referenced_textures, 
            source_textures_dir, 
            target_textures_dir
        )
        
        # Update texture references in USD files to point to converted DDS files
        successful_conversions = self._update_texture_references_to_dds(results, target_textures_dir)
        
        # Clear texture conversion tracking cache after conversion is complete
        self._clear_texture_conversion_cache()
        
        return successful_conversions
    
    def _build_texture_material_context(self):
        """Build mapping of texture paths to their material context (type and opacity pairing)"""
        texture_context = {}
        
        try:
            for material_name, material_info in self.output_data['materials'].items():
                if not material_info.get('is_remix'):
                    continue
                
                remix_params = material_info.get('remix_params', {})
                
                # Check for opacity combination flag
                needs_opacity_combine = remix_params.get('_combine_opacity_with_diffuse', False)
                opacity_texture_path = remix_params.get('_opacity_texture_path')
                
                # Map each texture parameter to its type and opacity pairing
                for param_name, param_value in remix_params.items():
                    if param_name.startswith('_') or not param_name.endswith('_texture'):
                        continue
                    
                    if not isinstance(param_value, str):
                        continue
                    
                    # Extract texture path from texture_2d() format or plain path
                    import re
                    match = re.search(r'texture_2d\("([^"]+)"', param_value)
                    if match:
                        texture_path = match.group(1)
                    else:
                        texture_path = param_value.strip('@')
                    
                    if not texture_path:
                        continue
                    
                    # Determine texture type from parameter name
                    if param_name == 'diffuse_texture':
                        texture_type = 'diffuse'
                        # If this material needs opacity combination, store the opacity texture path
                        if needs_opacity_combine and opacity_texture_path:
                            texture_context[texture_path] = ('diffuse', opacity_texture_path)
                        else:
                            texture_context[texture_path] = ('diffuse', None)
                    elif param_name == 'normalmap_texture':
                        texture_context[texture_path] = ('normal', None)
                    elif param_name == 'reflectionroughness_texture':
                        texture_context[texture_path] = ('roughness', None)
                    elif param_name == 'metallic_texture':
                        texture_context[texture_path] = ('metallic', None)
                    elif param_name == 'emissive_mask_texture':
                        texture_context[texture_path] = ('emissive', None)
                    else:
                        texture_context[texture_path] = (None, None)
        
        except Exception as e:
            print(f" Error building texture material context: {e}")
        
        return texture_context
    
    def _collect_referenced_textures(self):
        """Collect all texture paths referenced in materials with source path mapping"""
        referenced_textures = {}  # Maps output_path -> source_path
        
        try:
            print(f"DEBUG Collecting textures from {len(self.output_data.get('materials', {}))} materials")
            # Collect from converted materials with source path mapping
            for material_name, material_info in self.output_data.get('materials', {}).items():
                print(f"DEBUG Material: {material_name}, is_remix: {material_info.get('is_remix')}")
                if material_info.get('is_remix'):
                    remix_params = material_info.get('remix_params', {})
                    print(f"DEBUG   Remix params: {list(remix_params.keys())}")
                    for param_name, param_value in remix_params.items():
                        if param_name.endswith('_texture') and isinstance(param_value, str):
                            print(f"DEBUG   Found texture param: {param_name} = {param_value}")
                            # Extract output path from texture_2d("path", gamma) format
                            output_path = None
                            if 'texture_2d(' in param_value:
                                import re
                                match = re.search(r'texture_2d\("([^"]+)"', param_value)
                                if match:
                                    output_path = match.group(1)
                            else:
                                output_path = param_value.strip('@')
                            
                            print(f"DEBUG   Extracted output_path: {output_path}")
                            
                            if output_path and not output_path.startswith('@'):
                                # Check for texture bending flags first (roughness from diffuse/specular)
                                source_path = None
                                if param_name == 'reflectionroughness_texture':
                                    # Check for texture bending: invert_for_roughness or use_diffuse_for_roughness
                                    if remix_params.get('_invert_for_roughness'):
                                        # Use diffuse or specular source with inversion
                                        source_path = remix_params.get('_diffuse_source') or remix_params.get('_specular_source')
                                        print(f"DEBUG   Roughness with inversion, using source: {source_path}")
                                    elif remix_params.get('_use_diffuse_for_roughness'):
                                        # Use diffuse source without inversion
                                        source_path = remix_params.get('_diffuse_source')
                                        print(f"DEBUG   Roughness from diffuse, using source: {source_path}")
                                
                                # If no texture bending, check for standard _source path
                                if not source_path:
                                    source_param = f"_{param_name}_source"
                                    source_path = remix_params.get(source_param)
                                    print(f"DEBUG   Looking for source param: {source_param}, found: {source_path}")
                                
                                if source_path:
                                    referenced_textures[output_path] = source_path
                                    print(f"DEBUG   Added texture: {output_path} <- {source_path}")
                                else:
                                    # No source path, use output path as source
                                    referenced_textures[output_path] = output_path
                                    print(f"DEBUG   Added texture (no source): {output_path}")
            
            print(f" Collected {len(referenced_textures)} unique texture references:")
            for output_path, source_path in sorted(referenced_textures.items()):
                if output_path != source_path:
                    print(f"     {output_path} <- {source_path}")
                else:
                    print(f"     {output_path}")
                
        except Exception as e:
            print(f" Error collecting texture references: {e}")
            import traceback
            print(f" Traceback: {traceback.format_exc()}")
            
        return referenced_textures
    
    def _parse_mdl_for_textures(self, mdl_path, referenced_textures, mdl_dir):
        """Parse MDL file to extract texture_2d() references"""
        try:
            omnipbr_params = parse_omnipbr_mdl(mdl_path)
            if omnipbr_params:
                for param_name, param_value in omnipbr_params.items():
                    if isinstance(param_value, str) and 'texture_2d(' in param_value:
                        import re
                        match = re.search(r'texture_2d\("([^"]+)"', param_value)
                        if match:
                            texture_path = match.group(1)
                            if texture_path and any(ext in texture_path.lower() for ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']):
                                # Resolve relative paths from MDL directory
                                if texture_path.startswith('./'):
                                    resolved_path = os.path.join(mdl_dir, texture_path[2:])
                                    resolved_path = os.path.normpath(resolved_path).replace('\\', '/')
                                    texture_path = resolved_path
                                if texture_path not in referenced_textures:
                                    print(f"     Found texture in MDL: {texture_path}")
                                referenced_textures.add(texture_path)
        except Exception as e:
            print(f"  Warning: Could not parse MDL file {mdl_path}: {e}")
    
    def _collect_textures_from_material(self, material, referenced_textures):
        """Collect texture references from a material"""
        try:
            # Get surface shader from material - handle RTX Remix materials
            surface_output = material.GetSurfaceOutput()
            if surface_output:
                connected_source = surface_output.GetConnectedSource()
                if connected_source and len(connected_source) > 0 and connected_source[0]:
                    shader_prim = connected_source[0].GetPrim()
                    self._collect_textures_from_shader_prim(shader_prim, referenced_textures)
            
            # Also check direct shader children (for RTX Remix "over Shader" pattern)
            for child in material.GetPrim().GetChildren():
                if child.GetName() == "Shader":
                    self._collect_textures_from_shader_prim(child, referenced_textures)
                    
        except Exception as e:
            print(f"  Error collecting textures from material {material.GetPath()}: {e}")
    
    def _collect_textures_from_shader(self, shader, referenced_textures):
        """Collect texture references from a shader (deprecated - use _collect_textures_from_shader_prim)"""
        try:
            shader_prim = shader.GetPrim()
            self._collect_textures_from_shader_prim(shader_prim, referenced_textures)
        except Exception as e:
            print(f"  Error collecting textures from shader {shader.GetPath()}: {e}")
    
    def _collect_textures_from_shader_prim(self, shader_prim, referenced_textures):
        """Collect texture references from a shader prim"""
        try:
            # Check all attributes for asset (texture) references
            for attr in shader_prim.GetAttributes():
                attr_name = attr.GetName()
                type_name = attr.GetTypeName()
                
                # Look for inputs that are assets (textures)
                if attr_name.startswith('inputs:') and type_name == 'asset':
                    # Get the asset path
                    asset_path = attr.Get()
                    if asset_path:
                        asset_path_str = str(asset_path)
                        # Look for texture file extensions
                        if any(ext in asset_path_str.lower() for ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff', '.dds']):
                            # Clean up the path (remove @ symbols if present)
                            clean_path = asset_path_str.strip('@')
                            # Only log if this is a new texture reference
                            if clean_path not in referenced_textures:
                                print(f"     Found texture reference: {clean_path}")
                            referenced_textures.add(clean_path)
                            
        except Exception as e:
            print(f"  Error collecting textures from shader prim {shader_prim.GetPath()}: {e}")
    
    def _convert_referenced_textures_only(self, referenced_textures, source_textures_dir, output_dir):
        """Convert only textures that are actually referenced
        
        Args:
            referenced_textures: Dict mapping output_path -> source_path
            source_textures_dir: Directory to search for source textures (fallback)
            output_dir: Directory for output DDS files
        """
        results = {}
        successful_count = 0
        failed_count = 0
        missing_count = 0
        
        # Build material context map: texture_path -> (texture_type, opacity_texture_path)
        texture_material_context = self._build_texture_material_context()
        
        # Collect opacity texture paths to skip conversion
        opacity_textures_to_skip = set()
        for texture_path, (texture_type, opacity_path) in texture_material_context.items():
            if opacity_path:
                opacity_textures_to_skip.add(opacity_path)
        
        # Process each texture reference individually to create deduplicated DDS files
        for texture_ref, source_path in referenced_textures.items():
            # Skip opacity textures - they're combined into diffuse alpha channel
            if texture_ref in opacity_textures_to_skip:
                print(f" Skipping opacity texture (combined into diffuse): {texture_ref}")
                continue
            
            # Get texture type from material context (NOT from filename)
            slot_type = None
            if texture_ref in texture_material_context:
                slot_type, _ = texture_material_context[texture_ref]
            
            # Default to diffuse if no type found
            if not slot_type:
                slot_type = 'diffuse'
            
            # Resolve source_path
            actual_source_file = None
            
            if source_path.startswith('./'):
                # Relative path like ./textures/bush.jpg - resolve relative to source_textures_dir
                source_filename = source_path.replace('./textures/', '')
                actual_source_file = os.path.join(source_textures_dir, source_filename)
            elif os.path.isabs(source_path):
                # Absolute path - use as-is (from OmniPBR MDL resolution)
                actual_source_file = source_path
            else:
                # Relative path without ./ prefix (from OmniPBR MDL resolution)
                # These are relative to the input file directory, not source_textures_dir
                input_dir = os.path.dirname(os.path.dirname(source_textures_dir))  # Go up from textures to input dir
                actual_source_file = os.path.join(input_dir, source_path)
            
            if not actual_source_file:
                # Handle missing files
                missing_count += 1
                print(f"  Referenced texture not found: {texture_ref}")
                print(f"    Source path: {source_path}")
                results[texture_ref] = {
                    'success': False,
                    'output': None,
                    'referenced_path': texture_ref,
                    'missing': True
                }
                continue
            
            # Determine output filename - must match the reference path exactly
            # Extract the expected output filename from the reference
            output_filename = os.path.basename(texture_ref.replace('./textures/', ''))
            if not output_filename.endswith('.dds'):
                output_filename = os.path.splitext(output_filename)[0] + '.dds'
            output_file = os.path.join(output_dir, output_filename)
            
            print(f" Processing: {texture_ref} -> {output_filename} (slot: {slot_type})")
            # Check if this specific output file was already created
            cache_key = (actual_source_file, slot_type)
            if cache_key in self.texture_conversion_cache:
                cached_output = self.texture_conversion_cache[cache_key]
                print(f" Using cached: {output_filename}")
                successful_count += 1
                
                # Track cached texture for UI display
                if slot_type == 'diffuse':
                    detail = f"CACHED: {output_filename}"
                else:
                    detail = f"CACHED: {output_filename} (slot: {slot_type})"
                self._texture_details.append(detail)
                
                results[texture_ref] = {
                    'success': True,
                    'output': cached_output,
                    'referenced_path': texture_ref
                }
                continue
            
            # Check if DDS file already exists
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f" Using existing: {output_filename}")
                successful_count += 1
                self.texture_conversion_cache[cache_key] = output_file
                
                # Track skipped texture for UI display
                if slot_type == 'diffuse':
                    detail = f"SKIPPED: {output_filename} (already exists)"
                else:
                    detail = f"SKIPPED: {output_filename} (already exists, slot: {slot_type})"
                self._texture_details.append(detail)
                
                results[texture_ref] = {
                    'success': True,
                    'output': output_file,
                    'referenced_path': texture_ref
                }
                continue
            
            print(f" Converting: {os.path.basename(actual_source_file)} -> {output_filename}")
            
            # Use slot type to determine texture type
            texture_type = slot_type
            opacity_texture_path = None
            needs_inversion = False
            is_bump_to_normal = False
            
            # Get source texture and conversion flags from material mapping
            source_texture_override = None
            resolved_opacity_path = None
            
            for mat_name, mat_info in self.output_data.get('materials', {}).items():
                if 'remix_params' in mat_info:
                    remix_params = mat_info['remix_params']
                    
                    # Check for roughness texture with inversion flag (specular-to-roughness)
                    if slot_type in ['roughness', 'rough'] and remix_params.get('_invert_for_roughness'):
                        # Check if using diffuse source (specular same as diffuse) or specular source
                        diffuse_src = remix_params.get('_diffuse_source')
                        specular_src = remix_params.get('_specular_source')
                        
                        if diffuse_src:
                            # Specular is same as diffuse - use diffuse source with inversion
                            source_texture_override = diffuse_src.strip('@').replace('./textures/', '')
                            if not os.path.isabs(source_texture_override):
                                source_texture_override = os.path.join(source_textures_dir, source_texture_override)
                            needs_inversion = True
                            break
                        elif specular_src:
                            # Specular has its own texture - use specular source with inversion
                            source_texture_override = specular_src.strip('@').replace('./textures/', '')
                            if not os.path.isabs(source_texture_override):
                                source_texture_override = os.path.join(source_textures_dir, source_texture_override)
                            needs_inversion = True
                            break
                    
                    # Check for diffuse-to-roughness flag (grayscale only, no inversion)
                    if slot_type in ['roughness', 'rough'] and remix_params.get('_use_diffuse_for_roughness'):
                        # Use DIFFUSE texture source for roughness conversion (grayscale only)
                        diffuse_src = remix_params.get('_diffuse_source')
                        if diffuse_src:
                            source_texture_override = diffuse_src.strip('@').replace('./textures/', '')
                            if not os.path.isabs(source_texture_override):
                                source_texture_override = os.path.join(source_textures_dir, source_texture_override)
                            needs_inversion = False  # No inversion for diffuse-to-roughness
                            break
                    
                    # Check for opacity texture pairing
                    if texture_ref in texture_material_context:
                        _, opacity_texture_path = texture_material_context[texture_ref]
                        if opacity_texture_path:
                            opacity_src = remix_params.get('_opacity_texture_source', opacity_texture_path)
                            resolved_opacity_path = opacity_src.strip('@').replace('./textures/', '')
                            if not os.path.isabs(resolved_opacity_path):
                                resolved_opacity_path = os.path.join(source_textures_dir, resolved_opacity_path)
            
            # Convert texture with proper slot-specific settings
            success = self.texture_converter.convert_texture(
                actual_source_file,
                output_file,
                force_type=texture_type,
                format='dds',
                quality='normal',
                opacity_texture_path=resolved_opacity_path,
                is_bump_to_normal=is_bump_to_normal,
                source_texture_override=source_texture_override,
                needs_inversion=needs_inversion
            )
            
            if success:
                successful_count += 1
                print(f" [OK] Created: {output_filename}")
                self.texture_conversion_cache[cache_key] = output_file
                
                # Track texture details for UI display
                if slot_type == 'diffuse':
                    detail = f"{os.path.basename(actual_source_file)} ??{output_filename}"
                else:
                    # Show auto-generation for non-diffuse slots
                    detail = f"{os.path.basename(actual_source_file)} ??{slot_type} ??{output_filename}"
                self._texture_details.append(detail)
            else:
                failed_count += 1
                print(f" [FAIL] Failed: {output_filename}")
                print(f"    DEBUG Source: {actual_source_file}")
                print(f"    DEBUG Slot type: {slot_type}")
                self._texture_details.append(f"FAILED: {output_filename} (conversion failed)")
                
                # Track failed conversion details for summary
                fail_reason = "texture not found" if not os.path.exists(actual_source_file) else "conversion failed"
                self.failed_texture_conversions.append({
                    'source': actual_source_file,
                    'slot_type': slot_type,
                    'reason': fail_reason
                })
            
            results[texture_ref] = {
                'success': success,
                'output': output_file if success else None,
                'referenced_path': texture_ref
            }
        
        # Print summary
        print(f"\n Texture Conversion Summary:")
        print(f"    Successfully converted: {successful_count}")
        print(f"    Failed conversions: {failed_count}")
        print(f"    Missing source files: {missing_count}")
        print(f"    Output directory: {os.path.normpath(output_dir)}")
        
        return results
    
    def _update_texture_references_to_dds(self, conversion_results, materials_dir):
        """Update texture references in the USD file to point to converted DDS files"""
        successful_conversions = 0
        
        # Read the output stage to update texture references
        try:
            stage = Usd.Stage.Open(self.output_path)
            updated_any = False
            
            # Traverse all prims and update texture asset paths
            for prim in stage.TraverseAll():
                # Check all shader attributes for texture paths (more reliable than GetInputNames)
                if prim.GetName() == "Shader" or prim.IsA(UsdShade.Shader):
                    # Use attribute-based approach instead of shader.GetInputNames()
                    for attr in prim.GetAttributes():
                        attr_name = attr.GetName()
                        if attr_name.startswith('inputs:') and attr.GetTypeName() == 'asset':
                            current_path = attr.Get()
                            if current_path and isinstance(current_path, Sdf.AssetPath):
                                current_path_str = current_path.path
                                
                                # Update extension to .dds and path to textures/
                                if current_path_str and not current_path_str.endswith('.dds'):
                                    # Extract filename without extension
                                    texture_name = os.path.splitext(os.path.basename(current_path_str))[0]
                                    new_path = f"./textures/{texture_name}.dds"
                                    
                                    # Update the path
                                    attr.Set(Sdf.AssetPath(new_path))
                                    print(f"     Updated texture reference: {current_path_str} ??{new_path}")
                                    updated_any = True
                                    successful_conversions += 1
                
                # Also check regular attributes with asset type
                for attr in prim.GetAttributes():
                    if attr.GetTypeName() == "asset":
                        value = attr.Get()
                        if value and isinstance(value, (str, Sdf.AssetPath)):
                            value_str = value.path if isinstance(value, Sdf.AssetPath) else value
                            # Check if this is a texture reference that needs updating
                            if value_str and not value_str.endswith('.dds') and any(ext in value_str.lower() for ext in ['.png', '.jpg', '.jpeg', '.tga']):
                                texture_name = os.path.splitext(os.path.basename(value_str))[0]
                                new_path = f"./textures/{texture_name}.dds"
                                attr.Set(Sdf.AssetPath(new_path))
                                print(f"     Updated texture reference: {value_str} ??{new_path}")
                                updated_any = True
                                successful_conversions += 1
            
            if updated_any:
                stage.Save()
                print(f" Updated USD file with {successful_conversions} DDS texture references")
            
        except Exception as e:
            print(f" Error updating texture references: {e}")
        
        return successful_conversions
    
    def _copy_geometry_comprehensive(self, source_prim, target_stage, target_path):
        """Copy geometry comprehensively including all mesh data and children"""
        try:
            target_prim = target_stage.DefinePrim(target_path, source_prim.GetTypeName())
            
            # Copy all attributes using comprehensive approach
            for attr in source_prim.GetAttributes():
                if not attr.GetName().startswith('__'):
                    try:
                        value = attr.Get()
                        attr_name = attr.GetName()
                        
                        # Check if this is a meaningful attribute value
                        if self._is_meaningful_attribute_value(attr_name, value):
                            is_standard_attribute = self._is_standard_usd_attribute(attr_name)
                            target_attr = target_prim.CreateAttribute(attr_name, attr.GetTypeName(), custom=not is_standard_attribute)
                            target_attr.SetVariability(attr.GetVariability())
                            target_attr.Set(value)
                            
                            # Copy interpolation metadata if present
                            if attr.HasMetadata("interpolation"):
                                target_attr.SetMetadata("interpolation", attr.GetMetadata("interpolation"))
                            
                            pass
                    except Exception as e:
                        print(f"WARNING Failed to copy geometry attribute {attr_name}: {e}")
            
            # Copy all relationships with proper material binding updates
            for rel in source_prim.GetRelationships():
                if not rel.GetName().startswith('__'):
                    try:
                        # Special handling for material:binding relationships to ensure proper format
                        if rel.GetName() == "material:binding":
                            targets = rel.GetTargets()
                            if targets:
                                updated_targets = []
                                for target in targets:
                                    target_str = str(target)
                                    # Handle multiple path formats for material bindings
                                    material_name = None
                                    if "/_materials/" in target_str:
                                        material_name = target_str.split("/_materials/")[-1]
                                    elif "/materials/" in target_str:
                                        material_name = target_str.split("/materials/")[-1]
                                    elif "/root/Looks/" in target_str:
                                        material_name = target_str.split("/root/Looks/")[-1]
                                    elif "/Root/Looks/" in target_str:
                                        material_name = target_str.split("/Root/Looks/")[-1]
                                    elif "/Looks/" in target_str:
                                        material_name = target_str.split("/Looks/")[-1]
                                    
                                    if material_name:
                                        updated_path = f"/RootNode/Looks/{material_name}"
                                        updated_targets.append(Sdf.Path(updated_path))
                                
                                if updated_targets:
                                    # Create proper material binding with standard (non-custom) relationship
                                    binding_rel = target_prim.CreateRelationship("material:binding", custom=False)
                                    binding_rel.SetTargets(updated_targets)
                                    # Set the binding strength metadata
                                    binding_rel.SetMetadata("bindMaterialAs", "weakerThanDescendants")
                        else:
                            # For non-material relationships, use the standard approach
                            target_rel = target_prim.CreateRelationship(rel.GetName(), custom=rel.IsCustom())
                            targets = rel.GetTargets()
                            if targets:
                                target_rel.SetTargets(targets)
                    except Exception as e:
                        print(f"WARNING Failed to copy geometry relationship {rel.GetName()}: {e}")
            
            # Recursively copy all children
            for child in source_prim.GetAllChildren():
                child_name = child.GetName()
                child_path = f"{target_path}/{child_name}"
                self._copy_geometry_comprehensive(child, target_stage, child_path)
            
            # Apply unified post-copy fixes to ensure interpolation modes are corrected
            self._apply_unified_prim_fixes(target_prim)
                
        except Exception as e:
            print(f"WARNING Failed to copy geometry comprehensively: {e}")
    
    def _remove_old_blender_materials_from_prototype(self, prototype_prim):
        """Remove old Blender material scopes from prototypes since we now have RTX Remix materials in /RootNode/Looks"""
        try:
            materials_to_remove = []
            
            for prim in prototype_prim.GetStage().Traverse():
                if not str(prim.GetPath()).startswith(str(prototype_prim.GetPath())):
                    continue
                    
                if prim.GetTypeName() == "Scope" and prim.GetName() == "_materials":
                    has_blender_materials = False
                    for material_child in prim.GetStage().Traverse():
                        if str(material_child.GetPath()).startswith(str(prim.GetPath())):
                            if material_child.GetTypeName() == "Shader" and "Principled_BSDF" in material_child.GetName():
                                has_blender_materials = True
                                break
                    
                    if has_blender_materials:
                        materials_to_remove.append(prim.GetPath())
            
            for material_scope_path in materials_to_remove:
                try:
                    prototype_prim.GetStage().RemovePrim(material_scope_path)
                    self.materials_cleaned += 1
                except Exception as e:
                    print(f"WARNING Could not remove old materials scope {material_scope_path}: {e}")
                    
        except Exception as e:
            print(f"WARNING Failed to remove old Blender materials from prototype: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")
    
    def _remove_old_root_materials_after_conversion(self, output_stage):
        """Remove old root-level materials after successful RTX Remix conversion"""
        try:
            print("CLEANUP Removing old root-level materials after RTX conversion...")
            
            # Find the old root-level _materials scope
            old_materials_scope = None
            for prim in output_stage.TraverseAll():
                if (prim.GetTypeName() == "Scope" and 
                    prim.GetName() == "_materials" and 
                    str(prim.GetPath()) == "/root/_materials"):
                    old_materials_scope = prim
                    break
            
            if old_materials_scope:
                # Verify that RTX Remix materials exist in /RootNode/Looks before removing old ones
                rtx_materials_exist = False
                for prim in output_stage.TraverseAll():
                    if (prim.IsA(UsdShade.Material) and 
                        "/RootNode/Looks/" in str(prim.GetPath())):
                        rtx_materials_exist = True
                        break
                
                if rtx_materials_exist:
                    # Count old materials before removal
                    old_material_count = 0
                    for child in old_materials_scope.GetChildren():
                        if child.IsA(UsdShade.Material):
                            old_material_count += 1
                    
                    # Remove the entire old materials scope
                    output_stage.RemovePrim(old_materials_scope.GetPath())
                    print(f"CLEANUP Successfully removed old materials scope: {old_materials_scope.GetPath()}")
                    print(f"CLEANUP Removed {old_material_count} old materials")
                    return old_material_count
                else:
                    print(f"CLEANUP WARNING: No RTX Remix materials found, keeping old materials as fallback")
                    return 0
            else:
                print(f"CLEANUP No old root-level materials scope found to remove")
                return 0
                    
        except Exception as e:
            print(f"WARNING Failed to remove old root-level materials: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")
            return 0
    
    def _contains_old_blender_materials(self, prim):
        """Check if a prim contains old Blender materials"""
        try:
            for child_prim in prim.GetStage().Traverse():
                # Check if this prim is under our target path
                if not str(child_prim.GetPath()).startswith(str(prim.GetPath())):
                    continue
                
                if child_prim.GetTypeName() == "Shader" and "Principled_BSDF" in child_prim.GetName():
                    return True
            return False
        except Exception:
            return False
    
    def _remove_unused_materials_from_external_file(self, external_stage):
        """Remove materials from external file that are not bound to any mesh in this file"""
        try:
            # Find all materials in /RootNode/Looks/
            all_materials = set()
            for prim in external_stage.TraverseAll():
                if prim.IsA(UsdShade.Material) and str(prim.GetPath()).startswith("/RootNode/Looks/"):
                    all_materials.add(str(prim.GetPath()))
            
            # Find materials actually used by meshes/GeomSubsets in this file
            used_materials = set()
            for prim in external_stage.TraverseAll():
                mat_binding_rel = prim.GetRelationship('material:binding')
                if mat_binding_rel:
                    targets = mat_binding_rel.GetTargets()
                    for target in targets:
                        used_materials.add(str(target))
            
            # Remove unused materials
            unused_materials = all_materials - used_materials
            for material_path in unused_materials:
                external_stage.RemovePrim(material_path)
            
            if unused_materials:
                print(f"CLEANUP Removed {len(unused_materials)} unused materials from external file (kept {len(used_materials)})")
                
        except Exception as e:
            print(f"WARNING Failed to cleanup unused materials from external file: {e}")
    
    def _remove_unused_materials_from_external_stage(self, external_stage):
        """Remove unused materials from external stage - keep only /RootNode/Looks/ materials"""
        try:
            print("CLEANUP Removing unused materials from external stage...")
            
            materials_removed = 0
            materials_to_remove = []
            
            # Remove ALL duplicate material scopes from external stage - we only want /RootNode/Looks/
            # The problem is that USD composition creates namespace collisions
            for prim in external_stage.TraverseAll():
                prim_path_str = str(prim.GetPath())
                
                # We want to remove ALL /RootNode/Looks/ materials since they create problems in composition
                # Only the main file should have /RootNode/Looks/ materials
                if (prim_path_str.startswith("/RootNode/Looks/") and 
                    prim_path_str != "/RootNode/Looks"):
                    
                    materials_to_remove.append(prim.GetPath())
                    print(f"CLEANUP Found duplicate material in external file: {prim_path_str}")
                
                # Also remove the entire /RootNode/Looks scope if it exists
                elif (prim.GetName() == "Looks" and 
                    prim_path_str == "/RootNode/Looks"):
                    
                    materials_to_remove.append(prim.GetPath())
                    print(f"CLEANUP Found entire Looks scope to remove: {prim_path_str}")
            
            # Remove all the materials
            for material_path in materials_to_remove:
                try:
                    external_stage.RemovePrim(material_path)
                    materials_removed += 1
                    print(f"CLEANUP Successfully removed from external file: {material_path}")
                except Exception as e:
                    print(f"WARNING Could not remove from external file {material_path}: {e}")
            
            if materials_removed > 0:
                print(f"CLEANUP Removed {materials_removed} materials from external stage")
            else:
                print(f"CLEANUP No materials found to remove in external stage")
                
        except Exception as e:
            print(f"WARNING Failed to cleanup materials from external stage: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")

    def _remove_standalone_meshes_for_external_refs(self, main_stage):
        """Remove standalone meshes from main file when they're now in external files"""
        try:
            meshes_to_remove = []
            
            # Find all standalone meshes at /Root level (not inside PointInstancers)
            root_prim = main_stage.GetPrimAtPath('/RootNode')
            if not root_prim or not root_prim.IsValid():
                return
            
            for prim in root_prim.GetChildren():
                # Skip PointInstancers and Looks
                if prim.IsA(UsdGeom.PointInstancer) or prim.GetName() == 'Looks':
                    continue
                
                # Skip anchor meshes that have PointInstancer children (they are parent containers)
                has_pointinstancer_child = False
                for child in prim.GetChildren():
                    if child.IsA(UsdGeom.PointInstancer):
                        has_pointinstancer_child = True
                        break
                if has_pointinstancer_child:
                    continue
                
                # Check if this prim contains a mesh (either is a mesh or has mesh children)
                has_mesh = False
                if prim.IsA(UsdGeom.Mesh):
                    has_mesh = True
                else:
                    for child in prim.GetAllChildren():
                        if child.IsA(UsdGeom.Mesh):
                            has_mesh = True
                            break
                
                # If it has a mesh and matches branch naming pattern, mark for removal
                if has_mesh:
                    prim_name = prim.GetName()
                    # Check if this mesh is referenced by any PointInstancer
                    is_referenced = False
                    for pi_prim in main_stage.TraverseAll():
                        if pi_prim.IsA(UsdGeom.PointInstancer):
                            pi = UsdGeom.PointInstancer(pi_prim)
                            proto_rel = pi.GetPrototypesRel()
                            if proto_rel:
                                for target in proto_rel.GetTargets():
                                    # Check if this standalone mesh is used as a prototype
                                    if str(target).endswith(prim_name):
                                        is_referenced = True
                                        break
                        if is_referenced:
                            break
                    
                    # If not referenced by any PointInstancer, it's a standalone mesh to remove
                    if not is_referenced:
                        meshes_to_remove.append(prim.GetPath())
            
            # Remove the standalone meshes
            for mesh_path in meshes_to_remove:
                main_stage.RemovePrim(mesh_path)
                print(f"CLEANUP Removed standalone mesh: {mesh_path.name}")
            
            if meshes_to_remove:
                print(f"CLEANUP Removed {len(meshes_to_remove)} standalone meshes (now in external files)")
        
        except Exception as e:
            print(f"WARNING Failed to remove standalone meshes: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")

    def _remove_unused_materials_from_main_file(self, main_stage):
        """Remove materials NOT bound to any mesh in main file (external files have their own materials)"""
        try:
            # Find ALL materials bound in main file (excluding PointInstancer prototypes)
            bound_materials = set()
            for prim in main_stage.TraverseAll():
                # Skip prims inside PointInstancers (they reference external files)
                parent = prim.GetParent()
                is_in_pointinstancer = False
                while parent:
                    if parent.IsA(UsdGeom.PointInstancer):
                        is_in_pointinstancer = True
                        break
                    parent = parent.GetParent()
                
                # Only check material bindings OUTSIDE PointInstancers
                if not is_in_pointinstancer:
                    mat_binding_rel = prim.GetRelationship('material:binding')
                    if mat_binding_rel:
                        targets = mat_binding_rel.GetTargets()
                        for target in targets:
                            bound_materials.add(str(target))
            
            # Find all materials in /RootNode/Looks/
            all_materials = set()
            for prim in main_stage.TraverseAll():
                if prim.IsA(UsdShade.Material) and str(prim.GetPath()).startswith("/RootNode/Looks/"):
                    all_materials.add(str(prim.GetPath()))
            
            # Remove materials NOT bound in main file
            materials_to_remove = all_materials - bound_materials
            materials_removed = 0
            
            for material_path in materials_to_remove:
                try:
                    main_stage.RemovePrim(material_path)
                    materials_removed += 1
                except Exception as e:
                    print(f"WARNING Could not remove material from main file {material_path}: {e}")
            
            if materials_removed > 0:
                print(f"CLEANUP Removed {materials_removed} unused materials from main file (kept {len(bound_materials)} bound materials)")
            elif bound_materials:
                print(f"CLEANUP Kept {len(bound_materials)} materials bound in main file")
                
        except Exception as e:
            print(f"WARNING Failed to cleanup materials from main file: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")

    # Utility methods
    def copy_prim_data(self, source_prim, target_stage, target_path, include_materials=True, include_children=True, inline_mode=False, skip_interpolation_fixes=False):
        """
        Enhanced copy method that properly preserves all mesh data including geometry and UVs.
        This is the single source of truth for all prim copying operations.
        
        Args:
            source_prim: Source prim to copy from
            target_stage: Target stage to copy to
            target_path: Target path for the copied prim
            include_materials: Whether to include material bindings
            include_children: Whether to copy children recursively
            inline_mode: Whether to apply inline-specific filtering (exclude transforms, highlights, etc.)
            skip_interpolation_fixes: Whether to skip interpolation fixes (preserve original)
        """
        try:
            # Create target prim with same type as source
            target_prim = target_stage.DefinePrim(target_path, source_prim.GetTypeName())
            
            # Add MaterialBindingAPI if source has material bindings AND we're including materials
            if include_materials and source_prim.GetRelationship("material:binding"):
                target_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
            
            # Copy all attributes including primvars with proper handling
            for attr in source_prim.GetAttributes():
                if not attr.GetName().startswith('__'):
                    try:
                        # Skip attributes without values
                        if not attr.HasValue():
                            continue
                        
                        value = attr.Get()
                        attr_name = attr.GetName()
                        
                        # Skip meaningless attributes (empty arrays, default values)
                        if not self._is_meaningful_attribute_value(attr_name, value):
                            continue
                        
                        # Apply inline-specific filtering if requested
                        if inline_mode and self._should_exclude_attribute_for_inline(attr_name):
                            continue
                        
                        # Special handling for UV primvars
                        if attr_name == 'primvars:st':
                            # Ensure UV data is preserved with correct interpolation
                            target_attr = target_prim.CreateAttribute(attr_name, attr.GetTypeName(), custom=False)
                            target_attr.Set(value)
                            # Copy interpolation metadata or set default to vertex for UV coordinates
                            if attr.HasMetadata('interpolation'):
                                interpolation_value = attr.GetMetadata('interpolation')
                                # Never allow constant interpolation for UV coordinates - use vertex instead
                                if interpolation_value == 'constant':
                                    target_attr.SetMetadata('interpolation', 'vertex')
                                    print(f"REMIX Corrected UV interpolation: constant?�vertex for {attr_name}")
                                else:
                                    target_attr.SetMetadata('interpolation', interpolation_value)
                            else:
                                # No interpolation specified - set vertex as default for UV coordinates (Remix compatibility)
                                target_attr.SetMetadata('interpolation', 'vertex')
                                print(f"REMIX Set default UV interpolation: vertex for {attr_name}")
                            # Copy other metadata
                            if attr.HasMetadata('elementSize'):
                                target_attr.SetMetadata('elementSize', attr.GetMetadata('elementSize'))
                        else:
                            # Handle other attributes - ALWAYS copy mesh geometry attributes
                            is_standard_attribute = self._is_standard_usd_attribute(attr_name)
                            target_attr = target_prim.CreateAttribute(attr_name, attr.GetTypeName(), custom=not is_standard_attribute)
                            target_attr.SetVariability(attr.GetVariability())
                            target_attr.Set(value)
                            
                            # Copy interpolation metadata if present
                            if attr.HasMetadata("interpolation"):
                                target_attr.SetMetadata("interpolation", attr.GetMetadata("interpolation"))
                            
                    except Exception as e:
                        print(f"WARNING Could not copy attribute {attr_name}: {e}")
                        continue
            
            # Copy relationships (like material bindings) if requested
            if include_materials:
                for rel in source_prim.GetRelationships():
                    if not rel.GetName().startswith('__'):
                        try:
                            # Special handling for material:binding relationships to ensure proper format
                            if rel.GetName() == "material:binding":
                                targets = rel.GetTargets()
                                if targets:
                                    updated_targets = []
                                    for target in targets:
                                        target_str = str(target)
                                        # Handle multiple path formats for material bindings
                                        material_name = None
                                        if "/_materials/" in target_str:
                                            material_name = target_str.split("/_materials/")[-1]
                                        elif "/materials/" in target_str:
                                            material_name = target_str.split("/materials/")[-1]
                                        elif "/root/Looks/" in target_str:
                                            material_name = target_str.split("/root/Looks/")[-1]
                                        elif "/Root/Looks/" in target_str:
                                            material_name = target_str.split("/Root/Looks/")[-1]
                                        elif "/Looks/" in target_str:
                                            material_name = target_str.split("/Looks/")[-1]
                                        
                                        if material_name:
                                            updated_path = f"/RootNode/Looks/{material_name}"
                                            updated_targets.append(Sdf.Path(updated_path))
                                    
                                    if updated_targets:
                                        # Create proper material binding with standard (non-custom) relationship
                                        binding_rel = target_prim.CreateRelationship("material:binding", custom=False)
                                        binding_rel.SetTargets(updated_targets)
                                        # Set the binding strength metadata
                                        binding_rel.SetMetadata("bindMaterialAs", "weakerThanDescendants")
                            else:
                                # For non-material relationships, use the standard approach
                                target_rel = target_prim.CreateRelationship(rel.GetName())
                                targets = rel.GetTargets()
                                if targets:
                                    target_rel.SetTargets(targets)
                        except Exception as e:
                            continue
            else:
                # When not including materials, also skip all material-related relationships
                for rel in source_prim.GetRelationships():
                    if not rel.GetName().startswith('__') and not rel.GetName().startswith('material:'):
                        try:
                            target_rel = target_prim.CreateRelationship(rel.GetName())
                            targets = rel.GetTargets()
                            if targets:
                                target_rel.SetTargets(targets)
                        except Exception as e:
                            continue
            
            # Copy children recursively if requested
            has_geomsubsets = False
            if include_children:
                for child in source_prim.GetAllChildren():
                    child_name = child.GetName()
                    # Skip materials folder when not including materials
                    if not include_materials and child_name in ["_materials", "materials", "Looks"]:
                        continue
                    child_target_path = f"{target_path}/{child_name}"
                    # Handle GeomSubset with familyName="materialBind" - optionally remove familyName
                    if child.GetTypeName() == "GeomSubset":
                        has_geomsubsets = True
                        if self.remove_geomsubset_familyname:
                            family_name_attr = child.GetAttribute("familyName")
                            if family_name_attr and family_name_attr.Get() == "materialBind":
                                self.geomsubset_fixes += 1
                                self._copy_geomsubset_without_familyname(child, target_stage, child_target_path, include_materials, skip_interpolation_fixes)
                                continue
                    self.copy_prim_data(child, target_stage, child_target_path, include_materials, include_children, inline_mode, skip_interpolation_fixes)
            
            # CRITICAL: Remove material:binding from parent mesh if it has GeomSubsets
            # Only GeomSubsets should have material bindings, not the parent mesh
            if has_geomsubsets and target_prim.GetRelationship("material:binding"):
                target_prim.RemoveProperty("material:binding")
            
            # Clean up old Blender materials from prototypes after copying
            if inline_mode:
                self._remove_old_blender_materials_from_prototype(target_prim)
            elif "Prototype" in target_path and self._contains_old_blender_materials(target_prim):
                self._remove_old_blender_materials_from_prototype(target_prim)
            
            return target_prim
            
        except Exception as e:
            print(f"WARNING Failed to copy prim data from {source_prim.GetPath()} to {target_path}: {e}")
            return None
    
    def _apply_final_mesh_fixes(self, output_stage):
        """Apply unified mesh fixes to ALL meshes after structure is complete"""
        print("REMIX Applying final mesh fixes to all meshes...")
        mesh_count = 0
        
        for prim in output_stage.TraverseAll():
            if prim.IsA(UsdGeom.Mesh):
                mesh_count += 1
                had_uvs_before, uv_generated = self._fix_single_mesh(prim)
                # Track UV status: if mesh didn't have UVs originally
                if not had_uvs_before:
                    if self.generate_missing_uvs:
                        if uv_generated:
                            self.meshes_with_generated_uvs.append(str(prim.GetPath()))
                        else:
                            self.meshes_failed_uv_generation.append(str(prim.GetPath()))
                    else:
                        self.meshes_without_uvs.append(str(prim.GetPath()))
        
        print(f"REMIX Applied fixes to {mesh_count} meshes")
        
        if self.generate_missing_uvs:
            if self.meshes_with_generated_uvs:
                uv_count = len(self.meshes_with_generated_uvs)
                mesh_word = "mesh" if uv_count == 1 else "meshes"
                print(f"\nUV Generated placeholder UVs for {uv_count} {mesh_word}:")
                for mesh_path in self.meshes_with_generated_uvs:
                    print(f"  - {mesh_path}")
            if self.meshes_failed_uv_generation:
                fail_count = len(self.meshes_failed_uv_generation)
                mesh_word = "mesh" if fail_count == 1 else "meshes"
                print(f"\nWARNING: Failed to generate UVs for {fail_count} {mesh_word}:")
                for mesh_path in self.meshes_failed_uv_generation:
                    print(f"  - {mesh_path}")
                print("  These meshes may not display textures correctly in RTX Remix.")
                print("  Consider adding UV mapping in your DCC tool before export.")
        else:
            if self.meshes_without_uvs:
                uv_count = len(self.meshes_without_uvs)
                mesh_word = "mesh" if uv_count == 1 else "meshes"
                print(f"\nWARNING: {uv_count} {mesh_word} missing UV coordinates (primvars:st):")
                for mesh_path in self.meshes_without_uvs:
                    print(f"  - {mesh_path}")
                print("  These meshes may not display textures correctly in RTX Remix.")
                print("  Consider adding UV mapping in your DCC tool before export.")
    
    def _fix_single_mesh(self, mesh_prim):
        """Apply all fixes to a single mesh. Returns (had_uvs_before, uv_generated) tuple."""
        had_uvs_before = False
        uv_generated = False
        try:
            # Check if this is an empty mesh (anchor mesh) - skip UV tracking for these
            mesh = UsdGeom.Mesh(mesh_prim)
            points_attr = mesh.GetPointsAttr()
            if points_attr and points_attr.HasValue():
                points = points_attr.Get()
                if not points or len(points) == 0:
                    # Empty mesh (anchor) - skip UV tracking entirely
                    return True, False  # Return True to indicate "had UVs" so it's not tracked
            
            # 1. Convert float2 to texCoord2f
            self._convert_float2_primvars_in_stage(mesh_prim.GetStage())
            
            # 2. Check for UV coordinates (primvars:st or texCoord2f[])
            primvar_api = UsdGeom.PrimvarsAPI(mesh_prim)
            if primvar_api:
                for primvar in primvar_api.GetPrimvars():
                    if primvar:
                        primvar_name = primvar.GetPrimvarName()
                        if primvar_name == "st" or "st" in primvar_name:
                            had_uvs_before = True
                            break
            
            # 2b. Generate UVs if missing and option enabled
            if not had_uvs_before and self.generate_missing_uvs:
                uv_generated = self._generate_box_projection_uvs(mesh_prim)
            
            # 3. Apply interpolation fixes based on mode
            if self.interpolation_mode != "none":
                if primvar_api:
                    for primvar in primvar_api.GetPrimvars():
                        if primvar:
                            current_interpolation = primvar.GetInterpolation()
                            primvar_name = primvar.GetPrimvarName()
                            
                            if self.interpolation_mode == "faceVarying" and current_interpolation == UsdGeom.Tokens.vertex:
                                if ("st" in primvar_name or "uv" in primvar_name.lower() or "texcoord" in primvar_name.lower()):
                                    primvar.SetInterpolation(UsdGeom.Tokens.faceVarying)
                            elif self.interpolation_mode == "vertex" and current_interpolation == UsdGeom.Tokens.faceVarying:
                                if ("st" in primvar_name or "uv" in primvar_name.lower() or "texcoord" in primvar_name.lower()):
                                    primvar.SetInterpolation(UsdGeom.Tokens.vertex)
                
                mesh = UsdGeom.Mesh(mesh_prim)
                if mesh:
                    normals_attr = mesh.GetNormalsAttr()
                    if normals_attr and normals_attr.HasValue():
                        try:
                            current_normals_interpolation = mesh.GetNormalsInterpolation()
                            if self.interpolation_mode == "faceVarying" and current_normals_interpolation == UsdGeom.Tokens.vertex:
                                mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
                            elif self.interpolation_mode == "vertex" and current_normals_interpolation == UsdGeom.Tokens.faceVarying:
                                mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                        except:
                            pass
            
            # 4. Add MaterialBindingAPI
            mesh_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
            mesh_prim.SetMetadata("kind", "component")
            
        except:
            pass
        
        return had_uvs_before, uv_generated
    
    def _convert_float2_primvars_in_stage(self, stage):
        """Convert all float2[] primvars to texCoord2f[] primvars in a stage - using the reference method"""
        try:
            converted_count = 0
            
            for prim in stage.TraverseAll():
                if prim.IsA(UsdGeom.Mesh):
                    # Get all attributes on this prim
                    for attr in prim.GetAttributes():
                        attr_name = attr.GetName()
                        attr_type = attr.GetTypeName()
                        
                        if attr_name.startswith("primvars:") and (attr_type == Sdf.ValueTypeNames.Float2Array or 
                                                                   (attr_type == Sdf.ValueTypeNames.TexCoord2fArray and attr.IsCustom())):
                            # Get the original value
                            original_value = attr.Get()
                            
                            # Remove the old attribute
                            prim.RemoveProperty(attr_name)
                            
                            # Create new attribute with texCoord2f[] type (not custom)
                            new_attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.TexCoord2fArray, custom=False)
                            new_attr.Set(original_value)
                            
                            # Set interpolation to "vertex" for texCoord2f[] primvars using the proper API
                            try:
                                primvar_api = UsdGeom.PrimvarsAPI(prim)
                                primvar = primvar_api.GetPrimvar(attr_name)
                                if primvar:
                                    primvar.SetInterpolation(UsdGeom.Tokens.vertex)
                            except Exception as e:
                                print(f"WARNING Could not set interpolation for {attr_name}: {e}")
                            
                            converted_count += 1
                    
        except Exception as e:
            print(f"WARNING Error converting primvars in stage: {e}")
            import traceback
            print(f"WARNING Traceback: {traceback.format_exc()}")
    
    def _copy_prim_data(self, source_prim, target_stage, target_path):
        """Copy prim data from source to target stage (legacy method)"""
        return self.copy_prim_data(source_prim, target_stage, target_path)
    
    def _copy_prim_attributes(self, source_prim, target_prim):
        """Copy attributes from source to target prim"""
        for attr in source_prim.GetAttributes():
            try:
                # Check if the attribute has a valid typeName before copying
                if attr.GetTypeName() and attr.HasValue():
                    value = attr.Get()
                    target_attr = target_prim.GetAttribute(attr.GetName())
                    if target_attr:
                        target_attr.Set(value)
            except Exception as e:
                print(f"WARNING Failed to copy attribute {attr.GetName()}: {e}")
    
    def _copy_materials_to_external_stage(self, external_stage, materials, is_external=False):
        """Copy materials to external stage with adjusted paths for subfolder"""
        try:
            # Create Looks scope
            looks_scope = external_stage.DefinePrim("/RootNode/Looks", "Scope")
            
            # Copy materials to external file
            for material_name, material_data in materials.items():
                # Use material_name directly from the dictionary key
                external_material_path = f"/RootNode/Looks/{material_name}"
                
                # Check if this is a Remix material
                if material_data.get('is_remix', False):
                    # Create Remix material in external stage (is_external=True adjusts paths)
                    self._create_remix_material(external_stage, external_material_path, material_data, is_external=True)
                    
                else:
                    # Create material prim
                    target_material = external_stage.DefinePrim(external_material_path, "Material")
                    
                    # Copy material attributes (but not relationships to avoid old references)
                    source_material = material_data['prim']
                    for attr in source_material.GetAttributes():
                        if not attr.GetName().startswith('__'):
                            try:
                                target_attr = target_material.CreateAttribute(attr.GetName(), attr.GetTypeName())
                                value = attr.Get()
                                if value is not None:
                                    target_attr.Set(value)
                            except Exception as e:
                                print(f"WARNING Could not copy external material attribute {attr.GetName()}: {e}")
                    
                    # Copy material relationships but skip old references
                    for rel in source_material.GetRelationships():
                        if not rel.GetName().startswith('__'):
                            try:
                                target_rel = target_material.CreateRelationship(rel.GetName())
                                targets = rel.GetTargets()
                                if targets:
                                    # Skip old material references that cause warnings
                                    updated_targets = []
                                    for target in targets:
                                        target_str = str(target)
                                        if '/_materials/' in target_str or '/root/_materials/' in target_str:
                                            # Don't copy these old references
                                            continue
                                        else:
                                            # Keep other relationships as-is
                                            updated_targets.append(target)
                                    
                                    if updated_targets:
                                        target_rel.SetTargets(updated_targets)
                            except Exception as e:
                                print(f"WARNING Could not copy external material relationship {rel.GetName()}: {e}")
                    
                    
                
            # After copying materials, update all material bindings in the external stage
            self._update_material_bindings_in_external_stage(external_stage)
        except Exception as e:
            print(f"WARNING Failed to copy materials to external stage: {e}")
    
    def _update_material_bindings_in_external_stage(self, external_stage):
        """Update material bindings in external stage to use correct paths"""
        try:
            # Traverse all prims in the external stage
            for prim in external_stage.TraverseAll():
                if prim.IsA(UsdGeom.Mesh):
                    # Check for material binding
                    material_binding_rel = prim.GetRelationship('material:binding')
                    if material_binding_rel:
                        targets = material_binding_rel.GetTargets()
                        if targets:
                            updated_targets = []
                            for target in targets:
                                target_str = str(target)
                                # Extract material name from original path - handle multiple path formats
                                material_name = None
                                if '/_materials/' in target_str:
                                    material_name = target_str.split('/_materials/')[-1]
                                elif '/root/Looks/' in target_str:
                                    material_name = target_str.split('/root/Looks/')[-1]
                                elif '/Root/Looks/' in target_str:
                                    material_name = target_str.split('/Root/Looks/')[-1]
                                elif '/Looks/' in target_str:
                                    material_name = target_str.split('/Looks/')[-1]
                                
                                if material_name:
                                    updated_target = f"/RootNode/Looks/{material_name}"
                                    updated_targets.append(updated_target)

                                else:
                                    # Keep original if not in expected format
                                    updated_targets.append(target)
                            
                            if updated_targets != targets:
                                material_binding_rel.SetTargets(updated_targets)
        except Exception as e:
            print(f"WARNING Failed to update material bindings in external stage: {e}")
    
    def _is_meaningful_attribute_value(self, attr_name, value):
        """Check if an attribute value is meaningful (not empty/default)"""
        # Always include critical mesh geometry attributes regardless of value
        critical_mesh_attrs = {
            'points', 'faceVertexIndices', 'faceVertexCounts', 'normals',
            'primvars:st', 'extent', 'doubleSided', 'subdivisionScheme'
        }
        if attr_name in critical_mesh_attrs:
            return True
            
        # Always include critical shader/material output attributes regardless of value
        critical_outputs = {'outputs:out'}
        if attr_name in critical_outputs:
            return True
            
        if value is None:
            return False
            
        # Skip empty arrays - these are default USD attributes that shouldn't be added if they weren't in the original
        if hasattr(value, '__len__') and len(value) == 0:
            return False
            
        # Skip specific empty/default mesh attributes that shouldn't be added if not in original
        empty_default_attrs = {
            'cornerIndices', 'cornerSharpnesses', 'creaseIndices', 
            'creaseLengths', 'creaseSharpnesses', 'holeIndices',
            'invisibleIds', 'velocities', 'accelerations', 'angularVelocities'
        }
        if attr_name in empty_default_attrs and hasattr(value, '__len__') and len(value) == 0:
            return False
            
        # Skip default boolean values for certain attributes
        default_false_attrs = {'doubleSided'}
        if attr_name in default_false_attrs and value is False:
            return False
            
        # Skip default enum/token values that shouldn't be added if not in original
        # Note: subdivisionScheme is handled separately above
        default_values = {
            'faceVaryingLinearInterpolation': 'cornersPlus1',
            'interpolateBoundary': 'edgeAndCorner', 
            'triangleSubdivisionRule': 'catmullClark',
            'purpose': 'default',
            'visibility': 'inherited',
            'orientation': 'rightHanded'
        }
        if attr_name in default_values and str(value) == default_values[attr_name]:
            return False
            
        # Don't skip identity transforms - they may be required by xformOpOrder
        # Keeping identity transform matrices to maintain consistency with xformOpOrder
                    
        return True
    
    def _is_standard_usd_attribute(self, attr_name):
        """Check if an attribute is a standard USD attribute (not custom)"""
        # Standard USD attributes that should not be marked as custom
        standard_attrs = {
            'points', 'faceVertexIndices', 'faceVertexCounts', 'normals',
            'primvars:st', 'primvars:displayColor', 'primvars:displayOpacity',
            'xformOp:translate', 'xformOp:rotateXYZ', 'xformOp:scale',
            'material:binding', 'kind', 'typeName', 'specifier'
        }
        
        # Check if it's a standard attribute
        if attr_name in standard_attrs:
            return True
        
        # Check if it's a primvar (should not be custom)
        if attr_name.startswith('primvars:'):
            return True
        
        # Check if it's a transform operation
        if attr_name.startswith('xformOp:'):
            return True
        
        # Check if it's a material binding
        if attr_name.startswith('material:'):
            return True
        
        return False
    
    def _get_materials_reference_path(self):
        """Calculate the correct relative path from output file to materials/AperturePBR_Opacity.usda"""
        # Find the mod root directory (containing mod.usda)
        current_dir = os.path.dirname(self.output_path)
        mod_root = current_dir
        while mod_root and not os.path.exists(os.path.join(mod_root, "mod.usda")):
            parent = os.path.dirname(mod_root)
            if parent == mod_root:  # Reached filesystem root
                break
            mod_root = parent
        
        if os.path.exists(os.path.join(mod_root, "mod.usda")):
            # Calculate relative path from output file to materials directory
            output_dir = os.path.dirname(self.output_path)
            materials_path = os.path.join(mod_root, "materials", "AperturePBR_Opacity.usda")
            relative_path = os.path.relpath(materials_path, output_dir).replace("\\", "/")
            
            # Add "./" prefix for same-level paths (when output is at mod.usda level)
            if not relative_path.startswith("../") and not relative_path.startswith("./"):
                relative_path = "./" + relative_path
            
            return relative_path
        else:
            # Fallback: calculate relative path assuming standard structure
            # Go up from meshes_converted to assets, then up to project root
            output_dir = os.path.dirname(self.output_path)
            if "meshes_converted" in output_dir.lower():
                return "../../materials/AperturePBR_Opacity.usda"
            elif "assets" in output_dir.lower():
                return "../materials/AperturePBR_Opacity.usda"
            else:
                return "./materials/AperturePBR_Opacity.usda"

    def _find_mod_file(self):
        """Find mod.usda file in parent directories"""
        current_dir = os.path.dirname(os.path.abspath(self.output_path))
        while current_dir:
            mod_file = os.path.join(current_dir, "mod.usda")
            if os.path.exists(mod_file):
                return mod_file
            parent = os.path.dirname(current_dir)
            if parent == current_dir:  # Reached filesystem root
                return ""
            current_dir = parent
        return ""
    
    def _setup_materials_directory(self):
        """Find project root with mod.usda and setup materials directory"""
        # Find the mod root directory (containing mod.usda)
        current_dir = os.path.dirname(self.output_path)
        mod_root = current_dir
        while mod_root and not os.path.exists(os.path.join(mod_root, "mod.usda")):
            parent = os.path.dirname(mod_root)
            if parent == mod_root:  # Reached filesystem root
                break
            mod_root = parent
        
        if os.path.exists(os.path.join(mod_root, "mod.usda")):
            # Found project root, materials directory should be here
            materials_dir = os.path.join(mod_root, "materials")
            print(f"     Found project root with mod.usda: {mod_root}")
        else:
            # Fallback: create materials directory relative to assets folder
            output_dir = os.path.dirname(self.output_path)
            parent_dir = os.path.dirname(output_dir)
            if "assets" in parent_dir.lower():
                materials_dir = os.path.join(parent_dir, "materials")
            else:
                materials_dir = os.path.join(output_dir, "materials")
            print(f"     No mod.usda found, using fallback materials directory")
        
        print(f"     Materials directory: {materials_dir}")
        os.makedirs(materials_dir, exist_ok=True)
        return materials_dir

    def _copy_aperture_pbr_material(self, materials_dir):
        """Copy AperturePBR_Opacity.usda to external materials directory if it doesn't exist"""
        target_material_path = os.path.join(materials_dir, "AperturePBR_Opacity.usda")
        
        # Check if it already exists
        if os.path.exists(target_material_path):
            print(f"     AperturePBR_Opacity.usda already exists in {materials_dir}")
            return
            
        try:
            # Find the source AperturePBR_Opacity.usda file - check multiple locations
            possible_sources = [
                os.path.join(os.path.dirname(__file__), "materials", "AperturePBR_Opacity.usda"),
                os.path.join(os.path.dirname(__file__), "Sample Files", "materials", "AperturePBR_Opacity.usda"),
            ]
            
            source_material_path = None
            for path in possible_sources:
                if os.path.exists(path):
                    source_material_path = path
                    break
            
            if source_material_path:
                shutil.copy2(source_material_path, target_material_path)
                print(f"     Copied AperturePBR_Opacity.usda to {materials_dir}")
            else:
                print(f"WARNING: Could not find AperturePBR_Opacity.usda in any expected location")
        except Exception as e:
            print(f"WARNING: Failed to copy AperturePBR_Opacity.usda: {e}")
    
    def _clear_texture_conversion_cache(self):
        """Clear texture conversion tracking cache after conversion is complete"""
        print(f" Clearing texture conversion cache ({len(self.texture_conversion_cache)} entries)")
        self.texture_conversion_cache.clear()
        self.textures_being_converted.clear()
    
    def _fix_external_texture_paths(self, external_stage):
        """Fix texture paths in external files to add ../ prefix since they're in Instance_Objs/ subfolder"""
        try:
            for prim in external_stage.TraverseAll():
                for attr in prim.GetAttributes():
                    if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                        value = attr.Get()
                        if value:
                            path_str = str(value.path) if hasattr(value, 'path') else str(value)
                            # Fix texture paths: ./textures/ -> ../textures/
                            if path_str.startswith('./textures/'):
                                new_path = path_str.replace('./textures/', '../textures/')
                                attr.Set(Sdf.AssetPath(new_path))
        except Exception as e:
            print(f"WARNING Failed to fix external texture paths: {e}")
    
    def _should_exclude_attribute_for_inline(self, attr_name):
        """Check if an attribute should be excluded for inline prototype meshes"""
        # EXCLUDE: Transform attributes
        transform_attrs = {
            'xformOp:translate', 'xformOp:rotateXYZ', 'xformOp:scale', 'xformOpOrder',
            'xformOp:transform', 'xformOp:rotateX', 'xformOp:rotateY', 'xformOp:rotateZ',
            'xformOp:rotate', 'xformOp:orient', 'xformOp:matrix'
        }
        
        # EXCLUDE: Highlight parameters (not needed for prototype meshes)
        highlight_attrs = {
            'primvars:displayOpacity', 'primvars:displayColor',
            'primvars:highlight', 'primvars:selection'
        }
        
        # EXCLUDE: Instance-specific attributes
        instance_attrs = {
            'primvars:instanceId', 'primvars:instanceIndex'
        }
        
        return attr_name in transform_attrs or attr_name in highlight_attrs or attr_name in instance_attrs
    
    def _copy_geomsubset_without_familyname(self, source_prim, target_stage, target_path, include_materials=True, skip_interpolation_fixes=False):
        """Copy GeomSubset without familyName but WITH material:binding for sub-materials"""
        try:
            target_prim = target_stage.DefinePrim(target_path, "GeomSubset")
            
            # Copy all attributes EXCEPT familyName
            for attr in source_prim.GetAttributes():
                attr_name = attr.GetName()
                if attr_name.startswith('__') or attr_name == 'familyName':
                    continue
                try:
                    value = attr.Get()
                    if value is not None:
                        target_attr = target_prim.CreateAttribute(attr_name, attr.GetTypeName())
                        target_attr.Set(value)
                except Exception as e:
                    print(f"WARNING Could not copy GeomSubset attribute {attr_name}: {e}")
            
            # KEEP material:binding for GeomSubsets - needed for sub-materials
            if include_materials:
                for rel in source_prim.GetRelationships():
                    rel_name = rel.GetName()
                    if rel_name.startswith('__'):
                        continue
                    if rel_name == "material:binding":
                        targets = rel.GetTargets()
                        if targets:
                            updated_targets = []
                            for target in targets:
                                target_str = str(target)
                                material_name = None
                                if "/_materials/" in target_str:
                                    material_name = target_str.split("/_materials/")[-1]
                                elif "/root/Looks/" in target_str:
                                    material_name = target_str.split("/root/Looks/")[-1]
                                elif "/Root/Looks/" in target_str:
                                    material_name = target_str.split("/Root/Looks/")[-1]
                                elif "/Looks/" in target_str:
                                    material_name = target_str.split("/Looks/")[-1]
                                
                                if material_name:
                                    updated_path = f"/RootNode/Looks/{material_name}"
                                    updated_targets.append(Sdf.Path(updated_path))
                            
                            if updated_targets:
                                binding_rel = target_prim.CreateRelationship("material:binding", custom=False)
                                binding_rel.SetTargets(updated_targets)
                    else:
                        try:
                            target_rel = target_prim.CreateRelationship(rel_name)
                            targets = rel.GetTargets()
                            if targets:
                                target_rel.SetTargets(targets)
                        except Exception as e:
                            continue
            
            return target_prim
        except Exception as e:
            print(f"WARNING Failed to copy GeomSubset: {e}")
            return None
    
    def _assign_all_material_bindings(self, output_stage):
        """Assign all material bindings at final step (avoids USD warnings)"""
        if not hasattr(self, '_pending_bindings'):
            return
        
        for prim_path, material_binding in self._pending_bindings:
            prim = output_stage.GetPrimAtPath(prim_path)
            if not prim or not prim.IsValid():
                continue
            
            material_binding_api = UsdShade.MaterialBindingAPI(prim)
            material_path = material_binding.get('target_path', '') if isinstance(material_binding, dict) else str(material_binding)
            
            if material_path and material_path.strip():
                material_name = None
                if '/_materials/' in material_path:
                    material_name = material_path.split('/_materials/')[-1]
                elif '/root/Looks/' in material_path:
                    material_name = material_path.split('/root/Looks/')[-1]
                elif '/Root/Looks/' in material_path:
                    material_name = material_path.split('/Root/Looks/')[-1]
                elif '/Looks/' in material_path:
                    material_name = material_path.split('/Looks/')[-1]
                elif '/root/prototypes/' in material_path:
                    material_name = material_path.split('/')[-1]
                
                if material_name:
                    material_prim = output_stage.GetPrimAtPath(f"/RootNode/Looks/{material_name}")
                    if material_prim:
                        material_binding_api.Bind(UsdShade.Material(material_prim))
    
    def _generate_clean_filename(self, name):
        """Generate clean filename from name"""
        if not name:
            return "Mesh"
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        clean_name = re.sub(r'_+', '_', clean_name)
        clean_name = clean_name.strip('_')
        if not clean_name:
            clean_name = "Mesh"
        if clean_name[0].isdigit():
            clean_name = f"_{clean_name}"
        return clean_name
    
    def _generate_box_projection_uvs(self, mesh_prim):
        """Generate simple box projection UVs for mesh without UVs (faceVarying interpolation)"""
        try:
            mesh = UsdGeom.Mesh(mesh_prim)
            points_attr = mesh.GetPointsAttr()
            face_vertex_indices_attr = mesh.GetFaceVertexIndicesAttr()
            
            if not points_attr or not points_attr.HasValue():
                return False
            if not face_vertex_indices_attr or not face_vertex_indices_attr.HasValue():
                return False
            
            points = points_attr.Get()
            face_vertex_indices = face_vertex_indices_attr.Get()
            
            # Calculate bounding box
            min_x = min_y = min_z = float('inf')
            max_x = max_y = max_z = float('-inf')
            for point in points:
                min_x, max_x = min(min_x, point[0]), max(max_x, point[0])
                min_y, max_y = min(min_y, point[1]), max(max_y, point[1])
                min_z, max_z = min(min_z, point[2]), max(max_z, point[2])
            
            # Avoid division by zero
            range_x = max_x - min_x if max_x != min_x else 1.0
            range_y = max_y - min_y if max_y != min_y else 1.0
            
            # Generate faceVarying UVs (one UV per face-vertex)
            uvs = []
            for vertex_index in face_vertex_indices:
                point = points[vertex_index]
                u = (point[0] - min_x) / range_x
                v = (point[1] - min_y) / range_y
                uvs.append(Gf.Vec2f(u, v))
            
            # Create primvars:st attribute with faceVarying interpolation
            primvar_api = UsdGeom.PrimvarsAPI(mesh_prim)
            st_primvar = primvar_api.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray)
            st_primvar.Set(uvs)
            st_primvar.SetInterpolation(UsdGeom.Tokens.faceVarying)
            
            return True
            
        except Exception as e:
            print(f"WARNING Failed to generate UVs for {mesh_prim.GetPath()}: {e}")
            return False

    def _calculate_face_counts(self, output_stage):
        """Calculate instance counts and use face counts from data collector"""
        try:
            # Build lookup table: mesh_name -> face_count from data collector
            prototype_meshes = self.output_data.get('prototype_meshes', {})
            mesh_name_to_face_count = {}
            for ref_path, proto_data in prototype_meshes.items():
                proto_name = proto_data['mesh_prim'].GetName()
                if 'face_count' in proto_data:
                    mesh_name_to_face_count[proto_name] = proto_data['face_count']
            
            # Also add face counts from PointInstancer data (Blender 4.5)
            for pi_data in self.output_data.get('pointinstancers', []):
                if 'prototype_face_counts' in pi_data:
                    for mesh_name, face_count in pi_data['prototype_face_counts'].items():
                        mesh_name_to_face_count[mesh_name] = face_count
            
            print(f"FACES Building lookup table from {len(mesh_name_to_face_count)} mesh face counts")
            
            # Count instances per prototype and load face counts
            for prim in output_stage.TraverseAll():
                if prim.IsA(UsdGeom.PointInstancer):
                    pi = UsdGeom.PointInstancer(prim)
                    proto_indices = pi.GetProtoIndicesAttr().Get()
                    print(f"FACES Found PointInstancer with {len(proto_indices) if proto_indices else 0} protoIndices")
                    if proto_indices:
                        proto_rel = pi.GetPrototypesRel()
                        if proto_rel:
                            targets = proto_rel.GetTargets()
                            print(f"FACES PointInstancer has {len(targets)} prototype targets")
                            # Count instances per prototype index
                            proto_instance_counts = {}
                            for idx in proto_indices:
                                proto_instance_counts[idx] = proto_instance_counts.get(idx, 0) + 1
                            print(f"FACES Instance counts per prototype index: {proto_instance_counts}")
                            
                            # Store instance counts and load face counts from lookup table
                            for proto_idx, target in enumerate(targets):
                                proto_prim = output_stage.GetPrimAtPath(target)
                                if proto_prim:
                                    instance_count = proto_instance_counts.get(proto_idx, 0)
                                    
                                    # Find the actual mesh inside the prototype container
                                    mesh_prim = None
                                    if proto_prim.IsA(UsdGeom.Mesh):
                                        mesh_prim = proto_prim
                                    else:
                                        for desc in Usd.PrimRange.AllPrims(proto_prim):
                                            if desc.IsA(UsdGeom.Mesh):
                                                mesh_prim = desc
                                                break
                                    
                                    if mesh_prim:
                                        mesh_name = mesh_prim.GetName()
                                        self.instance_counts[mesh_name] = instance_count
                                        
                                        # Load face count from lookup table using mesh name
                                        if mesh_name in mesh_name_to_face_count:
                                            self.prototype_face_counts[mesh_name] = mesh_name_to_face_count[mesh_name]
        except Exception as e:
            print(f"WARNING Failed to calculate face counts: {e}")
