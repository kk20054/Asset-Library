# Meadow conversion tools

Exact conversion scripts used for this collection. Original Unity assets are not bundled.
Install Python dependencies: python -m pip install PyYAML Pillow numpy. Install gltf-validator with npm for official validation. Set MEADOW_WORK to your work folder when running the copied validator. Blender supplies bpy/mathutils.
Use a separate work folder with tools/, audit/, cache/. Source indexing streams the original gzip+tar package and records GUID/asset/pathname entries; pathname uses its first text line. Restore the included source_index.json to audit/source_index.json before extraction.
Commands: extract_sources.py <work> <original-package>; prepare_meadow_mapping.py --work <work>; prepare_textures.py <work>; prepare_pbr_specs.py <work>; Blender --background --python convert_meadow.py -- <work> <repository>.
Run build_library.py --work <work> --repo <repository> only after complete conversion with 144 exported sources and seven excluded sources. No runtime caches or installed dependencies are copied here.
Keep shared images/BIN paths together with Meadow glTF. Unity wind, particles, terrain shape/splat maps and procedural shaders are not reproduced.
