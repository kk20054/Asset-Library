# Use the author's Meadow layouts with Claude

The repository includes two complete static scene arrangements converted from the original Meadow Unity scenes: **Overview (369 placements: 361 models + eight visible Cube platforms/backdrops)** and **DioramaExample (609 placements across seven groups)**. These are the author's placements, not a newly generated scatter layout.

## Text entry points

Read small text documents in this order:

1. [Scene index](https://raw.githubusercontent.com/kk20054/Asset-Library/main/scenes/index.json).
2. The selected scene's [Overview summary](https://raw.githubusercontent.com/kk20054/Asset-Library/main/scenes/overview/summary.json) or [Diorama summary](https://raw.githubusercontent.com/kk20054/Asset-Library/main/scenes/diorama/summary.json).
3. The groups[].placement_pages entries relevant to the requested composition. Each page contains at most 24 read-only placement summaries. Read groups[].path when the complete group hierarchy is required.
4. The selected full layout.json only when complete hierarchy or placement details are needed.

Use the root [asset index](https://raw.githubusercontent.com/kk20054/Asset-Library/main/asset-index.json) and [manifest](https://raw.githubusercontent.com/kk20054/Asset-Library/main/manifest.json) for individual model identities and dependencies. Do not guess scene, group, model, or preview filenames.

The [authored-scene viewer](https://kk20054.github.io/Asset-Library/examples/authored-scenes.html) exposes source-camera and additional inspection views. See [scenes/README.md](scenes/README.md) for the conversion contract.

## Prompt to copy into Claude

> Use the original author's Meadow arrangement from https://github.com/kk20054/Asset-Library . Start by reading the raw scenes/index.json, then the selected scene's summary.json. Follow the needed groups[].placement_pages for small placement summaries, then groups[].path for complete hierarchy, to understand the author's grouping and layout. Select overview for the seasonal asset display and distant-scenery groups, or diorama for seven authored diorama groups. Load the entry.model URL using Three.js GLTFLoader with Three.js 0.180.0 core and addons. Keep the glTF's shared buffers/textures reachable through their original relative paths. Preserve every authored relative placement, parent hierarchy, local scale, rotation, pivot, and string source ID. Do not random-scatter, normalize, or recenter each model. Do not decompose world matrices and lose shear; do not reapply JSON world matrices on top of an already loaded scene.gltf. If the requested world needs a translated group, add one clearly described outer group wrapper while retaining its internal arrangement and necessary ancestors. Use source-camera for the source camera composition; complete-layout and group views are additional inspection cameras. Inspect preview paths and renderer receipts from the index rather than inventing images. Preview PNGs are Blender renders of the converted layout, not Unity source screenshots. Show loading failures visibly, and distinguish preserved static arrangement from unported particles, collisions, ASP settings, sky, wind, and post-processing. Report actual browser checks instead of claiming an untested Claude account or scene has rendered successfully.

## Read one group without loading every document

~~~js
const base = 'https://raw.githubusercontent.com/kk20054/Asset-Library/main/';
async function readJSON(path) {
  const response = await fetch(new URL(path, base));
  if (!response.ok) throw new Error(path + ': HTTP ' + response.status);
  return response.json();
}
const index = await readJSON('scenes/index.json');
const entry = index.scenes.find(item => item.id === 'diorama');
if (!entry) throw new Error('Missing authored scene');
const summary = await readJSON(entry.summary);
const chosen = summary.groups.find(group => group.name === 'Diorama 01 Summer');
if (!chosen) throw new Error('Missing authored group');
const groupLayout = await readJSON(chosen.path);
// groupLayout.groups retain the local hierarchy; groupLayout.objects reference it by parent_id.
// Load entry.model with GLTFLoader to view the complete authored static scene.
~~~

Read group_id, groups[].id/parent_id, objects[].parent_id, source IDs, asset references, and coordinate_contract together. The declared flip-X basis uses column-major matrices suitable for Matrix4.fromArray. The existing scene.gltf is already assembled with its native mesh-unit scales and pivots. Do not multiply each imported object by world_matrix_gltf again. For a custom reconstruction from metadata, reproduce the declared hierarchy and mesh-node attachment contract exactly.

A model source can appear many times and with several material variants. The 978 static placements across the two scenes are not 978 unique models. Overview's group called VFX also contains two visible authored Cube display pieces; the group name does not mean that particle animation was converted.

## Camera, screenshot, and runtime boundaries

The source-camera entry retains the original local camera composition. It will not show every seasonal bank or all seven dioramas at once. Complete-layout and per-group views were added for inspection and must be labeled accordingly.

Reference PNGs come from Blender rendering the converted scene layout. Use their index entries and per-scene preview receipts to identify exact paths, view, render engine, and dimensions. They are not original Unity screenshots and do not prove final browser output. The index currently lists 18 PNG references at 1600 × 900. Public verification receipts identify their tested commit.

All 35 source FX anchors remain recorded (Overview 21, Diorama 14), while dynamic particles are unported. Source collisions, ASP global behavior, Unity sky/post-processing, procedural wind/noise, and vertex-based shading are not restored by static mesh assembly. Each summary retains an unresolved GlobalTreeSSSDistance override. The portable PBR materials remain approximations even when the layout matrices match the source.

Serve local examples over HTTP. For a public deployment, verify the scene document **and every external dependency** from the actual browser origin. Cache shared resources and release them only after their last user. Pin a full commit SHA for reproducibility. If a chat service only reads text, it can still use the scene/group metadata to write code, but that does not prove it downloaded or understood the binary geometry.
