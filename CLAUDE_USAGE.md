# Using the unified library with Claude

## SoStylized in Godot or Blender

Category selection indexes stay below 200 KB; each asset points to a small details page containing its full record. Read the selected details page rather than fetching the entire catalog.

Read [collections/sostylized/index.json](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/collections/sostylized/index.json) first, then only the needed category index. Use the exact Release ZIP URLs in downloads.json. Full collection paths are ZIP members after extraction, not direct repository URLs. Four small examples have explicit direct_sample_url values. The older root asset-index.json still describes the 516 directly hosted Temple/Meadow assets.

> Use the SoStylized collection from https://github.com/kk20054/ThreeJS-Stylized-World-Assets for a Godot or Blender scene. Read the raw collections/sostylized/index.json and selected category index first. Select real IDs and download the matching category ZIPs from downloads.json; do not invent model paths or fetch ZIP-member paths from GitHub raw. Import self-contained GLBs after extraction, retaining metres, source pivots, hierarchy, cutout alpha and double-sided foliage. All supplied static meshes are native LOD0; use an outer parent for scene placement. Check material_readiness and MATERIAL_READINESS.md before using a mesh. Unreal wind, water, cloud fades, Landscape/RVT, Blueprints/Niagara and 42 authored Worlds are not automatically ported. Use PNG/EXR channels only with documented source roles, never guessed ORM packing. Preserve original rights and provenance.

## Temple and Meadow: read text before loading models

Start with these public English text entry points:

1. [asset-index.json](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/asset-index.json) — the compact catalog for selecting exact asset IDs.
2. [manifest.json](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/manifest.json) — collection, category, exact model paths, statistics, provenance, and export limitations.
3. [README.md](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/README.md) — formats, usage, and rights.
4. [FEASIBILITY.md](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/FEASIBILITY.md) — large-scene methods and the limits of current evidence.
5. [terrain-textures.json](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/collections/meadow/terrain-textures.json) — six ground-layer definitions and 14 textures (six diffuse, four normal, four mask).

