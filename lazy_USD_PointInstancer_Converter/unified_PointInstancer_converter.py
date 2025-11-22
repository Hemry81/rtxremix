#!/usr/bin/env python3
"""
Clean Unified USD PointInstancer Converter
Uses separate classes for data collection and output generation
"""

import os
import sys
import contextlib
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

@contextlib.contextmanager
def suppress_usd_warnings(quiet_mode=False):
    """Suppress USD warnings and optionally reduce verbose output"""
    import io
    from contextlib import redirect_stderr
    
    # Capture stderr to filter specific warnings
    captured = io.StringIO()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    
    class FilteredStderr:
        def __init__(self, quiet=False):
            self.current_line = ''
            self.skip_next_blank = False
            self.quiet = quiet
        
        def write(self, text):
            # Accumulate text until we have a complete line
            self.current_line += text
            
            # Check if we have complete lines
            while '\n' in self.current_line:
                line, self.current_line = self.current_line.split('\n', 1)
                line += '\n'
                
                # Skip blank lines after AperturePBR_Opacity warnings
                if self.skip_next_blank and line.strip() == '':
                    self.skip_next_blank = False
                    continue
                
                # Filter out AperturePBR_Opacity warnings and related USD errors
                skip_line = (
                    'AperturePBR_Opacity.usda' in line or
                    'Could not open asset' in line or
                    'Could not open layer' in line or
                    '_ReportErrors' in line or
                    'recomposing stage' in line or
                    'for reference introduced by' in line or
                    '@C:/Users/materials/' in line or
                    'Failed to open' in line or
                    'Warning: in _ResolveAsset' in line or
                    'Coding Error' in line or
                    'TfDiagnosticMgr' in line or
                    'Failed to resolve' in line or
                    'Cannot find' in line or
                    'No such file' in line or
                    'does not exist' in line or
                    'Tf.Warn' in line
                )
                
                # In quiet mode, also filter verbose debug output
                if self.quiet and not skip_line:
                    skip_line = (
                        line.strip().startswith('ANALYZE') or
                        line.strip().startswith('TARGET') or
                        line.strip().startswith('COUNT') or
                        line.strip().startswith('EXAMPLE') or
                        line.strip().startswith('DEBUG') or
                        line.strip().startswith('OK')
                    )
                
                if not skip_line:
                    old_stderr.write(line)
                else:
                    self.skip_next_blank = True
        
        def flush(self):
            # Write any remaining buffered content that's not filtered
            if self.current_line:
                skip_line = (
                    'AperturePBR_Opacity.usda' in self.current_line or
                    'Could not open asset' in self.current_line or
                    'Could not open layer' in self.current_line or
                    '_ReportErrors' in self.current_line or
                    'recomposing stage' in self.current_line or
                    'for reference introduced by' in self.current_line or
                    '@C:/Users/materials/' in self.current_line or
                    'Failed to open' in self.current_line or
                    'Warning: in _ResolveAsset' in self.current_line or
                    'Coding Error' in self.current_line or
                    'TfDiagnosticMgr' in self.current_line or
                    'Failed to resolve' in self.current_line or
                    'Cannot find' in self.current_line or
                    'No such file' in self.current_line or
                    'does not exist' in self.current_line or
                    'Tf.Warn' in self.current_line
                )
                
                # In quiet mode, also filter verbose debug output
                if self.quiet and not skip_line:
                    skip_line = (
                        self.current_line.strip().startswith('ANALYZE') or
                        self.current_line.strip().startswith('TARGET') or
                        self.current_line.strip().startswith('COUNT') or
                        self.current_line.strip().startswith('EXAMPLE') or
                        self.current_line.strip().startswith('DEBUG') or
                        self.current_line.strip().startswith('OK')
                    )
                
                if not skip_line and self.current_line.strip():
                    old_stderr.write(self.current_line)
                self.current_line = ''
            self.skip_next_blank = False
            old_stderr.flush()
    
    sys.stderr = FilteredStderr(quiet=quiet_mode)
    try:
        yield
    finally:
        # Ensure any remaining content is flushed before restoring stderr
        sys.stderr.flush()
        sys.stderr = old_stderr
        sys.stdout = old_stdout
