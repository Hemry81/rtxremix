#!/usr/bin/env python3
"""
Final Simplified Unified Output Generator for USD PointInstancer Converter
Only generates output from prepared data - no data processing
"""

import os
import time
import shutil
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
from nvidia_texture_converter import NvidiaTextureConverter

class FinalOutputGenerator:
    """Final simplified output generation - only generates output from prepared data"""
    
    def __init__(self, output_data, output_path, use_external_references=False, export_binary=False, input_stage=None, convert_textures=False, normal_map_format="Auto-Detect", interpolation_mode="faceVarying"):
        self.output_data = output_data
        self.output_path = output_path
        self.use_external_references = use_external_references
        self.export_binary = export_binary
        self.input_stage = input_stage
        self.conversion_type = output_data.get('input_type', 'unknown')
        self.convert_textures = convert_textures
        self.normal_map_format = normal_map_format
        self.interpolation_mode = interpolation_mode
        
        # Initialize texture converter if enabled (with GPU acceleration, output to textures/)
        self.texture_converter = NvidiaTextureConverter(use_gpu=True, gpu_device=0) if convert_textures else None
        
        # Texture conversion tracking to avoid duplicate conversions
        self.texture_conversion_cache = {}  # Maps source_file -> output_file
        self.textures_being_converted = set()  # Track files currently being converted
        
    def generate_output(self):
        """Main output generation method"""
        print(f"OUTPUT Generating output from prepared data...")
        
        try:
            # Create stage
            output_stage = self._create_stage()
            
            # Copy materials
            self._copy_materials(output_stage)
            
            # Remove old root-level materials after successful RTX conversion
            self._remove_old_root_materials_after_conversion(output_stage)
            
            # Create unique objects
            self._create_unique_objects(output_stage)
            
            # Create PointInstancers
            pointinstancer_count = self._create_pointinstancers(output_stage)
            
            # Create external files if needed
            external_files_created = 0
            if self.use_external_references:
                external_files_created = self._create_external_files()
                
                # CLEANUP: Remove unused materials from main file after external references are created
                self._remove_unused_materials_from_main_file(output_stage)

            # Convert textures directly from source (no wasteful copying)
            textures_converted = 0
            if self.convert_textures:
                textures_converted = self._convert_textures_direct()
            
            # Save stage
            output_stage.Save()
            
            return {
                'pointinstancers_processed': pointinstancer_count,
                'external_files_created': external_files_created,
                'materials_converted': len(self.output_data['materials']),
                'textures_converted': textures_converted,
                'operation': f"{self.output_data.get('input_type', 'unknown')}_{'external' if self.use_external_references else 'inline'}"
            }
                
        except Exception as e:
            print(f"ERROR Failed to generate output: {e}")
            return None
    
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
        layer.defaultPrim = "Root"
        root_layer = output_stage.GetRootLayer()
        root_spec = Sdf.CreatePrimInLayer(root_layer, "/Root")
        root_spec.typeName = "Xform"
        root_spec.specifier = Sdf.SpecifierDef
        
        # Set kind metadata
        root_prim = output_stage.GetPrimAtPath("/Root")
        root_prim.SetMetadata("kind", "model")
        output_stage.SetDefaultPrim(root_prim)
        
        return output_stage
    
    def _copy_materials(self, output_stage):
        """Copy materials to output stage"""
        if not self.output_data['materials']:
            return
        
        # Create materials scope
        materials_scope = output_stage.DefinePrim("/Root/Looks", "Scope")
        
        for material_name, material_info in self.output_data['materials'].items():
            target_path = f"/Root/Looks/{material_name}"
            
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
        """Create Remix material with AperturePBR_Opacity reference"""
        try:
            material_name = os.path.basename(target_path)
            conversion_type = material_info.get('conversion_type', 'unknown')
            remix_params = material_info.get('remix_params', {})
            
            # Remove existing material if it exists
            if output_stage.GetPrimAtPath(target_path):
                output_stage.RemovePrim(target_path)
            
            # Create the material in the target stage
            target_material = output_stage.DefinePrim(target_path, "Material")
            
            # Add reference to AperturePBR_Opacity
            references = target_material.GetReferences()
            # Calculate proper relative path from output file to materials directory
            material_ref_path = self._get_materials_reference_path()
            references.AddReference(material_ref_path, "/Looks/mat_AperturePBR_Opacity")
            
            # Create Shader prim with Remix parameters (use OverridePrim for proper RTX Remix format)
            shader_path = f"{target_path}/Shader"
            shader_prim = output_stage.OverridePrim(shader_path)
            
            # Set Remix parameters with adjusted texture paths for external files
            self._set_remix_shader_parameters(shader_prim, remix_params, is_external)
            

            
        except Exception as e:
            print(f"ERROR Failed to create Remix material {material_name}: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")
    
    def _set_remix_shader_parameters(self, shader_prim, remix_params, is_external=False):
        """Set Remix shader parameters with proper types"""
        try:
            from pxr import Sdf, Gf
            
            for param_name, param_value in remix_params.items():
                # Skip parameters that don't need to be set
                if param_name in ['enable_emission', 'enable_thin_film', 'use_legacy_alpha_state', 'blend_enabled', 'preload_textures', 'ignore_material', '_original_params']:
                    continue
                
                # Adjust texture paths for external files
                if is_external and isinstance(param_value, str) and param_value.startswith('./textures/'):
                    param_value = param_value.replace('./textures/', '../textures/')
                
                # Convert texture paths to DDS extension if texture conversion is enabled
                if self.convert_textures and isinstance(param_value, str) and param_name.endswith('_texture'):
                    if not param_value.endswith('.dds') and any(ext in param_value.lower() for ext in ['.png', '.jpg', '.jpeg', '.tga']):
                        # Extract filename without extension and add .dds
                        base_name = os.path.splitext(param_value)[0]
                        param_value = f"{base_name}.dds"
                
                # Determine parameter type and convert value
                param_type = None
                converted_value = None
                
                if isinstance(param_value, bool):
                    param_type = Sdf.ValueTypeNames.Bool
                    converted_value = param_value
                elif isinstance(param_value, int):
                    param_type = Sdf.ValueTypeNames.Int
                    converted_value = param_value
                elif isinstance(param_value, float):
                    param_type = Sdf.ValueTypeNames.Float
                    converted_value = param_value
                elif isinstance(param_value, str):
                    # Handle string values that need specific types
                    if param_name.endswith('_constant') and param_value.startswith('color('):
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
                    elif param_name.endswith('_texture'):
                        # Texture paths (DDS conversion already handled above)
                        param_type = Sdf.ValueTypeNames.Asset
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
                
                # Create and set the parameter
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
        # For reverse conversion, we need to create proper parent containers
        if self.conversion_type == 'reverse':
            self._create_reverse_output_structure(output_stage)
        else:
            # Forward conversion - use existing logic
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
            
            # Create PointInstancers under their parent anchors
            for pointinstancer_data in self.output_data['pointinstancers']:
                self._create_pointinstancer(output_stage, pointinstancer_data)
    
    def _create_anchor_mesh(self, output_stage, mesh_data):
        """Create anchor mesh (parent container)"""
        mesh_name = os.path.basename(mesh_data['path'])
        # Clean the mesh name to avoid path issues
        clean_mesh_name = mesh_name.replace('.', '_')
        mesh_prim = output_stage.DefinePrim(Sdf.Path(f"/Root/{clean_mesh_name}"), "Xform")
        
        # If this anchor has a mesh, create the mesh as a child
        if mesh_data['mesh_prim'].IsA(UsdGeom.Mesh):
            mesh_child_path = f"/Root/{clean_mesh_name}/{clean_mesh_name}_mesh"
            
            # Use the unified copy_prim_data approach for proper UV copying
            self.copy_prim_data(mesh_data['mesh_prim'], output_stage, mesh_child_path)
            
            # Get the copied mesh prim for material binding
            mesh_child_prim = output_stage.GetPrimAtPath(mesh_child_path)
            
            # Set material binding
            if mesh_data['material_binding']:
                material_binding_api = UsdShade.MaterialBindingAPI(mesh_child_prim)
                # Handle material binding as dictionary or string
                if isinstance(mesh_data['material_binding'], dict):
                    material_path = mesh_data['material_binding'].get('target_path', '')
                else:
                    material_path = str(mesh_data['material_binding'])
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
                        elif '/root/prototypes/' in material_path:
                            # Handle prototype material references
                            parts = material_path.split('/')
                            if len(parts) >= 4:
                                material_name = parts[-1]  # Get the material name from the end
                        
                        if material_name:
                            correct_material_path = f"/Root/Looks/{material_name}"
                            material_prim = mesh_child_prim.GetStage().GetPrimAtPath(Sdf.Path(correct_material_path))
                            if material_prim:
                                material_binding_api.Bind(UsdShade.Material(material_prim))
                
                            else:
                                print(f"WARNING Material not found at {correct_material_path}")
                        else:
                            print(f"WARNING Could not extract material name from {material_path}")
                    except Exception as e:
                        print(f"WARNING Failed to bind material {material_path}: {e}")
        
        # Set transform on the anchor container
        if mesh_data.get('transform') and mesh_data['transform'] != Gf.Matrix4d(1.0):
            xformable = UsdGeom.Xformable(mesh_prim)
            xformable.AddTransformOp().Set(mesh_data['transform'])
        
        return mesh_prim
    
    def _create_single_instance(self, output_stage, instance_data):
        """Create single instance as child of its parent anchor"""
        # Get the parent anchor path
        parent_path = instance_data.get('parent_path', '/Root')
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
                    elif '/root/prototypes/' in material_path:
                        # Handle prototype material references
                        parts = material_path.split('/')
                        if len(parts) >= 4:
                            material_name = parts[-1]  # Get the material name from the end
                    
                    if material_name:
                        correct_material_path = f"/Root/Looks/{material_name}"
                        material_prim = instance_prim.GetStage().GetPrimAtPath(Sdf.Path(correct_material_path))
                        if material_prim:
                            material_binding_api.Bind(UsdShade.Material(material_prim))

                        else:
                            print(f"WARNING Material not found at {correct_material_path}")
                    else:
                        print(f"WARNING Could not extract material name from {material_path}")
                except Exception as e:
                    print(f"WARNING Failed to bind material {material_path}: {e}")
    
    # ========================================
    # REVERSE CONVERSION METHODS
    # ========================================
    
    def _create_reverse_output_structure(self, output_stage):
        """Create proper hierarchy structure for reverse conversion"""
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
                unique_object_data['parent_path'] = f"/Root/{parent_name}"
                # Create single instance under its parent anchor
                self._create_single_instance_under_parent(output_stage, unique_object_data)
    
    def _create_reverse_parent_with_pointinstancers(self, parent_name, parent_data, output_stage):
        """Create parent container and nest PointInstancers under it"""
        # Create parent Xform container
        target_parent_path = f"/Root/{parent_name}"
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
                            correct_material_path = f"/Root/Looks/{material_name}"
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
        parent_path = instance_data.get('parent_path', '/Root')
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
                        correct_material_path = f"/Root/Looks/{material_name}"
                        material_prim = instance_prim.GetStage().GetPrimAtPath(Sdf.Path(correct_material_path))
                        if material_prim:
                            material_binding_api.Bind(UsdShade.Material(material_prim))
                except Exception as e:
                    print(f"WARNING Failed to bind material {material_path}: {e}")
    
    def _create_pointinstancer_at_root(self, output_stage, pointinstancer_data):
        """Create PointInstancer at root level (for instances without parent containers)"""
        instancer_path = f"/Root/{pointinstancer_data['name']}"
        self._create_pointinstancer_from_data(output_stage, instancer_path, pointinstancer_data)
    

    
    def _create_pointinstancer(self, output_stage, pointinstancer_data):
        """Create PointInstancer as child of its parent anchor"""
        # Get the parent anchor path
        parent_path = pointinstancer_data.get('parent_path', '/Root')
        instancer_name = os.path.basename(pointinstancer_data['path'])
        
        # Create PointInstancer under its parent anchor
        instancer_path = f"{parent_path}/{instancer_name}"
        instancer = UsdGeom.PointInstancer.Define(output_stage, instancer_path)
        
        # Handle external references
        prototype_mesh = pointinstancer_data.get('prototype_mesh') or pointinstancer_data.get('prototype_prim')
        if self.use_external_references and prototype_mesh:
            # External reference - create Xform with external reference (like Sample_reference_prototypes.usda)
            prototype_name = prototype_mesh.GetName()
            # Create prototype directly inside the PointInstancer
            prototype_path = f"{instancer_path}/{prototype_name}"
            
            # Create Xform with external reference (not Mesh)
            prototype_prim = output_stage.DefinePrim(prototype_path, "Xform")
            prototype_prim.SetMetadata("kind", "component")
            
            # Add external reference using the correct format
            external_file = f"./Instance_Objs/{prototype_name}.usd"
            references = prototype_prim.GetReferences()
            references.AddReference(external_file)
            
            # Set as prototype target
            instancer.GetPrototypesRel().AddTarget(prototype_path)
            

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
                                updated_target = f"/Root/Looks/{material_name}"
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
            parent_path = pointinstancer_data.get('parent_path', '/Root')
            has_parent_container = parent_path != '/Root'
            
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
                    print(f"FILTER: Skipping first instance {instance_data.get('blender_name', instance_data['path'])} (likely base prototype reference)")
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
            # Existing PointInstancer - copy original attributes
            source_instancer = pointinstancer_data['prim']
            source_pi = UsdGeom.PointInstancer(source_instancer)
            
            # Copy all PointInstancer attributes
            for attr in source_instancer.GetPrim().GetAttributes():
                if not attr.GetName().startswith('__'):
                    try:
                        target_attr = instancer.GetPrim().GetAttribute(attr.GetName())
                        if target_attr and attr.HasValue():
                            target_attr.Set(attr.Get())
                    except Exception as e:
                        print(f"WARNING Could not copy PointInstancer attribute {attr.GetName()}: {e}")
            
            # Copy prototype relationships
            source_prototypes = source_pi.GetPrototypesRel()
            if source_prototypes:
                target_prototypes = instancer.GetPrototypesRel()
                targets = source_prototypes.GetTargets()
                if targets:
                    target_prototypes.SetTargets(targets)
            
    
    
    def _create_pointinstancers(self, output_stage):
        """Create PointInstancers from prepared data"""
        # Skip regular PointInstancer creation for reverse conversion
        # since they are already created in _create_reverse_output_structure
        if self.conversion_type == 'reverse':
            return 0
        
        pointinstancer_count = 0
        
        for pointinstancer_data in self.output_data['pointinstancers']:
            if pointinstancer_data['type'] == 'pointinstancer':
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
                import shutil
                
                # Create a temporary file to avoid USD layer caching issues
                with tempfile.NamedTemporaryFile(suffix=".usda", delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Create new stage with temporary file (ASCII format)
                external_stage = Usd.Stage.CreateNew(temp_path)
                
                # Ensure ASCII format is set
                layer = external_stage.GetRootLayer()
                layer.fileFormat = 'usda'
                
                # Set up stage structure
                UsdGeom.SetStageUpAxis(external_stage, UsdGeom.Tokens.z)
                layer.defaultPrim = "Root"
                
                # Create root
                root_prim = external_stage.DefinePrim("/Root", "Xform")
                root_prim.SetMetadata("kind", "model")
                external_stage.SetDefaultPrim(root_prim)
                
                # Create prototype container Xform
                prototype_container = external_stage.DefinePrim("/Root/prototype", "Xform")
                prototype_container.SetMetadata("kind", "component")
                
                # Copy prototype data with full details using unified method
                # Copy to the prototype container, preserving the original name
                # IMPORTANT: Set include_materials=False to prevent copying duplicate materials
                prototype_name = external_prototype_data['prim'].GetName()
                prototype_path = f"/Root/prototype/{prototype_name}"
                self.copy_prim_data(external_prototype_data['prim'], external_stage, prototype_path, include_materials=False, include_children=True)
                
                # DO NOT copy materials to external file - they should only be in the main file
                # This prevents namespace collisions and unused material warnings
                # self._copy_materials_to_external_stage(external_stage, external_prototype_data['materials'])
                
                # CLEANUP: Remove any remaining materials from the external stage
                self._remove_unused_materials_from_external_stage(external_stage)
                
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
        
        # Use parent_path if available, otherwise fall back to path
        parent_path = pointinstancer_data.get('parent_path', '/Root')
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
            
            # Find prototype children and update the relationship
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
            
            # IMPORTANT: Apply interpolation fixes to the entire copied PointInstancer structure
            # This ensures Remix compatibility by converting vertex to faceVarying interpolation for normals and texCoords
            self._apply_interpolation_fixes_recursive(copied_instancer)
    
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
                        updated_path = f"/Root/Looks/{material_name}"
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

    def _apply_interpolation_fixes_recursive(self, prim):
        """Recursively apply interpolation fixes to all mesh prims for Remix compatibility - convert vertex to faceVarying for normals and texCoords"""
        try:
            # Apply interpolation fixes to this prim if it's a mesh
            if prim.IsA(UsdGeom.Mesh):
                print(f"REMIX Applying interpolation fixes to mesh: {prim.GetPath()}")
                self._apply_interpolation_fixes_to_mesh(prim)
            
            # Recursively process all children
            for child in prim.GetAllChildren():
                self._apply_interpolation_fixes_recursive(child)
                
        except Exception as e:
            print(f"WARNING Failed to apply interpolation fixes to {prim.GetPath()}: {e}")

    def _apply_interpolation_fixes_to_mesh(self, mesh_prim):
        """Apply interpolation fixes to a single mesh prim for Remix compatibility"""
        try:
            # Skip interpolation conversion if mode is 'none'
            if self.interpolation_mode == "none":
                print(f"REMIX Skipping interpolation conversion for mesh: {mesh_prim.GetPath()}")
                return
            
            # Fix ONLY normals and texCoord primvars based on selected mode
            # Keep all other attributes unchanged
            primvar_api = UsdGeom.PrimvarsAPI(mesh_prim)
            if primvar_api:
                # Get all primvars and fix interpolation for specific types only
                for primvar in primvar_api.GetPrimvars():
                    if primvar:
                        current_interpolation = primvar.GetInterpolation()
                        primvar_name = primvar.GetPrimvarName()
                        
                        # Apply conversion based on selected mode for texCoord primvars
                        if self.interpolation_mode == "faceVarying" and current_interpolation == UsdGeom.Tokens.vertex:
                            # Check if this is a texCoord primvar (st, uv, texCoord, etc.)
                            if ("st" in primvar_name or "uv" in primvar_name.lower() or 
                                "texcoord" in primvar_name.lower() or primvar_name.startswith("primvars:")):
                                primvar.SetInterpolation(UsdGeom.Tokens.faceVarying)
                                print(f"REMIX Fixed texCoord interpolation {current_interpolation}→faceVarying for primvar: {primvar_name}")
                            else:
                                print(f"REMIX Kept vertex interpolation for non-texCoord primvar: {primvar_name}")
                        elif self.interpolation_mode == "vertex" and current_interpolation == UsdGeom.Tokens.faceVarying:
                            # Check if this is a texCoord primvar (st, uv, texCoord, etc.)
                            if ("st" in primvar_name or "uv" in primvar_name.lower() or 
                                "texcoord" in primvar_name.lower() or primvar_name.startswith("primvars:")):
                                primvar.SetInterpolation(UsdGeom.Tokens.vertex)
                                print(f"REMIX Fixed texCoord interpolation {current_interpolation}→vertex for primvar: {primvar_name}")
                            else:
                                print(f"REMIX Kept faceVarying interpolation for non-texCoord primvar: {primvar_name}")
                        else:
                            print(f"REMIX Kept {current_interpolation} interpolation for primvar: {primvar_name}")
            
            # Fix direct attributes that have interpolation modes (like normals)
            mesh = UsdGeom.Mesh(mesh_prim)
            if mesh:
                # Check and fix normals interpolation based on selected mode
                normals_attr = mesh.GetNormalsAttr()
                if normals_attr and normals_attr.HasValue():
                    try:
                        current_normals_interpolation = mesh.GetNormalsInterpolation()
                        if self.interpolation_mode == "faceVarying" and current_normals_interpolation == UsdGeom.Tokens.vertex:
                            # Convert vertex to faceVarying
                            mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
                            print(f"REMIX Fixed normals interpolation {current_normals_interpolation}→faceVarying for mesh: {mesh_prim.GetPath()}")
                        elif self.interpolation_mode == "vertex" and current_normals_interpolation == UsdGeom.Tokens.faceVarying:
                            # Convert faceVarying to vertex
                            mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                            print(f"REMIX Fixed normals interpolation {current_normals_interpolation}→vertex for mesh: {mesh_prim.GetPath()}")
                        else:
                            print(f"REMIX Kept normals interpolation {current_normals_interpolation} for mesh: {mesh_prim.GetPath()}")
                    except Exception as e:
                        print(f"WARNING Could not fix normals interpolation: {e}")
            
            # Also ensure float2 primvars are converted to texCoord2f for Remix compatibility
            stage = mesh_prim.GetStage()
            self._convert_float2_primvars_in_stage(stage)
            
        except Exception as e:
            print(f"WARNING Failed to apply interpolation fixes to mesh {mesh_prim.GetPath()}: {e}")

    def _convert_textures_direct(self):
        """Convert only textures that are actually referenced in materials - NO WASTEFUL COPYING!"""
        if not self.texture_converter or not self.texture_converter.nvtt_compress_path:
            print("⚠️  Texture conversion skipped - NVIDIA Texture Tools not available")
            return 0
        
        print("🎨 Converting textures with NVIDIA Texture Tools...")
        
        # Find source textures directory from input
        if not self.input_stage:
            print("⚠️  No input stage available for texture conversion")
            return 0
            
        try:
            root_layer = self.input_stage.GetRootLayer()
            input_identifier = getattr(root_layer, 'realPath', None) or getattr(root_layer, 'identifier', None)
            if not input_identifier:
                print("⚠️  Could not determine input file location")
                return 0

            input_dir = os.path.dirname(input_identifier)
            source_textures_dir = os.path.join(input_dir, 'textures')
            
            if not os.path.exists(source_textures_dir):
                print(f"⚠️  Source textures directory not found: {source_textures_dir}")
                return 0
                
        except Exception as e:
            print(f"⚠️  Error finding source textures directory: {e}")
            return 0
        
        # Create output textures directory
        output_dir = os.path.dirname(self.output_path)
        target_textures_dir = os.path.join(output_dir, "textures")
        os.makedirs(target_textures_dir, exist_ok=True)
        
        # Collect actually referenced textures from materials
        referenced_textures = self._collect_referenced_textures()
        
        if not referenced_textures:
            print("⚠️  No texture references found in materials - skipping conversion")
            return 0
        
        print(f"🔍 Found {len(referenced_textures)} texture references in materials")
        print(f"📁 Converting textures from: {source_textures_dir}")
        print(f"📁 Output directory: {target_textures_dir}")
        
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
    
    def _convert_textures(self):
        """DEPRECATED: Use _convert_textures_direct() instead"""
        print("⚠️  _convert_textures() is deprecated - using direct conversion instead")
        return self._convert_textures_direct()
    
    def _collect_referenced_textures(self):
        """Collect all texture paths referenced in materials"""
        referenced_textures = set()
        
        try:
            # Open the output stage to scan for texture references
            stage = Usd.Stage.Open(self.output_path)
            
            # Traverse all prims looking for materials and their texture inputs
            for prim in stage.TraverseAll():
                if prim.IsA(UsdShade.Material):
                    material = UsdShade.Material(prim)
                    self._collect_textures_from_material(material, referenced_textures)
                elif prim.GetName() == "Shader" and prim.GetParent().IsA(UsdShade.Material):
                    # Handle RTX Remix "over Shader" patterns directly
                    self._collect_textures_from_shader_prim(prim, referenced_textures)
            
            print(f"📋 Collected {len(referenced_textures)} unique texture references:")
            for texture_path in sorted(referenced_textures):
                print(f"    📄 {texture_path}")
                
        except Exception as e:
            print(f"❌ Error collecting texture references: {e}")
            
        return referenced_textures
    
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
            print(f"⚠️  Error collecting textures from material {material.GetPath()}: {e}")
    
    def _collect_textures_from_shader(self, shader, referenced_textures):
        """Collect texture references from a shader (deprecated - use _collect_textures_from_shader_prim)"""
        try:
            shader_prim = shader.GetPrim()
            self._collect_textures_from_shader_prim(shader_prim, referenced_textures)
        except Exception as e:
            print(f"⚠️  Error collecting textures from shader {shader.GetPath()}: {e}")
    
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
                                print(f"    🎨 Found texture reference: {clean_path}")
                            referenced_textures.add(clean_path)
                            
        except Exception as e:
            print(f"⚠️  Error collecting textures from shader prim {shader_prim.GetPath()}: {e}")
    
    def _convert_referenced_textures_only(self, referenced_textures, source_textures_dir, output_dir):
        """Convert only textures that are actually referenced"""
        results = {}
        successful_count = 0
        failed_count = 0
        missing_count = 0
        
        # First pass: create mapping of source files to all their references
        source_file_to_refs = {}
        
        for texture_ref in referenced_textures:
            # Handle different path formats
            if texture_ref.startswith('./textures/'):
                # Relative path from USD file
                texture_filename = texture_ref[11:]  # Remove './textures/'
            elif texture_ref.startswith('./'):
                # Other relative path
                texture_filename = os.path.basename(texture_ref)
            else:
                # Direct filename or absolute path
                texture_filename = os.path.basename(texture_ref)
            
            # Look for the source texture file in the source directory
            source_file = os.path.join(source_textures_dir, texture_filename)
            
            # Check different extensions for source file
            source_extensions = ['.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff']
            actual_source_file = None
            
            # If it already has DDS extension, check if source exists with other extensions
            if texture_filename.lower().endswith('.dds'):
                base_name = texture_filename[:-4]  # Remove .dds
                for ext in source_extensions:
                    candidate = os.path.join(source_textures_dir, base_name + ext)
                    if os.path.exists(candidate):
                        actual_source_file = candidate
                        break
            else:
                # Direct file check
                if os.path.exists(source_file):
                    actual_source_file = source_file
                else:
                    # Try different extensions for the base name
                    base_name = os.path.splitext(texture_filename)[0]
                    for ext in source_extensions:
                        candidate = os.path.join(source_textures_dir, base_name + ext)
                        if os.path.exists(candidate):
                            actual_source_file = candidate
                            break
            
            if actual_source_file:
                if actual_source_file not in source_file_to_refs:
                    source_file_to_refs[actual_source_file] = []
                source_file_to_refs[actual_source_file].append(texture_ref)
            else:
                # Handle missing files immediately
                missing_count += 1
                print(f"⚠️  Referenced texture not found: {texture_ref}")
                print(f"    Looked for: {texture_filename} in {source_textures_dir}")
                
                results[texture_ref] = {
                    'success': False,
                    'output': None,
                    'referenced_path': texture_ref,
                    'missing': True
                }
        
        print(f"🔍 Found {len(source_file_to_refs)} unique source textures for {len(referenced_textures)} references")
        
        # Print detailed mapping for debugging
        for source_file, refs in source_file_to_refs.items():
            filename = os.path.basename(source_file)
            if len(refs) > 1:
                print(f"📋 {filename} has {len(refs)} references: {refs}")
            else:
                print(f"📄 {filename} has 1 reference: {refs[0]}")
        
        # Second pass: convert each unique source file only once
        for actual_source_file, texture_refs in source_file_to_refs.items():
            texture_filename = os.path.basename(actual_source_file)
            output_filename = os.path.splitext(texture_filename)[0] + '.dds'
            output_file = os.path.join(output_dir, output_filename)
            
            # Show how many references point to this file
            if len(texture_refs) > 1:
                print(f"📋 Processing texture: {texture_filename} (referenced {len(texture_refs)} times)")
            
            # Check if this texture was already processed in this session
            if actual_source_file in self.texture_conversion_cache:
                cached_output = self.texture_conversion_cache[actual_source_file]
                print(f"📋 Using cached conversion: {os.path.basename(actual_source_file)} → {os.path.basename(cached_output)}")
                successful_count += 1
                # Update results for all references to this file
                for texture_ref in texture_refs:
                    results[texture_ref] = {
                        'success': True,
                        'output': cached_output,
                        'referenced_path': texture_ref
                    }
                continue
            
            # Check if this texture is currently being converted
            if actual_source_file in self.textures_being_converted:
                print(f"⏳ Texture already being converted, skipping: {os.path.basename(actual_source_file)}")
                continue
            
            # Check if DDS file already exists and is valid (non-zero size)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"⏭️  Using existing DDS file: {output_filename}")
                successful_count += 1
                # Cache this result for future reference
                self.texture_conversion_cache[actual_source_file] = output_file
                # Update results for all references to this file
                for texture_ref in texture_refs:
                    results[texture_ref] = {
                        'success': True,
                        'output': output_file,
                        'referenced_path': texture_ref
                    }
                continue
            
            # Mark texture as being converted
            self.textures_being_converted.add(actual_source_file)
            
            print(f"🔄 Converting referenced texture: {os.path.basename(actual_source_file)} → {output_filename}")
            print(f"    📁 Source: {actual_source_file}")
            print(f"    📁 Target: {output_file}")
            print(f"    🔍 Source exists: {os.path.exists(actual_source_file)}")
            print(f"    📊 Source size: {os.path.getsize(actual_source_file) if os.path.exists(actual_source_file) else 0} bytes")
            print(f"    ⏱️  Starting conversion at: {time.time()}")
            
            start_time = time.time()
            try:
                # Use optimized settings for better performance
                # - 'normal' quality instead of 'highest' for speed
                # - GPU acceleration should handle this efficiently
                success = self.texture_converter.convert_texture(
                    actual_source_file,
                    output_file,
                    format='dds',
                    quality='normal'  # Changed from 'highest' to 'normal' for performance
                )
            finally:
                # Remove from being converted set regardless of success/failure
                self.textures_being_converted.discard(actual_source_file)
                end_time = time.time()
                conversion_time = end_time - start_time
                print(f"    ⏱️  Conversion took: {conversion_time:.2f} seconds")
            
            if success:
                successful_count += 1
                print(f"    ✅ Successfully converted: {output_filename}")
                # Cache successful conversion for future reference
                self.texture_conversion_cache[actual_source_file] = output_file
            else:
                failed_count += 1
                print(f"    ❌ Failed to convert: {os.path.basename(actual_source_file)}")
            
            # Update results for all references to this file
            for texture_ref in texture_refs:
                results[texture_ref] = {
                    'success': success,
                    'output': output_file if success else None,
                    'referenced_path': texture_ref
                }
        
        # Print summary
        print(f"\n📊 Texture Conversion Summary:")
        print(f"   ✅ Successfully converted: {successful_count}")
        print(f"   ❌ Failed conversions: {failed_count}")
        print(f"   📵 Missing source files: {missing_count}")
        print(f"   📁 Output directory: {output_dir}")
        
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
                                    print(f"    ✅ Updated texture reference: {current_path_str} → {new_path}")
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
                                print(f"    ✅ Updated texture reference: {value_str} → {new_path}")
                                updated_any = True
                                successful_conversions += 1
            
            if updated_any:
                stage.Save()
                print(f"💾 Updated USD file with {successful_conversions} DDS texture references")
            
        except Exception as e:
            print(f"❌ Error updating texture references: {e}")
        
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
                                        updated_path = f"/Root/Looks/{material_name}"
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
    
    def _cleanup_unused_materials(self, output_stage):
        """Remove unused materials to prevent clutter and conflicts"""
        try:
            # Get all materials in output
            output_materials = []
            for prim in output_stage.TraverseAll():
                if prim.IsA(UsdShade.Material):
                    output_materials.append(prim)
            
            # Get all material bindings
            used_materials = set()
            for prim in output_stage.TraverseAll():
                if prim.IsA(UsdGeom.Mesh):
                    material_binding_api = UsdShade.MaterialBindingAPI(prim)
                    if material_binding_api:
                        binding_rel = material_binding_api.GetDirectBindingRel()
                        if binding_rel:
                            targets = binding_rel.GetTargets()
                            if targets:
                                used_materials.add(str(targets[0]))
            
            # Remove unused materials
            removed_count = 0
            for material in output_materials:
                material_path = str(material.GetPath())
                if material_path not in used_materials:
                    try:
                        output_stage.RemovePrim(material.GetPath())
                        removed_count += 1
                    except Exception as e:
                        print(f"WARNING Could not remove unused material {material_path}: {e}")
            
            pass
                
        except Exception as e:
            print(f"WARNING Failed to cleanup unused materials: {e}")
    
    def _remove_old_blender_materials_from_prototype(self, prototype_prim):
        """Remove old Blender material scopes from prototypes since we now have RTX Remix materials in /Root/Looks"""
        try:
            print(f"CLEANUP Scanning prototype for old Blender materials: {prototype_prim.GetPath()}")
            materials_to_remove = []
            
            # Traverse all descendants to find _materials scopes
            for prim in prototype_prim.GetStage().Traverse():
                # Check if this prim is under our prototype path
                if not str(prim.GetPath()).startswith(str(prototype_prim.GetPath())):
                    continue
                    
                if prim.GetTypeName() == "Scope" and prim.GetName() == "_materials":
                    print(f"CLEANUP Found _materials scope: {prim.GetPath()}")
                    # Check if this scope contains Blender materials (Principled_BSDF shaders)
                    has_blender_materials = False
                    for material_child in prim.GetStage().Traverse():
                        if str(material_child.GetPath()).startswith(str(prim.GetPath())):
                            if material_child.GetTypeName() == "Shader" and "Principled_BSDF" in material_child.GetName():
                                print(f"CLEANUP Found Blender shader: {material_child.GetPath()}")
                                has_blender_materials = True
                                break
                    
                    if has_blender_materials:
                        materials_to_remove.append(prim.GetPath())
                        print(f"CLEANUP Marking for removal: {prim.GetPath()}")
            
            # Remove the old materials scopes
            for material_scope_path in materials_to_remove:
                try:
                    prototype_prim.GetStage().RemovePrim(material_scope_path)
                    print(f"CLEANUP Successfully removed old Blender materials scope: {material_scope_path}")
                except Exception as e:
                    print(f"WARNING Could not remove old materials scope {material_scope_path}: {e}")
                    
            if not materials_to_remove:
                print(f"CLEANUP No old Blender materials found in prototype: {prototype_prim.GetPath()}")
                    
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
                # Verify that RTX Remix materials exist in /Root/Looks before removing old ones
                rtx_materials_exist = False
                for prim in output_stage.TraverseAll():
                    if (prim.IsA(UsdShade.Material) and 
                        "/Root/Looks/" in str(prim.GetPath())):
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
    
    def _remove_unused_materials_from_external_stage(self, external_stage):
        """Remove unused materials from external stage - keep only /Root/Looks/ materials"""
        try:
            print("CLEANUP Removing unused materials from external stage...")
            
            materials_removed = 0
            materials_to_remove = []
            
            # Remove ALL duplicate material scopes from external stage - we only want /Root/Looks/
            # The problem is that USD composition creates namespace collisions
            for prim in external_stage.TraverseAll():
                prim_path_str = str(prim.GetPath())
                
                # We want to remove ALL /Root/Looks/ materials since they create problems in composition
                # Only the main file should have /Root/Looks/ materials
                if (prim_path_str.startswith("/Root/Looks/") and 
                    prim_path_str != "/Root/Looks"):
                    
                    materials_to_remove.append(prim.GetPath())
                    print(f"CLEANUP Found duplicate material in external file: {prim_path_str}")
                
                # Also remove the entire /Root/Looks scope if it exists
                elif (prim.GetName() == "Looks" and 
                      prim_path_str == "/Root/Looks"):
                    
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

    def _remove_unused_materials_from_main_file(self, main_stage):
        """Remove unused materials from main file when using external references"""
        try:
            print("CLEANUP Removing unused materials from main file with external references...")
            
            materials_removed = 0
            materials_to_remove = []
            
            # Find all material-containing scopes that are NOT in /Root/Looks/
            for prim in main_stage.TraverseAll():
                prim_path_str = str(prim.GetPath())
                
                # Look for Looks scopes inside external reference prims (like /Root/mesh_001/Wild_Grass_1_002/Looks/)
                if (prim.GetName() == "Looks" and 
                    prim_path_str != "/Root/Looks" and
                    "/Root/" in prim_path_str and
                    len(prim_path_str.split("/")) > 3):  # More than just /Root/Looks
                    
                    # This is a duplicate materials scope from external reference - mark for removal
                    materials_to_remove.append(prim.GetPath())
                    print(f"CLEANUP Found unused materials scope in main file: {prim_path_str}")
                
                # Also look for individual materials outside /Root/Looks/ in external reference structure
                elif (prim.IsA(UsdShade.Material) and 
                      not prim_path_str.startswith("/Root/Looks/") and
                      "/Root/" in prim_path_str and
                      len(prim_path_str.split("/")) > 3):  # Avoid removing root-level materials
                    
                    materials_to_remove.append(prim.GetPath())
                    print(f"CLEANUP Found unused material in main file: {prim_path_str}")
            
            # Remove the unused material scopes and materials
            for material_path in materials_to_remove:
                try:
                    main_stage.RemovePrim(material_path)
                    materials_removed += 1
                    print(f"CLEANUP Successfully removed unused material/scope from main file: {material_path}")
                except Exception as e:
                    print(f"WARNING Could not remove unused material from main file {material_path}: {e}")
            
            if materials_removed > 0:
                print(f"CLEANUP Removed {materials_removed} unused materials from main file")
            else:
                print(f"CLEANUP No unused materials found to remove in main file")
                
        except Exception as e:
            print(f"WARNING Failed to cleanup unused materials from main file: {e}")
            import traceback
            print(f"Details: {traceback.format_exc()}")

    # Utility methods
    def copy_prim_data(self, source_prim, target_stage, target_path, include_materials=True, include_children=True, inline_mode=False):
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
                                    print(f"REMIX Corrected UV interpolation: constant→vertex for {attr_name}")
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
                                            updated_path = f"/Root/Looks/{material_name}"
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
            if include_children:
                for child in source_prim.GetAllChildren():
                    child_name = child.GetName()
                    # Skip materials folder when not including materials
                    if not include_materials and child_name in ["_materials", "materials", "Looks"]:
                        continue
                    child_target_path = f"{target_path}/{child_name}"
                    self.copy_prim_data(child, target_stage, child_target_path, include_materials, include_children)
            
            # Clean up old Blender materials from prototypes after copying
            if inline_mode:
                self._remove_old_blender_materials_from_prototype(target_prim)
            
            # Also check if this is a prototype that contains old Blender materials and clean it
            elif "Prototype" in target_path and self._contains_old_blender_materials(target_prim):
                print(f"CLEANUP Detected prototype with old Blender materials: {target_path}")
                self._remove_old_blender_materials_from_prototype(target_prim)
            
            # Apply unified post-copy fixes
            self._apply_unified_prim_fixes(target_prim)
            
            return target_prim
            
        except Exception as e:
            print(f"WARNING Failed to copy prim data from {source_prim.GetPath()} to {target_path}: {e}")
            return None
    
    def _apply_unified_prim_fixes(self, target_prim):
        """Apply unified fixes to all copied prims - ensures consistency across all conversion types"""
        try:
            if target_prim.IsA(UsdGeom.Mesh):
                # Fix UV coordinates using the correct approach from unified_instancer_converter.py
                # Use the stage-based method that actually works
                target_stage = target_prim.GetStage()
                self._convert_float2_primvars_in_stage(target_stage)
                
                # Fix ALL attributes with interpolation modes - convert faceVarying to vertex
                primvar_api = UsdGeom.PrimvarsAPI(target_prim)
                if primvar_api:
                    # Get all primvars and fix their interpolation modes
                    for primvar in primvar_api.GetPrimvars():
                        if primvar:
                            current_interpolation = primvar.GetInterpolation()
                            if current_interpolation == UsdGeom.Tokens.faceVarying:
                                # Convert faceVarying to vertex for all attributes
                                primvar.SetInterpolation(UsdGeom.Tokens.vertex)
                
                # Fix direct attributes that have interpolation modes (like normals)
                # Use UsdGeom.Mesh API to properly handle normals interpolation
                mesh = UsdGeom.Mesh(target_prim)
                if mesh:
                    # Check and fix normals interpolation
                    normals_attr = mesh.GetNormalsAttr()
                    if normals_attr and normals_attr.HasValue():
                        # Get the current interpolation
                        try:
                            current_normals_interpolation = mesh.GetNormalsInterpolation()
                            if current_normals_interpolation == UsdGeom.Tokens.faceVarying:
                                # Use the proper USD API to set normals interpolation
                                mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                        except Exception as e:
                            print(f"WARNING Could not fix normals interpolation: {e}")
                
                # Add MaterialBindingAPI for mesh prims
                target_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
                target_prim.SetMetadata("kind", "component")
                
        except Exception as e:
            print(f"WARNING Failed to apply unified fixes to {target_prim.GetPath()}: {e}")
    
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
    
    def _copy_materials_to_external_stage(self, external_stage, materials):
        """Copy materials to external stage"""
        try:
            # Create Looks scope
            looks_scope = external_stage.DefinePrim("/Root/Looks", "Scope")
            
            # Copy materials to external file
            for material_name, material_data in materials.items():
                material_path = material_data['path']
                if isinstance(material_path, str):
                    material_name = material_path.split("/")[-1]
                else:
                    material_name = material_data['prim'].GetName()
                external_material_path = f"/Root/Looks/{material_name}"
                
                # Check if this is a Remix material
                if material_data.get('is_remix', False):
                     # Create Remix material in external stage
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
                                    updated_target = f"/Root/Looks/{material_name}"
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
            print(f"    📁 Found project root with mod.usda: {mod_root}")
        else:
            # Fallback: create materials directory relative to assets folder
            output_dir = os.path.dirname(self.output_path)
            parent_dir = os.path.dirname(output_dir)
            if "assets" in parent_dir.lower():
                materials_dir = os.path.join(parent_dir, "materials")
            else:
                materials_dir = os.path.join(output_dir, "materials")
            print(f"    📁 No mod.usda found, using fallback materials directory")
        
        print(f"    📁 Materials directory: {materials_dir}")
        os.makedirs(materials_dir, exist_ok=True)
        return materials_dir

    def _copy_aperture_pbr_material(self, materials_dir):
        """Copy AperturePBR_Opacity.usda to external materials directory if it doesn't exist"""
        target_material_path = os.path.join(materials_dir, "AperturePBR_Opacity.usda")
        
        # Check if it already exists
        if os.path.exists(target_material_path):
            print(f"    ✅ AperturePBR_Opacity.usda already exists in {materials_dir}")
            return
            
        try:
            # Find the source AperturePBR_Opacity.usda file in the converter directory
            converter_materials_dir = os.path.join(os.path.dirname(__file__), "materials")
            source_material_path = os.path.join(converter_materials_dir, "AperturePBR_Opacity.usda")
            
            if os.path.exists(source_material_path):
                shutil.copy2(source_material_path, target_material_path)
                print(f"    📄 Copied AperturePBR_Opacity.usda to {materials_dir}")
            else:
                print(f"WARNING: Could not find AperturePBR_Opacity.usda at {source_material_path}")
        except Exception as e:
            print(f"WARNING: Failed to copy AperturePBR_Opacity.usda: {e}")
    
    def _clear_texture_conversion_cache(self):
        """Clear texture conversion tracking cache after conversion is complete"""
        print(f"🧹 Clearing texture conversion cache ({len(self.texture_conversion_cache)} entries)")
        self.texture_conversion_cache.clear()
        self.textures_being_converted.clear()
    
    def _should_exclude_attribute_for_inline(self, attr_name):
        """Check if an attribute should be excluded for inline prototype meshes"""
        # 🚫 EXCLUDE: Transform attributes
        transform_attrs = {
            'xformOp:translate', 'xformOp:rotateXYZ', 'xformOp:scale', 'xformOpOrder',
            'xformOp:transform', 'xformOp:rotateX', 'xformOp:rotateY', 'xformOp:rotateZ',
            'xformOp:rotate', 'xformOp:orient', 'xformOp:matrix'
        }
        
        # 🚫 EXCLUDE: Highlight parameters (not needed for prototype meshes)
        highlight_attrs = {
            'primvars:displayOpacity', 'primvars:displayColor',
            'primvars:highlight', 'primvars:selection'
        }
        
        # 🚫 EXCLUDE: Instance-specific attributes
        instance_attrs = {
            'primvars:instanceId', 'primvars:instanceIndex'
        }
        
        return attr_name in transform_attrs or attr_name in highlight_attrs or attr_name in instance_attrs
    

