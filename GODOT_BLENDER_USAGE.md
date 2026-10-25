# SoStylized assets in Godot and Blender

This guide covers the portable SoStylized asset collection. The assets are intended for Godot, Blender, and other glTF 2.0 tools; using Three.js is optional. This delivery is an asset library, not a playable game or a migration of the original Unreal project.

## Find and download assets

1. Read the [SoStylized collection guide](collections/sostylized/README.md).
2. Use the [collection catalog](collections/sostylized/catalog.json) to identify the exact exported asset, source object, file path, and exported LODs. Read each item's exported_lods field and conversion notes before importing it. A source inventory entry alone does not establish that a portable export is available.
3. Download the required category packages from [this repository's Releases page](https://github.com/kk20054/ThreeJS-Stylized-World-Assets/releases). Use the actual release notes and catalog to select packages; do not infer ZIP names or construct a release URL from an asset name.
4. Extract the package before importing its GLB files. Preserve any companion catalog, preview, and provenance files. The full category packages are distributed separately from the small direct examples in the repository.

Each published GLB is intended to be self-contained: mesh data, portable materials, and their textures are embedded. A self-contained GLB does not need the original RAR, Unreal installation, or source uasset files at runtime. If the catalog declares additional dependencies for a particular item, retain them with that item.

Only use counts, package availability, and links recorded in the current catalog and release notes. Source object counts, exported model counts, material variants, and authored LOD counts describe different things.

## Shared import contract

- The GLB export has already converted Unreal centimetres to metres and uses +Y up, right-handed glTF coordinates. Do not apply another 0.01 scale or an additional Unreal-to-glTF axis conversion.
- Preserve imported node transforms, hierarchy, mesh-local transforms, and author pivots. Apply any scene-specific overall placement or scale on a new outer parent. Recentring each part can break modular assembly.
- This release supplies native LOD0 only, recorded as exported_lods=[0]. Additional source LODs are not included. Target-engine generated LODs are separate derivatives.
- Geometry and static material output are separate conversion concerns. Inspect the item's notes for omitted helpers, collisions, unsupported behavior, or material fallbacks. A visible mesh is not proof that a collision shape or animated effect was exported.
- Source material parameters are evaluated into portable static material data where supported by the native bake. Keep supplied color, normal, roughness, and opacity assignments rather than guessing new ones from texture filenames.
- Preserve material alpha mode, cutoff, and double-sided settings. The original source image's alpha channel may not be the source material's actual opacity mask. Do not replace a baked cutout with guessed transparency or an opaque fallback.

## Godot

1. Extract a selected package into a suitable project asset directory, or copy the selected GLBs there. Let Godot finish importing them.
2. Open the GLB in the advanced import dialog to inspect its scene hierarchy and materials. Instantiate its imported scene, or create an inherited scene for project-specific adjustments.
3. Keep the imported transforms and materials initially. Put project placement and miniature-world scaling on a parent Node3D so the original asset remains reusable.
4. The supplied geometry is native LOD0. Configure any generated import LODs and distance selection for your own scene; those do not reproduce the author's omitted lower-LOD policy.
5. Inspect leaf/grass silhouettes, two-sided foliage, normal direction, pivots, and scale under the lighting and renderer used by your project. Adjust lighting after checking the unchanged imported materials.

For editable materials, use Godot's material extraction or scene inheritance workflow and keep the original GLB as the source. Godot-generated import caches are reproducible engine data; they are not additional source textures that must be distributed beside a self-contained GLB.

Collision, navigation, placement density, streaming, and interaction belong to the consuming project. Build and test them explicitly. This library does not modify a game's world state, save format, combat, or simulation.

## Blender

1. Extract the selected package.
2. Choose **File > Import > glTF 2.0 (.glb/.gltf)** and select the GLB.
3. Keep the imported hierarchy and transforms. Blender handles glTF's coordinate conversion during import; do not add another 0.01 scale or manual axis rotation merely because the authoring source was Unreal.
4. Use Material Preview or a controlled rendered view to inspect the supplied materials and cutout silhouettes. Solid viewport shading does not demonstrate the textured appearance.
5. Keep the supplied LOD0 identifiable if you prepare a reduced-detail derivative.
6. Save a .blend copy for your own layout or edits. If you re-export glTF, verify units, hierarchy, alpha settings, and the selected LOD again in the receiving application.

Textures embedded in a GLB are read by Blender's importer. A missing original RAR path is not a reason to substitute unrelated image files. Record deliberate material or geometry edits separately from the supplied conversion.

## What static GLB conversion does not include

The original library uses Unreal-specific material graphs and runtime systems. Portable static meshes and baked material inputs do not automatically reproduce:

- Procedural wind, foliage interaction, temporal fades, subsurface scattering, runtime seasonal mixing, weather, or changing global material parameters.
- Unreal water shaders, refraction, caustics, river behavior, or animated texture playback. A water-shaped mesh or texture atlas does not provide those behaviors by itself.
- Blueprints, Niagara systems, particles, audio behavior, collision logic, navigation, or project simulation.
- Landscape heightfields, layer blending, virtual-texture behavior, terrain collision, or a complete traversable world.
- Original lighting, post-processing, sky behavior, cameras, and complete authored scene arrangements.

The source archive contains 42 Unreal map files. Their presence in the source inventory does not mean their layouts have been converted. Only an explicitly published scene conversion and its documented scope can establish portable authored placements. Individual GLBs and preview images must not be described as the complete original Unreal scenes.

## Provenance and rights

The user-supplied source is the single SoStylized.rar archive stored locally under the combined labels **Stylized Mega Bundle / Stylized Nature**. Those two labels do not establish two independent source packages. Consult the collection catalog and source records for exact source object paths, archive identity, hashes, and conversion scope.

Original ownership and source license terms remain applicable. Conversion, packaging, and repository publication do not grant a new permissive license or change the rights attached to third-party models and textures. Use the assets under the rights associated with the original source. Tool and engine licenses remain separate from asset rights.
