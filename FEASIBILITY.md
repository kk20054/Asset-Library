# Large-world feasibility: Temple + Meadow

The two collections can provide building blocks for a Three.js world: Temple supplies Chinese architecture and props; Meadow adds vegetation, rocks, and background meshes. That is a content-coverage assessment, not proof of a finished world, a consistent art direction, or a supported object count.

## Evidence and current limits

| Question | Evidence | Limit |
| --- | --- | --- |
| Can the combined library load in Three.js? | All 516 models passed the [unified browser loading check](validation/unified-browser-load.json). The renamed public viewer and mixed scene also rendered successfully. | Public runtime checks cover the stated samples; all-file format and local browser checks are recorded separately. |
| Are complete authored arrangements included? | Overview preserves 369 static objects (361 models + eight visible Cubes); DioramaExample preserves 609 across seven groups. | These 978 placements preserve static hierarchy and material choices, not the complete Unity runtime or dynamic effects. |
| What is present in Meadow? | 381 exported glTF variants from 144 independent static environment FBXs; 516 model assets across both collections. | Variants are not additional independent source models; six ground layers and 14 surface textures are separate resources. |
| Are Meadow files structurally valid? | All 381 variants passed [Khronos validation](validation/meadow-gltf.json) with zero specification errors and zero dependency errors; 276 warnings concern runtime-generated normal tangents. | Format validation does not prove final lighting, source-shader equivalence, or public-host accessibility. |
| Can Unity files be used directly? | Actual mesh and Prefab material content is exported as portable glTF. | Unity scripts, custom shaders, particle behavior, scene lighting, and binary Terrain assets are not a browser runtime. |
| Do the two collections look coherent together? | Their roles are complementary. | No inventory count or format check establishes matched brushwork, saturation, scale, lighting, or density. Inspect the actual combined scene. |
| Does instancing reduce calls in the mixed scene? | A local far-camera run observed 484 clone calls versus 9 instanced calls with equal 386,594 submitted triangles. | This is a bounded 385-placement scene observation; no general FPS, supported world size, or geographic streaming benchmark is established. |

Meadow's audited static meshes cover trees, rocks, grass, flowers, cover plants, mushrooms, props, and distant hill/mountain forms. The six particle/VFX source meshes and one editor helper are outside the static export scope. Three binary Unity Terrain assets are excluded; hill/mountain mesh props do not replace a terrain, navigation, collision, or streaming system.

The [anonymous public-delivery receipt](validation/unified-public-access.json) records 822/822 successful URL checks with CORS, file lengths where present and hashed model samples. The [public browser receipt](validation/public-browser-preview.json) covers the live Pages viewer, mixed scene and raw cross-origin model/texture loading. This establishes delivery of the earlier asset-library/mixed-demo snapshot without GitHub credentials; individual coding-assistant environments may still restrict outbound requests. It does not establish final remote verification of the subsequently added authored scenes, TIFF-alpha updates, or final preview PNG set.

## Authored layout reuse and independent evidence

The original Overview and DioramaExample static arrangements are included as complete scene.gltf files, layout metadata, summaries, and small per-group JSON documents. Start at [scenes/index.json](scenes/index.json), read the selected summary, then follow only the required group paths. The [scene README](scenes/README.md) explains the contract; [CLAUDE_AUTHORED_SCENES.md](CLAUDE_AUTHORED_SCENES.md) provides a direct reuse prompt. GLTFLoader resolves the scene's external dependencies when the original relative layout remains reachable.

Overview has 361 model placements plus eight original visible Cube platforms/backdrops; DioramaExample has 609 model placements. Source counts additionally record 21 and 14 FX anchors, respectively, plus each scene's global settings. All 35 FX anchors remain metadata without particle animation. Collisions, ASP global behavior, Unity sky/post-processing, and procedural shader behavior are not claimed as equivalent runtime systems.

