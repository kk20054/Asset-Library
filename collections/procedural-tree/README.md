# Procedural Tree — external source reference

Upstream: [nicoo-474/procedural-tree](https://github.com/nicoo-474/procedural-tree), pinned to [`a5f5e026b17657c17ed0bbb8c7a924f81cc5a69f`](https://github.com/nicoo-474/procedural-tree/tree/a5f5e026b17657c17ed0bbb8c7a924f81cc5a69f). Four species (oak, willow, pine and cherry) and four seasons are implemented in the browser, with GLB export.

## Rights

No repository LICENSE/COPYING or author license declaration was found at that commit. The bundled three.js header is MIT, but that does not license the generator or its output. The upstream commercial/source-output license remains **unconfirmed**. After this was disclosed, the owner explicitly directed use of all supplied material in this project. A [pinned private source snapshot](https://github.com/kk20054/fanren-godot-world/tree/main/reference_assets/procedural-tree/nicoo-474_a5f5e026) records that project-use exception and retains the upstream files and three.js notice. The public Asset-Library contains this index and technical assessment, not a new public source mirror or an MIT grant for the generator. See [the shared rights table](../../RIGHTS_AND_COMMERCIAL_USE.md).

## Godot and Blender handoff

The GLB exporter bakes current leaf instance positions and spherical normals. It retains POSITION/NORMAL/UV/COLOR_0, embedded PNGs, alpha mask cutoff 0.45, double-sided material flags and roughness. Preserve the authored normals and vertex colours on import. Spherical normals are not lost simply because the output is GLB.

The GLB does not contain the generator, seed/season controls, wind, whole-canopy sway, growth animation, instancing, scene lighting, ground, AO or the custom shader treatment of backface normals. Recreate those behaviours with the existing Godot environment and wind system; do not claim a visual one-click port. Check both leaf sides, alpha cutouts and lighting on one tree before using MultiMesh for groups. Use simple trunk collision only.

For the owner-directed project work, name outputs by species, season and seed, and keep a JSON sidecar recording those values, density/branch parameters and the upstream commit. The original export filename does not include season. This entry is a vegetation reference, not a combat controller or character-animation system.
