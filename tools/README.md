# Local conversion tools

These scripts document the original conversion pipeline. They require the separately owned Unity source package and an isolated work directory; they do not download or license the source assets.

Order: extract_sources.py → prepare_unity_mapping.py → prepare_textures.py → prepare_pbr_specs.py → convert_models.py. The FBX/GLB stage runs inside Blender 5.2.2. Python helpers use Pillow and PyYAML 6.0.2. The source GUID index and extracted-source receipts are local inputs, not a replacement source archive.

The generated models and public manifest are ready for Three.js use without running these tools.