An independent source-YAML check compared ten original Prefab-root landmarks and Overview's eight visible Cube roots against accumulated glTF parent-chain matrices. The checked source-root positions matched, including the nonuniform-scale/rotated-parent case that produces shear. This geometric evidence concerns the preserved arrangement; it does not establish final material appearance, Unity lighting equivalence, browser completion, or remote delivery of a later revision.

Preserve local parent transforms rather than decomposing flattened world matrices. Keep Unity 64-bit IDs as JSON strings; JavaScript numbers cannot safely retain every source file ID. Retain native mesh scales/pivots once and avoid a second application of JSON world matrices after loading an assembled glTF. Do not normalize, recenter, or random-scatter the authored objects. A clearly labeled outer whole-group translation can reposition an arrangement without changing its internal layout.

Only source-camera corresponds to the original author's local camera. Complete-layout and per-group views are added inspection cameras. Preview references identify **Blender renders of the converted layout, not original Unity screenshots**. Read actual index entries and receipts for image paths/provenance; no fixed final PNG count or completed final remote QA is inferred here.

## Storage is different from runtime cost

The unchanged Temple baseline is 135 self-contained GLBs totaling **355,670,520 bytes**, with **430,042 triangles** when counting one of every exported asset. That library sum is not the number submitted in a particular camera view.

A local read of those 135 GLBs found **445 embedded image references**, totaling **336,649,963 encoded image bytes**. SHA-256 deduplication of image contents found **239 distinct images**, totaling **209,768,888 encoded bytes**. This identifies repeated image data across independent files. It does not measure allocated GPU memory, and it is not a promised download saving for every subset.

The largest Temple triangle counts include SM_Character_Merged (51,511), SK_Character_AsStaticMesh (35,927), SM_Bell_B (29,734), and SM_Roof3x5 (21,520). Static character props and decorative high-detail modules need not be loaded for a landscape view. Meadow has 381 exported material variants from 144 independent source models after filtering lower LODs and duplicate combinations. Current total_payload_bytes and per-asset dependencies are recorded in the manifest; no combined byte total is frozen in this document.

Meadow's glTF documents reference shared buffers and textures. Preserve their relative paths; loading only the JSON is insufficient. Shared files allow HTTP reuse, but applications should still cache loaded documents and intentionally share decoded geometry/materials. Do not assume two separately parsed glTF documents automatically share every GPU allocation.

## Static foliage colors and ground textures

The source oak leaf image is grayscale; a grayscale export would lose the material's actual green appearance. The inspected source S_Tree_Leaf.shader and M_OakTree_Leaf_01_Summer material establish the color sequence used by the corrected bake:

1. Convert the sampled base color into the working color space and apply _BaseAlbedoDesaturation.
2. Multiply by _BaseAlbedoBrightness.
3. Apply overlay with _BaseAlbedoColor, selecting the overlay branch from the **material color** channel being above/below 0.5, rather than the sampled texture channel.
4. Use _BaseLerpBetweenColorandTexture to blend between the material color and the overlay result, then encode the portable color texture.

For the inspected summer oak leaf material, desaturation = 1, brightness = 1, and the color/texture lerp = 1; _BaseAlbedoColor is approximately (0.14902, 0.48235, 0.26263). Those source controls explain why keeping only the raw grayscale pixels was incorrect. The export bakes this base-color branch. It does not claim to reproduce procedural wind, noise-driven tint variation, vertex-AO/vertex-mask shading, SSS, or runtime global season changes. Treat the resulting glTF as a static PBR approximation and avoid applying the material overlay twice.

[collections/meadow/terrain-textures.json](collections/meadow/terrain-textures.json) records **six TerrainLayer definitions and 14 unique image files: six diffuse, four normal, and four mask textures**. It includes source identities, layer tileSize/tileOffset, normalScale, remap values, and importer notes. Normals and masks are shared between some layers. The demo applies the real Grass diffuse and normal to one tiled plane material; it provides a surface-material check without reconstructing Unity Terrain blending.

