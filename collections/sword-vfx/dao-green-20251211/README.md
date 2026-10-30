# DaoGreen Sword/Saber VFX — source inventory

The supplied `Particle_2025.12.11_DaoGreen刀.rar` contains a UnityPackage with 25 resources: seven PNG textures, four FBX meshes, seven materials, two ShaderGraphs, one particle prefab with six ParticleSystems (a disabled root and five material-backed child layers), one animation, one Timeline, one preview scene and one Bloom settings asset. See [the factual inventory](inventory.json). No package code was executed.

## Rights and availability

The owner confirms this pack was purchased from [VFXCASE's exact 剑影刀光 / DaoGreen product](https://www.vfxcase.com/2025/12/11/20251211_dao_green/). Its product notice permits purchasers to modify the source and use it in personal and commercial projects. This is recorded as **commercial game-project use allowed for the purchaser**; see [the evidence](license-evidence.json). Public raw-source redistribution is not expressly addressed by that notice.

The original RAR, UnityPackage and extracted ingredients are stored in [the existing private game repository](https://github.com/kk20054/fanren-godot-world/tree/main/reference_assets/sword-vfx/dao-green-20251211). Claude web must have GitHub integration access to that private repository. This public collection supplies the inventory and handoff, not an unrestricted paid-asset mirror. The package is Unity URP source; “commercially usable” does not mean its ParticleSystem/ShaderGraph runs unchanged in Godot.

## Private payload layout

- `source_unity/archives/`: unchanged original RAR and UnityPackage.
- `source_unity/materials/`, `shaders/`, `prefabs/`, `animations/`, `timelines/`, `scenes/`, `settings/`: original Unity resources and their .meta files.
- `textures/`: seven original PNGs and their .meta files.
- `meshes/`: four original FBXs and their .meta files; Charactor.fbx belongs to the preview character.
- `manifest.json`, `guid_map.json`, `effect_summary.json`, `license-evidence.json`: exact paths, GUID references, parsed source settings and rights evidence.

The private payload retains source files; it is not a finished Godot port. No converted GLBs or Godot resources are supplied in this entry yet. Unity URP Unlit materials, ShaderGraph, particle modules and Timeline require target-engine reconstruction. The purchaser may reuse the PNGs and mesh data in this project; rebuild blend mode, depth handling, soft intersection, dissolve, emission and particle trajectories. Bloom is a scene effect, not an exported texture property.

## Ordinary-attack application

Use a short, bounded sword arc for each real attack phase, anchored to the existing effect/hand anchor and current attack direction. Keep startup, active peak and recovery aligned with the original ActionClock. A bright trail does not create a second hitbox or another damage event. Show hit flashes/sparks only on real positive contacts; respect guard and interruption. Let the equipped technique choose a stable VFX profile through existing game data. No combat code or Godot implementation is added by this inventory upload.