from unified_data_collector import UnifiedDataCollector
from unified_data_converter import UnifiedDataConverter
from unified_output_generator import FinalOutputGenerator

class CleanUnifiedConverter:
    """Clean unified converter using separate data collection and output generation"""
    
    def __init__(self, input_path, export_binary=False):
        self.input_path = input_path
        self.export_binary = export_binary
        self.stage = None
        self.input_type = None
        
    def convert(self, output_path, use_external_references=False, export_binary=None, convert_textures=False, normal_map_format="Auto-Detect", interpolation_mode="faceVarying", auto_blend_alpha=True, remove_geomsubset_familyname=True, generate_missing_uvs=False, report_path=None, quiet_mode=False):
        """Main conversion method"""
        if not quiet_mode:
            print(f"CONVERT Starting conversion: {self.input_path} → {output_path}")
        
        # Use provided export_binary or default from constructor
        if export_binary is None:
            export_binary = self.export_binary
        
        # Suppress USD warnings for the entire conversion process
        with suppress_usd_warnings(quiet_mode=quiet_mode):
            # Load stage
            if not self._load_stage():
                return None
            
            # Detect input type only if not already set
            if not self.input_type:
                if not self.detect_input_type():
                    return None
            else:
                print(f"ANALYZE Using manually set input type: {self.input_type}")
            
            # Collect data
            collector = UnifiedDataCollector(self.stage, self.input_type, auto_blend_alpha=auto_blend_alpha)
            if not collector.collect_data():
                return None
            
            # Check for failed prototypes (particle system without point cloud export)
            if collector.failed_prototypes:
                self._show_particle_export_error(collector.failed_prototypes)
                return None
            
            # Convert data for output
            converter = UnifiedDataConverter(collector.unified_data, use_external_references)
            output_data = converter.convert_data()
            converter.prepare_external_prototypes(use_external_references)
            
            # Generate output
            generator = FinalOutputGenerator(output_data, output_path, use_external_references, export_binary, self.stage, convert_textures, normal_map_format, interpolation_mode, remove_geomsubset_familyname, generate_missing_uvs)
            result = generator.generate_output()
        
        if result:
            # Generate report if requested
            if report_path:
                self._generate_report(report_path, output_data, result)
            
            # Calculate total faces from prototype details
            total_faces = 0
            if result.get('prototype_face_counts'):
                for proto_name, face_count in result['prototype_face_counts'].items():
                    inst_count = result.get('instance_counts', {}).get(proto_name, 0)
                    total_faces += face_count * inst_count
            
            # Format large numbers
            def format_large_number(num):
                if num >= 1_000_000_000_000:
                    return f"{num / 1_000_000_000_000:.2f} Trillion"
                elif num >= 1_000_000_000:
                    return f"{num / 1_000_000_000:.2f} Billion"
                elif num >= 1_000_000:
                    return f"{num / 1_000_000:.2f} Million"
                else:
                    return f"{num:,}"
            
            # Print final summary
            print("\n" + "="*80)
            print("SUCCESS Conversion completed!")
            print("="*80)
            print(f"PointInstancers processed: {result['pointinstancers_processed']}")
            print(f"External files created: {result['external_files_created']}")
            print(f"Materials converted: {result['materials_converted']}")
            print(f"Textures converted: {result.get('textures_converted', 0)}")
            total_instances = sum(result.get('instance_counts', {}).values())
            print(f"Total Instances: {total_instances:,}")
            print(f"Total faces generated: {format_large_number(total_faces)}")
            if result.get('prototype_face_counts'):
                print(f"\nPrototype details:")
                for proto_name, face_count in result['prototype_face_counts'].items():
                    inst_count = result.get('instance_counts', {}).get(proto_name, 0)
                    total = face_count * inst_count
                    print(f"  {proto_name}: {face_count:,} faces × {inst_count} instances = {total:,} faces")
            print(f"\nOperation: {result['operation']}")
            print("="*80)
            
            # Display failed texture conversions if any
            if result.get('failed_texture_conversions'):
                for fail_info in result['failed_texture_conversions']:
                    print(f"DEBUG Texture convert failed: Source: {fail_info['source']}, material type: {fail_info['slot_type']}, {fail_info['reason']}")
            
            # Refresh mod.usda to trigger RTX Remix auto-refresh
            mod_refreshed = self._refresh_mod_file(generator)
            result['mod_refreshed'] = mod_refreshed
            result['mod_file'] = generator.mod_file if generator.mod_file else None
        
        return result
    
    def _load_stage(self):
        """Load USD stage from input file"""
        try:
            self.stage = Usd.Stage.Open(self.input_path)
            if not self.stage:
                print(f"ERROR Failed to load stage: {self.input_path}")
                return False
            
            print(f"OK Stage loaded successfully")
            return True
            
        except Exception as e:
            print(f"ERROR Failed to load stage: {e}")
            return False
    
    def detect_input_type(self):
        """Automatically detect input type using the working approach from unified_instancer_converter.py"""
        print("ANALYZE Analyzing input format...")
        
        # Check for existing PointInstancers
        existing_pointinstancers = []
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.PointInstancer):
                existing_pointinstancers.append(prim)
        
        # Check for instanceable references (FORWARD conversion)
        instanceable_refs = 0
        instanceable_xforms = []
        
        # Check for Blender 3.6+ style: Meshes with prepend references
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.Mesh):
                # Check if this Mesh has references (Blender 3.6 style)
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
                            instanceable_refs += 1
                            instanceable_xforms.append(prim.GetParent())
                            break
            elif prim.IsA(UsdGeom.Xform):
                # Check if this Xform is instanceable using multiple methods
                if self._is_instanceable(prim):
                    # Check if this Xform has references
                    if prim.GetReferences():
                        instanceable_refs += 1
                        instanceable_xforms.append(prim)
        
        # Check for Blender 4.5 specific attributes (REVERSE conversion)
        # Use proper duplicate detection logic from unified_instancer_converter.py
        from collections import defaultdict
        import re
        data_name_counts = defaultdict(int)
        blender45_indicators = 0
        
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.Mesh):
                data_name_attr = prim.GetAttribute("userProperties:blender:data_name")
                if data_name_attr and data_name_attr.Get():
                    blender45_indicators += 1
                    data_name_counts[data_name_attr.Get()] += 1
        
        # Count duplicate blender:data_names
        duplicate_datanames = sum(1 for count in data_name_counts.values() if count > 1)
        
        # Check for Blender 3.6 non-instancing: Xforms with pattern like "Cone__1083652720"
        xform_base_names = defaultdict(int)
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.Xform) and prim.GetName() not in ['root', 'Root']:
                # Extract base name before underscore/hash (e.g., "Cone__123" -> "Cone")
                name = prim.GetName()
                # Match patterns like "Name__hash" or "Name_hash"
                match = re.match(r'^([A-Za-z0-9_]+?)(?:__|_)\d+', name)
                if match:
                    base_name = match.group(1)
                    xform_base_names[base_name] += 1
        
        duplicate_xform_names = sum(1 for count in xform_base_names.values() if count > 1)
        
        # Determine input type (prioritize instanceable references for forward conversion)
        if existing_pointinstancers:
            if blender45_indicators > 0:
                self.input_type = 'blender45_pointinstancer'
                print(f" Detected input type: BLENDER 4.5 POINTINSTANCER")
                print(f"  TARGET Found {len(existing_pointinstancers)} existing PointInstancers")
                print(f"  COUNT Total objects with blender:data_name: {blender45_indicators}")
            else:
                self.input_type = 'existing_pointinstancer'
                print(f" Detected input type: EXISTING POINTINSTANCER")
                print(f"  TARGET Found {len(existing_pointinstancers)} existing PointInstancers")
        elif instanceable_refs > 0:
            # Prioritize forward conversion when instanceable references are found
            self.input_type = 'forward_instanceable'
            print(f" Detected input type: FORWARD (Instanceable References → PointInstancer)")
            print(f"  TARGET Found {instanceable_refs} instanceable Xforms with references")
            if instanceable_xforms:
                print(f"  EXAMPLE: {instanceable_xforms[0].GetPath()}")
        elif duplicate_datanames > 0:
            # Use proper reverse conversion detection
            self.input_type = 'reverse'
            print(f" Detected input type: REVERSE (Individual Objects → PointInstancer)")
            print(f"  TARGET Found {duplicate_datanames} groups with duplicate blender:data_name")
            print(f"  COUNT Total objects with blender:data_name: {blender45_indicators}")
        elif duplicate_xform_names > 0:
            # Blender 3.6 non-instancing: duplicate Xform names
            self.input_type = 'reverse'
            print(f" Detected input type: REVERSE (Blender 3.6 Non-Instancing → PointInstancer)")
            print(f"  TARGET Found {duplicate_xform_names} groups with duplicate Xform base names")
        else:
            print(f" ERROR Could not determine input type")
            print(f"   Existing PointInstancers: {len(existing_pointinstancers)}")
            print(f"   Instanceable references: {instanceable_refs}")
            print(f"   Blender 4.5 indicators: {blender45_indicators}")
            print(f"   Duplicate blender:data_name groups: {duplicate_datanames}")
            return False
        
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
    
    def _refresh_mod_file(self, generator):
        """Open and save mod.usda as text to trigger RTX Remix auto-refresh"""
        try:
            if generator.mod_file:
                print(f"DEBUG mod.usda found: {generator.mod_file}")
                # Read file as text
                with open(generator.mod_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Write back unchanged to update modification time
                with open(generator.mod_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"REFRESH mod.usda refreshed successfully: {generator.mod_file}")
                return True
            else:
                print("DEBUG mod.usda not found - skipping refresh")
                return False
        except Exception as e:
            print(f"WARNING Failed to refresh mod.usda: {e}")
            return False
    
    def _show_particle_export_error(self, failed_objects):
        """Show error popup for particle system export issues"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Create hidden root window
            root = tk.Tk()
            root.withdraw()
            
            # Get unique object names
            unique_objects = sorted(set(failed_objects))
            objects_list = "\n  • " + "\n  • ".join(unique_objects)
            
            error_message = (
                "❌ Particle System Export Error\n\n"
                "This USD file was likely exported from a Blender particle system "
                "without enabling 'Point Cloud' export.\n\n"
                "Failed to collect mesh data for the following objects:"
                f"{objects_list}\n\n"
                "Solution:\n"
                "1. In Blender, ensure the particle mesh is a SINGLE mesh object\n"
                "   (not parented to Xform/Empty, no nested hierarchy)\n"
                "2. Select the particle system\n"
                "3. Enable 'Point Cloud' in the USD export settings\n"
                "4. Re-export the USD file\n\n"
                "Important: Each particle mesh should be a single mesh object only.\n"
                "Meshes with parent Xforms or nested hierarchies will create blank geometry."
            )
            
            messagebox.showerror("Particle System Export Error", error_message)
            root.destroy()
            
        except Exception as e:
            # Fallback to console output if GUI not available
            print(f"\n{'='*60}")
            print("ERROR: Particle System Export Issue")
            print(f"{'='*60}")
            print("This USD file was likely exported from a Blender particle system")
            print("without enabling 'Point Cloud' export.\n")
            print("Failed to collect mesh data for the following objects:")
            for obj in sorted(set(failed_objects)):
                print(f"  • {obj}")
            print("\nSolution:")
            print("1. In Blender, ensure the particle mesh is a SINGLE mesh object")
            print("   (not parented to Xform/Empty, no nested hierarchy)")
            print("2. Select the particle system")
            print("3. Enable 'Point Cloud' in the USD export settings")
            print("4. Re-export the USD file")
            print("\nImportant: Each particle mesh should be a single mesh object only.")
            print("Meshes with parent Xforms or nested hierarchies will create blank geometry.")
            print(f"{'='*60}\n")
    
    def _generate_report(self, report_path, output_data, result):
        """Generate detailed JSON conversion report"""
        import json
        from datetime import datetime
        
        try:
            report = {
                "conversion_summary": {
                    "input_file": self.input_path,
                    "output_file": result.get('output_file', ''),
                    "conversion_type": output_data.get('input_type', 'unknown'),
                    "total_materials": len(output_data.get('materials', {})),
                    "converted_materials": [],
                    "pointinstancers_processed": result.get('pointinstancers_processed', 0),
                    "external_files_created": result.get('external_files_created', 0),
                    "textures_converted": result.get('textures_converted', 0),
                    "timestamp": datetime.now().isoformat()
                },
                "materials": {}
            }
            
            # Add material details
            for material_name, material_info in output_data.get('materials', {}).items():
                report['conversion_summary']['converted_materials'].append(material_name)
                
                material_report = {
                    "conversion_type": material_info.get('conversion_type', 'none'),
                    "is_remix": material_info.get('is_remix', False)
                }
                
                # Add remix parameters if available
                if 'remix_params' in material_info:
                    remix_params = material_info['remix_params'].copy()
                    # Convert non-serializable types
                    for key, value in remix_params.items():
                        if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict)):
                            remix_params[key] = str(value)
                    material_report['remix_parameters'] = remix_params
                
                report['materials'][material_name] = material_report
            
            # Write report
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"REPORT Generated conversion report: {report_path}")
            
        except Exception as e:
            print(f"WARNING Failed to generate report: {e}")

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert USD files with PointInstancer optimization')
    parser.add_argument('input', help='Input USD file path')
    parser.add_argument('output', help='Output USD file path')
    parser.add_argument('--external-refs', action='store_true', 
                       help='Use external references for prototypes')
    parser.add_argument('--binary', action='store_true', 
                       help='Export as binary USD format')
    parser.add_argument('--convert-textures', action='store_true',
                       help='Enable texture conversion to DDS (enabled by default, kept for compatibility)')
    parser.add_argument('--no-texture-conversion', action='store_true',
                       help='Disable texture conversion (textures are converted by default)')
    parser.add_argument('--interpolation', choices=['faceVarying', 'vertex', 'none'], 
                       default='faceVarying',
                       help='Interpolation conversion mode for normals and texCoords (default: faceVarying)')
    parser.add_argument('--disable-auto-blend', action='store_true',
                       help='Disable automatic blend mode for alpha textures (enabled by default)')
    parser.add_argument('--keep-geomsubset-familyname', action='store_true',
                       help='Keep GeomSubset familyName attribute (removed by default to fix cyan meshes)')
    parser.add_argument('--generate-missing-uvs', action='store_true',
                       help='Generate placeholder UVs for meshes without UVs (simple box projection)')
    parser.add_argument('--report', type=str, metavar='FILE',
                       help='Generate detailed JSON conversion report (e.g., conversion_report.json)')
    
    args = parser.parse_args()
    
    # Determine export format
    if args.output.endswith('.usdc'):
        export_binary = True
        print("Using binary format (.usdc)")
    elif args.output.endswith('.usda'):
        export_binary = False
        print("Using ASCII format (.usda)")
    else:
        export_binary = args.binary
        print(f"Using {'binary' if export_binary else 'ASCII'} format")
    
    # Create converter and run (texture conversion enabled by default)
    converter = CleanUnifiedConverter(args.input, export_binary)
    convert_textures = not args.no_texture_conversion
    auto_blend_alpha = not args.disable_auto_blend
    remove_geomsubset_familyname = not args.keep_geomsubset_familyname
    generate_missing_uvs = args.generate_missing_uvs
    result = converter.convert(args.output, args.external_refs, convert_textures=convert_textures, interpolation_mode=args.interpolation, auto_blend_alpha=auto_blend_alpha, remove_geomsubset_familyname=remove_geomsubset_familyname, generate_missing_uvs=generate_missing_uvs, report_path=args.report)
    
    if result:
        print("Conversion successful!")
        if convert_textures and result.get('textures_converted', 0) > 0:
            print(f"   Textures converted: {result['textures_converted']}")
    else:
        print("Conversion failed!")
        exit(1)

if __name__ == "__main__":
    main()
