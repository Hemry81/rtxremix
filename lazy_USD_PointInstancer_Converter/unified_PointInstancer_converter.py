#!/usr/bin/env python3
"""
Clean Unified USD PointInstancer Converter
Uses separate classes for data collection and output generation
"""

import os
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
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
        
    def convert(self, output_path, use_external_references=False, export_binary=None, convert_textures=False, normal_map_format="Auto-Detect", interpolation_mode="faceVarying"):
        """Main conversion method"""
        print(f"CONVERT Starting conversion: {self.input_path} → {output_path}")
        
        # Use provided export_binary or default from constructor
        if export_binary is None:
            export_binary = self.export_binary
        
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
        collector = UnifiedDataCollector(self.stage, self.input_type)
        if not collector.collect_data():
            return None
        
        # Convert data for output
        converter = UnifiedDataConverter(collector.unified_data, use_external_references)
        output_data = converter.convert_data()
        converter.prepare_external_prototypes(use_external_references)
        
        # Generate output
        generator = FinalOutputGenerator(output_data, output_path, use_external_references, export_binary, self.stage, convert_textures, normal_map_format, interpolation_mode)
        result = generator.generate_output()
        
        if result:
            print("SUCCESS Conversion completed!")
            print(f"  📊 PointInstancers processed: {result['pointinstancers_processed']}")
            print(f"  📁 External files created: {result['external_files_created']}")
            print(f"  🎨 Materials converted: {result['materials_converted']}")
            print(f"  🔧 Operation: {result['operation']}")
        
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
        
        # Use the working approach from unified_instancer_converter.py
        for prim in self.stage.TraverseAll():
            if prim.IsA(UsdGeom.Xform):
                # Check if this Xform is instanceable using multiple methods
                if self._is_instanceable(prim):
                    # Check if this Xform has references
                    if prim.GetReferences():
                        instanceable_refs += 1
                        instanceable_xforms.append(prim)
        
        # Check for Blender 4.5 specific attributes (REVERSE conversion)
        # Use proper duplicate detection logic from unified_instancer_converter.py
        from collections import defaultdict
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
        
        # Determine input type (prioritize instanceable references for forward conversion)
        if existing_pointinstancers:
            if blender45_indicators > 0:
                self.input_type = 'blender45_pointinstancer'
                print(f"📊 Detected input type: BLENDER 4.5 POINTINSTANCER")
                print(f"  TARGET Found {len(existing_pointinstancers)} existing PointInstancers")
                print(f"  COUNT Total objects with blender:data_name: {blender45_indicators}")
            else:
                self.input_type = 'existing_pointinstancer'
                print(f"📊 Detected input type: EXISTING POINTINSTANCER")
                print(f"  TARGET Found {len(existing_pointinstancers)} existing PointInstancers")
        elif instanceable_refs > 0:
            # Prioritize forward conversion when instanceable references are found
            self.input_type = 'forward_instanceable'
            print(f"📊 Detected input type: FORWARD (Instanceable References → PointInstancer)")
            print(f"  TARGET Found {instanceable_refs} instanceable Xforms with references")
            if instanceable_xforms:
                print(f"  EXAMPLE: {instanceable_xforms[0].GetPath()}")
        elif duplicate_datanames > 0:
            # Use proper reverse conversion detection
            self.input_type = 'reverse'
            print(f"📊 Detected input type: REVERSE (Individual Objects → PointInstancer)")
            print(f"  TARGET Found {duplicate_datanames} groups with duplicate blender:data_name")
            print(f"  COUNT Total objects with blender:data_name: {blender45_indicators}")
        else:
            print(f"❌ ERROR Could not determine input type")
            print(f"  📊 Existing PointInstancers: {len(existing_pointinstancers)}")
            print(f"  📊 Instanceable references: {instanceable_refs}")
            print(f"  📊 Blender 4.5 indicators: {blender45_indicators}")
            print(f"  📊 Duplicate blender:data_name groups: {duplicate_datanames}")
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
                       help='Convert textures using NVIDIA Texture Tools with proper gamma correction')
    parser.add_argument('--interpolation', choices=['faceVarying', 'vertex', 'none'], 
                       default='faceVarying',
                       help='Interpolation conversion mode for normals and texCoords (default: faceVarying)')
    
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
    
    # Create converter and run
    converter = CleanUnifiedConverter(args.input, export_binary)
    result = converter.convert(args.output, args.external_refs, convert_textures=args.convert_textures, interpolation_mode=args.interpolation)
    
    if result:
        print("Conversion successful!")
        if args.convert_textures and result.get('textures_converted', 0) > 0:
            print(f"  🎨 Textures converted: {result['textures_converted']}")
    else:
        print("Conversion failed!")
        exit(1)

if __name__ == "__main__":
    main()
