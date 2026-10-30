# Claude: combat environment, VFX and technique iteration

Use this library with the actual Godot project [kk20054/fanren-godot-world](https://github.com/kk20054/fanren-godot-world). Improve the existing combat modules and game data; this document is a development brief, not an implemented combat feature. The owner confirms the supplied packs were purchased and instructs actual use in this project; implement with them rather than stopping at a catalog. The tree's named license exception and original source terms remain recorded. Begin with [library-index.json](library-index.json) and [rights status](RIGHTS_AND_COMMERCIAL_USE.md).

## Select real reusable assets

| Combat role | Existing source | Verified starting assets | Retrieval |
| --- | --- | --- | --- |
| Broadleaf canopy / edge bushes | Meadow | MEADOW_SM_OakTree_01; MEADOW_SM_BirchBush_01 | models/Meadow/Trees/ plus the shared resources declared by each glTF |
| Low grass / foliage | Meadow | MEADOW_SM_Grass_01_01; CoverPlants / Plants / Flowers categories | collections/meadow/asset-index.json |
| Grouped rocks | Meadow | MEADOW_SM_RockGroup_01 and MEADOW_SM_RockGroup_02 | models/Meadow/Rocks/ plus relative dependencies |
| Pine / bamboo forest edges | SoStylized | Trees category; SM_Bamboo1..4 are indexed examples | collections/sostylized/indexes/Trees.json and the Trees Release ZIP |
| Ferns / bamboo bushes / grass masses | SoStylized | SM_Fern1..3; SM_BambooBush01, plus the Foliage index | Foliage Release ZIP, not a guessed repository binary path |
| Large rock silhouettes | SoStylized | SM_BoulderClassic1..4 | Rocks Release ZIP |
| Sect ruins / stone lamps / steps | Temple | Existing Buildings, Pillar and Props entries | collections/temple/asset-index.json; use actual IDs and bounds |
| Procedural canopy technique | nicoo-474/procedural-tree | Four species/four seasons, baked spherical normals on GLB export | Pinned source in the private project repository; owner-directed project use with the missing upstream license recorded; see collections/procedural-tree/ |
| Ordinary attack sword arcs | DaoGreen source inventory | Seven PNGs, four FBXs, six-ParticleSystem Unity prefab (disabled root plus five render layers) | Purchased source payload in the private game repository; public index at collections/sword-vfx/dao-green-20251211/ |

The former models/, textures/, scenes/ and collection paths remain stable. Do not treat a glTF JSON alone as a complete asset; retain declared buffers/textures. SoStylized catalog paths are members of category ZIPs. Ignore collision/editor helper meshes when choosing visible props. A static GLB is not a converted wind/cloud/water material.

## Fetch the private source ingredients

Authorize Claude's GitHub integration for `kk20054/fanren-godot-world`, then start with `reference_assets/index.json`. Read the sword manifest, `effect_summary.json` and `guid_map.json` before fetching only the needed resources. Binary PNG/FBX/archive files use Git LFS. A small response beginning `version https://git-lfs.github.com/spec/v1` is a pointer, not image, mesh or archive data. In an authorized local checkout, retrieve the actual objects with `git lfs pull --include="reference_assets/**"`; do not try to import the pointer text. Verify the downloaded file against the asset manifest. The source text and parsed settings remain directly readable through the GitHub connector. The public catalog alone does not grant an account access to the private repository.

## Scene and environment

Make one continuous sword-cultivation place: an open, readable combat floor framed by uneven groves, grass masses, stones, a worn path and sparse sect markers. Keep fighting silhouettes, projectiles and telegraphs legible. Group grass/flowers in drifts with calm gaps rather than an even scatter. Ground colour, canopy, stone and fog must agree on biome and light. Use foliage masks/materials under their original terms.

Reuse the existing large-world Vista/landform/vegetation approach for a shared wind direction, gust strength, sun direction/colour, sky fill, cloud shadow and palette. Inspect the actual module APIs before wiring them. The combat sandbox remains standalone: do not instantiate the whole outdoor map, create a second WorldState, write life time from a shader, or import a huge runtime solely for wind. Expose the minimum shared presentation parameters to existing combat materials. Preserve leaf normals and check two-sided leaf shading. Use MultiMesh/LOD for repeated plants only where already useful; no blanket full-map density increase.

## Reference-driven combat

Study the existing source clips and notes, including [BV197nZ6BEWj](https://www.bilibili.com/video/BV197nZ6BEWj/), docs/research/combat_iteration_assessment_2026-10-29.md, the earlier combat/flight benchmarks and archived reference screenshots in the game repo. Actually inspect relevant moments of startup, contact and recovery before claiming a reproduction. Borrow readability, movement rhythm and relationship between character and effect; keep the game's cultivation identity. Reference visibility is not permission to copy a game's entire content or simulation.

Work on the existing heading/aim, ActionClock, motion and contact results: make normal-speed attacks coherent, contact readable and recovery continuous. Respect real interruption, guard and dodge results. Keep bright effects subordinate to the fighter silhouette and floor telegraphs; use brief hit flashes only when a real positive contact occurred. Do not invent contact with a cosmetic glow.

## Sword light on ordinary attacks

For the purchaser's project, read the [private source payload](https://github.com/kk20054/fanren-godot-world/tree/main/reference_assets/sword-vfx/dao-green-20251211) through the authorized GitHub integration, then port the DaoGreen PNG/mesh ingredients into Godot materials and bounded attack arcs. Unity ShaderGraph, ParticleSystem and Timeline need reconstruction; reading their names is not a port. First prove a single ordinary slash through startup, active peak, contact and recovery using the original attack phase, existing effect/hand anchor and heading. Then configure three-hit variations, direction and interruption through stable presentation profiles. Effects consume the original phase; they create no second clock, damage tick or hitbox. Keep placeholders explicit if the source package cannot be fetched.

## Technique selection

Extend the existing 功法 page so learned techniques can be selected/equipped/switched through stable technique IDs and the original controller/rule/save contract. Let the equipped technique drive its legal combat skill configuration and ordinary-attack sword-light profile. Keep one authoritative selection and explicit old-save defaults. Do not add a disconnected selector that only changes icons, a second inventory or another combat settlement. If the trial needs a standalone preference, keep it explicitly ephemeral rather than pretending it is a saved life selection.

Deliver a locally runnable increment and list exactly what changed, what was observed, temporary assets and remaining issues. Focus checks on changed rules, actual rendering and the delivered executable; do not expand routine font/resolution/text-scale or whole-life test matrices for an environment/VFX increment.