Mask images retain their source channels and have unverified channel semantics (channel_mapping is null). They are **not repacked or guessed as ORM**. Source importer sRGB settings are recorded separately from the portable linear-data role. Normal pixels and source flipGreenChannel settings are preserved as metadata; independent normal orientation validation is not claimed. These texture resources do not include terrain meshes, heightfields, splatmaps, collision, or a streaming terrain system.

The inspected grass/foliage albedo inputs also require retaining real cutout alpha from TIFF files whose stored fourth channel is not recognized as alpha by Pillow. The conversion uses **tifffile 2026.10.15** to read those samples directly, alongside numpy/Pillow/PyYAML. Replacing that channel with opaque alpha would turn foliage cards into solid rectangles; it is a material-conversion defect rather than evidence of a different authored placement. This alpha handling is specific to inspected albedo inputs and does not assign ORM semantics to terrain mask channels. See [tools/README.md](tools/README.md).

## Apply Three.js mechanisms deliberately

### Reuse repeated objects

Load each selected source once. Shared-resource clones reuse geometry/materials but still create separate renderable objects. For large repeated populations, InstancedMesh groups objects that share geometry and material(s) while varying transforms. It reduces draw calls; it does not remove vertex processing, fragment overdraw, texture cost, or the material passes a model requires. A multi-mesh tree is not automatically one draw call. See the official [InstancedMesh documentation](https://threejs.org/docs/pages/InstancedMesh.html).

Keep batches spatially bounded so that a world-wide bounding volume does not keep distant populations submitted. Preserve each source mesh's local-to-root transform when flattening a hierarchy. After setMatrixAt changes, mark instanceMatrix.needsUpdate and update bounds. The included mixed scene handles local transforms and reflected source geometry; the application still needs an appropriate regional batching design.

### Supply actual LOD geometry

The Temple baseline exports highest-detail render meshes and lists excluded lower-LOD/helper names. **79 Temple assets record source lower LODs.** Those excluded meshes are not present merely because the source had them. A later optimization pass can export and validate the existing source LODs before inventing replacements.

Three.js LOD selects supplied objects by camera distance, with hysteresis available to reduce boundary flicker. It does not generate lower-detail meshes. Determine transition distances from the actual camera and silhouette, and separately decide where grass/flowers disappear. See [LOD](https://threejs.org/docs/pages/LOD.html).

### Optimize textures after measuring

JPEG/PNG bytes describe encoded files, not GPU allocation. A compressed KTX2/BasisU edition may reduce texture storage and transfer costs, but requires a compatible transcoder, detectSupport(renderer), and GLTFLoader.setKTX2Loader(). Keep decoder requirements explicit. See [KTX2Loader](https://threejs.org/docs/pages/KTX2Loader.html) and [GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).

Use color-space annotations correctly: color textures and normal/roughness data have different roles. Check cutout leaves at distance and at oblique angles rather than hiding artifacts with broad transparency. See [Texture](https://threejs.org/docs/pages/Texture.html).

### Bound shadow cost

Start the comparison with shadows disabled and one consistent lighting setup. When testing shadows, limit casting objects and the shadow-camera range to useful nearby content, and record map resolution. Static lighting may use manual shadow updates, but moving vegetation, lights, or loaded regions require corresponding updates. Larger shadow maps cost more computation. See [LightShadow](https://threejs.org/docs/pages/LightShadow.html).

### Load regions on demand

The library is modular: a world application can request a nearby region and prefetch its neighbors. Maintain explicit states for loading, ready, failure/retry, and release. Keep reference counts for assets used by multiple regions and dispose only after their final user releases them. Geometry, materials, textures, and image bitmaps require deliberate cleanup. See [GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).

The included example loads only five selected source models and the selected Grass diffuse/normal surface textures at startup. **It does not implement geographic lazy loading.** A full streaming test needs at least two connected regions, evidence that the second region is absent from initial requests, a successful boundary transition, a failure/retry path, and repeated travel that does not continually increase retained resources.

## Reproduce the bounded scene comparison

Open [examples/world-demo.html](examples/world-demo.html) through an HTTP server. The mixed run used the following source IDs and fixed-seed model placements:

| Asset ID | Placements |
| --- | ---: |
| SM_Temple | 1 |
| MEADOW_SM_OakTree_06 | 96 |
| MEADOW_SM_Grass_01_01 | 192 |
| MEADOW_SM_Flower_09_01 | 64 |
| MEADOW_SM_Rock_12 | 32 |
| Total | 385 |

The single tiled ground plane uses the real Grass diffuse and normal textures from the terrain index and is not another model placement. Counts are test inputs, not a capacity claim. Clones and instancing use the same source assets and transforms.

A **2026-10-21 bounded local browser observation**, using the far camera, Three.js 0.180.0, Chrome 155 on Windows, a 1280 × 720 drawing buffer, DPR 1, and shadows off, reported:

| Mode | Actual draw calls | Submitted triangles |
| --- | ---: | ---: |
| Shared-resource clones | 484 | 386,594 |
| Instanced meshes | 9 | 386,594 |

The equal triangle count establishes equal submitted geometry for this observation while the draw-call count changes. It is not a universal FPS, object-capacity result, isolated GPU-time measurement, or proof of final visual acceptance. The corrected static color bake restored green oak crowns in the local visual check. The final Summer selection retains 385 placements, 386,594 submitted triangles, and 9 instanced draw calls. Public-host and full-catalog checks must be identified by their own receipts rather than inferred from these local counters.

1. Confirm the selected IDs, successful model/dependency requests, actual textures, source scales, and ground contact.
2. Inspect both near and far cameras. Check foliage cutout edges, missing parts, shading, building proportions, and overall composition.
3. Leave each camera/mode running through 30 warm-up frames and at least 120 measured frames. Each mode and camera change resets timing samples. The rolling window retains up to 240 samples.
4. Compare actual renderer calls and submitted triangles. Multi-material primitives may require multiple draws. Instancing and clone modes should not change placement counts.
5. Repeat with a public raw base URL. Confirm external Meadow buffers/textures resolve, not just the top-level glTF document.
6. Compare cold and warm cache behavior. Switching modes should reuse the selected assets rather than download the library again.

The page reports RAF frame-interval p50/p95. These intervals include browser scheduling and display cadence; they are not isolated GPU duration or a CPU simulation benchmark. Browser developer tools can add CPU/GPU diagnostics when needed.

## What a performance receipt must record

Record device/OS/browser, Three.js version, asset commit, selected IDs and populations, camera route, drawing-buffer dimensions, DPR, antialiasing, shadow/postprocessing settings, and cold/warm cache state. Keep first-visible latency, model/dependency transfer, shader-compilation stalls, cross-region stalls, and steady rendering separate.

Use renderer.info for calls, triangles, programs, geometries, and textures. The memory fields are **object counts, not bytes**. For multiple render passes, control info.autoReset/reset() so the counter covers the intended work. compileAsync can reduce first-display stalls once the final lighting/environment is configured. See [WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html).

Report actual p50/p95 and exceptional stalls for the stated run; do not extrapolate a five-source desktop test into a universal FPS or world-size promise. Increase populations only to answer a concrete question, and retain a visible-quality comparison so lower detail is not mistaken for a free optimization.

## Art-direction check

Technical portability and visual compatibility are separate decisions. Compare the two collections under one camera, exposure, light direction, and environment. Check architecture/vegetation scale, rock stroke density, tree/grass saturation, seasonal colors, texture frequency, foliage density, shadow hardness, and distant silhouettes. A convincing shared scene may require selective material adjustments and restrained asset selection. No claim of final visual acceptance is made from file inventories or renderer statistics.
