# SoStylized portable asset collection

Portable SoStylized assets for **Godot and Blender**, with glTF 2.0 GLBs as the interchange format. Three.js can also load compatible assets, but it is not required. For step-by-step import instructions, read [GODOT_BLENDER_USAGE.md](../../GODOT_BLENDER_USAGE.md).

## Delivered files

**1,090 portable files:** 787 self-contained native LOD0 GLBs (including collision/utility meshes), 285 PNG textures, one EXR texture, and 17 WAV audio files. Seven category ZIPs total 2,781,517,098 bytes. The GLBs retain embedded texture duplication for independent import; select only the assets needed by your project.

| Category | Files | ZIP size |
| --- | ---: | ---: |
| [Trees](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Trees_part01.zip) | 161 | 413.6 MiB |
| [Rocks](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Rocks_part01.zip) | 324 | 972.0 MiB |
| [Foliage](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Foliage_part01.zip) | 109 | 153.1 MiB |
| [WaterSky](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_WaterSky_part01.zip) | 45 | 16.2 MiB |
| [Other](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Other_part01.zip) | 148 | 71.4 MiB |
| [Textures](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Textures_part01.zip) | 286 | 995.5 MiB |
| [Audio](https://github.com/kk20054/Asset-Library/releases/download/sostylized-godot-blender-2026-10-25/SoStylized_Godot_Blender_Audio_part01.zip) | 17 | 30.8 MiB |

The Other category separates collision, helper, demo and effect geometry from ordinary visible props. See [format and bounded Godot import evidence](validation/index.json); geometry/specification validity is separate from material readiness.

## Collection contents and selection

The [collection catalog](catalog.json) is the authority for published asset paths, source identity, export scope, and each item's exported_lods field. Read the actual entry before downloading or loading a model. A native Unreal source object listed during inventory is not automatically a completed portable asset.

The repository provides English text catalogs, indexes, documented previews, and a small set of direct examples. The complete portable asset payload is intended for category ZIP packages on [GitHub Releases](https://github.com/kk20054/Asset-Library/releases). Consult the release notes for the packages actually available and their contents; no model total, release tag, or package filename is implied by this guide.

After extracting a category package, import its GLBs directly into Godot or Blender. Self-contained GLBs embed the mesh data and portable material textures. Preserve companion catalog and provenance files when copying a subset. Do not upload only a catalog and expect an application to have the binary models.

## Source identity

The source is one user-supplied **SoStylized.rar** archive, locally described by the combined labels **Stylized Mega Bundle / Stylized Nature**. These labels refer to the same physical archive, not two independently verified packages. The source uses Unreal assets under /Game/SoStylized; it is not a Unity package or a native Blender library.

Source archive SHA256:

~~~text
59425c4db32a6f4c164829cb5c6cbe7e8e2714eb6da517eb52f4bdfa9ba32333
~~~

The source archive includes 42 Unreal map files. These maps are source data, not proof of a converted layout. This asset collection must not be described as a complete recreation of those maps unless a separate authored-scene export is explicitly identified and validated.

## Portable geometry and material contract

- **Units and axes:** the GLB conversion already handles Unreal centimetres to metres and glTF +Y up, right-handed coordinates. Do not apply another 0.01 scale or axis correction. Retain the imported hierarchy, pivots, and local transforms.
- **LOD:** native LOD0 only, recorded in each entry as exported_lods=[0]. Source lower LODs are not included; target-engine generated LODs are separate derivatives.
- **Materials:** the portable appearance uses native static material baking where supported, with embedded texture data and documented fallbacks. A baked glTF material does not reproduce the complete original Unreal material graph.
- **Foliage:** preserve source-derived opacity masks, alpha cutoffs, and double-sided settings. Source texture alpha alone may not encode the material silhouette.
- **Dependencies:** self-contained GLBs can be imported without Unreal or the original archive. Retain any additional dependency explicitly declared by an individual catalog entry.
- **Edits:** place application-specific scale, position, and rotation on an outer parent. Preserve an unchanged source copy when preparing derivative materials or geometry.

Previews illustrate the export and must be read with their provenance and capture notes. A converted-asset render must not be labeled as an original Unreal screenshot or proof of full runtime parity.

The portable payload covers static meshes, Texture2D images and SoundWave audio. Other native classes remain source-inventory metadata, including two TextureCube objects, one VolumeTexture, material graphs, foliage rules and runtime components. Their listing is not a portable export.

## Boundaries

Wind, weather, foliage interaction, dynamic seasonal/global material changes, source subsurface shading, water shaders, animated water texture playback, Blueprints, Niagara, particles, Landscape, collision behavior, and world simulation are not automatically transferred by a static GLB conversion. Lighting and post-processing also belong to the receiving scene. Read per-asset notes for any narrower supported behavior.

This delivery organizes reusable assets. It does not modify the existing game's code, world state, saves, combat, or simulation, and it does not claim a complete game or a converted Unreal project.

## Ownership and license

Original asset ownership and source license terms remain in force. Conversion, ZIP packaging, and publication do not create a new permissive license or change third-party asset rights. Use these assets under the rights associated with the original source packages. The licenses for Unreal, Blender, Godot, Three.js, and conversion or validation tools are separate from model and texture rights.
