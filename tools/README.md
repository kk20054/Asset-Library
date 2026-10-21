# Local conversion tools

These scripts document the conversion pipeline. They require the separately owned Unity source packages and an isolated working directory; they do not download or license the source assets. Keep original packages read-only. Source GUID indexes, extracted-source hashes, and conversion receipts are traceability inputs, not replacement source archives.

## Runtimes and Python dependencies

The FBX/glTF stages run inside **Blender 5.2.2**. The helper environment uses:

- **numpy** for pixel/channel calculations.
- **Pillow** for image conversion and portable PNG/JPEG output.
- **PyYAML 6.0.2** for Unity YAML/metadata parsing.
- **tifffile 2026.10.15** for reading the actual stored TIFF samples, including meaningful cutout alpha in inspected albedo files without a recognized ExtraSamples alpha declaration.

Do not treat Pillow's opaque fallback as evidence that a source grass/foliage image has no alpha. For the inspected source albedo inputs, tifffile preserves the stored cutout channel before color baking and alpha-cutoff export. This is not a general instruction to treat every fourth TIFF channel as alpha, nor to guess terrain-mask ORM packing. Preserve source role, channel, and importer evidence.

The browser deliverables do not require these Python dependencies or a Unity installation. They use Three.js GLTFLoader and the exported model/texture resources.

## Pipeline boundaries

The Temple scripts are in this directory. Their sequence is extract_sources.py → prepare_unity_mapping.py → prepare_textures.py → prepare_pbr_specs.py → convert_models.py. The [Meadow scripts](meadow/) have their own extraction/mapping steps, texture/PBR preparation, shared-resource glTF conversion, terrain-texture metadata export, and library assembly. Consult each script's current arguments rather than assuming the Temple and Meadow source packages have the same layout.

The Meadow static color bake follows inspected source shader/material controls: desaturation, brightness, the material-color-controlled overlay branch, and color/texture lerp. Dynamic wind/noise, vertex-AO/vertex masks, seasonal blending, SSS, particles, collisions, ASP settings, and Unity post-processing are not restored by that bake.

## Authored scenes and audits

The published [scene index](../scenes/index.json), [scene documentation](../scenes/README.md), and [Claude scene guide](../CLAUDE_AUTHORED_SCENES.md) cover complete static author arrangements: Overview has 369 objects (361 models + eight visible Cubes), and DioramaExample has 609. Thirty-five FX anchors remain metadata, not particle animation.

Authored-scene parsing and assembly preserve local parent hierarchies, native mesh-unit/pivot transforms, and source IDs as strings. Do not flatten world matrices through TRS decomposition: parent nonuniform scale and child rotation can produce real shear. Independent source-landmark checks operate on source group roots before native FBX geometry-unit adapters. The source-camera and additional inspection cameras have distinct provenance.

Preview PNGs are Blender renders of the converted layouts rather than original Unity screenshots. Their actual paths, view IDs, dimensions, and renderer provenance belong to the scene index and preview receipts. Do not assume a final image set or final remote QA is complete from the presence of conversion scripts or documentation.

Generated models, authored scenes, and public JSON are usable without rerunning the conversion tools. Retain scene.gltf and all external buffer/texture dependencies with their relative paths when copying a scene.
