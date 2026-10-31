# RedFly Sword Qi VFX

The owner supplied the purchased **Particle_2025.12.23_RedFly红飞.rar** package for project development on 2026-10-31. It is indexed in the Sword and Saber VFX category alongside DaoGreen.

## Included source

The original RAR contains one UnityPackage with **22 assets plus 22 .meta files**: seven PNG textures, two FBX files, six materials, two URP Unlit ShaderGraphs, one prefab containing six ParticleSystems/renderers, one animation clip, one Timeline, one preview scene and one Bloom settings asset. The archive integrity check and extraction passed. See [inventory.json](inventory.json) for source paths, sizes, hashes and texture dimensions.

## Retrieve the complete payload

[Open the source collection in the existing private game repository](https://github.com/kk20054/fanren-godot-world/tree/main/reference_assets/sword-vfx/red-fly-20251223). Authorize Claude's GitHub connection for kk20054/fanren-godot-world, then read manifest.json, effect_summary.json and guid_map.json in that collection before fetching only the needed files. Original archives and the full Assets/vfxCase hierarchy are retained. Binary files use Git LFS; retrieve actual objects, not pointer text.

The matching [RedFly MP4 preview](https://github.com/kk20054/fanren-godot-world/blob/main/reference_assets/sword-vfx/red-fly-20251223/previews/Particle_2025.12.23_RedFly.mp4) is stored with the private payload. Its filename, size and hash are recorded in index.json.

## Target-engine use

PNG textures and FBX source geometry are available as adaptation inputs. Mesh01.FBX is the effect mesh; Charactor.fbx is the preview-character source. Unity ParticleSystem, ShaderGraph, Timeline and Bloom behaviour need target-engine reconstruction. This entry does not supply a finished Godot effect, converted GLB, or runtime equivalence test. Use it for sword-qi and attack-effect development with the existing game action phases and the in-game effect editor.

## Purchase and source terms

Purchase and project-use authorization are owner-confirmed. No license text was included in the containers, and exact-pack commercial/public-source redistribution rights are not independently asserted. Following the existing purchased-VFX arrangement, this public entry contains the index and instructions; the complete paid source payload is in the private repository. See [rights status](../../../RIGHTS_AND_COMMERCIAL_USE.md).
