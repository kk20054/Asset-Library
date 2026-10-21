# Authored scene conversion tools

These scripts reproduce the published static layouts from the original author package. Original Unity files are not bundled. Python dependencies: numpy, PyYAML, Pillow and tifffile 2026.10.15. Blender 5.2.2 LTS was used for glTF imports and reference rendering. Install the official gltf-validator npm package for standard validation.

Prepare the original Meadow extraction, mapping and portable model library with ../meadow tools first. The work folder must contain audit/extracted_source.json, audit/unity_mapping.json and cache/source. The repository must contain the converted individual Meadow library and manifest.json.

```text
python convert_scene_layouts.py --work <work> --repo <repository>
python assemble_authored_scenes.py --work <work> --repo <repository>
blender -b -t 4 --python-exit-code 1 --python render_authored_previews.py -- <repository> overview all
blender -b -t 4 --python-exit-code 1 --python render_authored_previews.py -- <repository> diorama all
python finalize_authored_previews.py --repo <repository>
python build_claude_pages.py --repo <repository>
python check_authored_scenes.py --repo <repository> --evidence <repository>/scenes/validation/source-landmarks.json --output <work>/audit/independent-check.json
node validate_authored_gltf.mjs --repository <repository>
node ../verify-authored-scenes.mjs --output <work>/audit/public-authored-scenes.json
```

The scene validator uses MEADOW_WORK for its output folder, or defaults to the script directory parent. GLTF_VALIDATOR_MODULE can select an installed validator module. Keep derived logs outside the source package.

The hierarchy uses flip-X coordinate conversion, original local transforms and native mesh-unit nodes. World matrices are evidence, not transforms to apply a second time. Source camera direction/up are adapted from Unity +Z to glTF -Z. Additional bounds-framing cameras are inspection views.

PNG references are Blender Eevee renders of the converted static layouts. They do not reproduce Unity sky, SSS, wind, particles or postprocessing. The Three.js viewer uses source directional parameters with added hemisphere and ambient inspection fill. Neither a PNG nor matrix checks certify visual parity with Unity or a specific Claude account.
