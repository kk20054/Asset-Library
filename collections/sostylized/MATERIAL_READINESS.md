# SoStylized material readiness

This is a portable environment asset collection for Godot and Blender. Read [README.md](README.md) and [GODOT_BLENDER_USAGE.md](../../GODOT_BLENDER_USAGE.md) with the actual release catalog. A successful export or import does not establish visual parity with Unreal or acceptance of every asset.

## Select assets from the catalog

Use catalog.json for source identity, status, path, hashes, exported_lods, uv_normalization, warnings, and required_extensions. Load only entries marked packaged with a real payload path. Inventory totals include source objects and are not render-ready totals. Consult the release notes for packages actually published.

The portable static-mesh policy is native Unreal **LOD0 only** (exported_lods=[0]). These are source mesh exports, not reconstructed geometry. GLBs embed geometry and portable textures; Unreal is not needed to import a self-contained GLB. Units are metres, +Y up, right-handed; do not apply a second centimetre conversion. Preserve source pivots and local transforms.

The packager normalizes a material's single referenced UV channel to TEXCOORD_0 and updates texture references without changing binary geometry or image chunks. Stale tangents are removed when the UV channel changes. Mixed material UV channels are preserved and flagged instead of being silently flattened. Check each entry's report; UV normalization does not repair an incomplete material bake.

## Material limitations and known exceptions

Native static baking captures supported material values, not the complete Unreal graph. Per-asset engine_log_warnings also retain native exporter warnings about subsurface-to-Default-Lit fallback, overlapping or degenerate bake UVs, and other export limitations. These log warnings are separate from glTF specification validity. Godot and Blender import glTF materials, while wind, global environment parameters, camera/depth fades, runtime virtual textures (RVT), Blueprints, Niagara, animated water and source lighting require receiving-engine work. Preserve foliage cutoffs and double-sided settings; source texture alpha alone may not describe the final silhouette.

| Asset | Observed readiness and required work |
| --- | --- |
| SM_CliffClassic1 | The lower portion is black in the inspected bake. Its embedded base-color PNG is byte-identical to the older LOD0 export; this is not a new UV0-packaging artifact. Source MI_RockClassic enables UseVTBlend?, and M_Rock references landscape RVTs and bottom-edge blending. This points to scene-dependent RVT baking as the limitation. Use an explicitly adapted material or rebake without that dependency before relying on the exposed lower cliff. The portable material remains unresolved. |
| SM_IndividualCloudPlane | The inspected baked base-color texture has alpha=0 throughout, so the exported material is invisible. Source evidence references CameraDepthFade, MPC_GlobalEnvironment and a Blueprint that sets opacity/fade parameters. The mesh and texture source are usable inputs for a custom cloud shader; the current bake is not a visible cloud effect. Do not treat forcing opaque alpha as faithful reproduction. |
| SM_OakTree1 | An additional Blender CPU view shows large near-black canopy/card regions. The source exporter reports overlapping bake UVs and a subsurface fallback, but the exact cause has not been isolated. Geometry imports; the material requires repair before visual use. See [additional Oak preview](previews/oak-contact-sheet.png). |
| SM_OakFallen1_SnowCover | A single additional CPU view shows wood and snow geometry without the OakTree1 canopy defect. This only describes the inspected asset and angle. |
| SM_WaterRiver04 | A pale cyan/white static water approximation was visible. Source water animation, depth response and other Unreal shader behavior are not transferred. Build a target-engine water material when motion or scene interaction is required. |

Read-only Blender CPU review covered six selected native GLBs: bush, bamboo and pine silhouettes/materials were visible; the cliff, cloud and water limitations above were recorded. This is bounded sample evidence, not whole-collection visual acceptance or a Godot runtime certification. The published [preview receipt](previews/preview-receipt.json) records the six source identities, portable hashes and capture scope. Detailed source-material diagnosis remains local preparation evidence.

## Scene scope and rights

The 42 Unreal Worlds are indexed as source identities only. Their authored layouts, Landscape, placement, lighting and simulation are not delivered as converted scenes by this collection. Six source animations and one DemoPawn skeletal mannequin are excluded from the static environment conversion.

The source is the user-supplied SoStylized.rar archive, locally described as Stylized Mega Bundle / Stylized Nature; those labels identify one archive. Original ownership and license terms remain in force. Conversion and packaging grant no new asset license, redistribution permission or commercial clearance. Tool licenses are separate from model and texture rights.

## Recorded import evidence

[Format validation](validation/glb-format.json) covered all 787 packaged GLBs: zero specification/container errors and zero external resource references. The 634 warnings concern receiving-engine generation of normal-map tangents. [Godot 4.7.2 import](validation/godot-samples.json) covered six representative GLBs with successful import/instantiation, populated texture/material slots and matching dimensions; it was headless and did not certify their rendered appearance. Native bake warnings were retained for 301 mesh assets and do not have the same meaning as glTF format errors.
