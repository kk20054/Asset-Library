# Stylized World Assets for Godot, Blender and Three.js

A portable environment library combining **Stylized Chinese Lost Temple**, **Meadow Environment – Stylized Pack 1.6**, and **SoStylized (Stylized Mega Bundle / Stylized Nature)**. Godot and Blender can import the portable assets directly; Three.js is optional. English catalogs help coding assistants select actual files.

## SoStylized: Godot and Blender downloads

The complete SoStylized portable payload contains **787 LOD0 GLBs (including helpers), 286 PNG/EXR textures, and 17 WAV files**. Seven category ZIPs total about **2.78 GB**. All 787 GLBs passed the [format/resource check](collections/sostylized/validation/glb-format.json); six representative GLBs were imported and instantiated in [Godot 4.7.2](collections/sostylized/validation/godot-samples.json). Material limitations remain separate.

Start with the [small collection index](collections/sostylized/index.json), the [English import guide](GODOT_BLENDER_USAGE.md), and [material readiness notes](collections/sostylized/MATERIAL_READINESS.md). Category ZIPs on [GitHub Releases](https://github.com/kk20054/ThreeJS-Stylized-World-Assets/releases/tag/sostylized-godot-blender-2026-10-25) contain self-contained native LOD0 GLBs, original PNG/EXR textures, and WAV audio. The [download index](collections/sostylized/downloads.json) records exact filenames, sizes and SHA256 values. Extract the ZIP before importing.

The new collection is distributed through Releases to keep gigabytes of portable assets out of the existing Git/Pages viewer. Its catalog paths identify files **inside an extracted ZIP**, rather than files under the repository root. Four [small direct GLB examples](collections/sostylized/samples/) and a [converted-asset preview](collections/sostylized/previews/contact_sheet.png) are included for inspection. The 42 source Unreal Worlds are indexed only; their authored layouts are not converted. Cloud, water, wind and landscape-blend materials require target-engine work; consult the per-asset readiness flags.

## Existing direct browser library

- [Compact asset index](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/asset-index.json): select exact asset IDs without downloading the model library.
- [Full manifest](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/manifest.json): paths, collection, category, geometry statistics, sizes, provenance, and limitations.
- [Instructions for Claude: individual assets](CLAUDE_USAGE.md).
- [Original authored scene layouts](scenes/README.md), [compact scene index](scenes/index.json), and [Claude authored-scene guide](CLAUDE_AUTHORED_SCENES.md).
- [Authored scene viewer](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/examples/authored-scenes.html): source camera, complete-layout view, and individual authored groups.
- [Asset viewer](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/).
- [Temple + Meadow comparison](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/examples/world-demo.html): the same seeded placements rendered as shared-resource clones or instanced meshes.
- [Large-world feasibility and measurement notes](FEASIBILITY.md).
- [Loading and disposal helper](examples/load-model.js).

The existing direct browser library contains **516 model assets: 135 Temple GLBs and 381 Meadow glTF variants**, representing **278 independent source models** (134 Temple + 144 Meadow). Source FBX counts, Prefab counts, material combinations, and exported assets are different quantities. Use the manifest for current paths, hashes, dependencies, and payload sizes; do not add per-asset dependency sizes without deduplicating shared files.

## Collections and formats

| Collection | Exported assets | Independent source models | Runtime format |
| --- | ---: | ---: | --- |
| Temple | 135 | 134 | Self-contained GLB; original IDs such as SM_Temple. |
| Meadow | 381 | 144 | glTF JSON with shared external resources; MEADOW_ IDs. |

The existing **135 Temple GLBs, 355,670,520 bytes**, retain their original paths and bytes. The additional Temple output preserves a second source material variant; it is not a new source FBX. Those files represent 134 source FBXs.

The **381 Meadow variants** retain actual Prefab material choices after lower-LOD filtering and deduplication of the 537 source material combinations. They cover 144 static environment FBXs. Six particle/VFX source meshes and one editor helper are excluded. Every Meadow glTF must retain its declared relative dependencies under models/Meadow/_shared/buffers and models/Meadow/_shared/textures.

Both formats load through GLTFLoader. No Unity runtime is required. This export does not require Draco, Meshopt, or KTX2 decoders unless a future manifest explicitly declares a compressed version.

## Load only the assets you need

Use the same pinned Three.js version for the core and addons. The included browser examples use **0.180.0**.

~~~js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const base = 'https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/';
const response = await fetch(new URL('manifest.json', base));
if (!response.ok) throw new Error('Manifest HTTP ' + response.status);
const { assets } = await response.json();
const chosen = [
  assets.find(asset => asset.collection === 'temple' && asset.id === 'SM_Temple'),
  assets.find(asset => asset.collection === 'meadow' && asset.category === 'Trees'),
];
if (chosen.some(asset => !asset)) throw new Error('Required assets are missing from the current manifest.');
const loader = new GLTFLoader();
for (const asset of chosen) {
  const gltf = await loader.loadAsync(new URL(asset.path, base).href);
  scene.add(gltf.scene);
}
~~~

For Meadow, passing the original glTF URL lets GLTFLoader resolve relative buffers and textures correctly. **Downloading or uploading only the .gltf file is incomplete.** If you vendor a subset, copy its transitive dependencies and preserve their relative paths, or deliberately rewrite the URIs. Refer to the glTF JSON rather than guessing shared-resource filenames.

Use raw URLs for JSON/model data, not GitHub blob pages. Serve JavaScript modules from the Pages site or your application host; GitHub raw JavaScript MIME types are not an ES-module hosting guarantee. Pin the base URL to a full commit SHA for reproducible builds. Public access removes the need for a GitHub token; it does not guarantee that a particular chat service or sandbox can reach every host or understand binary geometry.

Models use +Y up, right-handed coordinates, and meters. Preserve source import scale and pivots; check each asset's bounds before combining modules. Temple architecture includes modular building parts, not just complete buildings. Included Temple character and panda objects are static props, not rigged animation assets.

## Original author arrangements

The library also contains two complete **static** Meadow scene arrangements: **Overview has 369 objects (361 environment models + eight visible original Cube display platforms/backdrops)**; **DioramaExample has 609 objects across seven groups**. The 978 placements reuse library assets and are not 978 additional unique models. Start with [scenes/index.json](scenes/index.json), then the selected summary and only the needed groups[].path JSON files. Load the selected scene.gltf with GLTFLoader to resolve its shared dependencies automatically.

The original hierarchy, local transforms, material choices, and string source IDs are preserved. Unity 64-bit file IDs stay JSON strings; do not convert them to JavaScript numbers. Preserve the hierarchy because nonuniform parent scale and child rotation can create world shear. Do not normalize or recenter each model, flatten/decompose world transforms, or apply JSON world matrices again to an already assembled glTF. A clearly identified translation on one outer whole-group wrapper is available for adaptations without changing its internal layout.

The source-camera view retains the original local camera composition. Complete-layout and group views are additional inspection cameras. Reference PNGs are **Blender renders of the converted layout, not original Unity screenshots**; consult the scene index and preview receipts for actual available paths and provenance, without inferring a fixed final image count.

All **35 source FX anchors** remain metadata (21 Overview + 14 Diorama); particles, collisions, ASP global behavior, Unity sky/post-processing, and other dynamic shader effects are not reproduced as a Unity runtime. See [scenes/README.md](scenes/README.md) and [CLAUDE_AUTHORED_SCENES.md](CLAUDE_AUTHORED_SCENES.md) for direct reuse instructions and a copyable prompt.

## Portability boundaries

The portable materials use actual source renderer/material assignments where available. A glTF material is not a copy of a Unity ShaderGraph or custom shader.

- Temple retains portable base color, normal, ORM, and enabled opacity masks. Base colors are capped at 2048 pixels and normal/data maps at 1024; opaque colors use JPEG and alpha/data images use PNG. Existing GLB geometry is not newly decimated.
- Meadow's shared buffers and textures reduce repeated file dependencies between material variants. Inspect per-asset metadata for the actual material mapping and omitted source behavior. Its static color bake follows the source shader's desaturation → brightness → color-controlled overlay → color/texture lerp sequence. The overlay branch is selected by _BaseAlbedoColor, not the sampled texture; this preserves the source material's green overlay on grayscale oak leaf images.
- Procedural wind, noise-driven variation, vertex-AO/vertex-mask shading, subsurface scattering, and runtime seasonal blending are not reproduced by that base-color bake. The exported material remains a static PBR approximation.
- Inspected grass/foliage albedo TIFFs can contain real cutout alpha without a recognized ExtraSamples alpha tag. The conversion uses tifffile to read that stored alpha rather than replacing it with Pillow's opaque fallback. This does not assign new semantics to terrain mask channels; see the [tool dependency notes](tools/README.md).
- Wind, global seasonal/top-layer behavior, particles, water distortion, terrain blending, and baked scene lighting require separate Three.js work. They are not implied by an FBX or material conversion.
- The three binary Unity Terrain assets are not ported as terrain. Distant hill/mountain mesh props do not provide a streamed or traversable terrain system.
- Exported lower-LOD exclusions are explicit. Three.js LOD can switch supplied meshes; it does not generate missing lower-detail geometry.

Original source archives and full-resolution authoring images remain in the source library. Provenance is carried in the manifest and supporting source catalogs. The original Temple [source inventory](source-catalog.json), [Prefab assignments](source-prefabs.json), and [material mapping](source-materials.json) are retained for traceability.

## Ground surface textures

[collections/meadow/terrain-textures.json](collections/meadow/terrain-textures.json) provides **six TerrainLayer definitions and 14 unique texture files: six diffuse, four normal, and four mask images**. It preserves the source layer tiling, offsets, normal scale, remap settings, texture identity, and importer notes. Shared normals/masks account for fewer texture files than layer references.

Masks preserve their original channels. Their channel semantics are unverified, so channel_mapping is null; **do not guess ORM packing**. Source mask importer color-space settings are recorded separately from the portable linear-data role. Normal pixels and importer flipGreenChannel values are recorded without claiming independent orientation validation.

These are surface materials, not Unity Terrain meshes, heightfields, splatmaps, colliders, or a complete terrain scene. The mixed demo tiles the real Grass diffuse and normal on a single plane material; it does not reconstruct Unity terrain blending.

## Validation and local use

For the current authored-scenes/foliage-alpha revision, all 381 Meadow models passed the [current standard check](collections/meadow/validation-current.json). Both combined scene glTF files passed with zero specification/dependency errors; [independent source checks](scenes/validation/authored-transforms.json) confirm 978 static placements, ten landmarks, native pivots and the nonuniform-scale hierarchy. The [18 rendered references](scenes/index.json) retain their original camera or explicitly labeled inspection camera. Anonymous published checks passed [372/372 authored-scene URLs](scenes/validation/public-access.json), including 48 small placement pages and all shared scene resources, and [822/822 library URLs](validation/current-public-access.json), with CORS and length checks. [Current scene checks](scenes/validation/gltf-validation.json) and [alpha recovery checks](scenes/validation/foliage-alpha.json) record their exact scope.

All **381 Meadow glTF variants passed** the [Khronos glTF validation check](validation/meadow-gltf.json) with **zero specification errors and zero dependency errors**. The 276 warnings concern runtime-generated normal-map tangents. The unchanged Temple baseline has its own 135/135 pass record with zero specification/container errors. [Validation files](validation/) identify the files and URLs covered by each receipt. All **516 assets loaded successfully** in the [unified local browser check](validation/unified-browser-load.json). The [anonymous public-access check](validation/unified-public-access.json) passed **822/822 URL checks**, including CORS and available file lengths, with successful hashes for the two model samples and their selected dependencies. The renamed Pages viewer, mixed scene and cross-origin raw loading were also [opened and rendered in a browser](validation/public-browser-preview.json). Individual Claude accounts or sandboxes may still impose their own network restrictions. These receipts apply to their recorded asset-library and mixed-demo snapshot; they do not certify this later authored-scene/alpha-update revision, its final remote delivery, or a completed PNG set.

The mixed-scene example loads five selected source models plus the Grass surface textures. A bounded local far-camera run in Chrome 155 on Windows at 1280 × 720, DPR 1, with shadows off, observed **484 draw calls for clones and 9 for instancing**, with **386,594 submitted triangles in both modes** across 385 model placements. These are observations for that scene, not a general FPS or world-capacity claim. The example does not implement terrain streaming. See the [measured scene receipt](validation/mixed-scene.json) and [FEASIBILITY.md](FEASIBILITY.md) for selected IDs, measurement conditions, and limits.

Serve a local checkout over HTTP, then open /examples/world-demo.html. Do not use a file URL:

~~~sh
python -m http.server 8080
~~~

The demo accepts ?mode=clone or ?mode=instanced and an optional base query parameter pointing to a raw repository root. A cross-origin test must check both the glTF and every external buffer/texture request. Visible loading failures should be investigated rather than replaced with a silent placeholder.

## Source and rights

The source packages are user-supplied Stylized Chinese Lost Temple (Assets/Stylarts namespace), Meadow Environment – Stylized Pack 1.6 (Assets/ANGRY MESH namespace), and one SoStylized.rar archive (Unreal /Game/SoStylized namespace). Conversion and repository publication do not change the original assets' ownership or license terms. This repository does not grant a new permissive license for third-party models or textures; use them under the rights attached to the original source packages. Three.js and validation tooling retain their own licenses.