The repository is [kk20054/ThreeJS-Stylized-World-Assets](https://github.com/kk20054/ThreeJS-Stylized-World-Assets). A public repository makes HTTP retrieval possible without authentication. It does **not** establish that an untested Claude account has retrieved the files, parsed GLB geometry, or executed the viewer. Some chat tools can read the text index but cannot execute WebGL or fetch binary resources. Report that limitation precisely if it occurs.

The direct browser catalog contains **516 model assets: 135 self-contained Temple GLBs and 381 Meadow glTF material variants**, with **144 independent Meadow source models**. The 14 ground texture files are additional surface resources, not 14 extra model assets. Read current payload sizes and hashes from the manifest instead of hard-coding totals.

## Reuse the original author's arrangement

For the author's complete static placements, use [CLAUDE_AUTHORED_SCENES.md](CLAUDE_AUTHORED_SCENES.md), [scenes/README.md](scenes/README.md), and the [scene index](https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/scenes/index.json). Read the chosen summary first, then only relevant small group JSON files. Overview contains 369 static objects (361 models + eight visible Cube platforms/backdrops), and DioramaExample contains 609. Load the index entry's scene.gltf URL with GLTFLoader; retain all shared buffer/texture dependencies.

Keep JSON 64-bit source IDs as strings, preserve every local parent transform and native pivot, and retain shear in the full hierarchy. Do not random-scatter, normalize, recenter, or separately rescale the author's objects. Do not apply JSON world matrices twice. An explicit whole-group outer translation can adapt a group to another scene while preserving its internal arrangement.

Only source-camera is the source author's local camera. Other complete-layout/group cameras are added inspection views. Preview PNGs are Blender renders of the converted layout, not Unity screenshots. Their index and receipts identify what actually exists; this guide does not claim a final PNG set or final remote QA is complete. The 35 FX anchors (21 + 14) preserve source metadata, while particle behavior, collisions, ASP settings, Unity sky, and post-processing remain outside the static conversion.

## Prompt to copy into Claude

> Build a Three.js scene using https://github.com/kk20054/ThreeJS-Stylized-World-Assets . Read the raw asset-index.json first, then consult manifest.json for the chosen assets. Use only IDs and paths present in the manifest; do not guess filenames. Select Temple assets with collection "temple" and Meadow assets with collection "meadow"; Meadow IDs have a MEADOW_ prefix. Load only the assets needed for the scene using GLTFLoader from https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/ . Temple GLBs are self-contained. Meadow .gltf files reference shared .bin buffers and textures: preserve every relative dependency, and load from the original URL rather than uploading only the .gltf file. Use Three.js 0.180.0 for both core and addons, +Y up and meters, and source pivots. Cache loaded assets, reuse geometry/materials, show errors visibly, and release resources only when no remaining object uses them. Two complete static author arrangements are included under scenes/: Overview has 369 objects and DioramaExample has 609. For those arrangements, follow CLAUDE_AUTHORED_SCENES.md, read scenes/index.json plus the selected summary/group JSON, and preserve hierarchy, source-ID strings, shear and pivots without random scatter or per-model recentering. Unity shader behavior, wind, particles, seasonal layers, terrain blending, collisions, ASP settings and binary Terrain assets are not automatically reproduced. For a ground plane, consult collections/meadow/terrain-textures.json and use the documented diffuse/normal roles and tiling. The demo uses the Grass diffuse and normal with one tiled material. Mask channel semantics are unverified: do not assume ORM packing. These layer files are not a Unity Terrain mesh or heightfield. The foliage base color already includes the source material color bake; avoid applying that overlay a second time. Do not claim a target FPS or a supported world size without measurements on the target device.

## Select a small subset

~~~js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const base = 'https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/';
async function getJSON(path) {
  const response = await fetch(new URL(path, base));
  if (!response.ok) throw new Error(path + ': HTTP ' + response.status);
  return response.json();
}
// Read asset-index.json first to choose IDs; use manifest for full metadata.
const catalog = await getJSON('manifest.json');
const temple = catalog.assets.find(a => a.collection === 'temple' && a.id === 'SM_Temple');
const tree = catalog.assets.find(a => a.collection === 'meadow' && a.category === 'Trees');
if (!temple || !tree) throw new Error('The requested subset is missing.');
const loader = new GLTFLoader();
for (const asset of [temple, tree]) {
  const gltf = await loader.loadAsync(new URL(asset.path, base).href);
  scene.add(gltf.scene);
}
~~~

The glTF URL is also the base for resolving its relative dependencies. If code first fetches glTF JSON and calls parseAsync manually, supply the **glTF file's directory URL** as the resource path. Supplying the repository root instead can break Meadow's buffer and texture paths.

To copy a subset locally, inspect each selected glTF's buffers[].uri and images[].uri, copy those files, and preserve the relative layout. Some resources are shared by multiple assets. Avoid deleting or disposing a shared resource while another selected object still uses it. Do not assume asset.bytes includes all shared dependencies; inspect the manifest's actual size fields and distinguish model-document size from unique transferred dependency size.

## Static foliage color and terrain limits

The Meadow bake follows the inspected source leaf shader: desaturate the sample, apply brightness, apply overlay using _BaseAlbedoColor to choose the branch, then lerp between that color and the textured result. The oak leaf source image is grayscale; its green comes from the material overlay. Treat the exported color texture as the baked base color, not a raw grayscale input requiring another guessed tint. Wind, procedural noise/variation, vertex-AO/vertex masks, seasonal blending, and SSS are not reproduced by this static PBR approximation.

For the inspected albedo TIFF inputs with meaningful untagged cutout alpha, conversion uses tifffile rather than trusting an opaque Pillow fallback. The stored silhouette alpha and source cutoff remain part of the exported material; this does not establish unknown terrain-mask channel packing. Tool requirements are listed in [tools/README.md](tools/README.md).

TerrainLayer texture metadata preserves authored tileSize, tileOffset, normalScale, and source importer notes. Preserve mask pixels and unknown channel_mapping values instead of inventing a packing scheme. The six layers and 14 shared texture files do not include terrain geometry, heightmaps, splatmaps, collision, or layer blending.

## Browser examples and checks

- [Asset viewer](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/).
- [Mixed Temple + Meadow scene](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/examples/world-demo.html).
- [Source of the mixed scene](examples/world-demo.js).
- [Authored scene viewer](https://kk20054.github.io/ThreeJS-Stylized-World-Assets/examples/authored-scenes.html), [layout documentation](scenes/README.md), and [copyable authored-scene prompt](CLAUDE_AUTHORED_SCENES.md).

The mixed scene uses five selected source models and the real Grass diffuse/normal surface textures, deterministic placements, near/far camera presets, and clone/InstancedMesh modes. Each mode resets its own timing window. The page shows actual renderer statistics and labels the scope of measurements; resource counts are not GPU-memory bytes. One bounded local run at 1280 × 720/DPR 1 in Chrome 155 on Windows, with the far camera and shadows off, observed 484 clone draw calls versus 9 instanced draw calls, both submitting 386,594 triangles over 385 model placements. This demonstrates draw-call reduction for that scene, not a benchmark result established for another user's device, or a general FPS claim. The earlier asset-library/mixed-demo public snapshot was checked separately in [the public-access receipt](validation/unified-public-access.json) and [browser preview receipt](validation/public-browser-preview.json). Those receipts do not certify final remote delivery of the newer authored scenes, alpha fixes, or PNG set. See FEASIBILITY.md for exact source IDs.

A cross-origin check can use the local HTTP demo with a base parameter:

~~~text
/examples/world-demo.html?mode=instanced&base=https%3A%2F%2Fraw.githubusercontent.com%2Fkk20054%2FThreeJS-Stylized-World-Assets%2Fmain%2F
~~~

In developer tools, verify successful requests for the selected model documents and their external resources. Switch rendering modes and confirm cached assets are reused. A glTF JSON HTTP 200 response alone does not prove that its buffer, texture, and WebGL uploads succeeded.

Use raw GitHub URLs for JSON/model data, Pages or your own host for JavaScript modules, and a pinned commit SHA when reproducibility matters. Never embed a GitHub token in a public browser example. When network access is restricted, report the failing hostname and status without claiming the library is invalid or that Claude has successfully loaded it.
