#!/usr/bin/env python3
"""
Texture Alpha Combiner for RTX Remix
Combines separate opacity textures into diffuse texture alpha channels
"""

import os
import tempfile
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("  PIL/Pillow not available - texture alpha combining disabled")


class TextureAlphaCombiner:
    """Combines opacity textures with diffuse textures for RTX Remix compatibility"""
    
    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow is required for texture alpha combining")
    
    def create_temp_combined_texture(self, diffuse_path, opacity_path):
        """
        Combine diffuse RGB with opacity as alpha channel.
        
        Args:
            diffuse_path: Path to diffuse/color texture
            opacity_path: Path to opacity/alpha texture
            
        Returns:
            str: Path to temporary combined texture, or None if failed
        """
        try:
            # Load textures
            diffuse = Image.open(diffuse_path).convert('RGB')
            opacity = Image.open(opacity_path).convert('L')  # Grayscale
            
            # Resize opacity to match diffuse if needed
            if diffuse.size != opacity.size:
                opacity = opacity.resize(diffuse.size, Image.LANCZOS)
            
            # Create RGBA image
            rgba = Image.new('RGBA', diffuse.size)
            rgba.paste(diffuse, (0, 0))
            rgba.putalpha(opacity)
            
            # Save to temp file
            temp_dir = tempfile.gettempdir()
            base_name = Path(diffuse_path).stem
            temp_path = os.path.join(temp_dir, f"{base_name}_combined.png")
            rgba.save(temp_path)
            
            return temp_path
            
        except Exception as e:
            print(f"  Failed to combine textures: {e}")
            return None
